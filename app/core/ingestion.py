import re
import hashlib
from pathlib import Path
from typing import List, Dict, Any
from app.core.privacy import PIIScrubber
from app.config import CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS

class DocumentIngestionPipeline:
    """
    Extracts text, scrubs PII, and recursively chunks documents with SHA-256 verification.
    """
    def __init__(self, chunk_size: int = CHUNK_SIZE_TOKENS, chunk_overlap: int = CHUNK_OVERLAP_TOKENS):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        elif suffix == ".pdf":
            text_parts = []
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text_parts.append(extracted)
            except Exception:
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(file_path))
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text_parts.append(extracted)
                except Exception as e:
                    raise RuntimeError(f"Could not extract PDF text: {e}")
            return "\n\n".join(text_parts)
        elif suffix == ".docx":
            try:
                import docx
                doc = docx.Document(file_path)
                return "\n".join([p.text for p in doc.paragraphs if p.text])
            except Exception as e:
                raise RuntimeError(f"Could not extract DOCX text: {e}")
        else:
            raise ValueError(f"Unsupported document format: {suffix}")

    def clean_text(self, text: str) -> str:
        # Purge null bytes, normalize linebreaks and duplicate whitespaces
        cleaned = text.replace("\x00", "")
        cleaned = re.sub(r'\r\n|\r', '\n', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
        return cleaned.strip()

    def recursive_chunk(self, text: str) -> List[str]:
        # Split text primarily along section headers (markdown # or numbered paragraphs)
        raw_sections = re.split(r'\n(?=#{1,3}\s|\d+\.\s+[A-Z])', text)
        sections = [s.strip() for s in raw_sections if s.strip()]
        if not sections:
            sections = [text.strip()]

        chunks = []
        current_chunk = []
        current_len = 0
        target_words = min(250, self.chunk_size)

        for sec in sections:
            sec_words = sec.split()
            if not sec_words:
                continue

            # If section itself exceeds target size, split it with overlap
            if len(sec_words) > target_words:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                
                i = 0
                step = max(1, target_words - self.chunk_overlap)
                while i < len(sec_words):
                    sub_chunk = " ".join(sec_words[i : i + target_words])
                    chunks.append(sub_chunk)
                    i += step
            elif current_len + len(sec_words) <= target_words:
                current_chunk.append(sec)
                current_len += len(sec_words)
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [sec]
                current_len = len(sec_words)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        raw_text = self.extract_text(file_path)
        cleaned_text = self.clean_text(raw_text)
        sanitized_text, redacted_info = PIIScrubber.sanitize(cleaned_text)
        
        raw_chunks = self.recursive_chunk(sanitized_text)
        processed_chunks = []
        doc_name = file_path.name

        for idx, chunk_text in enumerate(raw_chunks):
            chunk_hash = hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()[:12]
            processed_chunks.append({
                "chunk_id": f"{doc_name}_c{idx:03d}_{chunk_hash}",
                "content": chunk_text,
                "metadata": {
                    "source": doc_name,
                    "chunk_index": idx,
                    "total_chunks": len(raw_chunks),
                    "sha256": chunk_hash,
                    "redacted_count": len(redacted_info)
                }
            })

        return processed_chunks

    @classmethod
    def process_document(cls, file_path: Path) -> List[Dict[str, Any]]:
        pipeline = cls()
        return pipeline.process_file(file_path)

# Alias for backwards compatibility
DocumentIngestionEngine = DocumentIngestionPipeline
