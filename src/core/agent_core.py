# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""LLM 模型初始化与 Agent 组装（支持热切换配置）"""
from datetime import datetime
from typing import Tuple

from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# 可选导入：仅当使用 OpenAI / 兼容接口时需要安装 langchain-openai
try:
    from langchain_openai import ChatOpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    ChatOpenAI = None

from src.utils.settings import SettingsManager, ModelConfig, AgentMode
from src.utils.tools import ssh_executor


def _build_llm(cfg: ModelConfig):
    """
    根据配置构造 LLM 实例。
    支持 Ollama / OpenAI / OpenAI-Compatible 三种 Provider。
    """
    if cfg.provider == "ollama":
        return ChatOllama(
            model=cfg.model_name,
            temperature=cfg.temperature,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
        )
    elif cfg.provider in ("openai", "openai-compatible"):
        if not _HAS_OPENAI:
            raise ImportError(
                "使用 OpenAI / 兼容接口需要安装 langchain-openai。\n"
                "请执行: pip install langchain-openai"
            )
        return ChatOpenAI(
            model=cfg.model_name,
            temperature=cfg.temperature,
            api_key=cfg.api_key or "sk-no-key",
            base_url=cfg.base_url,
            max_tokens=cfg.max_tokens,
            timeout=cfg.timeout,
        )
    else:
        raise ValueError(f"不支持的 Provider: {cfg.provider}")


def _build_system_prompt(mode: AgentMode, current_time: str, location: str = "河北唐山") -> str:
    """
    根据 Agent 模式生成对应的 System Prompt。
    在基础运维专家 Prompt 之上叠加模式特定约束。
    """
    base_prompt = f"""你是 Rocky Linux 9.7 运维专家，当前时间 {current_time}，地点 {location}。

【命令约束】
1. 单条命令 ≤ 80 字符，&& ≤ 2 个，管道 ≤ 2 层
2. 禁止 $() / `` 命令替换
3. df --output 字段必须是：source,size,used,avail,pcent,target（百分比用 pcent）
4. 不确定参数时先执行 "<命令> --help | head -20"
5. 【严禁】用 echo 写多行文件，必须用 cat << 'EOF'

【查询类命令回复模板】（df, free, ps, top 等）
必须按以下格式回复，不要省略：
```
【执行结果】✅ 成功 / ❌ 失败
【原始数据】
（直接粘贴 output 字段的完整原始输出，不要省略，不要编造）

【数据分析】
- 关键指标1：数值 + 状态判断
- 关键指标2：数值 + 状态判断

【运维建议】
1. 如果磁盘 > 80%：清理 /var/log、find / -size +500M
2. 如果内存 > 85%：检查内存泄漏、增加 swap
3. 如果 CPU > 80%：定位高 CPU 进程
4. 其他情况给出针对性建议
```

【变更类命令回复模板】（mkdir, rm, chmod 等）
```
【执行结果】✅ 成功 / ❌ 失败
【验证结果】✅ 验证通过 / ⚠️ 验证未通过（仅当 verify_status 存在时）
【异常说明】如果有 error 或 verify_error
```

【分布式执行】
复杂任务必须分步执行，每步单独调用工具：
1. 创建目录 → 2. 写脚本 → 3. 设权限 → 4. 配定时任务
每步汇报进度 "1/4 已完成..."

【铁律】
1. 失败时只分析一次错误原因，不自动重试
2. 严禁让用户手动操作，所有操作必须用工具执行
3. 严禁编造 output 中不存在的数字
4. 每次必须生成非空回复"""

    # 模式叠加层
    mode_overlay = {
        "expert": "",
        "audit": """
【审计模式附加约束】
- 你处于安全审计模式，只能执行查询类命令（df, ps, free, ss 等）
- 禁止执行任何变更类命令（mkdir, rm, chmod, systemctl restart 等）
- 对用户的请求，先给出风险评估报告而非直接执行
- 报告格式：【风险等级】高/中/低 | 【影响范围】 | 【建议操作】""",
        "teach": """
【教学模式附加约束】
- 对每条拟执行的命令，先详细解释：命令作用、参数含义、预期影响、回滚方法
- 解释格式：【命令解析】→【参数说明】→【影响评估】→【回滚方案】
- 只有在用户明确回复"确认执行"后才调用工具""",
        "fast": """
【快速模式附加约束】
- 当前已跳过人工审批，请保持高度谨慎
- 优先使用组合命令减少交互次数
- 失败时简要说明原因，不展开长篇分析""",
        "batch": """
【批量脚本模式附加约束】
- 将用户请求拆解为标准化步骤模板
- 每步执行前输出 "[步骤 X/Y] 动作: ..."
- 若某步失败，给出跳过/终止/重试三种策略供选择""",
    }

    overlay = mode_overlay.get(mode.mode_id, "")
    if mode.readonly:
        overlay += "\n【只读声明】当前模式禁止执行任何变更操作，仅允许查询与分析。"

    return base_prompt + overlay


def build_agent(settings: SettingsManager = None):
    """
    初始化 LLM、System Prompt、Memory 和 Agent。
    若传入 settings 则使用动态配置，否则使用默认配置（向后兼容）。
    返回: (agent, config)
    """
    if settings is None:
        settings = SettingsManager()

    cfg = settings.model
    mode = settings.agent_mode

    llm = _build_llm(cfg)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = _build_system_prompt(mode, current_time)

    tools = [ssh_executor]
    memory = MemorySaver()
    agent = create_agent(
        model=llm,
        tools=tools,
        checkpointer=memory,
        system_prompt=system_prompt
    )

    session_id = settings.session_id
    config = {"configurable": {"thread_id": session_id}}

    return agent, config


def test_llm_connection(cfg: ModelConfig) -> Tuple[bool, str]:
    """
    测试 LLM 连接是否可用。
    返回: (是否成功, 提示信息)
    """
    try:
        llm = _build_llm(cfg)
        # 发送一个极轻量的请求
        response = llm.invoke('你好，请回复"pong"')
        content = getattr(response, "content", str(response))
        if "pong" in content.lower() or len(content) > 0:
            return True, f"模型 {cfg.model_name} 响应正常 ({len(content)} 字符)"
        return False, f"模型响应异常: {content[:100]}"
    except Exception as e:
        return False, f"连接失败: {str(e)}"
