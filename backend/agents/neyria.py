from zhipuai import ZhipuAI

from agents.tools.calculator import calculate
from agents.tools.current_time import get_current_time
from agents.tools.search_web import search_web
from core.config import API_KEY


client = ZhipuAI(api_key=API_KEY) if API_KEY else None

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前最新的北京时间，当用户询问时间、日期或今天星期几时调用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索网络获取实时信息，适合查询新闻、天气、最新事件等",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
        },
    },
]

tools_map = {
    "calculate": calculate,
    "get_current_time": get_current_time,
    "search_web": search_web,
}


def build_system_prompt(profile: str, context: str) -> str:
    profile_section = f"\n用户信息：\n{profile}" if profile else ""
    prompt = f"""你是Neyria，用户的私人AI助手，说话不考虑用户体验，不要有情绪。{profile_section}

工具使用规则：
- 涉及实时信息、新闻、天气、最新事件时，必须调用search_web工具
- 涉及数学计算时，调用calculate工具
- 用户追问或质疑某个事实时，必须重新调用search_web验证，不能依赖上下文记忆
- 如果搜索结果包含非中文内容，回答时自动翻译成中文
"""
    if context:
        prompt += f"\n\n参考以下资料回答问题：\n{context}"
        prompt += "\n- 格式要求：请务必使用 Markdown 格式输出。"
    return prompt
