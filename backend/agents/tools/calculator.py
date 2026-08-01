import ast
import operator
import re

from langchain_core.tools import tool

# 第一层校验：长度与字符白名单（仅允许数字、四则运算符、幂、取模、括号、小数点、空格）
MAX_EXPRESSION_LENGTH = 100
SAFE_EXPRESSION_PATTERN = re.compile(r"^[0-9+\-*/%().\s]+$")

# 第二层校验：AST 节点与运算符白名单，杜绝函数调用、属性访问、名称引用等一切非算术结构
_ALLOWED_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 幂运算防护：避免 9**9**9 之类表达式造成 CPU/内存耗尽
_MAX_POW_BASE = 10**6
_MAX_POW_EXPONENT = 128


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("表达式仅支持数字")

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY_OPS:
        return _ALLOWED_UNARY_OPS[type(node.op)](_eval_node(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(left) > _MAX_POW_BASE or abs(right) > _MAX_POW_EXPONENT:
                raise ValueError("幂运算数值超出允许范围")
        return _ALLOWED_BINARY_OPS[type(node.op)](left, right)

    raise ValueError(f"表达式包含不允许的语法: {type(node).__name__}")


def safe_calculate(expression: str) -> float:
    expression = (expression or "").strip()
    if not expression:
        raise ValueError("表达式为空")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise ValueError("表达式过长")
    if not SAFE_EXPRESSION_PATTERN.match(expression):
        raise ValueError("表达式包含不允许的字符")

    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree)


@tool
def calculate(expression: str) -> str:
    """计算数学表达式（仅支持数字与 + - * / % ** 及括号）"""
    try:
        result = safe_calculate(expression)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
    except ZeroDivisionError:
        return "计算失败：除数不能为零"
    except Exception:
        return "计算失败：仅支持由数字和 + - * / % ** 括号组成的算术表达式"
