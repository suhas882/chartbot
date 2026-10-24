import re
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Generator
from app.core.privacy import PIIScrubber
from app.core.llm import LocalLLMClient
from app.core.vector_store import HybridVectorStore
from app.agent.registry import ToolRegistry
from app.agent.permissions import gatekeeper, PermissionTicket
from app.agent.grader import EvidenceGrader
from app.core.event_db import EventDatabaseEngine

SYSTEM_RAG_PROMPT = """You are a secure, privacy-first local enterprise knowledge assistant.
You strictly answer user questions based ONLY on the verified local evidence provided in <verified_context>.
Rules:
1. Every factual statement must cite its exact source chunk tag, e.g. [Filename.md#chunk_0].
2. Do not use outside knowledge or make ungrounded claims.
3. If the provided context does not contain enough information to answer the question, clearly state:
   "I do not possess verified documentation regarding this topic in my local knowledge base. Please upload relevant files or ask a question scoped to your indexed documents."
4. Maintain a professional, concise, and structured tone.
"""

class AgentRouter:
    """
    State router and pipeline orchestrator coordinating query classification,
    backend database access control, hybrid document retrieval, evidence grading,
    tool handling, and grounded response generation.
    """
    def __init__(self, vector_store: HybridVectorStore, llm_client: LocalLLMClient):
        self.vector_store = vector_store
        self.llm = llm_client
        self.event_db = EventDatabaseEngine(llm_client=llm_client)
        # Keep only server-derived event context. Client supplied history is never trusted.
        self._conversation_contexts = OrderedDict()

    def clear_conversation(self, conversation_id: str) -> None:
        self._conversation_contexts.pop(conversation_id, None)

    @staticmethod
    def _is_follow_up(query: str) -> bool:
        return bool(re.match(
            r"^\s*(?:(?:and|also)\b|(?:what|how)\s+about\b|"
            r"(?:what|which|where|when|how\s+many|how\s+much)\b|"
            r"(?:show|tell|give|check)\s+(?:me\s+)?(?:its|their|the|those|that|these|them)\b)",
            query,
            re.IGNORECASE,
        ))

    def process_conversation_query(self, user_query: str, conversation_id: str) -> Dict[str, Any]:
        context = self._conversation_contexts.get(conversation_id, {})
        event_name = context.get("event_name")
        query_for_router = user_query
        if event_name and self._is_follow_up(user_query):
            # Do not override an explicitly named event in a follow-up.
            known_event = self.event_db.find_event_name(user_query)
            if not known_event:
                query_for_router = f"{user_query} for {event_name}"

        result = self.process_query(query_for_router)
        records = result.get("records") or []
        names = {str(row.get("event_name") or row.get("name") or "").strip() for row in records}
        names.discard("")
        is_event_query = any(str(table).lower() == "events" for table in result.get("tables_accessed", []))
        if is_event_query and len(names) == 1:
            context = {"event_name": next(iter(names))}
            self._conversation_contexts[conversation_id] = context
            self._conversation_contexts.move_to_end(conversation_id)
            while len(self._conversation_contexts) > 1000:
                self._conversation_contexts.popitem(last=False)
        elif is_event_query and not self._is_follow_up(user_query):
            # A new broad or ambiguous event question must not inherit a stale event.
            self._conversation_contexts.pop(conversation_id, None)
        return result

    def classify_intent(self, query: str) -> str:
        q_lower = query.strip().lower()

        # Catalog-backed event-name matching lets natural titles route to SQL
        # even when they contain none of the generic event keywords below.
        if self.event_db.find_event_name(query):
            return "EVENT_DB_QUERY"

        # Greetings & identity
        if q_lower in ["hi", "hello", "hey", "greetings", "help", "who are you", "what can you do"]:
            return "CONVERSATIONAL"

        # Mutating tool: Purge document
        if any(trigger in q_lower for trigger in ["delete document", "purge document", "remove document", "delete file", "purge file", "remove file"]):
            return "PURGE_DOCUMENT"

        # Mutating tool: Create summary report
        if any(trigger in q_lower for trigger in ["create report", "generate report", "make report", "save report", "summary report", "create summary"]):
            return "CREATE_REPORT"

        # Read-only tool: List documents
        if any(trigger in q_lower for trigger in ["list documents", "show documents", "available documents", "what documents", "indexed files", "show files"]):
            return "LIST_DOCUMENTS"

        # Event database queries & security access checks
        event_triggers = [
            # Core domain terms
            "ticket", "tickets", "seat", "seats", "venue", "venues", "location", "locations",
            "event", "events", "summit", "festival", "expo", "gala", "symphony", "concert",
            "culinary", "wine", "jazz", "music", "orchestra", "philharmonic", "chef",
            "ai summit", "tech summit", "cybersecurity", "cyber", "cloud defense", "conference",
            # Query intents
            "when and where", "where is", "when is", "what time", "schedule", "timing", "doors open",
            "available", "availability", "booking", "book", "reserve", "register", "registration",
            "booking link", "event link", "url", "urls", "link", "links", "website",
            "price", "prices", "cost", "how much", "cheap", "cheapest", "tier", "pass", "passes",
            "sold out", "accessible", "wheelchair", "row", "section",
            "organizer", "who is organizing", "who organizes", "capacity", "attend",
            "different locations", "two locations", "multiple locations", "two cities",
            # Indian cities & venues
            "bengaluru", "bangalore", "hyderabad", "mumbai", "delhi", "chennai", "goa",
            "noida", "panaji", "madras", "bombay",
            "biec", "hitex", "jio world", "music academy", "kala academy",
            "november", "december", "india",
            # Security access test triggers
            "credit card", "profit margin", "production cost", "customer", "admin password",
            "cvv", "card number", "secret key"
        ]
        if any(trigger in q_lower for trigger in event_triggers):
            return "EVENT_DB_QUERY"

        # Default knowledge inquiry
        return "RAG_QUERY"

    def handle_conversational(self) -> Dict[str, Any]:
        docs = self.vector_store.list_documents()
        doc_count = len(docs)
        text = (
            "Hello! I am your privacy-first AI Assistant equipped with **Direct Relational Database Access** "
            "and **Grounded Document RAG**.\n\n"
            "**Key Capabilities:**\n"
            "• **Live Event & Ticket Queries**: Ask about ticket availability, seat codes/details, venue dates, multi-location events, and get clickable booking URLs.\n"
            "• **Strict Backend Access Control**: Zero-trust table and column whitelisting enforced at the backend engine to prevent unauthorized access to sensitive financials or customer PII.\n"
            "• **Document RAG (ChromaDB + BM25)**: Query internal policies, security frameworks, or uploaded enterprise files.\n"
            "• **100% Local Inference**: Zero cloud telemetry or data leakage.\n\n"
            f"Currently, live events in **India** are indexed in the relational database, and **{doc_count} document(s)** are in the local vector store. "
            "How can I assist you today?"
        )
        return {
            "intent": "CONVERSATIONAL",
            "response": text,
            "citations": [],
            "action_proposed": None,
            "steps": ["Query scanned", "Identified general greeting", "Returned local capability briefing"]
        }

    def handle_list_documents(self) -> Dict[str, Any]:
        result = ToolRegistry.execute_read_only("list_available_documents", {}, self.vector_store)
        docs = result.get("documents", [])
        if not docs:
            text = "There are currently no documents indexed in your local knowledge base. Please upload PDF, TXT, MD, or DOCX files to get started."
        else:
            text = f"**Currently Indexed Local Documents ({len(docs)}):**\n\n"
            for d in docs:
                text += f"• **{d['filename']}** — {d.get('indexed_chunks', 0)} indexed chunks\n"
        return {
            "intent": "LIST_DOCUMENTS",
            "response": text,
            "citations": [],
            "action_proposed": None,
            "steps": ["Scanned query", "Executed read-only tool 'list_available_documents'"]
        }

    def handle_create_report_request(self, query: str) -> Dict[str, Any]:
        # Extract topic or filename if mentioned
        topic_match = re.search(r"(?:about|for|on|titled)\s+([\"']?)([^\"'\n\.,]+)\1", query, re.IGNORECASE)
        topic = topic_match.group(2).strip() if topic_match else "Executive Knowledge Summary"
        safe_filename = re.sub(r"[^\w\-]", "_", topic.lower())[:30] + ".md"

        # Retrieve knowledge relevant to the topic
        retrieved = self.vector_store.hybrid_search(topic, top_k=5)
        graded, has_evidence = EvidenceGrader.grade_retrieval(topic, retrieved)

        if has_evidence:
            content = f"## 1. Executive Overview\n\n"
            content += f"This report provides an evidence-grounded summary regarding **{topic}**, consolidated from internal documentation.\n\n"
            content += f"## 2. Key Findings & Core Policies\n\n"
            for i, chunk in enumerate(graded[:3]):
                cid = chunk["chunk_id"]
                src = chunk["metadata"].get("source", "Document")
                raw_body = chunk["content"]
                # Clean headers and OCR line breaks
                clean_body = re.sub(r'CONFIDENTIAL & PROPRIETARY.*?(?=Page|\n|$)', '', raw_body)
                clean_body = re.sub(r'Page \d+ of \d+', '', clean_body)
                clean_body = re.sub(r'\s+', ' ', clean_body).strip()
                # Split into key sentences
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_body) if len(s.strip()) > 20]
                content += f"### Finding {i+1}: {src} `[{cid}]`\n\n"
                for s in sentences[:4]:
                    content += f"• {s}\n"
                content += "\n"
            content += "## 3. Governance & Verification Notice\n\n"
            content += "All assertions in this document are strictly grounded in verified local vector and lexical chunks. No external cloud endpoints were queried.\n"
        else:
            content = f"## Report: {topic}\n\nNo specific local documentation found for this topic at time of generation.\n"

        args = {
            "topic": topic,
            "filename": safe_filename,
            "content": content
        }

        # Create ticket requiring HITL approval
        ticket = gatekeeper.create_ticket(
            tool_name="create_summary_report",
            args=args,
            description=f"Generate and write local markdown report '{safe_filename}' based on retrieved evidence.",
            risk_level="MEDIUM"
        )

        response_text = (
            f"I have prepared the draft for **{topic}** and created a permission request.\n\n"
            f"**Proposed Mutating Action:** `create_summary_report`\n"
            f"• Target File: `data/reports/{safe_filename}`\n"
            f"• Risk Level: **{ticket.risk_level}**\n\n"
            "Please review and approve this action in the Permission Inspector to execute."
        )

        return {
            "intent": "CREATE_REPORT",
            "response": response_text,
            "citations": [c["chunk_id"] for c in graded],
            "action_proposed": ticket.dict(),
            "steps": ["Scanned query", "Extracted topic", "Retrieved evidence", "Drafted report", "Created permission ticket"]
        }

    def handle_purge_document_request(self, query: str) -> Dict[str, Any]:
        # Extract filename
        docs = self.vector_store.list_documents()
        doc_names = [d["filename"] for d in docs]

        target_file = None
        for name in doc_names:
            if name.lower() in query.lower():
                target_file = name
                break

        if not target_file:
            # Fallback regex search for filenames like document.pdf, report.md
            match = re.search(r"[\w\-]+\.(?:pdf|txt|md|docx)", query, re.IGNORECASE)
            if match:
                target_file = match.group(0)

        if not target_file:
            return {
                "intent": "PURGE_DOCUMENT",
                "response": "Please specify the exact filename of the document you would like to purge (e.g. 'delete document Enterprise_Policy.md').",
                "citations": [],
                "action_proposed": None,
                "steps": ["Scanned query", "Could not locate target filename in query"]
            }

        ticket = gatekeeper.create_ticket(
            tool_name="purge_document_record",
            args={"filename": target_file},
            description=f"Permanently remove file '{target_file}' from disk and purge all its vector embeddings from ChromaDB.",
            risk_level="HIGH"
        )

        response_text = (
            f"I have initiated a Right-to-be-Forgotten purge request for **{target_file}**.\n\n"
            f"**Proposed Mutating Action:** `purge_document_record`\n"
            f"• Target File: `{target_file}`\n"
            f"• Risk Level: **HIGH (Destructive)**\n\n"
            "Because this will delete disk files and vector representations, your explicit authorization is required. Please approve or reject below."
        )

        return {
            "intent": "PURGE_DOCUMENT",
            "response": response_text,
            "citations": [],
            "action_proposed": ticket.dict(),
            "steps": ["Scanned query", "Identified target file", "Created HIGH-risk permission ticket"]
        }

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Processes query synchronously through full Agentic RAG pipeline."""
        intent = self.classify_intent(user_query)

        if intent == "CONVERSATIONAL":
            return self.handle_conversational()
        elif intent == "LIST_DOCUMENTS":
            return self.handle_list_documents()
        elif intent == "CREATE_REPORT":
            return self.handle_create_report_request(user_query)
        elif intent == "PURGE_DOCUMENT":
            return self.handle_purge_document_request(user_query)
        elif intent == "EVENT_DB_QUERY":
            return self.event_db.execute_natural_query(user_query)

        # RAG Query Pipeline
        # 1. PII Scrub
        clean_query, pii_detected = PIIScrubber.scrub(user_query)

        # 2. Hybrid Search (ChromaDB + BM25)
        raw_chunks = self.vector_store.hybrid_search(clean_query, top_k=5)

        # 3. Grade Evidence
        graded_chunks, has_evidence = EvidenceGrader.grade_retrieval(clean_query, raw_chunks)

        if not has_evidence:
            return {
                "intent": "RAG_QUERY",
                "response": EvidenceGrader.format_refusal(),
                "citations": [],
                "action_proposed": None,
                "steps": [
                    "Scrubbed query for PII",
                    "Performed Hybrid Search (Dense ChromaDB + Sparse BM25)",
                    "Evidence Grader: No chunks exceeded confidence threshold (0.55)",
                    "Triggered privacy refusal response"
                ]
            }

        # 4. Construct Verified Context Prompt
        context_blocks = []
        for c in graded_chunks:
            cid = c["chunk_id"]
            src = c["metadata"].get("source", "Document")
            context_blocks.append(f"[{cid}] (Source: {src}):\n{c['content']}")

        full_context = "\n\n".join(context_blocks)
        prompt = (
            f"<verified_context>\n{full_context}\n</verified_context>\n\n"
            f"Query: {clean_query}\n\n"
            f"Provide an accurate, evidence-grounded answer based strictly on the context above. "
            f"Cite each fact with its exact source chunk tag [Source#chunk_id]."
        )

        # 5. Local LLM Generation
        response_text = self.llm.generate(prompt, system_prompt=SYSTEM_RAG_PROMPT)

        # 6. Verify Grounding & Citations
        verification = EvidenceGrader.verify_citations(response_text, graded_chunks)

        return {
            "intent": "RAG_QUERY",
            "response": response_text,
            "citations": [c["chunk_id"] for c in graded_chunks],
            "verification": verification,
            "action_proposed": None,
            "steps": [
                f"Scrubbed PII ({len(pii_detected)} entities redacted)",
                f"Retrieved {len(raw_chunks)} candidate chunks via Hybrid RRF",
                f"Evidence Grader passed {len(graded_chunks)} relevant chunks",
                f"Generated answer via local {self.llm.model}",
                f"Citation check: {len(verification['verified_citations'])} verified references"
            ]
        }
