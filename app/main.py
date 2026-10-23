import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import (
    BASE_DIR, RAW_DOCS_DIR, CHROMA_DIR, REPORTS_DIR,
    DEFAULT_LLM_MODEL, EMBEDDING_MODEL_NAME, LOCAL_ONLY_MODE
)
from app.core.ingestion import DocumentIngestionEngine
from app.core.vector_store import HybridVectorStore
from app.core.llm import LocalLLMClient
from app.agent.permissions import gatekeeper
from app.agent.router import AgentRouter
from app.core.db_security import DatabaseSecurityEngine
from app.core.event_db import DB_PATH
from init_event_db import ensure_india_demo_database

ensure_india_demo_database()

# Initialize core services
vector_store = HybridVectorStore()
llm_client = LocalLLMClient()
router = AgentRouter(vector_store, llm_client)

app = FastAPI(
    title="Chartbot",
    description="Local India event assistant with live ticket, seat, schedule, venue, and event-link data.",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Request schemas
class ChatRequest(BaseModel):
    message: str

class ApprovalRequest(BaseModel):
    ticket_id: str
    action: str  # "approve" or "reject"

class CreateEventRequest(BaseModel):
    name: str
    category: str = "Technology"
    description: str = ""
    organizer: str = "Event Management"
    venue_name: str
    city: str
    state: str = ""
    address: str = ""
    event_date: str # YYYY-MM-DD
    start_time: str = "09:00 AM"
    end_time: str = "05:00 PM"
    doors_open: str = "08:00 AM"
    capacity: int = 5000
    ticket_tiers: Optional[List[Dict[str, Any]]] = None
    booking_url: Optional[str] = None
    official_url: Optional[str] = None
    seat_prefix: Optional[str] = None

@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    ollama_info = llm_client.check_ollama_status()
    docs = vector_store.list_documents()
    total_chunks = vector_store.collection.count()
    
    # Check relational DB stats
    events_count = 0
    if DB_PATH.exists():
        try:
            res = DatabaseSecurityEngine.execute_safe_query(DB_PATH, "SELECT COUNT(*) as cnt FROM events")
            events_count = res["data"][0]["cnt"] if res["data"] else 0
        except Exception:
            pass

    return {
        "status": "ONLINE",
        "local_only": LOCAL_ONLY_MODE,
        "llm_engine": {
            "target_model": DEFAULT_LLM_MODEL,
            "ollama_available": ollama_info["available"],
            "active_model": ollama_info["active_model"],
            "installed_models": ollama_info.get("installed_models", [])
        },
        "embeddings": {
            "model": EMBEDDING_MODEL_NAME,
            "provider": "ChromaDB ONNX / PyTorch (Local)",
            "total_chunks_indexed": total_chunks
        },
        "relational_db": {
            "engine": "SQLite3 (Read-Only Least Privilege URI)",
            "database_file": "data/events.db",
            "events_count": events_count,
            "whitelisted_tables": list(DatabaseSecurityEngine.ALLOWED_TABLES.keys()),
            "restricted_tables_blocked": list(DatabaseSecurityEngine.FORBIDDEN_TABLES),
            "security_policy": "STRICT_BACKEND_ACCESS_CONTROL_ENFORCED"
        },
        "indexed_documents_count": len(docs),
        "pending_agent_tickets": len(gatekeeper.list_pending())
    }

@app.get("/api/events")
def list_events() -> List[Dict[str, Any]]:
    """Returns public events from the relational database via safe whitelisted query."""
    if not DB_PATH.exists():
        return []
    res = DatabaseSecurityEngine.execute_safe_query(
        DB_PATH,
        """
        SELECT e.event_id, e.name, e.category, e.description, e.organizer,
               l.city, l.state, l.country, l.venue_name, s.event_date
        FROM events e
        JOIN event_schedules s ON e.event_id = s.event_id
        JOIN event_locations l ON s.location_id = l.location_id
        ORDER BY e.event_id, s.event_date
        """
    )
    return res.get("data", [])

@app.get("/api/seats-page")
def get_seats_page(event_id: int, schedule_id: int) -> Dict[str, Any]:
    """Return public event, ticket availability, and seat details for the local demo booking view."""
    if event_id <= 0 or schedule_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid event or schedule.")
    event = DatabaseSecurityEngine.execute_safe_query(
        DB_PATH,
        f"""SELECT e.event_id, e.name, e.category, s.schedule_id, s.event_date,
                   s.start_time, s.end_time, l.venue_name, l.city, l.state
            FROM events e
            JOIN event_schedules s ON e.event_id = s.event_id
            JOIN event_locations l ON s.location_id = l.location_id
            WHERE e.event_id = {event_id} AND s.schedule_id = {schedule_id}
            LIMIT 1"""
    ).get("data", [])
    if not event:
        raise HTTPException(status_code=404, detail="Event session not found.")
    tickets = DatabaseSecurityEngine.execute_safe_query(
        DB_PATH,
        f"""SELECT t.ticket_id, t.tier_name, t.price, t.currency, t.perks,
                   a.tickets_available, a.status
            FROM tickets t
            JOIN availability a ON t.ticket_id = a.ticket_id
            WHERE t.schedule_id = {schedule_id}
            ORDER BY t.price LIMIT 25"""
    ).get("data", [])
    seats = DatabaseSecurityEngine.execute_safe_query(
        DB_PATH,
        f"""SELECT seat_code, section, row_num, seat_number, tier_name, is_accessible
            FROM seats WHERE schedule_id = {schedule_id}
            ORDER BY section, seat_number LIMIT 250"""
    ).get("data", [])
    return {"event": event[0], "tickets": tickets, "seats": seats}
@app.get("/api/seats")
def list_seats() -> List[Dict[str, Any]]:
    """Returns public seat codes for the demo events (whitelisted columns only)."""
    if not DB_PATH.exists():
        return []
    res = DatabaseSecurityEngine.execute_safe_query(
        DB_PATH,
        """
        SELECT e.name AS event_name, l.city, l.venue_name, st.seat_code, st.section,
               st.row_num, st.seat_number, st.tier_name, st.is_accessible
        FROM seats st
        JOIN event_schedules s ON st.schedule_id = s.schedule_id
        JOIN events e ON s.event_id = e.event_id
        JOIN event_locations l ON st.location_id = l.location_id
        ORDER BY e.name, st.section, st.seat_number
         LIMIT 250
        """
    )
    return res.get("data", [])

@app.post("/api/events/create")
def create_event_endpoint(req: CreateEventRequest) -> Dict[str, Any]:
    """Administrative endpoint to register a new event across all 7 relational tables."""
    try:
        from add_event import add_new_event
        res = add_new_event(
            name=req.name,
            category=req.category,
            description=req.description,
            organizer=req.organizer,
            venue_name=req.venue_name,
            city=req.city,
            state=req.state,
            address=req.address,
            event_date=req.event_date,
            start_time=req.start_time,
            end_time=req.end_time,
            doors_open=req.doors_open,
            capacity=req.capacity,
            ticket_tiers=req.ticket_tiers,
            booking_url=req.booking_url,
            official_url=req.official_url,
            seat_prefix=req.seat_prefix
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/database/schema")
def get_database_schema() -> Dict[str, Any]:
    """Provides backend security schema transparency: whitelisted vs restricted."""
    return {
        "whitelisted_tables": {tbl: sorted(list(cols)) for tbl, cols in DatabaseSecurityEngine.ALLOWED_TABLES.items()},
        "restricted_tables": sorted(list(DatabaseSecurityEngine.FORBIDDEN_TABLES)),
        "restricted_columns": sorted(list(DatabaseSecurityEngine.FORBIDDEN_COLUMNS)),
        "enforcement_layer": "SQLite Authorizer + Read-Only Connection + Backend Table/Column Whitelist"
    }

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest) -> Dict[str, Any]:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    result = router.process_query(request.message)
    return result

@app.get("/api/documents")
def list_documents() -> List[Dict[str, Any]]:
    return vector_store.list_documents()

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    supported_extensions = [".pdf", ".txt", ".md", ".docx"]
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in supported_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format '{file_ext}'. Allowed formats: {', '.join(supported_extensions)}"
        )

    # Save to RAW_DOCS_DIR
    target_path = RAW_DOCS_DIR / file.filename
    content_bytes = await file.read()
    with open(target_path, "wb") as f:
        f.write(content_bytes)

    # Ingest, scrub PII, chunk, and embed
    try:
        chunks = DocumentIngestionEngine.process_document(target_path)
        if not chunks:
            raise HTTPException(status_code=400, detail="No readable text extracted from document.")
            
        vector_store.add_chunks(chunks)
        return {
            "status": "SUCCESS",
            "filename": file.filename,
            "chunks_created": len(chunks),
            "message": f"Successfully indexed '{file.filename}' into local vector database."
        }
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.delete("/api/documents/{filename}")
def delete_document(filename: str) -> Dict[str, Any]:
    purged_chunks = vector_store.delete_document(filename)
    raw_path = RAW_DOCS_DIR / filename
    if raw_path.exists():
        raw_path.unlink()
    return {
        "status": "SUCCESS",
        "filename": filename,
        "purged_chunks": purged_chunks,
        "message": f"Purged all vector chunks and files for '{filename}'."
    }

