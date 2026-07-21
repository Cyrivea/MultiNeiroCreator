import chromadb

from core.config import BACKEND_DIR


DEFAULT_COLLECTION_NAME = "documents"
client_db = chromadb.PersistentClient(path=str(BACKEND_DIR / "chroma_db"))


def get_collection(name: str = DEFAULT_COLLECTION_NAME):
    try:
        return client_db.get_collection(name)
    except Exception:
        return client_db.create_collection(name)


def build_metadata_filter(
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
