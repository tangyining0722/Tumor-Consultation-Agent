import hashlib
from .reader import chunk_text
from .store import get_chunk, save_chunk
from .llm import LLMClient

def read_document(text: str, providers: list[str], max_chunks: int = 8) -> dict:
    """逐块处理，结果写入 SQLite；不等于模型一次读完全文。"""
    chunks = chunk_text(text)[:max_chunks]
    doc_hash=hashlib.sha256(text.encode()).hexdigest()
    output={}
    for provider in providers:
        client=LLMClient(provider)
        summaries=[]
        for i, chunk in enumerate(chunks):
            cached=get_chunk(doc_hash,provider,i)
            if cached is None:
                cached=client.ask("请只根据以下文献片段提取研究类型、研究人群、主要结果、局限性。不得虚构未出现的内容。\n\n"+chunk, max_tokens=850)
                save_chunk(doc_hash,provider,i,cached)
            summaries.append(f"片段 {i+1}:\n{cached}")
        output[provider]={"chunks_processed":len(chunks),"summaries":summaries,
            "warning":"只处理了选定片段；片段摘要不能保证保留全文所有细节。"}
    return output
