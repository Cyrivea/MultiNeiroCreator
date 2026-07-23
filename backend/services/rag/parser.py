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


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap 不能小于 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须小于 chunk_size")

    step = chunk_size - chunk_overlap
    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start += step

    return chunks
