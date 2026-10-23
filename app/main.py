import os
from pathlib import Path
from typing import Dict, Any, List
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

# Initialize core services
vector_store = HybridVectorStore()
llm_client = LocalLLMClient()
router = AgentRouter(vector_store, llm_client)

app = FastAPI(
    title="Privacy-First Agentic RAG Chatbot",
    description="Local RAG chatbot and permission-governed AI agent running open-source models with strict DB access control.",
    version="1.0.0"
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
        "SELECT event_id, name, category, description, organizer FROM events ORDER BY event_id"
    )
    return res.get("data", [])

@app.get("/api/database/schema")
def get_database_schema() -> Dict[str, Any]:
    """Provides backend security schema transparency: whitelisted vs restricted."""
    return {
        "whitelisted_tables": {tbl: sorted(list(cols)) for tbl, cols in DatabaseSecurityEngine.ALLOWED_TABLES.items()},
        "restricted_tables": sorted(list(DatabaseSecurityEngine.FORBIDDEN_TABLES)),
        "restricted_columns": sorted(list(DatabaseSecurityEngine.FORBIDDEN_COLUMNS)),
        "enforcement_layer": "Backend Python AST & Read-Only SQLite Engine"
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

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Agentic RAG Chatbot API is operational."})
