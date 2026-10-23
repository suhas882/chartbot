import os
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from pathlib import Path
from app.config import RAW_DOCS_DIR
from app.core.ingestion import DocumentIngestionEngine
from app.core.vector_store import HybridVectorStore

def main():
    store = HybridVectorStore()
    docs = list(RAW_DOCS_DIR.glob("*.*"))
    print(f"Found {len(docs)} documents in {RAW_DOCS_DIR}")
    for doc in docs:
        print(f"Processing {doc.name}...")
        chunks = DocumentIngestionEngine.process_document(doc)
        print(f"  Generated {len(chunks)} chunks.")
        store.add_chunks(chunks)
        print(f"  Indexed into ChromaDB & BM25.")
        
    print("\nCurrent Indexed Documents:")
    for d in store.list_documents():
        print(f" - {d['filename']}: {d.get('indexed_chunks', 0)} chunks")
    print(f"Total vector count in ChromaDB: {store.collection.count()}")

if __name__ == "__main__":
    main()
