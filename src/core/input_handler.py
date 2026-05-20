# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""用户输入处理（支持单行/多行模式）"""


def smart_input(prompt: str = "") -> str:
    """
    智能输入处理器：
    - 默认单行模式，直接输入后回车提交
    - 空输入（直接回车）不提交，重新提示
    - 输入 '<<<' 后回车进入多行模式，空行提交
    """
    while True:
        print(prompt, end="", flush=True)
        try:
            first_line = input()
        except EOFError:
            return "exit"

        # 空输入不提交，继续等待
        if first_line.strip() == "":
            continue

        # 多行模式触发（注意：必须是三个小于号 <<<）
        if first_line.strip() == "<<<":
            print("  [多行模式，空行提交]")
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip() == "":
                        break
                    lines.append(line)
                except EOFError:
                    break
            if not lines:
                continue  # 多行模式也没输入内容，继续等待
            return "\n".join(lines)

        return first_line
