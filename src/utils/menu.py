# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""终端交互式菜单系统（支持彩色输出与层级导航）"""
import os
import sys
import json
from typing import Optional, Callable, List, Tuple

from src.utils.settings import SettingsManager, ModelConfig, SSHHost, AgentMode, SecurityPolicy


# ==================== 终端颜色常量 ====================
class Color:
    """ANSI 颜色码，兼容 Windows 10+ 和主流 Unix 终端"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


def _c(text: str, color: str) -> str:
    """快捷着色函数"""
    return f"{color}{text}{Color.RESET}"


# ==================== 菜单基类 ====================
class MenuItem:
    """菜单项定义"""
    def __init__(self, key: str, label: str, action: Optional[Callable] = None,
                 submenu: Optional["MenuScreen"] = None, color: str = Color.CYAN):
        self.key = key
        self.label = label
        self.action = action          # 无 submenu 时执行的动作
        self.submenu = submenu        # 有 submenu 时进入子菜单
        self.color = color


class MenuScreen:
    """菜单屏幕（单页）"""
    def __init__(self, title: str, items: List[MenuItem],
                 header_func: Optional[Callable] = None,
                 footer_func: Optional[Callable] = None):
        self.title = title
        self.items = items
        self.header_func = header_func  # 动态头部（如显示当前配置）
        self.footer_func = footer_func  # 动态底部
        self.parent: Optional[MenuScreen] = None
        # 自动绑定子菜单的 parent
        for item in items:
            if item.submenu:
                item.submenu.parent = self

    def render(self) -> None:
        """渲染当前菜单页"""
        os.system("cls" if os.name == "nt" else "clear")
        width = 52

        # 顶部标题栏
        print(_c("╔" + "═" * width + "╗", Color.BOLD + Color.BLUE))
        title_line = f" {self.title} ".center(width, " ")
        print(_c("║" + title_line + "║", Color.BOLD + Color.WHITE + Color.BG_BLUE))
        print(_c("╠" + "═" * width + "╣", Color.BOLD + Color.BLUE))

        # 动态头部
        if self.header_func:
            header = self.header_func()
            for line in header.split("\n"):
                print(_c("║ " + line.ljust(width - 2) + " ║", Color.DIM))
            print(_c("╠" + "═" * width + "╣", Color.BOLD + Color.BLUE))

        # 菜单项
        for item in self.items:
            prefix = f"  [{item.key}]"
            label = f" {item.label}"
            line = (prefix + label).ljust(width - 2)
            print(_c("║" + line + " ║", item.color))

        # 返回/退出提示
        back_key = "0" if self.parent is None else "q"
        back_text = "  [0] ❌ 退出程序" if self.parent is None else "  [q] ↩️  返回上级"
        print(_c("╠" + "═" * width + "╣", Color.BOLD + Color.BLUE))
        print(_c("║" + back_text.ljust(width - 2) + " ║", Color.YELLOW))
        print(_c("╚" + "═" * width + "╝", Color.BOLD + Color.BLUE))

        # 动态底部
        if self.footer_func:
            print(self.footer_func())

    def run(self) -> bool:
        """
        运行当前菜单页，返回 True 表示继续运行，False 表示退出整个程序
        """
        while True:
            self.render()
            choice = input(_c("\n👉 请选择: ", Color.BOLD + Color.GREEN)).strip().lower()

            # 返回上级
            if choice == "q" and self.parent is not None:
                return True

            # 退出程序
            if choice == "0" and self.parent is None:
                confirm = input(_c("确认退出? (y/n): ", Color.YELLOW)).strip().lower()
                if confirm in ("y", "yes", "是"):
                    print(_c("\n👋 再见！", Color.CYAN))
                    return False
                continue

            # 匹配菜单项
            matched = [i for i in self.items if i.key == choice]
            if not matched:
                print(_c("⚠️  无效选项，按回车继续...", Color.RED))
                input()
                continue

            item = matched[0]

            # 进入子菜单
            if item.submenu:
                should_continue = item.submenu.run()
                if not should_continue:
                    return False
                continue

            # 执行动作
            if item.action:
                try:
                    item.action()
                except Exception as e:
                    print(_c(f"\n❌ 操作失败: {e}", Color.RED))
                    input("按回车继续...")

        return True


# ==================== 各菜单页构建函数 ====================

def build_main_menu(settings: SettingsManager) -> MenuScreen:
    """构建主菜单"""
    def header() -> str:
        return settings.get_summary()

    def footer() -> str:
        return _c("\n💡 提示: 数字键快速选择，q 返回上级，0 退出", Color.DIM)

    return MenuScreen(
        title="🤖 安全远程运维 Agent 控制台 v1.1",
        items=[
            MenuItem("1", "🧠 模型配置     → 切换LLM / 温度 / API地址", submenu=build_model_menu(settings)),
            MenuItem("2", "🔌 SSH连接      → 主机 / 凭据 / 多主机管理", submenu=build_ssh_menu(settings)),
            MenuItem("3", "🎭 Agent模式    → 专家 / 审计 / 教学 / 快速", submenu=build_mode_menu(settings)),
            MenuItem("4", "🛡️  安全策略     → 白名单 / 审批 / 复杂度限制", submenu=build_security_menu(settings)),
            MenuItem("5", "📋 会话管理     → 历史 / 导出 / 记忆清除", submenu=build_session_menu(settings)),
            MenuItem("6", "📊 系统状态     → 配置摘要 / 测试连接", submenu=build_status_menu(settings)),
            MenuItem("7", "▶️  开始对话     → 进入运维交互主循环", action=lambda: None, color=Color.GREEN + Color.BOLD),
        ],
        header_func=header,
        footer_func=footer,
    )


def build_model_menu(settings: SettingsManager) -> MenuScreen:
    """模型配置子菜单"""
    def header() -> str:
        m = settings.model
        return (f"当前模型: {m.model_name}\n"
                f"Provider: {m.provider} | Temp: {m.temperature} | URL: {m.base_url}")

    def switch_model() -> None:
        """根据 Provider 类型智能切换模型选择方式"""
        provider = settings.model.provider

        # ========== Ollama 本地模式：自动列出可用模型 ==========
        if provider == "ollama":
            print(_c("\n🔄 正在获取本地 Ollama 模型列表...", Color.CYAN))
            model_list = []
            try:
                import urllib.request
                import json as _json
                base_url = settings.model.base_url.rstrip("/")
                req = urllib.request.Request(
                    f"{base_url}/api/tags",
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    model_list = [m.get("name", m.get("model", "unknown")) for m in data.get("models", [])]
            except Exception as e:
                print(_c(f"  ⚠️  获取模型列表失败: {e}", Color.YELLOW))
                print(_c("  请确认 Ollama 服务已启动", Color.DIM))

            if model_list:
                print(_c(f"\n📋 检测到 {len(model_list)} 个本地模型:", Color.CYAN))
                for i, name in enumerate(model_list, 1):
                    marker = "▶ " if name == settings.model.model_name else "  "
                    print(f"  {marker}[{i}] {name}")
                print(f"  [0] 自定义输入...")

                choice = input(_c("\n👉 选择编号或输入模型名: ", Color.GREEN)).strip()
                if choice.isdigit():
                    idx = int(choice)
                    if 1 <= idx <= len(model_list):
                        settings.model.model_name = model_list[idx - 1]
                    elif idx == 0:
                        custom = input("输入模型名: ").strip()
                        if custom:
                            settings.model.model_name = custom
                elif choice:
                    settings.model.model_name = choice
            else:
                # 获取失败时回退到手动输入
                custom = input(_c("输入模型名 (如 qwen3:8b-q4_K_M): ", Color.GREEN)).strip()
                if custom:
                    settings.model.model_name = custom

        # ========== OpenAI / 兼容接口：手动输入 ==========
        else:
            print(_c(f"\n🔌 当前 Provider: {provider}", Color.CYAN))
            print(_c("远程 API 模式，请手动输入模型名称", Color.DIM))
            print(_c("\n常用模型参考:", Color.DIM))
            if provider == "openai":
                refs = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            else:
                refs = ["qwen3-32b", "deepseek-chat", "llama3-70b"]
            for ref in refs:
                print(f"  • {ref}")

            current = settings.model.model_name
            custom = input(_c(f"\n输入模型名 (当前: {current}): ", Color.GREEN)).strip()
            if custom:
                settings.model.model_name = custom

        settings.save()
        print(_c(f"\n✅ 已切换模型: {settings.model.model_name}", Color.GREEN))
        input("按回车继续...")

    def set_provider() -> None:
        print(_c("\n📋 Provider 类型:", Color.CYAN))
        print("  [1] ollama          (本地默认)")
        print("  [2] openai          (官方 API)")
        print("  [3] openai-compatible (兼容接口，如 vLLM / Xinference)")
        p = input(_c("👉 选择: ", Color.GREEN)).strip()
        mapping = {"1": "ollama", "2": "openai", "3": "openai-compatible"}
        if p in mapping:
            settings.model.provider = mapping[p]
        if settings.model.provider in ("openai", "openai-compatible"):
            url = input("Base URL (默认 https://api.openai.com/v1): ").strip()
            if url:
                settings.model.base_url = url
            key = input("API Key: ").strip()
            settings.model.api_key = key
        settings.save()
        print(_c("✅ Provider 已更新", Color.GREEN))
        input("按回车继续...")

    def set_temperature() -> None:
        t = input(_c("输入 temperature (0.0~1.0，当前 {}): ".format(settings.model.temperature), Color.GREEN)).strip()
        try:
            val = float(t)
            if 0.0 <= val <= 2.0:
                settings.model.temperature = round(val, 2)
                settings.save()
                print(_c(f"✅ Temperature 已设为 {settings.model.temperature}", Color.GREEN))
            else:
                print(_c("⚠️  超出范围", Color.YELLOW))
        except ValueError:
            print(_c("⚠️  输入无效", Color.YELLOW))
        input("按回车继续...")

    def test_model() -> None:
        print(_c("\n🔄 正在测试模型连接...", Color.CYAN))
        try:
            from src.core.agent_core import test_llm_connection
            ok, msg = test_llm_connection(settings.model)
            if ok:
                print(_c(f"✅ {msg}", Color.GREEN))
            else:
                print(_c(f"❌ {msg}", Color.RED))
        except Exception as e:
            print(_c(f"❌ 测试异常: {e}", Color.RED))
        input("按回车继续...")

    return MenuScreen(
        title="🧠 模型配置",
        items=[
            MenuItem("1", "🔄 切换模型        → 选择或输入模型名称", action=switch_model),
            MenuItem("2", "🏭 切换 Provider   → Ollama / OpenAI / 兼容", action=set_provider),
            MenuItem("3", "🌡️  设置 Temperature → 控制输出随机性", action=set_temperature),
            MenuItem("4", "🔗 测试连接        → 验证模型可正常响应", action=test_model),
        ],
        header_func=header,
    )


def build_ssh_menu(settings: SettingsManager) -> MenuScreen:
    """SSH 连接配置子菜单"""
    def header() -> str:
        h = settings.active_host
        lines = [f"当前主机 [{settings.active_host_index}]: {h.name}"]
        for i, host in enumerate(settings.hosts):
            marker = "▶ " if i == settings.active_host_index else "  "
            lines.append(f"{marker}[{i}] {host.name}@{host.hostname}:{host.port}")
        return "\n".join(lines)

    def edit_current() -> None:
        h = settings.active_host
        print(_c("\n📋 编辑当前主机（直接回车保留原值）", Color.CYAN))
        h.name = input(f"  别名 [{h.name}]: ").strip() or h.name
        h.hostname = input(f"  地址 [{h.hostname}]: ").strip() or h.hostname
        port = input(f"  端口 [{h.port}]: ").strip()
        h.port = int(port) if port.isdigit() else h.port
        h.username = input(f"  用户名 [{h.username}]: ").strip() or h.username
        pwd = input(f"  密码 [{h.password}]: ").strip()
        if pwd:
            h.password = pwd
        key = input(f"  私钥路径 [{h.key_file or '无'}]: ").strip()
        h.key_file = key
        settings.save()
        print(_c("✅ 主机配置已保存", Color.GREEN))
        input("按回车继续...")

    def add_host() -> None:
        print(_c("\n📋 添加新主机", Color.CYAN))
        name = input("  别名: ").strip() or "new_host"
        hostname = input("  地址: ").strip() or "192.168.1.1"
        port = int(input("  端口 [22]: ").strip() or "22")
        username = input("  用户名: ").strip() or "root"
        password = input("  密码: ").strip()
        key_file = input("  私钥路径（无则回车）: ").strip()
        new_host = SSHHost(name=name, hostname=hostname, port=port,
                           username=username, password=password, key_file=key_file)
        settings.add_host(new_host)
        print(_c(f"✅ 已添加并切换到: {name}@{hostname}", Color.GREEN))
        input("按回车继续...")

    def switch_host() -> None:
        if len(settings.hosts) <= 1:
            print(_c("⚠️  只有一个主机，无需切换", Color.YELLOW))
            input("按回车继续...")
            return
        print(_c("\n📋 主机列表:", Color.CYAN))
        for i, h in enumerate(settings.hosts):
            print(f"  [{i}] {h.name}@{h.hostname}:{h.port}")
        idx = input(_c("\n👉 选择主机编号: ", Color.GREEN)).strip()
        if idx.isdigit() and settings.switch_host(int(idx)):
            print(_c(f"✅ 已切换到: {settings.active_host.name}", Color.GREEN))
        else:
            print(_c("❌ 无效编号", Color.RED))
        input("按回车继续...")

    def test_ssh() -> None:
        print(_c("\n🔄 正在测试 SSH 连接...", Color.CYAN))
        try:
            from src.core.ssh_client import test_connection
            h = settings.active_host
            ok, msg = test_connection(h.hostname, h.port, h.username, h.password, h.key_file)
            if ok:
                print(_c(f"✅ {msg}", Color.GREEN))
            else:
                print(_c(f"❌ {msg}", Color.RED))
        except Exception as e:
            print(_c(f"❌ 测试异常: {e}", Color.RED))
        input("按回车继续...")

    def remove_host() -> None:
        if len(settings.hosts) <= 1:
            print(_c("⚠️  至少保留一个主机", Color.YELLOW))
            input("按回车继续...")
            return
        print(_c("\n📋 可删除的主机:", Color.CYAN))
        for i, h in enumerate(settings.hosts):
            print(f"  [{i}] {h.name}@{h.hostname}")
        idx = input(_c("\n👉 输入要删除的编号: ", Color.GREEN)).strip()
        if idx.isdigit() and settings.remove_host(int(idx)):
            print(_c("✅ 已删除", Color.GREEN))
        else:
            print(_c("❌ 删除失败", Color.RED))
        input("按回车继续...")

    return MenuScreen(
        title="🔌 SSH 连接管理",
        items=[
            MenuItem("1", "✏️  编辑当前主机   → 修改地址/端口/凭据", action=edit_current),
            MenuItem("2", "➕ 添加新主机     → 配置多主机环境", action=add_host),
            MenuItem("3", "🔄 切换主机       → 在已保存主机间切换", action=switch_host),
            MenuItem("4", "🗑️  删除主机       → 移除不再使用的主机", action=remove_host),
            MenuItem("5", "🔗 测试连接       → 验证 SSH 连通性", action=test_ssh),
        ],
        header_func=header,
    )


def build_mode_menu(settings: SettingsManager) -> MenuScreen:
    """Agent 模式切换子菜单"""
    def header() -> str:
        m = settings.agent_mode
        return (f"当前模式: {m.mode_name}\n"
                f"说明: {m.description}")

    def set_mode(mode_id: str, name: str, desc: str,
                 skip_approval: bool = False, readonly: bool = False,
                 verbose: bool = True) -> Callable:
        def _action() -> None:
            settings.set_agent_mode(AgentMode(
                mode_id=mode_id, mode_name=name, description=desc,
                skip_approval=skip_approval, readonly=readonly, verbose_analysis=verbose
            ))
            print(_c(f"\n✅ 已切换到: {name}", Color.GREEN))
            print(_c(f"   {desc}", Color.DIM))
            if readonly:
                print(_c("   ⚠️  当前为只读模式，不会执行任何变更命令", Color.YELLOW))
            if skip_approval:
                print(_c("   ⚠️  当前已跳过人工审批，请谨慎操作！", Color.RED))
            input("按回车继续...")
        return _action

    return MenuScreen(
        title="🎭 Agent 运行模式",
        items=[
            MenuItem("1", "🔧 运维专家模式   → 标准执行 + 人工审批 + 自动验证",
                     action=set_mode("expert", "运维专家模式", "标准运维执行模式，含人工审批与自动验证")),
            MenuItem("2", "🔍 安全审计模式   → 只读分析 + 风险评估报告",
                     action=set_mode("audit", "安全审计模式", "仅执行查询类命令，生成风险评估报告", readonly=True)),
            MenuItem("3", "📚 教学解释模式   → 解释命令作用 + 学习引导",
                     action=set_mode("teach", "教学解释模式", "先解释命令原理与影响，经确认后再执行", verbose=True)),
            MenuItem("4", "⚡ 快速执行模式   → 跳过审批 + 批量执行（慎用）",
                     action=set_mode("fast", "快速执行模式", "跳过人工审批，适合已知安全的批量操作", skip_approval=True)),
            MenuItem("5", "📦 批量脚本模式   → 脚本化多步骤自动执行",
                     action=set_mode("batch", "批量脚本模式", "支持预定义脚本模板，分步自动执行", verbose=True)),
        ],
        header_func=header,
    )


def build_security_menu(settings: SettingsManager) -> MenuScreen:
    """安全策略子菜单"""
    def header() -> str:
        s = settings.security
        return (f"白名单: {'✅' if s.enable_whitelist else '❌'} | "
                f"危险拦截: {'✅' if s.enable_danger_block else '❌'} | "
                f"人工审批: {'✅' if s.enable_human_approval else '❌'} | "
                f"自动验证: {'✅' if s.auto_verify else '❌'}")

    def toggle(field: str, label: str) -> Callable:
        def _action() -> None:
            current = getattr(settings.security, field)
            setattr(settings.security, field, not current)
            settings.save()
            status = "开启" if not current else "关闭"
            print(_c(f"\n✅ {label} 已{status}", Color.GREEN))
            input("按回车继续...")
        return _action

    def set_limits() -> None:
        s = settings.security
        print(_c("\n📋 当前限制值:", Color.CYAN))
        print(f"  最大长度: {s.max_command_length}")
        print(f"  最大 &&:  {s.max_and_operators}")
        print(f"  最大管道: {s.max_pipe_depth}")
        print(f"  审批超时: {s.approval_timeout_sec}s")
        try:
            length = input("  新最大长度 (回车保留): ").strip()
            if length:
                s.max_command_length = int(length)
            and_ops = input("  新最大 && 数 (回车保留): ").strip()
            if and_ops:
                s.max_and_operators = int(and_ops)
            pipes = input("  新最大管道层数 (回车保留): ").strip()
            if pipes:
                s.max_pipe_depth = int(pipes)
            timeout = input("  新审批超时秒数 (回车保留): ").strip()
            if timeout:
                s.approval_timeout_sec = int(timeout)
            settings.save()
            print(_c("✅ 限制已更新", Color.GREEN))
        except ValueError:
            print(_c("❌ 输入必须为整数", Color.RED))
        input("按回车继续...")

    return MenuScreen(
        title="🛡️ 安全策略配置",
        items=[
            MenuItem("1", f"{'🚫' if settings.security.enable_whitelist else '✅'} 命令白名单      → 切换开关",
                     action=toggle("enable_whitelist", "命令白名单")),
            MenuItem("2", f"{'🚫' if settings.security.enable_danger_block else '✅'} 危险命令拦截    → 切换开关",
                     action=toggle("enable_danger_block", "危险命令拦截")),
            MenuItem("3", f"{'🚫' if settings.security.enable_human_approval else '✅'} 人工审批        → 切换开关",
                     action=toggle("enable_human_approval", "人工审批")),
            MenuItem("4", f"{'🚫' if settings.security.auto_verify else '✅'} 自动验证        → 切换开关",
                     action=toggle("auto_verify", "变更后自动验证")),
            MenuItem("5", "📏 复杂度限制      → 长度 / && / 管道 / 超时", action=set_limits),
        ],
        header_func=header,
    )


def build_session_menu(settings: SettingsManager) -> MenuScreen:
    """会话管理子菜单"""
    def show_history() -> None:
        log_file = os.path.join(settings.log_dir, f"{settings.session_id}.jsonl")
        if not os.path.exists(log_file):
            print(_c("\n⚠️  暂无会话历史", Color.YELLOW))
            input("按回车继续...")
            return
        print(_c("\n📋 最近 20 条交互记录:", Color.CYAN))
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]
        for i, line in enumerate(lines, 1):
            try:
                obj = json.loads(line)
                role = obj.get("role", "?")
                content = obj.get("content", "")[:60].replace("\n", " ")
                color = Color.BLUE if role == "user" else Color.GREEN
                print(_c(f"  {i:2}. [{role:6}] {content}...", color))
            except json.JSONDecodeError:
                pass
        input("\n按回车继续...")

    def export_session() -> None:
        log_file = os.path.join(settings.log_dir, f"{settings.session_id}.jsonl")
        if not os.path.exists(log_file):
            print(_c("\n⚠️  无记录可导出", Color.YELLOW))
            input("按回车继续...")
            return
        export_name = input("导出文件名 (默认 session_export.json): ").strip() or "session_export.json"
        try:
            with open(log_file, "r", encoding="utf-8") as src:
                data = [json.loads(line) for line in src if line.strip()]
            with open(export_name, "w", encoding="utf-8") as dst:
                json.dump(data, dst, ensure_ascii=False, indent=2)
            print(_c(f"✅ 已导出到: {export_name} ({len(data)} 条记录)", Color.GREEN))
        except Exception as e:
            print(_c(f"❌ 导出失败: {e}", Color.RED))
        input("按回车继续...")

    def clear_memory() -> None:
        confirm = input(_c("⚠️  确认清空当前会话记忆? (y/n): ", Color.RED)).strip().lower()
        if confirm in ("y", "yes", "是"):
            settings.session_id = f"运维会话_{os.urandom(4).hex()}"
            settings.save()
            print(_c(f"✅ 已生成新会话 ID: {settings.session_id}", Color.GREEN))
        else:
            print(_c("已取消", Color.YELLOW))
        input("按回车继续...")

    def set_session_id() -> None:
        sid = input(f"输入新会话 ID (当前 {settings.session_id}): ").strip()
        if sid:
            settings.session_id = sid
            settings.save()
            print(_c(f"✅ 会话 ID 已更新", Color.GREEN))
        input("按回车继续...")

    return MenuScreen(
        title="📋 会话管理",
        items=[
            MenuItem("1", "📜 查看历史       → 最近 20 条交互", action=show_history),
            MenuItem("2", "💾 导出会话       → 保存为 JSON 文件", action=export_session),
            MenuItem("3", "🆕 清空记忆       → 生成新会话 ID", action=clear_memory),
            MenuItem("4", "🏷️  设置会话 ID    → 自定义标识", action=set_session_id),
        ],
    )


def build_status_menu(settings: SettingsManager) -> MenuScreen:
    """系统状态子菜单"""
    def show_summary() -> None:
        print(_c("\n" + settings.get_summary(), Color.CYAN))
        input("\n按回车继续...")

    def test_all() -> None:
        print(_c("\n🔄 测试模型连接...", Color.CYAN))
        try:
            from src.core.agent_core import test_llm_connection
            ok1, msg1 = test_llm_connection(settings.model)
            print(_c(f"  {'✅' if ok1 else '❌'} LLM: {msg1}", Color.GREEN if ok1 else Color.RED))
        except Exception as e:
            print(_c(f"  ❌ LLM: {e}", Color.RED))

        print(_c("\n🔄 测试 SSH 连接...", Color.CYAN))
        try:
            from src.core.ssh_client import test_connection
            h = settings.active_host
            ok2, msg2 = test_connection(h.hostname, h.port, h.username, h.password, h.key_file)
            print(_c(f"  {'✅' if ok2 else '❌'} SSH ({h.name}): {msg2}", Color.GREEN if ok2 else Color.RED))
        except Exception as e:
            print(_c(f"  ❌ SSH: {e}", Color.RED))

        input("\n按回车继续...")

    def open_settings_file() -> None:
        path = os.path.abspath(settings._config_file)
        print(_c(f"\n📁 配置文件路径: {path}", Color.CYAN))
        print(_c("可直接编辑该 JSON 文件进行高级配置", Color.DIM))
        input("按回车继续...")

    return MenuScreen(
        title="📊 系统状态",
        items=[
            MenuItem("1", "📋 配置摘要       → 查看所有当前配置", action=show_summary),
            MenuItem("2", "🧪 一键测试       → 同时测 LLM + SSH", action=test_all),
            MenuItem("3", "📁 打开配置目录   → 显示 settings.json 路径", action=open_settings_file),
        ],
    )


# ==================== 入口函数 ====================

def show_menu(settings: SettingsManager) -> bool:
    """
    显示主菜单并处理选择。
    返回 True 表示用户选择开始对话，False 表示退出程序。
    """
    menu = build_main_menu(settings)
    result = menu.run()
    # menu.run() 返回 False 表示用户选了退出
    # 但用户也可能选了 "7 开始对话"，此时 action=None 且未退出
    # 这里需要区分：如果用户从主菜单按了 7，run() 会返回 True（因为未触发退出）
    # 但我们需要外部知道用户选了 "开始对话"
    # 因此用一个全局标记 hack 一下
    return result


# 用于标记用户是否选择了"开始对话"
_start_chat_flag = False

def mark_start_chat() -> None:
    global _start_chat_flag
    _start_chat_flag = True

def consume_start_chat_flag() -> bool:
    global _start_chat_flag
    val = _start_chat_flag
    _start_chat_flag = False
    return val
