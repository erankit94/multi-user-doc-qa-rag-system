"""
main.py — FastAPI backend for the Multi-User Document Q&A System.

Endpoints:
  POST /login            → authenticate with email, get session token
  POST /logout           → invalidate session token
  GET  /me               → return current user info
  POST /query            → submit a question, get answer + sources
  POST /clear-history    → reset conversation for the session
  GET  /ingestion-status → list what's been ingested into ChromaDB
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from backend import auth, session as session_store
from backend.ingest import list_ingested
from backend.qa import answer

app = FastAPI(title="Multi-User Document Q&A API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _require_user(x_session_token: Optional[str] = Header(None)):
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Missing X-Session-Token header")
    user = auth.get_user(x_session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return user, x_session_token


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/login")
def login(req: LoginRequest):
    result = auth.login(req.email)
    if not result:
        raise HTTPException(
            status_code=403,
            detail=f"Unknown email '{req.email}'. Allowed users: {auth.list_users()}",
        )
    return result


@app.post("/logout")
def logout(x_session_token: Optional[str] = Header(None)):
    if x_session_token:
        auth.logout(x_session_token)
        session_store.clear_history(x_session_token)
    return {"message": "Logged out"}


@app.get("/me")
def me(x_session_token: Optional[str] = Header(None)):
    user, _ = _require_user(x_session_token)
    return user


@app.post("/query")
def query(req: QueryRequest, x_session_token: Optional[str] = Header(None)):
    user, token = _require_user(x_session_token)
    result = answer(
        query=req.question,
        token=token,
        allowed_companies=user["allowed_companies"],
        top_k=req.top_k,
    )
    return {
        "question": req.question,
        "answer":   result["answer"],
        "sources":  result["sources"],
        "user":     user["email"],
        "accessible_companies": user["allowed_companies"],
    }


@app.post("/clear-history")
def clear_history(x_session_token: Optional[str] = Header(None)):
    _, token = _require_user(x_session_token)
    session_store.clear_history(token)
    return {"message": "Conversation history cleared"}


@app.get("/ingestion-status")
def ingestion_status(x_session_token: Optional[str] = Header(None)):
    user, _ = _require_user(x_session_token)
    return {"ingested": list_ingested(user["allowed_companies"])}


@app.get("/health")
def health():
    return {"status": "ok"}
