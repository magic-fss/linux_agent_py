# SSH Agent

基于 Python 的智能 SSH 命令执行 Agent，支持 LLM 命令生成、多层安全扫描与分布式任务执行。

## 功能特性

- **LLM 智能生成**：对接 Ollama 本地模型，自然语言描述自动转换为可执行命令
- **安全扫描**：内置高危命令黑名单与语义分析，根目录操作自动标记并强制确认
- **分布式执行**：支持多节点并发任务下发，实时显示子任务执行状态
- **错误自修复**：执行失败后自动诊断（如权限不足自动重试 `sudo`）
- **双模式兼容**：支持 Ollama 结构化 JSON 输出与纯文本降级解析

## 项目结构

```
.
├── config/              # 配置文件
│   ├── __init__.py
│   └── config.py
├── docs/                # 文档
│   └── README.md
├── src/                 # 源代码
│   ├── __init__.py
│   ├── main.py          # 程序入口
│   ├── core/            # 核心模块
│   │   ├── __init__.py
│   │   ├── agent_core.py      # Agent 核心逻辑
│   │   ├── ssh_client.py      # SSH 客户端
│   │   ├── command_guard.py   # 命令安全守卫
│   │   └── input_handler.py   # 输入处理
│   └── utils/           # 工具/UI
│       ├── __init__.py
│       ├── menu.py        # 菜单界面
│       ├── settings.py    # 配置设置
│       └── tools.py       # 工具函数
├── tests/               # 单元测试
│   ├── __init__.py
│   └── test_core.py
├── .gitignore
└── requirements.txt     # Python 依赖
```

## 环境要求

- Python 3.12+
- Ollama 本地服务（默认端口 11434）
- 远程 Linux 服务器用于 SSH 目标节点

## 安装

```bash
git clone https://github.com/magic-fss/ssh-agent.git
cd ssh-agent
pip install -r requirements.txt
```

## 配置

编辑 `config/config.py` 设置 SSH 连接与 Ollama 参数：

```python
SSH_HOST = "192.168.1.100"
SSH_PORT = 22
SSH_USER = "root"
SSH_KEY = "~/.ssh/id_rsa"

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:14b"
```

## 使用

```bash
# 直接运行
python src/main.py

# 模块方式运行
python -m src.main
```

### 示例

```bash
> 查看当前磁盘使用情况
[LLM] df -h
[Guard] 安全扫描通过
[Result] Filesystem  Size  Used Avail Use% Mounted on
         /dev/sda1   50G   20G   28G  42% /

> 清理 /var/log 下 30 天前的日志
[Guard] ⚠️ 检测到根目录操作，自动注入 sudo
[Confirm] 确认执行? [Y/n]: y
[Result] 执行成功
```

## 测试

```bash
python -m unittest discover tests/ -v
```

## 技术栈

- Python 3.12
- Paramiko（SSH 客户端）
- Ollama API（本地 LLM）
- Colorama（终端颜色）
- PyYAML（配置解析）

## 安全提示

- 高危命令默认强制二次确认，请勿关闭安全扫描
- 建议先在测试环境验证后再用于生产环境
- 推荐使用 SSH 密钥认证

## License

[MIT](LICENSE)
