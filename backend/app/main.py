"""LangStudy API. Run: uvicorn app.main:app --reload --port 8000

Routes live in app/routers/ (one module per area); this file wires them up,
runs startup tasks and serves the built frontend.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, jobs, maintenance
from .deps import current_user
from .languages import public_languages
from .routers import admin, auth, cards, courses, practice, sessions, speech


@asynccontextmanager
async def lifespan(_app: FastAPI):
    jobs.recover()
    maintenance.start()
    yield


db.init()  # migrations run on import so scripts and tests get the current schema too
app = FastAPI(title="LangStudy", version="0.3.0", lifespan=lifespan)

for r in (auth.router, admin.router, practice.router, sessions.router, cards.router, speech.router, courses.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def api_health():
    return {"ok": True}


@app.get("/api/config", tags=["practice"])
def get_config(_: dict = Depends(current_user)):
    return {
        "languages": public_languages(),
        "demoMode": config.demo_mode(),
        "model": None if config.demo_mode() else config.model_label(),
        "sttServer": config.stt_server_enabled(),
        "ttsServer": config.TTS_ENABLED,
        "pronounceServer": config.gateway_enabled(),
    }


# Serve the built frontend (frontend/dist) when present, so one process is enough.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def frontend_file(path: str) -> Path:
    """File under DIST for a URL path; anything else (incl. ../ escapes) gets index.html (history-mode routes)."""
    root = DIST.resolve()
    index = root / "index.html"
    if not path:
        return index
    target = (root / path).resolve()
    if target.is_file() and target.is_relative_to(root):
        return target
    return index


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        return FileResponse(frontend_file(path))
