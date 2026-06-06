"""API package. Run with: uvicorn backend.api.app:app --host 0.0.0.0 --port 8000"""

from backend.api.app import app

__all__ = ["app"]
