import os
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from app.core.vector_store import HybridVectorStore
from app.core.llm import LocalLLMClient
from app.agent.router import AgentRouter

def test():
    store = HybridVectorStore()
    llm = LocalLLMClient()
    router = AgentRouter(store, llm)
    
    print("=== Testing 1: In-Scope Grounded Query ===")
    res1 = router.process_query("What are the password requirements and session timeout rules?")
    print("Response:\n", res1["response"])
    print("Citations:", res1.get("citations"))
    print("Steps:", res1.get("steps"))
    print("\n" + "="*50 + "\n")
    
    print("=== Testing 2: Out-of-Scope Query (Refusal) ===")
    res2 = router.process_query("Who won the 2026 FIFA World Cup in soccer?")
    print("Response:\n", res2["response"])
    print("Steps:", res2.get("steps"))
    print("\n" + "="*50 + "\n")

    print("=== Testing 3: Agent Mutating Tool Proposal (Permission Ticket) ===")
    res3 = router.process_query("Create a summary report about Local AI Governance")
    print("Response:\n", res3["response"])
    print("Action Proposed:", res3.get("action_proposed"))
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    test()
