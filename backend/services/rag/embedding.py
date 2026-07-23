from google import genai

from core.config import EMBEDDING_API_KEY

client_ai = (
    genai.Client(api_key=EMBEDDING_API_KEY)
    if EMBEDDING_API_KEY
    else None
)


def get_embedding(text: str):
    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，RAG 向量检索暂不可用")

    result = client_ai.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )

    return result.embeddings[0].values


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，文档向量化暂不可用")

    embeddings = []

    for text in texts:
        result = client_ai.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        embeddings.append(result.embeddings[0].values)

    return embeddings