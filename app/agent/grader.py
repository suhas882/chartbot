import re
from typing import List, Dict, Any, Tuple
from app.config import SIMILARITY_THRESHOLD

class EvidenceGrader:
    """
    Evaluates retrieved chunks for query relevance and validates citations
    to eliminate hallucinations and enforce evidence grounding.
    """

    @classmethod
    def grade_retrieval(cls, query: str, chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Grades retrieved chunks based on semantic similarity and lexical keyword overlap.
        Returns filtered relevant chunks and a boolean flag indicating if sufficient evidence exists.
        """
        if not chunks:
            return [], False

        query_words = set(re.findall(r"\w+", query.lower()))
        # Filter common stopwords
        stopwords = {"what", "is", "the", "a", "an", "and", "or", "in", "on", "of", "to", "for", "with", "how", "why", "can", "you", "tell", "me", "about"}
        keywords = query_words - stopwords

        graded_chunks = []
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            dense_sim = chunk.get("dense_similarity", 0.0)
            bm25_score = chunk.get("bm25_score", 0.0)

            # Keyword overlap count
            overlap_count = sum(1 for kw in keywords if kw in content)
            lexical_ratio = overlap_count / max(1, len(keywords))

            # Composite grade
            passed = False
            if dense_sim >= SIMILARITY_THRESHOLD:
                passed = True
            elif bm25_score > 1.2 and lexical_ratio >= 0.2:
                passed = True
            elif lexical_ratio >= 0.5:
                passed = True

            if passed:
                chunk["relevance_score"] = max(dense_sim, lexical_ratio)
                graded_chunks.append(chunk)

        # Sort by relevance score
        graded_chunks.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        has_sufficient_evidence = len(graded_chunks) > 0
        return graded_chunks, has_sufficient_evidence

    @classmethod
    def verify_citations(cls, response_text: str, valid_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extracts citations like [source_c000_hash] or [source#chunk_id] from response_text and verifies them
        against the provided valid_chunks list.
        """
        valid_cids = {c.get("chunk_id") for c in valid_chunks}
        # Find all brackets [ ... ]
        raw_matches = re.findall(r"\[([a-zA-Z0-9_\-\.#]+)\]", response_text)
        
        verified = []
        unverified = []
        for cit in raw_matches:
            if cit in valid_cids or any(cit in vcid for vcid in valid_cids):
                verified.append(cit)
            elif "_c" in cit or "#chunk_" in cit:
                unverified.append(cit)

        is_grounded = len(verified) > 0

        return {
            "is_grounded": is_grounded,
            "verified_citations": list(set(verified)),
            "unverified_citations": list(set(unverified))
        }

    @classmethod
    def format_refusal(cls, reason: str = "no_evidence") -> str:
        """Standardized transparent refusal when evidence is lacking."""
        return (
            "I do not possess verified documentation regarding this topic in my local knowledge base. "
            "To maintain strict privacy and factual grounding, I only answer questions backed by your uploaded documents. "
            "Please upload relevant files or rephrase your question around indexed topics."
        )
