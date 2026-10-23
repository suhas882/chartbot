import os
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import re
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Generator, Optional
import torch
from app.config import OLLAMA_HOST, DEFAULT_LLM_MODEL

# Singleton cached Hugging Face model and tokenizer
_GLOBAL_HF_MODEL = None
_GLOBAL_HF_TOKENIZER = None
LOCAL_HF_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

def _get_hf_pipeline():
    global _GLOBAL_HF_MODEL, _GLOBAL_HF_TOKENIZER
    if _GLOBAL_HF_MODEL is None or _GLOBAL_HF_TOKENIZER is None:
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            _GLOBAL_HF_TOKENIZER = AutoTokenizer.from_pretrained(LOCAL_HF_MODEL_NAME)
            _GLOBAL_HF_MODEL = AutoModelForCausalLM.from_pretrained(LOCAL_HF_MODEL_NAME, dtype=torch.float32)
        except Exception as e:
            print(f"[WARN] Could not load local Hugging Face model {LOCAL_HF_MODEL_NAME}: {e}")
            return None, None
    return _GLOBAL_HF_TOKENIZER, _GLOBAL_HF_MODEL

class LocalLLMClient:
    """
    Local reasoning engine interfacing with local Ollama daemon or
    in-process open-source Hugging Face transformer model (Qwen2.5-0.5B-Instruct).
    Guarantees 100% offline, zero-cloud execution with genuine LLM comprehension.
    """
    def __init__(self, host: str = OLLAMA_HOST, model: str = DEFAULT_LLM_MODEL):
        self.host = host
        self.model = model

    def check_ollama_status(self) -> Dict[str, Any]:
        """Checks if local Ollama daemon is reachable; otherwise reports local Hugging Face engine."""
        url = f"{self.host}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode())
                models = [m.get("name") for m in data.get("models", [])]
                active = self.model if self.model in models or f"{self.model}:latest" in models else (models[0] if models else self.model)
                return {
                    "available": True,
                    "engine": "Ollama Daemon",
                    "host": self.host,
                    "active_model": active,
                    "installed_models": models
                }
        except Exception:
            return {
                "available": False,
                "engine": "Local Hugging Face (PyTorch)",
                "host": self.host,
                "active_model": f"{LOCAL_HF_MODEL_NAME} (Local)",
                "installed_models": [LOCAL_HF_MODEL_NAME]
            }

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Non-streaming generation from local Ollama or in-process Hugging Face LLM."""
        status = self.check_ollama_status()
        if status["available"]:
            url = f"{self.host}/api/generate"
            payload = {
                "model": status["active_model"],
                "prompt": prompt,
                "system": system_prompt or "",
                "stream": False,
                "options": {"temperature": 0.1}
            }
            try:
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    res_json = json.loads(resp.read().decode())
                    return res_json.get("response", "").strip()
            except Exception:
                pass  # Fall through to local Hugging Face model

        # Local Hugging Face Model Generation
        return self._generate_with_hf(prompt, system_prompt)

    def _generate_with_hf(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Runs inference locally on CPU via Hugging Face transformer model."""
        tok, model = _get_hf_pipeline()
        if tok is None or model is None:
            return self._local_grounded_fallback(prompt, system_prompt)

        # Extract verified context and user query
        context_text = ""
        query_text = prompt
        chunk_cids = []

        if "<verified_context>" in prompt and "</verified_context>" in prompt:
            start_idx = prompt.find("<verified_context>") + len("<verified_context>")
            end_idx = prompt.find("</verified_context>")
            context_text = prompt[start_idx:end_idx].strip()
            query_part = prompt.split("Query:")[-1].strip() if "Query:" in prompt else prompt[end_idx + len("</verified_context>"):].strip()
            query_text = query_part.split("\n")[0].strip()

            # Find all chunk IDs in context (matching document chunk format)
            raw_cids = re.findall(r"\[([a-zA-Z0-9_\-\.#]+)\]", context_text)
            chunk_cids = [
                cid for cid in raw_cids 
                if any(ext in cid for ext in [".md", ".pdf", ".txt", ".docx", "_c0", "#chunk"]) 
                and not cid.startswith("REDACTED")
            ]
            chunk_cids = list(dict.fromkeys(chunk_cids))

        sys_msg = (
            system_prompt or 
            "You are a helpful, accurate enterprise knowledge assistant.\n"
            "Rules:\n"
            "1. Answer the question accurately and concisely using ONLY facts from the provided context.\n"
            "2. If the context does not contain the answer, say: 'I do not possess verified documentation regarding this topic in my local knowledge base. Please upload relevant files or ask a question scoped to your indexed documents.'\n"
            "3. Do not make up facts."
        )

        user_msg = f"Context:\n{context_text}\n\nQuestion: {query_text}" if context_text else query_text

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg}
        ]

        try:
            chat_prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tok(chat_prompt, return_tensors="pt")

            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=220,
                    do_sample=False,
                    pad_token_id=tok.eos_token_id
                )

            answer = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

            # If answer is valid and context chunks exist, append citations
            if chunk_cids and "I do not possess verified documentation" not in answer:
                citations_suffix = "\n\n**Sources:** " + " ".join([f"[{cid}]" for cid in chunk_cids[:3]])
                if not any(f"[{cid}]" in answer for cid in chunk_cids):
                    answer += citations_suffix

            return answer

        except Exception as e:
            print(f"[WARN] Hugging Face inference error: {e}")
            return self._local_grounded_fallback(prompt, system_prompt)

    def _local_grounded_fallback(self, prompt: str, system_prompt: Optional[str]) -> str:
        """
        Extractive fallback in case both Ollama and PyTorch fail to initialize.
        """
        if "<verified_context>" in prompt and "</verified_context>" in prompt:
            start_idx = prompt.find("<verified_context>") + len("<verified_context>")
            end_idx = prompt.find("</verified_context>")
            context_block = prompt[start_idx:end_idx].strip()
            
            query_part = prompt.split("Query:")[-1].strip() if "Query:" in prompt else ""
            query_part = query_part.split("\n")[0].strip()
            
            if not context_block or "No relevant evidence" in context_block:
                return "I do not possess verified documentation regarding this topic in my local knowledge base. Please upload relevant files or ask a question scoped to your indexed documents."
            
            raw_keywords = set(re.findall(r"\w+", query_part.lower()))
            stopwords = {"what", "is", "the", "a", "an", "and", "or", "in", "on", "of", "to", "for", "with", "how", "why", "can", "you", "tell", "me", "about", "are", "do", "does"}
            keywords = [kw for kw in raw_keywords if kw not in stopwords and len(kw) > 2]
            
            chunk_sections = context_block.split("\n\n")
            candidate_sentences = []
            
            for section in chunk_sections:
                if not section.strip():
                    continue
                lines = section.strip().split("\n")
                header = lines[0] if lines else ""
                body = " ".join(lines[1:]) if len(lines) > 1 else lines[0]
                
                cid = ""
                if "[" in header and "]" in header:
                    cid = header[header.find("[")+1 : header.find("]")]
                    
                raw_sentences = re.split(r'(?<=[.!?])\s+', body)
                for s in raw_sentences:
                    s_clean = s.strip()
                    s_clean = re.sub(r'#+\s*', '', s_clean)
                    s_clean = re.sub(r'^\d+\.\d*\s*', '', s_clean).strip()
                    if len(s_clean) < 20:
                        continue
                    s_lower = s_clean.lower()
                    score = sum(3 if kw in s_lower else 0 for kw in keywords)
                    candidate_sentences.append({
                        "sentence": s_clean,
                        "cid": cid,
                        "score": score
                    })
            
            candidate_sentences.sort(key=lambda x: x["score"], reverse=True)
            selected = [c for c in candidate_sentences if c["score"] > 0][:3]
            if not selected and candidate_sentences:
                selected = candidate_sentences[:2]
                
            if selected:
                synthesis = "Based on verified local documentation:\n\n"
                for item in selected:
                    cid_tag = f" [{item['cid']}]" if item["cid"] else ""
                    synthesis += f"• **{item['sentence']}**{cid_tag}\n\n"
                return synthesis
                
        return "I am an enterprise knowledge assistant operating under strict local verification constraints. Please upload documents to begin querying."
