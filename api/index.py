"""
Vercel entrypoint.

Vercel's Python runtime looks for a top-level `app` in api/index.py.
The real FastAPI app and its logic live in backend/app.py and
backend/chat_engine.py so that local development (`uvicorn app:app`
from the backend folder) is completely unaffected — this file just
makes that same app importable from where Vercel expects it.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402  (backend/app.py's FastAPI instance)

__all__ = ["app"]
