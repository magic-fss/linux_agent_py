# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""命令安全校验与验证命令生成"""
import re
from config.config import (
    MAX_COMMAND_LENGTH, MAX_AND_OPERATORS, MAX_PIPE_DEPTH,
    DANGEROUS_COMMANDS, ALLOWED_COMMAND_PREFIXES
)

# ================= 参数级校验配置 =================
# df --output 可用字段白名单（严格限定）
DF_OUTPUT_FIELDS = {
    "source", "fstype", "itotal", "iused", "iavail", "ipcent",
    "size", "used", "avail", "pcent", "file", "target"
}

# ps -o 常用字段白名单
PS_OUTPUT_FIELDS = {
    "pid", "ppid", "pgid", "sid", "cmd", "comm", "args",
    "%cpu", "%mem", "etime", "time", "user", "group", "ruid", "rgid",
    "tty", "stat", "start", "rss", "vsz", "ni", "pri"
}

# 查询类命令（不需要自动验证，但需要数据分析建议）
QUERY_COMMANDS = {
    "df", "free", "ps", "top", "uptime", "who", "w", "last",
    "netstat", "ss", "ip", "ifconfig", "lscpu", "lsblk", "lsusb", "lspci",
    "du", "uname", "hostname", "dmesg", "ping", "curl", "wget",
    "rpm", "dnf", "yum", "systemctl", "journalctl"
}


def validate_command_complexity(command: str) -> tuple[bool, str]:
    """
    校验命令复杂度：长度、&&数量、管道深度、命令替换
    返回: (是否通过, 错误信息)
    """
    stripped = command.strip()

    # 1. 长度限制
    if len(stripped) > MAX_COMMAND_LENGTH:
        return False, (
            f"命令过长（{len(stripped)}字符），超出限制{MAX_COMMAND_LENGTH}字符。\n"
            f"请拆分执行，每次只查一个维度。"
        )

    # 2. && 连接数限制
    and_count = stripped.count("&&")
    if and_count > MAX_AND_OPERATORS:
        return False, (
            f"命令串联过多（{and_count + 1}条），超出限制{MAX_AND_OPERATORS + 1}条。\n"
            f"请分步执行，每次最多串联{MAX_AND_OPERATORS + 1}条短命令。"
        )

    # 3. 管道深度限制
    pipe_count = stripped.count("|")
    if pipe_count > MAX_PIPE_DEPTH:
        return False, (
            f"管道嵌套过深（{pipe_count}层），超出限制{MAX_PIPE_DEPTH}层。\n"
            f"请简化命令，减少管道使用。"
        )

    # 4. 子shell/命令替换限制
    if stripped.count("$(") > 1 or stripped.count("`") > 0:
        return False, "禁止使用命令替换（$() / ``），请使用简单命令。"

    return True, ""


def validate_command_whitelist(command: str) -> tuple[bool, str]:
    """
    白名单校验：检查命令前缀是否在允许列表中
    支持 && 和 | 拆分后的子命令逐一校验
    """
    if not ALLOWED_COMMAND_PREFIXES:
        return True, ""

    # 按 && 和 | 拆分，检查每个子命令的前缀
    sub_commands = re.split(r'\s*&&\s*|\s*\|\s*', command.strip())

    for sub in sub_commands:
        sub = sub.strip()
        if not sub:
            continue

        # 提取命令前缀（处理 sudo 前缀）
        parts = sub.split()
        cmd_prefix = parts[0] if parts else ""

        if cmd_prefix == "sudo" and len(parts) > 1:
            cmd_prefix = parts[1]

        if cmd_prefix not in ALLOWED_COMMAND_PREFIXES:
            return False, f"安全拦截：命令 '{cmd_prefix}' 不在运维白名单内。"

    return True, ""


def is_dangerous_command(command: str) -> str | None:
    """
    危险命令检测
    返回: 匹配到的危险命令子串，None 表示安全
    """
    for danger in DANGEROUS_COMMANDS:
        if danger in command:
            return danger
    return None


