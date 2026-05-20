# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""
安全远程运维 Agent (LangGraph 人在回路版) v1.1
入口文件：负责菜单导航、交互循环与事件流处理
新增：终端菜单系统、模型热切换、多主机管理、Agent模式切换
"""
from langgraph.types import Command

from src.utils.settings import SettingsManager
from config.config import MAX_COMMAND_LENGTH, MAX_AND_OPERATORS, MAX_PIPE_DEPTH
from src.core.agent_core import build_agent
from src.core.input_handler import smart_input
from src.utils.menu import build_main_menu, Color, _c


def _print_banner(settings: SettingsManager) -> None:
    """打印启动横幅与当前配置摘要"""
    print(_c("""
╔══════════════════════════════════════════════════╗
║  🤖 安全远程运维 Agent (LangGraph 人在回路版) v1.1  ║
╠══════════════════════════════════════════════════╣""", Color.BOLD + Color.BLUE))
    for line in settings.get_summary().split("\n"):
        print(_c(f"║  {line:<48} ║", Color.CYAN))
    print(_c("╚══════════════════════════════════════════════════╝", Color.BOLD + Color.BLUE))
    print()


def _print_chat_help() -> None:
    """打印对话模式下的快捷键帮助"""
    print(_c("""
📖 对话快捷键:
   <<<        进入多行模式（空行提交）
   /menu      返回主菜单
   /mode      查看/切换当前 Agent 模式
   /host      查看/切换当前主机
   /model     查看当前模型
   /history   查看本轮对话历史
   exit       结束会话并返回菜单
