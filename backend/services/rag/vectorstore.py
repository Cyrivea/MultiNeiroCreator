import chromadb
from core.config import BACKEND_DIR

DEFAULT_COLLECTION_NAME = "documents"


class VectorStore:
    def __init__(self, collection_name: str = DEFAULT_COLLECTION_NAME):
        self.client_db = chromadb.PersistentClient(path=str(BACKEND_DIR / "chroma_db"))
        self.collection = self._get_or_create_collection(collection_name)

    def _get_or_create_collection(self, name: str):
        try:
            return self.client_db.get_collection(name)
        except Exception:
            return self.client_db.create_collection(name)

    def _build_metadata_filter(
        self,
        user_id: int | None = None,
        project_id: int | None = None,
        scope: str | None = None,
    ):
        where: dict[str, int | str] = {}
        if user_id is not None:
            where["user_id"] = user_id
        if project_id is not None:
            where["project_id"] = project_id
        if scope:
            where["scope"] = scope
        return where or None

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )

    def delete_documents(
        self,
        ids: list[str] | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
        scope: str | None = None,
    ) -> None:
        where = self._build_metadata_filter(user_id, project_id, scope)
        self.collection.delete(ids=ids, where=where)

    def query(
        self,
        query_embeddings: list[list[float]] | None = None,
        query_texts: list[str] | None = None,
        n_results: int = 5,
        user_id: int | None = None,
        project_id: int | None = None,
        scope: str | None = None,
    ):
        where = self._build_metadata_filter(user_id, project_id, scope)
        return self.collection.query(
            query_embeddings=query_embeddings,
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )

    def count(self) -> int:
        return self.collection.count()

    def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
        project_id: int | None = None,
        scope: str | None = None,
    ):
        where = self._build_metadata_filter(user_id, project_id, scope)
        return self.collection.get(
            limit=limit,
            offset=offset,
            where=where,
        )


vectorstore = VectorStore()
