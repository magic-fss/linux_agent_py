# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""运行时动态配置管理器（支持持久化与热切换）"""
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict


@dataclass
class ModelConfig:
    """LLM 模型配置"""
    provider: str = "ollama"           # ollama | openai | openai-compatible
    model_name: str = "qwen3:8b-q4_K_M"
    base_url: str = "http://localhost:11434"
    api_key: str = ""                   # OpenAI / 兼容接口需要
    temperature: float = 0.0
    timeout: int = 120                  # 模型响应超时（秒）
    max_tokens: int = 4096

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ModelConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SSHHost:
    """单主机 SSH 配置"""
    name: str = "default"
    hostname: str = "192.168.20.129"
    port: int = 22
    username: str = "admin"
    password: str = "123456"
    key_file: str = ""                  # 私钥路径（优先于密码）
    key_passphrase: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SSHHost":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SecurityPolicy:
    """安全策略配置"""
    enable_whitelist: bool = True
    enable_danger_block: bool = True
    enable_complexity_check: bool = True
    enable_human_approval: bool = True   # 人工审批开关
    approval_timeout_sec: int = 30      # 审批等待超时
    max_command_length: int = 80
    max_and_operators: int = 2
    max_pipe_depth: int = 2
    auto_verify: bool = True             # 变更后自动验证

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SecurityPolicy":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentMode:
    """Agent 运行模式"""
    mode_id: str = "expert"             # expert | audit | teach | batch | fast
    mode_name: str = "运维专家模式"
    description: str = "标准运维执行模式，含人工审批"
    skip_approval: bool = False         # 快速模式可设为True（不推荐生产环境）
    readonly: bool = False              # 审计/教学模式只读
    verbose_analysis: bool = True       # 是否输出详细分析


class SettingsManager:
    """
    全局运行时配置管理器
    - 支持从 JSON 文件加载/保存
    - 支持热切换，无需重启程序
    - 线程安全（单线程 CLI 场景下顺序访问即可）
    """

    _instance: Optional["SettingsManager"] = None
    _config_file: str = "agent_settings.json"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file: Optional[str] = None):
        if self._initialized:
            return
        if config_file:
            self._config_file = config_file

        self.model: ModelConfig = ModelConfig()
        self.hosts: List[SSHHost] = [SSHHost()]
        self.active_host_index: int = 0
        self.security: SecurityPolicy = SecurityPolicy()
        self.agent_mode: AgentMode = AgentMode()
        self.session_id: str = "运维会话_001"
        self.log_dir: str = "./logs"

        self._load()
        self._initialized = True

    # ==================== 持久化 ====================

    def _load(self) -> None:
        """从 JSON 文件加载配置"""
        if not os.path.exists(self._config_file):
            return
        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "model" in data:
                self.model = ModelConfig.from_dict(data["model"])
            if "hosts" in data:
                self.hosts = [SSHHost.from_dict(h) for h in data["hosts"]]
            if "active_host_index" in data:
                self.active_host_index = data["active_host_index"]
            if "security" in data:
                self.security = SecurityPolicy.from_dict(data["security"])
            if "agent_mode" in data:
                mode_data = data["agent_mode"]
                self.agent_mode = AgentMode(
                    mode_id=mode_data.get("mode_id", "expert"),
                    mode_name=mode_data.get("mode_name", "运维专家模式"),
                    description=mode_data.get("description", ""),
                    skip_approval=mode_data.get("skip_approval", False),
                    readonly=mode_data.get("readonly", False),
                    verbose_analysis=mode_data.get("verbose_analysis", True),
                )
            if "session_id" in data:
                self.session_id = data["session_id"]
            if "log_dir" in data:
                self.log_dir = data["log_dir"]
        except Exception as e:
            print(f"[Settings] 加载配置文件失败（将使用默认配置）: {e}")

    def save(self) -> None:
        """保存当前配置到 JSON 文件"""
        data = {
            "model": self.model.to_dict(),
            "hosts": [h.to_dict() for h in self.hosts],
            "active_host_index": self.active_host_index,
            "security": self.security.to_dict(),
            "agent_mode": {
                "mode_id": self.agent_mode.mode_id,
                "mode_name": self.agent_mode.mode_name,
                "description": self.agent_mode.description,
                "skip_approval": self.agent_mode.skip_approval,
                "readonly": self.agent_mode.readonly,
                "verbose_analysis": self.agent_mode.verbose_analysis,
            },
            "session_id": self.session_id,
            "log_dir": self.log_dir,
        }
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Settings] 保存配置文件失败: {e}")

    # ==================== 快捷访问 ====================

    @property
    def active_host(self) -> SSHHost:
        """获取当前激活的主机配置"""
        if 0 <= self.active_host_index < len(self.hosts):
            return self.hosts[self.active_host_index]
        return self.hosts[0] if self.hosts else SSHHost()

    def add_host(self, host: SSHHost) -> None:
        """添加新主机"""
        self.hosts.append(host)
        self.active_host_index = len(self.hosts) - 1
        self.save()

    def remove_host(self, index: int) -> bool:
        """删除指定主机，至少保留一个"""
        if len(self.hosts) <= 1 or not (0 <= index < len(self.hosts)):
            return False
        self.hosts.pop(index)
        if self.active_host_index >= len(self.hosts):
            self.active_host_index = len(self.hosts) - 1
        self.save()
        return True

    def switch_host(self, index: int) -> bool:
        """切换当前激活主机"""
        if 0 <= index < len(self.hosts):
            self.active_host_index = index
            self.save()
            return True
        return False

    def set_agent_mode(self, mode: AgentMode) -> None:
        """切换 Agent 运行模式"""
        self.agent_mode = mode
        self.save()

    def set_model(self, cfg: ModelConfig) -> None:
        """更新模型配置"""
        self.model = cfg
        self.save()

    # ==================== 环境变量同步（向后兼容）====================

    def sync_to_env(self) -> None:
        """
        将当前配置同步到环境变量，供旧版 config.py 读取
        注意：仅同步当前激活主机
        """
        host = self.active_host
        os.environ["SSH_HOST"] = host.hostname
        os.environ["SSH_PORT"] = str(host.port)
        os.environ["SSH_USER"] = host.username
        os.environ["SSH_PASSWORD"] = host.password

    def get_summary(self) -> str:
        """返回当前配置摘要（用于菜单展示）"""
        m = self.model
        h = self.active_host
        s = self.security
        mode = self.agent_mode
        lines = [
            f"  🧠 模型: {m.model_name} (temp={m.temperature}, provider={m.provider})",
            f"  🔌 主机: {h.name}@{h.hostname}:{h.port} ({h.username})",
            f"  🎭 模式: {mode.mode_name} {'[只读]' if mode.readonly else ''}{'[免审批]' if mode.skip_approval else ''}",
            f"  🛡️ 安全: 白名单={'开' if s.enable_whitelist else '关'} | 审批={'开' if s.enable_human_approval else '关'} | 自动验证={'开' if s.auto_verify else '关'}",
            f"  📁 配置: {self._config_file} | 会话: {self.session_id}",
        ]
        return "\n".join(lines)