""", Color.DIM))


def run_chat_loop(settings: SettingsManager) -> None:
    """
    核心运维对话循环。
    支持在对话中通过 / 命令快速查看状态或返回菜单。
    """
    # 同步配置到环境（供旧版模块读取）
    settings.sync_to_env()

    # 构建 Agent（使用当前配置）
    agent, config = build_agent(settings)

    print(_c("🚀 已进入运维对话模式！", Color.GREEN + Color.BOLD))
    print(f"📏 命令限制：长度≤{MAX_COMMAND_LENGTH}字符，&&≤{MAX_AND_OPERATORS}个，管道≤{MAX_PIPE_DEPTH}层")
    print("⚡ 审批快捷方式：直接回车 = 确认执行，输入 n/N = 取消")
    _print_chat_help()

    chat_history = []

    while True:
        try:
            query = smart_input("👤 你: ")
            cmd = query.strip().lower()

            # 内置斜杠命令
            if cmd == "/menu":
                print(_c("↩️  返回主菜单...", Color.YELLOW))
                return
            if cmd == "/mode":
                m = settings.agent_mode
                print(_c(f"  当前模式: {m.mode_name} ({m.mode_id})", Color.CYAN))
                print(_c(f"  {m.description}", Color.DIM))
                continue
            if cmd == "/host":
                h = settings.active_host
                print(_c(f"  当前主机: [{settings.active_host_index}] {h.name}@{h.hostname}:{h.port}", Color.CYAN))
                continue
            if cmd == "/model":
                m = settings.model
                print(_c(f"  当前模型: {m.model_name} (provider={m.provider}, temp={m.temperature})", Color.CYAN))
                continue
            if cmd == "/history":
                if not chat_history:
                    print(_c("  暂无历史", Color.DIM))
                for i, (role, text) in enumerate(chat_history[-10:], 1):
                    color = Color.BLUE if role == "user" else Color.GREEN
                    print(_c(f"  {i}. [{role}] {text[:60]}...", color))
                continue
            if cmd in ("exit", "quit", "退出"):
                print(_c("↩️  返回主菜单...", Color.YELLOW))
                return

            # 记录用户输入
            chat_history.append(("user", query))

            inputs = {"messages": [("user", query)]}

            while True:
                print(_c("🤖 Agent 正在处理...", Color.MAGENTA))
                pending_interrupts = []
                last_event = None

                # 运行 Agent，捕获执行过程中的所有事件
                for event in agent.stream(inputs, config, stream_mode="values"):
                    last_event = event
                    if "__interrupt__" in event:
                        for intr in event["__interrupt__"]:
                            pending_interrupts.append({
                                "id": intr.id,
                                "value": intr.value
                            })
                        break

                # 处理 pending interrupts（人工审批 + 超时处理）
                if pending_interrupts:
                    resume_map = {}
                    for intr in pending_interrupts:
                        req = intr["value"]
                        action = req.get('action', 'ssh_execute')

                        # 超时处理分支
                        if action == "timeout_handler":
                            print(f"\n⏱️ 【命令执行超时】")
                            print(f"  主机: {req.get('hostname', 'N/A')}")
                            print(f"  命令: \033[91m{req.get('command', 'N/A')}\033[0m")
                            print(f"  已等待: {req.get('execution_time', 30)} 秒")
                            print(f"\n  可能原因：")
                            print(f"    1. 目标目录文件数量过多")
                            print(f"    2. 网络延迟或 SSH 通道阻塞")
                            print(f"    3. 命令本身需要较长时间完成")

                            user_input = input(f"\n  {req.get('question', '是否继续等待?')} ").strip()
                            is_continue = user_input.lower() in ('y', 'yes', '是', '继续')

                            if is_continue:
                                print("  ⏳ 继续等待 60 秒...")
                            else:
                                print("  ❌ 已取消任务")

                            resume_map[intr["id"]] = {"continue": is_continue}

                        # 普通审批分支
                        else:
                            print(f"\n⚠️ 【人工审批请求】")
                            print(f"  动作: {action}")
                            print(f"  主机: {req.get('hostname', 'N/A')}")
                            print(f"  命令: \033[91m{req.get('command', 'N/A')}\033[0m")
                            print(f"  说明: {req.get('description', '无')}")

                            user_input = input(f"\n  {req.get('question', '是否确认执行?')} ").strip()
                            is_approved = user_input.lower() not in ('n', 'no', '否', '取消')

                            if is_approved:
                                print("  ✅ 已确认执行")
                            else:
                                print("  ❌ 已拒绝执行")

                            resume_map[intr["id"]] = {"approved": is_approved}

                    # 构造 Command(resume) 恢复执行
                    inputs = Command(resume=resume_map)
                    continue

                # 没有 interrupt，正常结束本轮
                if last_event and "messages" in last_event:
                    final_messages = last_event["messages"]
                    if final_messages:
                        last_msg = final_messages[-1]
                        content = getattr(last_msg, 'content', str(last_msg))
                        print(f"\n🤖 Agent: {content}\n")
                        chat_history.append(("agent", content))
                break

        except KeyboardInterrupt:
            print(_c("\n\n⚠️  收到中断信号，返回菜单...", Color.YELLOW))
            return
        except Exception as e:
            print(_c(f"\n❌ 运行时异常: {e}", Color.RED))
            import traceback
            traceback.print_exc()
            cont = input(_c("是否继续对话? (y/n): ", Color.YELLOW)).strip().lower()
            if cont not in ('y', 'yes', '是'):
                return


def main() -> None:
    """程序主入口：初始化配置 → 显示菜单 → 根据选择进入对话或配置"""
    settings = SettingsManager()
    _print_banner(settings)

    while True:
        # 重新构建菜单（确保配置变更后菜单显示最新状态）
        menu = build_main_menu(settings)

        # 修改 "开始对话" 项的 action，使其进入对话模式
        for item in menu.items:
            if item.key == "7":
                item.action = lambda: run_chat_loop(settings)

        # 运行菜单，返回 False 表示用户选择退出
        should_continue = menu.run()
        if not should_continue:
            break

    print(_c("\n👋 程序已退出", Color.CYAN))


if __name__ == "__main__":
    main()
