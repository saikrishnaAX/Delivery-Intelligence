import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.database import engine, Base, SessionLocal
from app.api.routes import router
from app.api.org_routes import org_router
from app.seed.mock_data import seed_database
from app.migrate import migrate
from app.services.auto_sync import auto_sync_loop
from app.services.asana_webhooks import ensure_asana_webhooks

settings = get_settings()
_auto_sync_task: asyncio.Task | None = None
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _auto_sync_task, settings
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    migrate()
    db = SessionLocal()
    try:
        from app.services.issue_intelligence import recover_orphaned_jobs
        n = recover_orphaned_jobs(db)
        if n:
            logger.info("Recovered %s orphaned issue-intelligence job(s) from prior run", n)
    finally:
        db.close()
    # Only seed demo data when mock mode is on AND Asana is not configured for live sync
    if settings.use_mock_data and not settings.asana_configured:
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
    if settings.auto_sync_enabled and settings.asana_configured:
        _auto_sync_task = asyncio.create_task(auto_sync_loop())
        if settings.asana_webhook_target_url.strip():
            try:
                webhook_result = await ensure_asana_webhooks()
                logger.info("Asana webhooks: %s", webhook_result)
            except Exception:
                logger.exception("Asana webhook registration failed")
    yield
    if _auto_sync_task:
        _auto_sync_task.cancel()
        try:
            await _auto_sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Autorox AI Delivery Intelligence",
    description="Enterprise AI-powered delivery analytics dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)
app.include_router(org_router, prefix=settings.api_prefix)


@app.get("/", response_class=HTMLResponse)
def root():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Autorox API</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 48px auto; padding: 0 16px; line-height: 1.5; }}
    h1 {{ font-size: 1.25rem; }}
    a {{ color: #2563eb; }}
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Autorox AI Delivery Intelligence — API</h1>
  <p>This port is the <strong>backend API</strong>, not the dashboard UI.</p>
  <ul>
    <li><a href="/health">Health check</a> — <code>/health</code></li>
    <li><a href="/docs">API docs</a> — <code>/docs</code></li>
    <li><a href="{settings.api_prefix}/sprint-sheet">Sprint sheet API</a> (requires query params)</li>
  </ul>
  <p>Open the app UI at <a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a></p>
  <p><small>Start backend: <code>scripts\\run-backend.cmd</code> or <code>python -m uvicorn app.main:app --host 127.0.0.1 --port 8003</code> from <code>backend</code></small></p>
</body>
</html>"""


@app.get("/health")
def health():
    return {"status": "healthy", "service": "delivery-intelligence-api"}
