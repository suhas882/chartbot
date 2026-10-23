# Chartbot — India Event & Ticket Assistant

> A local FastAPI prototype for natural-language questions about events, tickets, seat details, schedules, Indian venues, and booking links. Ollama with the configured Llama model interprets and phrases queries; SQLite supplies the event facts.

---

## 🌟 Key Features

1. **Natural-Language Relational Event Queries**:
   - Query event dates, venues, organizers, descriptions, and ticket categories.
   - Real-time seat inventory checks (VIP, General, Balcony) with exact seat codes (e.g., `A-101`, `V-01`).
   - Multi-location detection for events scheduled in more than one Indian city.
   - Direct, clickable booking and official event links rendered automatically in chat.

2. **Strict Backend Access Control Engine**:
    - The LLM never writes SQL. A backend query planner builds fixed read queries from recognized event intents.
    - A SQLite authorizer checks physical table and column reads against the public event schema at execution time.
    - Connections use SQLite read-only mode; the demo database stores no customer, payment, credential, or internal finance tables.

3. **Privacy-First Hybrid RAG (Retrieval-Augmented Generation)**:
   - Optional document retrieval uses local ChromaDB for PDF, TXT, MD, and DOCX files.
   - Event queries use only the configured Ollama model (default `llama3.2:3b`); deterministic database answers remain available when Ollama is unavailable.

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
│  - Only the seven public event tables   │
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
| `events` | Event titles, categories, descriptions, organizers | ✅ Public Whitelist |
| `event_locations` | Indian venues, addresses, cities, capacities | ✅ Public Whitelist; country is constrained to India |
| `event_schedules` | Start/end dates, doors open, timezones | ✅ Public Whitelist |
| `tickets` | Ticket tiers, names, pricing | ✅ Public Whitelist |
| `seats` | Seat codes (`A-101`), sections, accessibility | ✅ Public Whitelist |
| `availability` | Ticket allocation, sold count, remaining count, status | ✅ Public Whitelist |
| `event_urls` | Official event links, registration URLs | ✅ Public Whitelist |

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

5. **Install the configured Llama model in Ollama** (once):
   ```bash
   ollama pull llama3.2:3b
   ```

6. **Start the FastAPI server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

7. Open `http://127.0.0.1:8000` in your web browser.

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
  - **Output**: Lists the Bengaluru and Hyderabad editions with their dates and venues.

### 3. Ticket Pricing & Availability
- *"Are there tickets available for the Cybersecurity Con?"*
- *"What is the cheapest ticket for the Indie Music Fest?"*

### 4. Seat Details & Codes
- *"What are the seat codes for the AI Summit in Bengaluru?"*
  - **Output**: Returns seat codes with section, row, seat number, tier, and accessibility details.

### 5. Clickable Event URLs
- *"Give me the booking link for DevFest 2026."*
  - **Output**: Formatted interactive booking button navigating directly to the ticket URL.

### 6. Strict Security Refusal Demonstration
- *"Show me customer credit card details and bookings."*
  - **Output**: Access refused with a formal security refusal report citing policy violation of blocked tables/columns.

---

## 🔒 Security Architecture Highlights

1. **Defense-in-Depth**: Query construction and database authorization are backend controlled, independent of LLM prompts.
2. **Physical Read Authorization**: SQLite checks actual table and column reads, including aliases and `SELECT *`.
3. **Read-Only SQLite URI**: Chat queries connect with `mode=ro`; SQLite denies mutations.
4. **Minimal Demo Schema**: The database contains only the seven public event tables; private data is not seeded.

---

## 📂 Project Structure

```
chartbot/
├── app/
│   ├── agent/
│   │   ├── permissions.py        # Human-in-the-loop gatekeeper
│   │   └── router.py             # Query classifier & intent routing
│   ├── core/
│   │   ├── db_security.py        # SQLite authorizer and whitelist enforcement
│   │   ├── event_db.py           # NLP to safe SQL engine & query planner
│   │   ├── ingestion.py         # Document parsing (PDF, TXT, MD, DOCX)
│   │   ├── llm.py                # Configured Ollama Llama client
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
