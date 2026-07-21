from zhipuai import ZhipuAI

from core.config import API_KEY


client_ai = ZhipuAI(api_key=API_KEY) if API_KEY else None


def get_embedding(text: str):
    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，RAG 向量检索暂不可用")
    response = client_ai.embeddings.create(model="embedding-3", input=text)
    return response.data[0].embedding


def get_embeddings_batch(texts: list[str]) -> list:
    if not texts:
        return []
    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，文档向量化暂不可用")
    response = client_ai.embeddings.create(model="embedding-3", input=texts)
    return [item.embedding for item in response.data]
