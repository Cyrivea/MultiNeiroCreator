import hashlib

from services.rag.vectorstore import vectorstore


def add_indexed_document(
    filename: str,
    chunks: list[str],
    embeddings: list,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> int:
    metadatas = [
        {
            "source": filename,
            "user_id": user_id if user_id is not None else -1,
            "project_id": project_id if project_id is not None else -1,
            "scope": scope,
        }
        for _ in chunks
    ]
    ids = [
        hashlib.md5(f"{filename}:{user_id}:{project_id}:{scope}:{index}".encode()).hexdigest()
        for index in range(len(chunks))
    ]
    vectorstore.add_documents(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas,
    )
    return len(chunks)


def retrieve_documents(
    query_embedding,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[str]:
    results = vectorstore.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )
    if not results or not results.get("documents") or not results["documents"][0]:
        return []
    return results["documents"][0]
