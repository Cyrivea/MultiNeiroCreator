import hashlib
import json
from pathlib import Path

import chromadb
from zhipuai import ZhipuAI

from core.config import API_KEY, BACKEND_DIR


client_ai = ZhipuAI(api_key=API_KEY) if API_KEY else None
client_db = chromadb.PersistentClient(path=str(BACKEND_DIR / "chroma_db"))

try:
    collection = client_db.get_collection("documents")
except Exception:
    collection = client_db.create_collection("documents")


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


def read_file(file_path: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "docx":
        from docx import Document

        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    if ext in ["txt", "md", "json"]:
        return Path(file_path).read_text(encoding="utf-8")
    raise ValueError(f"不支持的文件类型：{ext}")


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    chunks: list[str] = []
    for index in range(0, len(text), chunk_size):
        chunk = text[index : index + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def add_document(file_path: str, filename: str) -> int:
    text = read_file(file_path, filename)
    chunks = chunk_text(text)
    embeddings = get_embeddings_batch(chunks)

    metadatas = [{"source": filename} for _ in chunks]
    ids = [hashlib.md5(f"{filename}{index}".encode()).hexdigest() for index in range(len(chunks))]

    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    return len(chunks)


def search(query: str, n_results: int = 3) -> list[str]:
    embedding = get_embedding(query)
    results = collection.query(query_embeddings=[embedding], n_results=n_results)
    if not results or not results.get("documents") or not results["documents"][0]:
        return []
    return results["documents"][0]
