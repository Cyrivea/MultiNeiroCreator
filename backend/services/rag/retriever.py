import hashlib

from services.rag.vectorstore import vectorstore


def _build_chunk_ids(
    filename: str,
    chunk_count: int,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[str]:
    return [
        hashlib.md5(f"{filename}:{user_id}:{project_id}:{scope}:{index}".encode()).hexdigest()
        for index in range(chunk_count)
    ]


def _build_chunk_metadatas(
    filename: str,
    chunk_count: int,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[dict]:
    return [
        {
            "source": filename,
            "user_id": user_id if user_id is not None else -1,
            "project_id": project_id if project_id is not None else -1,
            "scope": scope,
            "chunk_index": index,
            "chunk_count": chunk_count,
            "chunk_size": chunk_size if chunk_size is not None else -1,
            "chunk_overlap": chunk_overlap if chunk_overlap is not None else -1,
        }
        for index in range(chunk_count)
    ]


def add_indexed_document(
    filename: str,
    chunks: list[str],
    embeddings: list,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    replace_existing: bool = True,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    if replace_existing:
        vectorstore.delete_documents(
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            source=filename,
        )

    chunk_count = len(chunks)
    metadatas = _build_chunk_metadatas(
        filename=filename,
        chunk_count=chunk_count,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    ids = _build_chunk_ids(
        filename=filename,
        chunk_count=chunk_count,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )
    vectorstore.add_documents(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas,
    )
    return chunk_count


def list_indexed_documents(
    limit: int = 100,
    offset: int = 0,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[dict]:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []

    grouped: dict[tuple[str, int, int, str], dict] = {}
    for metadata, document in zip(metadatas, documents):
        key = (
            str(metadata.get("source", "")),
            int(metadata.get("user_id", -1)),
            int(metadata.get("project_id", -1)),
            str(metadata.get("scope", scope)),
        )
        item = grouped.get(key)
        if item is None:
            preview = (document or "").replace("\n", " ").strip()
            grouped[key] = {
                "filename": metadata.get("source", ""),
                "user_id": metadata.get("user_id", -1),
                "project_id": metadata.get("project_id", -1),
                "scope": metadata.get("scope", scope),
                "chunk_count": 1,
                "chunk_size": metadata.get("chunk_size", -1),
                "chunk_overlap": metadata.get("chunk_overlap", -1),
                "preview": preview[:160],
            }
            continue

        item["chunk_count"] += 1

    documents_list = list(grouped.values())
    documents_list.sort(key=lambda item: str(item["filename"]).lower())
    return documents_list[offset : offset + limit]


def delete_indexed_document(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> int:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename,
    )
    ids = results.get("ids") or []
    if not ids:
        return 0

    vectorstore.delete_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename,
    )
    return len(ids)


def get_indexed_document_chunks(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[str]:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename,
    )
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []
    if not documents:
        return []

    ordered_chunks = sorted(
        zip(metadatas, documents),
        key=lambda item: int(item[0].get("chunk_index", 0)),
    )
    return [document for _, document in ordered_chunks]


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
