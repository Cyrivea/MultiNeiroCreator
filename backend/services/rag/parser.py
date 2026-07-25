from pathlib import Path


def _read_plain_text(file_path: str) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return Path(file_path).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文本文件编码无法识别，请转为 UTF-8 后重试")


def read_file(file_path: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if text:
            return text
        raise ValueError("PDF 未提取到可读文本，可能是扫描件或图片型 PDF，需先进行 OCR")
    if ext == "docx":
        from docx import Document

        doc = Document(file_path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
        if text:
            return text
        raise ValueError("DOCX 未提取到可读文本，请检查文档内容是否为空")
    if ext in ["txt", "md", "json", "csv"]:
        text = _read_plain_text(file_path).strip()
        if text:
            return text
        raise ValueError("文本文件内容为空，无法建立 RAG 索引")
    if ext in ["doc", "xls", "xlsx", "ppt", "pptx"]:
        raise ValueError(f"当前本地解析链暂不支持 .{ext} 直读，请先转换为 PDF、DOCX 或 TXT")
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
