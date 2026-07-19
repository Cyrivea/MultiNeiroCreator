from langchain_core.tools import tool


@tool
def calculate(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except Exception:
        return "计算失败"
