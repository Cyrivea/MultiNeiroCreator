from pathlib import Path


def read_file(file_path: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "docx":
        from docx import Document

        doc = Document(file_path)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
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
