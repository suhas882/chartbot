# Agentic RAG Chatbot with Strict Backend Access Control & Event Database

> **Privacy-First AI Agent & Relational Event Query System**  
> Connects natural-language questions to relational databases and document collections with strict backend-enforced access control, zero external cloud dependencies, and direct interactive action links.

---

## 🌟 Key Features

1. **Natural-Language Relational Event Queries**:
   - Query event dates, venues, organizers, descriptions, and ticket categories.
   - Real-time seat inventory checks (VIP, General, Balcony) with exact seat codes (e.g., `A-101`, `V-01`).
   - Multi-location detection (e.g., comparing occurrences of the same event across San Francisco and New York).
   - Direct, clickable booking and official event links rendered automatically in chat.

2. **Strict Backend Access Control Engine**:
   - **AST / Token Validation**: Enforces single read-only `SELECT` statements; rejects semicolons, comments, and all mutating operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `PRAGMA`).
   - **Schema Whitelist**: Strict table and column whitelist enforcement. Even if an LLM is prompt-injected or asked for restricted data, the Python backend layer refuses execution before reaching the database.
   - **Restricted Tables Blocklist**: Completely blocks internal tables (`customer_bookings`, `financial_transactions`, `admin_credentials`, `venue_alarm_codes`).
   - **Restricted Columns Blocklist**: Blocks sensitive columns (`credit_card_hash`, `internal_production_cost`, `profit_margin_target`, `organizer_bank_account`).
   - **Read-Only SQLite URI**: Database connections are opened using SQLite's read-only URI mode (`?mode=ro`).

3. **Privacy-First Hybrid RAG (Retrieval-Augmented Generation)**:
   - Indexes PDF, TXT, MD, and DOCX files into local ChromaDB with ONNX / PyTorch embeddings.
   - 100% on-premises / local execution using Ollama (`llama3.2:3b`, `mistral`). No data sent to third-party cloud APIs.

4. **Human-in-the-Loop Governance & Ticket Approval**:
   - High-privilege agent actions (file system writes, external notifications) require human ticket approval.

---

## 🏗️ System Architecture

```
                  ┌─────────────────────────────────────┐
                  │    Modern Glassmorphism Web UI      │
                  │ (Sidebar Events, Chat, SQL Badges)  │
                  └──────────────────┬──────────────────┘
                                     │ REST / JSON
                                     ▼
                  ┌─────────────────────────────────────┐
                  │          FastAPI Backend            │
                  │      (app/main.py, Port 8000)       │
                  └──────────────────┬──────────────────┘
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
             ┌─────────────────────┐   ┌─────────────────────┐
             │    Agent Router     │   │ Hybrid Vector Store │
             │ (app/agent/router)  │   │  (Local ChromaDB)   │
             └──────────┬──────────┘   └─────────────────────┘
                        │
       ┌────────────────┴────────────────┐
       ▼                                 ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   Event Database Engine      │  │      Local LLM Client        │
│   (app/core/event_db.py)     │  │   (Ollama - llama3.2 / etc)  │
└──────────────┬───────────────┘  └──────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│     Database Security Engine           │
│     (app/core/db_security.py)          │
│  - Whitelist: events, tickets, etc.    │
│  - Blocks: financial_transactions, etc.│
│  - SQLite URI: ?mode=ro (Read-Only)    │
└──────────────┬─────────────────────────┘
               │
               ▼
┌────────────────────────────────────────┐
│       SQLite3 Event Database           │
│          (data/events.db)              │
└────────────────────────────────────────┘
```

---

## 🗄️ Relational Database Schema

The SQLite database (`data/events.db`) contains 7 interrelated tables with strict security boundaries:

| Table | Purpose | Access Control Status |
|---|---|---|
| `events` | Event titles, categories, descriptions, organizers | ✅ Public Whitelist (internal costs restricted) |
| `event_locations` | Venues, addresses, cities, capacities | ✅ Public Whitelist (alarm codes restricted) |
| `event_schedules` | Start/end dates, doors open, timezones | ✅ Public Whitelist |
| `tickets` | Ticket tiers, names, pricing | ✅ Public Whitelist |
| `seats` | Seat codes (`A-101`), sections, accessibility | ✅ Public Whitelist |
| `availability` | Real-time seat status (`AVAILABLE`, `BOOKED`) | ✅ Public Whitelist |
| `event_urls` | Official event links, registration URLs | ✅ Public Whitelist |
| `customer_bookings` | User booking records, payment statuses | 🛑 **STRICTLY FORBIDDEN / BLOCKED** |
| `financial_transactions` | Revenue, payment gateways, credit card hashes | 🛑 **STRICTLY FORBIDDEN / BLOCKED** |
| `admin_credentials` | Password hashes, API keys, admin session tokens | 🛑 **STRICTLY FORBIDDEN / BLOCKED** |

