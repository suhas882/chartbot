# Data Privacy and Local AI Governance Framework (GOV-AI-2026)

## 1. Local AI Deployment Mandate
1.1 In compliance with enterprise confidentiality policies, all conversational AI systems and agentic workflows must execute exclusively on local hardware infrastructure.
1.2 Transmission of customer proprietary data, source code, or internal documentation to external third-party cloud LLM APIs is strictly prohibited without explicit CISO written authorization.
1.3 Supported open-source foundation models for on-premise execution include Llama 3.2 (3B), Qwen 2.5 (3B), and Phi 3.5 Mini, quantized in GGUF 4-bit or 8-bit formats.

## 2. PII Sanitization and Data Minimization
2.1 All unstructured inputs must undergo automated Personally Identifiable Information (PII) scrubbing prior to vector embedding generation.
2.2 Detected email addresses, phone numbers, Social Security Numbers (SSNs), and API authentication tokens must be masked with standardized placeholder tags (e.g., [EMAIL_REDACTED], [API_KEY_REDACTED]).
2.3 Chunking window size is standardized at 512 tokens with a 50-token overlap to prevent cross-boundary context truncation.

## 3. Human-In-The-Loop (HITL) Permission Controls
3.1 Read-only operations such as semantic retrieval, document listing, and text synthesis may operate autonomously.
3.2 Any mutating or destructive agent capability—including persistent file creation, report export, document purging, or configuration updates—requires interactive Human-In-The-Loop (HITL) authorization via a signed permission ticket.
3.3 Permission tickets expire automatically after 300 seconds (5 minutes) if unacknowledged by an authorized administrator.

## 4. Right-to-be-Forgotten and Vector Purge
4.1 When a document is marked for deletion, the system must perform an instantaneous cascading purge.
4.2 All associated vector embeddings stored in the ChromaDB persistent collection and in-memory BM25 lexical indices must be deleted alongside the underlying file.
