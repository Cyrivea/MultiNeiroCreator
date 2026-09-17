from zhipuai import ZhipuAI

from agents.prompt_loader import build_base_prompt
from core.config import API_KEY

client = ZhipuAI(api_key=API_KEY) if API_KEY else None


def build_system_prompt(profile: str, context: str) -> str:
    """主体规则全部来自 prompts/*.md 文件装配（C17），这里只负责运行时变量注入。"""
    profile_section = f"\n用户信息：\n{profile}" if profile else ""
    prompt = build_base_prompt(profile_section)
    if context:
        prompt += (
            "\n\n<knowledge_base_context>\n"
            "以下内容是后端已经从用户当前项目的私有 RAG 知识库检索出的结果。"
            "请直接把它当作可用资料回答用户问题：\n"
            f"{context}\n"
            "</knowledge_base_context>\n"
            "- 格式要求：请务必使用 Markdown 格式输出。"
        )
    return prompt
