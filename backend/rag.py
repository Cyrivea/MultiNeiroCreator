import os
import hashlib
import chromadb
from dotenv import load_dotenv
from zhipuai import ZhipuAI

load_dotenv()
client_ai = ZhipuAI(api_key=os.getenv("API_KEY"))
client_db = chromadb.PersistentClient(path="./chroma_db")

try:
    collection = client_db.get_collection("documents")
except:
    collection = client_db.create_collection("documents")

def get_embedding(text):
    """单条文本向量化"""
    response = client_ai.embeddings.create(
        model="embedding-3",
        input=text
    )
    return response.data[0].embedding

def get_embeddings_batch(texts: list) -> list:
    """【优化】批量文本向量化：将多条文本一次性发给智谱，极大提升上传速度，避免触发 Rate Limit"""
    if not texts:
        return []
    response = client_ai.embeddings.create(
        model="embedding-3",
        input=texts  # 智谱 SDK 天然支持传入 List[str]
    )
    return [item.embedding for item in response.data]

def read_file(file_path: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() for page in reader.pages)
    elif ext == "docx":
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext in ["txt", "md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件类型：{ext}")

def chunk_text(text: str, chunk_size: int = 500) -> list:
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def add_document(file_path: str, filename: str):
    """【修复】严格保留 filename 参数，供 main.py 正确调用"""
    text = read_file(file_path, filename)
    chunks = chunk_text(text)
    
    # 【优化】使用批量向量化，彻底告别 for 循环串行卡顿
    embeddings = get_embeddings_batch(chunks)
    
    # 为 RAG 溯源埋下伏笔：在 metadata 中存入来源文件名
    metadatas = [{"source": filename} for _ in chunks]
    ids = [hashlib.md5(f"{filename}{i}".encode()).hexdigest() for i in range(len(chunks))]
    
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    return len(chunks)

def search(query: str, n_results: int = 3) -> list:
    embedding = get_embedding(query)
    results = collection.query(query_embeddings=[embedding], n_results=n_results)
    
    # 【修复】增加空值防崩卫兵，确保没有任何文档时返回空列表而不是抛出 IndexError
    if not results or not results.get("documents") or not results["documents"][0]:
        return []
    return results["documents"][0]