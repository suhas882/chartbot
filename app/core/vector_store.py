import os
import re
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from app.config import CHROMA_DIR, TOP_K_RETRIEVAL, SIMILARITY_THRESHOLD

class HybridVectorStore:
    """
    Dual-engine retriever combining ChromaDB (Dense Vector Search) with 
    in-memory BM25 (Sparse Lexical Search) using Reciprocal Rank Fusion (RRF).
    """
    COLLECTION_NAME = "knowledge_base"

    def __init__(self, persist_directory: str = str(CHROMA_DIR)):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False, is_persistent=True)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        
        # In-memory BM25 index components
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_chunk_map: List[Dict[str, Any]] = []
        self._rebuild_bm25()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        words = re.findall(r'[a-zA-Z0-9]+', text.lower())
        tokens = []
        for w in words:
            tokens.append(w)
            if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                tokens.append(w[:-1])
        return tokens

    def _rebuild_bm25(self):
        """Reconstructs the BM25 lexical index from ChromaDB documents."""
        all_docs = self.collection.get()
        if not all_docs or not all_docs['documents']:
            self.bm25_index = None
            self.bm25_chunk_map = []
            return

        tokenized_corpus = []
        self.bm25_chunk_map = []
        for i, doc_text in enumerate(all_docs['documents']):
            tokenized_corpus.append(self._tokenize(doc_text))
            self.bm25_chunk_map.append({
                "chunk_id": all_docs['ids'][i],
                "content": doc_text,
                "metadata": all_docs['metadatas'][i] if all_docs['metadatas'] else {}
            })

        if tokenized_corpus:
            self.bm25_index = BM25Okapi(tokenized_corpus)

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        if not chunks:
            return

        ids = [c["chunk_id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        self._rebuild_bm25()

    def delete_document(self, filename: str) -> int:
        """Deletes all chunks associated with a specific document (Right-to-be-Forgotten)."""
        existing = self.collection.get(where={"source": filename})
        if existing and existing["ids"]:
            count = len(existing["ids"])
            self.collection.delete(ids=existing["ids"])
            self._rebuild_bm25()
            return count
        return 0

    def list_documents(self) -> List[Dict[str, Any]]:
        all_data = self.collection.get()
        if not all_data or not all_data['metadatas']:
            return []

        doc_summary: Dict[str, Dict[str, Any]] = {}
        for meta in all_data['metadatas']:
            src = meta.get('source', 'Unknown')
            if src not in doc_summary:
                doc_summary[src] = {
                    "filename": src,
                    "total_chunks": meta.get('total_chunks', 1),
                    "indexed_chunks": 0
                }
            doc_summary[src]["indexed_chunks"] += 1

        return list(doc_summary.values())

    def hybrid_search(self, query: str, top_k: int = TOP_K_RETRIEVAL) -> List[Dict[str, Any]]:
        """
        Executes parallel dense and sparse search, merging results with Reciprocal Rank Fusion.
        """
        if self.collection.count() == 0:
            return []

        # 1. Dense Semantic Search (ChromaDB)
        dense_results = self.collection.query(
            query_texts=[query],
            n_results=min(15, self.collection.count())
        )

        dense_ranked = []
        if dense_results and dense_results['ids'] and dense_results['ids'][0]:
            for rank, cid in enumerate(dense_results['ids'][0]):
                # Distance in cosine space: distance = 1 - cosine_similarity. Similarity = 1 - distance.
                dist = dense_results['distances'][0][rank] if dense_results['distances'] else 0.5
                sim = max(0.0, 1.0 - dist)
                dense_ranked.append({
                    "chunk_id": cid,
                    "content": dense_results['documents'][0][rank],
                    "metadata": dense_results['metadatas'][0][rank],
                    "dense_similarity": sim,
                    "dense_rank": rank
                })

        # 2. Sparse Lexical Search (BM25)
        sparse_ranked = []
        if self.bm25_index:
            query_tokens = self._tokenize(query)
            bm25_scores = self.bm25_index.get_scores(query_tokens)
            # Pair scores with chunk objects
            scored_chunks = list(zip(self.bm25_chunk_map, bm25_scores))
            # Sort descending by BM25 score
            scored_chunks = sorted(scored_chunks, key=lambda x: x[1], reverse=True)[:15]
            
            for rank, (item, score) in enumerate(scored_chunks):
                if score > 0.0:  # Only include positive keyword matches
                    sparse_ranked.append({
                        "chunk_id": item["chunk_id"],
                        "content": item["content"],
                        "metadata": item["metadata"],
                        "bm25_score": score,
                        "sparse_rank": rank
                    })

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_Score = SUM( 1 / (60 + rank_i) )
        rrf_dict: Dict[str, Dict[str, Any]] = {}

        for item in dense_ranked:
            cid = item["chunk_id"]
            if cid not in rrf_dict:
                rrf_dict[cid] = item.copy()
                rrf_dict[cid]["rrf_score"] = 0.0
            rrf_dict[cid]["rrf_score"] += (1.0 / (60.0 + item["dense_rank"]))

        for item in sparse_ranked:
            cid = item["chunk_id"]
            if cid not in rrf_dict:
                rrf_dict[cid] = item.copy()
                rrf_dict[cid]["rrf_score"] = 0.0
            rrf_dict[cid]["rrf_score"] += (1.0 / (60.0 + item["sparse_rank"]))

        # Sort combined results by RRF score
        merged = sorted(rrf_dict.values(), key=lambda x: x["rrf_score"], reverse=True)

        # 4. Confidence Threshold Filter
        # Retain chunks that meet either dense similarity or strong BM25 presence
        filtered = []
        for chunk in merged:
            sim = chunk.get("dense_similarity", 0.0)
            if sim >= SIMILARITY_THRESHOLD or chunk.get("bm25_score", 0.0) > 0.5:
                filtered.append(chunk)

        return filtered[:top_k]
