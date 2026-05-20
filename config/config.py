"""全局配置常量（向后兼容层）

注意：v1.1 版本推荐使用 settings.py 中的 SettingsManager 进行动态配置管理。
本文件保留为向后兼容的静态默认值，实际运行时优先读取环境变量。
"""
import os

# SSH 连接配置（可被 SettingsManager 覆盖）
HOSTNAME = os.getenv("SSH_HOST", "192.168.20.129")
PORT = int(os.getenv("SSH_PORT", "22"))
USERNAME = os.getenv("SSH_USER", "admin")
PASSWORD = os.getenv("SSH_PASSWORD", "123456")

# 命令复杂度限制
MAX_COMMAND_LENGTH = 1000          # 单条命令最大字符数
MAX_AND_OPERATORS = 2            # 最多允许的 && 个数
MAX_PIPE_DEPTH = 2               # 管道 | 最大深度

# 危险命令黑名单
DANGEROUS_COMMANDS = [
    "rm -rf /", "mkfs", "dd if=", "> /dev/sda", ":(){:|:&};:"
]

# 运维白名单（Rocky Linux / RHEL 系常用命令）
ALLOWED_COMMAND_PREFIXES = [
    # 1. 基础文件与目录操作
    "ls", "cat", "pwd", "cd", "cp", "mv", "mkdir", "rm", "rmdir", "ln", "touch",
    "chmod", "chown", "chgrp", "find", "locate", "file", "du", "basename", "dirname",
    # 2. 文本查看与处理
    "head", "tail", "less", "more", "grep", "awk", "sed", "sort", "uniq", "wc",
    "cut", "diff", "strings",
    # 3. 系统状态与性能监控
    "top", "ps", "df", "free", "uptime", "who", "w", "last", "uname", "hostname",
    "dmesg", "lscpu", "lsblk", "lsusb", "lspci",
    # 4. 网络工具
    "ping", "curl", "wget", "netstat", "ss", "ip", "ifconfig", "nslookup", "dig",
    "traceroute", "telnet", "nc",
    # 5. 软件包管理 (Rocky Linux / RHEL 专属)
    "rpm", "dnf", "yum",
    # 6. 系统服务与日志
    "systemctl", "journalctl", "service",
    # 7. 压缩与归档
    "tar", "zip", "unzip", "gzip", "gunzip", "bzip2",
    # 8. 其他常用工具
    "echo", "whoami", "id", "date", "cal", "history", "clear", "exit", "sudo",
    "tee", "xargs", "nohup"
]