@app.get("/api/agent/tickets")
def list_tickets() -> List[Dict[str, Any]]:
    return [t.dict() for t in gatekeeper.list_pending()]

@app.post("/api/agent/approve")
def handle_approval(request: ApprovalRequest) -> Dict[str, Any]:
    ticket = gatekeeper.get_ticket(request.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or expired.")

    if request.action == "approve":
        gatekeeper.approve_ticket(request.ticket_id)
        result = gatekeeper.execute_ticket(request.ticket_id, vector_store)
        return {
            "status": "SUCCESS",
            "action": "APPROVED",
            "ticket_id": request.ticket_id,
            "execution_result": result
        }
    elif request.action == "reject":
        gatekeeper.reject_ticket(request.ticket_id)
        return {
            "status": "SUCCESS",
            "action": "REJECTED",
            "ticket_id": request.ticket_id,
            "message": "Mutating action rejected by user."
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'.")

@app.get("/api/reports")
def list_reports() -> List[Dict[str, Any]]:
    reports = []
    if REPORTS_DIR.exists():
        for r in REPORTS_DIR.glob("*.md"):
            reports.append({
                "filename": r.name,
                "size_bytes": r.stat().st_size,
                "modified": r.stat().st_mtime
            })
    return reports

# Frontend static files mounting
FRONTEND_DIR = BASE_DIR / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/seats")
def serve_seats_page():
    """Serve the local demo ticket and seat details view."""
    return FileResponse(FRONTEND_DIR / "index.html")
@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Agentic RAG Chatbot API is operational."})
