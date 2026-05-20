# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""LangChain 工具定义（支持动态配置与模式感知）"""
import json
from langchain_core.tools import tool
from langgraph.types import interrupt

from src.utils.settings import SettingsManager
from src.core.command_guard import (
    validate_command_complexity,
    validate_command_whitelist,
    is_dangerous_command,
    validate_command_args,
    generate_verify_command,
    is_query_command
)
from src.core.ssh_client import execute_ssh_command, is_permission_denied


@tool
def ssh_executor(command: str, auto_verify: bool = True) -> str:
    """
    通过 SSH 连接到 Linux 服务器并执行 Shell 命令。

    约束：
    - 单条命令长度 ≤ 80 字符
    - 最多用 && 串联 3 条命令
    - 管道 | 嵌套不超过 2 层
    - 禁止命令替换 $() / ``
    - 命令参数必须符合预定义规范（如 df --output 字段名）

    特性：
    - 若执行结果提示权限不足，会自动尝试 sudo 重试一次
    - 若 auto_verify=True 且执行成功，会自动运行验证命令确认结果
    - 查询类命令（df, free, ps 等）不会触发自动验证
    - 命令执行超过 30 秒会自动超时并返回错误信息
    """
    settings = SettingsManager()
    sec = settings.security
    mode = settings.agent_mode

    if not command or not command.strip():
        return json.dumps(
            {"status": "error", "message": "命令不能为空"},
            ensure_ascii=False
        )

    command = command.strip()

    # 0. 审计/只读模式：拦截变更类命令
    if mode.readonly and not is_query_command(command):
        return json.dumps(
            {
                "status": "blocked",
                "message": f"【审计模式拦截】当前处于 {mode.mode_name}，禁止执行变更类命令。"
                           f"如需执行，请切换到运维专家模式。"
            },
            ensure_ascii=False
        )

    # 1. 危险命令拦截（可被安全策略关闭）
    if sec.enable_danger_block:
        danger = is_dangerous_command(command)
        if danger:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"安全拦截：禁止执行包含 '{danger}' 的危险命令！"
                },
                ensure_ascii=False
            )

    # 2. 白名单校验（可被安全策略关闭）
    if sec.enable_whitelist:
        ok, msg = validate_command_whitelist(command)
        if not ok:
            return json.dumps(
                {"status": "error", "message": msg},
                ensure_ascii=False
            )

    # 3. 复杂度校验（可被安全策略关闭）
    if sec.enable_complexity_check:
        ok, msg = validate_command_complexity(command)
        if not ok:
            return json.dumps(
                {"status": "error", "message": msg},
                ensure_ascii=False
            )

    # 4. 参数级校验（字段名、参数合法性）
    ok, msg = validate_command_args(command)
    if not ok:
        return json.dumps(
            {"status": "error", "message": msg},
            ensure_ascii=False
        )

    # 5. 人工审批（可被安全策略或模式关闭）
    if sec.enable_human_approval and not mode.skip_approval:
        approval = interrupt({
            "action": "ssh_execute",
            "hostname": settings.active_host.hostname,
            "command": command,
            "question": "是否确认在远程服务器上执行此命令？(直接回车=确认，输入 n/N=取消)"
        })

        if not approval or not approval.get("approved"):
            return json.dumps(
                {"status": "canceled", "message": "用户/管理员拒绝了该命令的执行。"},
                ensure_ascii=False
            )

    # 6. 执行命令（带超时检测，使用动态配置）
    result = execute_ssh_command(command, timeout=sec.approval_timeout_sec, settings=settings)

    # 7. 如果超时，询问用户是否继续等待或结束
    if result.get("timeout_flag"):
        approval = interrupt({
            "action": "timeout_handler",
            "hostname": settings.active_host.hostname,
            "command": command,
            "execution_time": result.get("execution_time", sec.approval_timeout_sec),
            "question": "命令执行超时，是否继续等待 60 秒？(y/n)"
        })

        is_continue = approval and approval.get("continue", False)
        if is_continue:
            result = execute_ssh_command(command, timeout=60, settings=settings)
        else:
            return json.dumps(
                {
                    "status": "canceled",
                    "message": "用户取消了超时等待。"
                },
                ensure_ascii=False
            )

    # 8. 权限不足自动 sudo 重试
    if is_permission_denied(result):
        sudo_command = f"sudo {command}"
        print(f"⚠️ 权限不足，自动尝试 sudo 重试: {sudo_command}")
        sudo_result = execute_ssh_command(sudo_command, timeout=sec.approval_timeout_sec, settings=settings)
        if sudo_result.get("status") == "success":
            result = sudo_result
        else:
            result["sudo_attempted"] = True
            result["sudo_error"] = sudo_result.get("error", "sudo 重试失败")

    # 9. 自动验证（仅变更类命令，且策略开启）
    if sec.auto_verify and not is_query_command(command) and result.get("status") == "success":
        verify_cmd = generate_verify_command(command)
        if verify_cmd:
            verify_result = execute_ssh_command(verify_cmd, timeout=10, settings=settings)
            result["verify_status"] = verify_result.get("status")
            result["verify_output"] = verify_result.get("output", "")
            result["verify_error"] = verify_result.get("error", "")

    # 10. 记录会话日志
    try:
        import os
        log_dir = settings.log_dir
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{settings.session_id}.jsonl")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "role": "tool",
                "command": command,
                "result": result,
                "mode": mode.mode_id,
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return json.dumps(result, ensure_ascii=False)
