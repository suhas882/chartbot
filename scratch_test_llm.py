import os
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from app.core.vector_store import HybridVectorStore

def main():
    store = HybridVectorStore()
    query = "What are the password requirements and session timeout rules?"
    chunks = store.hybrid_search(query, top_k=2)
    
    context_text = "\n\n".join([f"[{c['chunk_id']}]:\n{c['content']}" for c in chunks])
    
    print("Loading local Hugging Face model Qwen/Qwen2.5-0.5B-Instruct...")
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", dtype=torch.float32)
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are an enterprise knowledge assistant operating under strict factual verification rules.\n"
                "Rules:\n"
                "1. Answer the user question accurately and concisely using ONLY the information in the provided context.\n"
                "2. For every factual claim, cite the exact chunk tag provided in brackets, e.g. [Document.md_c000_1234].\n"
                "3. If the context does not contain the answer, state that verified documentation was not found.\n"
                "4. Do not make up facts."
            )
        },
        {
            "role": "user",
            "content": f"<verified_context>\n{context_text}\n</verified_context>\n\nQuestion: {query}"
        }
    ]
    
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt")
    
    print("Generating response...")
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=180, do_sample=False)
        
    generated = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    print("\n" + "="*50)
    print("MODEL GENERATED ANSWER:")
    print(generated)
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
