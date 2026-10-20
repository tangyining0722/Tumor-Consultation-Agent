import io
from pypdf import PdfReader

def extract_pdf_text(content: bytes, max_pages: int = 80) -> tuple[str, list[str]]:
    reader = PdfReader(io.BytesIO(content))
    warnings = []
    if len(reader.pages) > max_pages:
        warnings.append(f"文档共 {len(reader.pages)} 页，仅处理前 {max_pages} 页")
    pieces = []
    for i, page in enumerate(reader.pages[:max_pages], start=1):
        try:
            value = page.extract_text() or ""
        except Exception:
            value = ""
        if value.strip(): pieces.append(f"[第{i}页]\n{value}")
    if not pieces:
        warnings.append("未提取到文字：扫描版 PDF 需要另行 OCR，本版本不支持")
    return "\n\n".join(pieces), warnings

def chunk_text(text: str, size: int = 4500, overlap: int = 300) -> list[str]:
    if size <= overlap or overlap < 0: raise ValueError("size 必须大于 overlap，且 overlap 非负")
    chunks=[]
    start=0
    while start < len(text):
        end=min(start+size,len(text))
        chunks.append(text[start:end])
        if end == len(text): break
        start=end-overlap
    return chunks
