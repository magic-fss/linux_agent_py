# SSH Agent Project

基于 Python 的 SSH 命令执行 Agent，支持安全扫描、LLM 命令生成与分布式任务执行。

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

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
# 在项目根目录执行
cd project
python src/main.py

# 或使用模块方式
python -m src.main
```

## 测试

```bash
python -m unittest discover tests/
```

## 环境要求

- Python 3.12+
- 详见 requirements.txt