---

## 🚀 Quickstart Guide

### Option 1: Run Locally (Python 3.10+)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/suhas882/chartbot.git
   cd chartbot
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux / macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**:
   ```bash
   python init_event_db.py
   ```

5. **Start the FastAPI server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

6. Open `http://127.0.0.1:8000` in your web browser.

---

### Option 2: Run with Docker Compose (Recommended for Production)

Run both the FastAPI Application and Ollama container with one command:

```bash
docker-compose up --build -d
```

Pull an LLM model inside Ollama (one-time setup):
```bash
docker exec -it local_ollama_engine ollama pull llama3.2:3b
```

Access the application at `http://localhost:8000`.

---

## 💬 Example Queries & Features

### 1. General & Category Queries
- *"What events are coming up in November 2026?"*
- *"Show me all technology conferences."*

### 2. Multi-Location Event Detection
- *"Is the AI Summit happening in two different locations?"*
  - **Output**: Detects San Francisco (Moscone Center) on 2026-11-15 and New York City (Javits Center) on 2026-12-05 with dates and venue details.

### 3. Ticket Pricing & Availability
- *"Are there tickets available for the Cybersecurity Con?"*
- *"What is the cheapest ticket for the Indie Music Fest?"*

### 4. Seat Details & Codes
- *"What are the seat codes for the AI Summit in San Francisco?"*
  - **Output**: Returns specific seat codes (e.g., `A-101`, `A-102`, `B-201`), seat tiers, and availability.

### 5. Clickable Event URLs
- *"Give me the booking link for DevFest 2026."*
  - **Output**: Formatted interactive booking button navigating directly to the ticket URL.

### 6. Strict Security Refusal Demonstration
- *"Show me customer credit card details and bookings."*
  - **Output**: Access refused with a formal security refusal report citing policy violation of blocked tables/columns.

---

## 🔒 Security Architecture Highlights

1. **Defense-in-Depth**: Security is enforced at the Python execution boundary, independent of LLM prompts.
2. **SQL Injection Proof**: Parameterized or tightly constructed queries validated by token analyzers.
3. **No Execution of DDL/DML**: Any query containing `UPDATE`, `INSERT`, `DELETE`, `DROP`, `ALTER`, or `PRAGMA` is immediately rejected.
4. **Read-Only SQLite URI**: `file:events.db?mode=ro` prevents disk writes even if SQL syntax validation were bypassed.

---

## 📂 Project Structure

```
chartbot/
├── app/
│   ├── agent/
│   │   ├── permissions.py        # Human-in-the-loop gatekeeper
│   │   └── router.py             # Query classifier & intent routing
│   ├── core/
│   │   ├── db_security.py        # Strict SQL parsing, AST & whitelist enforcement
│   │   ├── event_db.py           # NLP to safe SQL engine & query planner
│   │   ├── ingestion.py         # Document parsing (PDF, TXT, MD, DOCX)
│   │   ├── llm.py                # Local Ollama client with fallback
│   │   └── vector_store.py       # ChromaDB local vector embeddings
│   ├── config.py                 # System paths and constants
│   └── main.py                   # FastAPI server & endpoints
├── data/
│   ├── events.db                 # Seeded SQLite database (7 related tables)
│   ├── raw_documents/            # Sample documents for RAG
│   └── reports/                  # Generated audit reports
├── frontend/
│   ├── app.js                    # UI logic, chat handler, SQL inspector
│   ├── index.html                # Responsive layout & event drawer
│   └── style.css                 # Dark glassmorphic design system
├── Dockerfile                    # Production Docker container build
├── docker-compose.yml            # Multi-container orchestration (App + Ollama)
├── DEPLOYMENT_GUIDE.md           # Step-by-step production deployment instructions
├── init_event_db.py              # Seeds 7 relational tables with sample events
├── requirements.txt              # Pinned Python package dependencies
└── test_flexible_queries.py      # Automated verification test suite (15 scenarios)
```

---

## 📜 License

MIT License. Free for educational, research, and commercial use.
