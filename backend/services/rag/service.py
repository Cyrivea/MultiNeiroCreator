from services.rag.embedding import get_embedding, get_embeddings_batch
from services.rag.parser import chunk_text, read_file
from services.rag.retriever import add_indexed_document, retrieve_documents
from services.rag.vectorstore import get_collection


def add_document(
    file_path: str,
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> int:
    text = read_file(file_path, filename)
    chunks = chunk_text(text)
    embeddings = get_embeddings_batch(chunks)
    collection = get_collection()
    return add_indexed_document(
        collection=collection,
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )


def search(
    query: str,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[str]:
    embedding = get_embedding(query)
    collection = get_collection()
    return retrieve_documents(
        collection=collection,
        query_embedding=embedding,
        n_results=n_results,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )
