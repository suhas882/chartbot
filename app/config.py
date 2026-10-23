import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DOCS_DIR = DATA_DIR / "raw_documents"
CHROMA_DIR = DATA_DIR / "chroma_data"
REPORTS_DIR = DATA_DIR / "reports"

# Ensure directories exist
for d in [DATA_DIR, RAW_DOCS_DIR, CHROMA_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Model Settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# RAG & Chunking Parameters
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50
SIMILARITY_THRESHOLD = 0.35  # Minimum confidence threshold for all-MiniLM-L6-v2 embeddings
TOP_K_RETRIEVAL = 4

# Security & Privacy Settings
ENABLE_PII_SCRUBBING = True
LOCAL_ONLY_MODE = True
