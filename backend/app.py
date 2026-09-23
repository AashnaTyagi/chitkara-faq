"""
FastAPI backend for the Chitkara University Punjab helpdesk.

  POST /api/chat     {"message": "...", "conversation_id": "..." | null}
  GET  /api/health   liveness check (used by Render)
  GET  /             serves the frontend from ../frontend

Run locally (from the backend folder):
    uvicorn app:app --reload
"""
import logging
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from typing import Optional

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chat_engine import ChitkaraAssistant

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chitkara.api")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SHOW_TRACE = os.getenv("SHOW_AGENT_TRACE", "true").strip().lower() == "true"
RATE_LIMIT = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "15"))
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
CONV_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,200}$")

app = FastAPI(title="UniAssist-Ai API", version="1.0.0")

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

# ---------- assistant (created on first use, so /api/health works even if Azure config is wrong)
_assistant: Optional[ChitkaraAssistant] = None
_assistant_lock = Lock()


def get_assistant() -> ChitkaraAssistant:
    global _assistant
    if _assistant is None:
        with _assistant_lock:
            if _assistant is None:
                _assistant = ChitkaraAssistant()
    return _assistant


# ---------- simple in-memory rate limit per visitor IP
_hits: dict = defaultdict(deque)
_hits_lock = Lock()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def allow_request(ip: str) -> bool:
    now = time.monotonic()
    with _hits_lock:
        window = _hits[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= RATE_LIMIT:
            return False
        window.append(now)
        return True


# ---------- API models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(default=None, max_length=200)


class KBCall(BaseModel):
    question: str
    answer: str


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    kb_calls: list[KBCall] = []


# ---------- routes
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    # Sync def: FastAPI runs it in a worker thread, so the blocking Azure SDK calls are fine.
    if not allow_request(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many messages in a short time. Wait a minute and try again.")

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Type a question first.")

    conversation_id = body.conversation_id if body.conversation_id and CONV_ID_RE.match(body.conversation_id) else None

    try:
        bot = get_assistant()
        if not conversation_id:
            conversation_id = bot.new_conversation()
        try:
            result = bot.ask(conversation_id, message)
        except openai.NotFoundError:
            # Conversation expired or was deleted: start a new one and retry once.
            conversation_id = bot.new_conversation()
            result = bot.ask(conversation_id, message)
    except Exception:
        log.exception("Chat request failed")
        raise HTTPException(status_code=502, detail="UniAssist-Ai couldn't get an answer right now. Try again in a moment.")

    return ChatResponse(
        conversation_id=conversation_id,
        answer=result["answer"],
        kb_calls=result["kb_calls"] if SHOW_TRACE else [],
    )


# ---------- frontend (mounted last so /api routes take priority)
# On Vercel the frontend is served as static files directly (see vercel.json),
# so this mount only runs for local `uvicorn` dev and for platforms like Render.
if not os.getenv("VERCEL") and FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
elif not os.getenv("VERCEL"):
    log.warning("Frontend folder not found at %s; serving API only.", FRONTEND_DIR)