def validate_command_args(command: str) -> tuple[bool, str]:
    """
    参数级校验：对高频易错命令做字段名/参数合法性检查
    返回: (是否通过, 错误信息)
    """
    parts = command.strip().split()
    if not parts:
        return True, ""

    cmd = parts[0]

    # 1. df --output 字段名校验
    if cmd == "df":
        for i, part in enumerate(parts):
            if part == "--output" or part.startswith("--output="):
                # 提取字段列表
                if "=" in part:
                    fields_str = part.split("=", 1)[1]
                elif i + 1 < len(parts):
                    fields_str = parts[i + 1]
                else:
                    continue

                fields = [f.strip() for f in fields_str.split(",")]
                invalid = [f for f in fields if f not in DF_OUTPUT_FIELDS]
                if invalid:
                    return False, (
                        f"df --output 包含非法字段：{', '.join(invalid)}。\n"
                        f"可用字段：{', '.join(sorted(DF_OUTPUT_FIELDS))}"
                    )
                break

    # 2. ps -o 字段名校验
    elif cmd == "ps":
        for i, part in enumerate(parts):
            if part == "-o" or part == "--format":
                if i + 1 < len(parts):
                    fields_str = parts[i + 1]
                    fields = [f.strip() for f in fields_str.split(",")]
                    invalid = [f for f in fields if f not in PS_OUTPUT_FIELDS]
                    if invalid:
                        return False, (
                            f"ps -o 包含非法字段：{', '.join(invalid)}。\n"
                            f"可用字段：{', '.join(sorted(PS_OUTPUT_FIELDS))}"
                        )
                break

    # 3. sort -k 参数校验（防止越界）
    elif cmd == "sort":
        for i, part in enumerate(parts):
            if part == "-k":
                if i + 1 < len(parts):
                    key_str = parts[i + 1]
                    if not key_str.isdigit():
                        return False, f"sort -k 参数必须是正整数，当前为 '{key_str}'"
                break

    # 4. echo 命令校验：禁止包含 \n 转义序列（应使用 cat << 'EOF' 写多行文件）
    if cmd == "echo":
        if "\\n" in command:
            return False, (
                "echo 命令包含 \\n 转义序列，无法正确写入多行内容。\n"
                "请使用 cat << 'EOF' 方式创建多行文件：\n"
                "cat > ~/file.sh << 'EOF'\n"
                "#!/bin/bash\n"
                "...\n"
                "EOF"
            )

    return True, ""


def is_query_command(command: str) -> bool:
    """
    判断命令是否为查询类命令（不需要自动验证，但需要数据分析）
    """
    parts = command.strip().split()
    if not parts:
        return False
    cmd = parts[0]
    if cmd == "sudo" and len(parts) > 1:
        cmd = parts[1]
    return cmd in QUERY_COMMANDS


def generate_verify_command(command: str) -> str | None:
    """
    根据原始命令生成对应的验证命令
    仅对变更类命令生成验证命令，查询类命令返回 None
    返回: 验证命令字符串，None 表示无需/无法验证
    """
    # 查询类命令不需要验证
    if is_query_command(command):
        return None

    stripped = command.strip()
    parts = stripped.split()
    if not parts:
        return None

    cmd = parts[0]
    # 提取所有非选项参数（不以 - 开头的参数）
    args = [p for p in parts[1:] if not p.startswith('-') and p]

    if not args:
        return None

    # rm / rmdir → 验证目标是否已不存在
    if cmd in ("rm", "rmdir"):
        target = args[0]
        return f"ls -d {target} 2>/dev/null || echo 'VERIFY_OK: 目标已删除'"

    # mkdir → 验证所有创建的目录
    elif cmd == "mkdir":
        if len(args) == 1:
            return f"ls -ld {args[0]}"
        else:
            targets = " ".join(args)
            return f"ls -ld {targets}"

    # touch → 验证文件是否存在
    elif cmd == "touch":
        return f"ls -l {args[-1]}"

    # chmod / chown / chgrp → 验证权限/属主是否已变更
    elif cmd in ("chmod", "chown", "chgrp"):
        return f"ls -l {args[-1]}"

    # cp → 验证目标是否存在
    elif cmd == "cp":
        if len(args) >= 2:
            return f"ls -l {args[-1]}"

    # mv → 验证新路径存在且旧路径不存在
    elif cmd == "mv":
        if len(args) >= 2:
            old_path = args[-2]
            new_path = args[-1]
            return (
                f"ls -l {new_path} && "
                f"(ls -d {old_path} 2>/dev/null || echo 'VERIFY_OK: 旧路径已移除')"
            )

    # 其他变更命令：返回 None，不自动验证
    return None
