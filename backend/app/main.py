import logging
import time
from functools import lru_cache
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()
from app.routers.ai import router as ai_router
from app.routers.notes import router as notes_router
from app.routers.sources import router as sources_router
from app.routers.documents import router as documents_router
from app.routers.quizzes import router as quizzes_router
from app.routers.auth import router as auth_router
from app.routers.ingestion import router as ingestion_router
from app.routers.routing import router as routing_router
from app.routers.step_through import router as step_through_router
from app.routers.learn import router as learn_router
from app.config import settings
from app.database import engine
import app.models  # noqa: F401 - register all SQLAlchemy metadata


app = FastAPI()
logger = logging.getLogger(__name__)
application_logger = logging.getLogger("app")
application_logger.setLevel(settings.log_level)
# Uvicorn deliberately configures its own loggers rather than the root logger.
# Reuse its error stream for application telemetry so INFO measurements are
# visible in the deployed process without adding another logging dependency.
server_handlers = logging.getLogger("uvicorn.error").handlers or logging.getLogger("uvicorn").handlers
if server_handlers and not application_logger.handlers:
    application_logger.handlers.extend(server_handlers)
    application_logger.propagate = False


@app.middleware("http")
async def record_request_telemetry(request, call_next):
    """Emit one bounded completion event for production latency analysis."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        route = request.scope.get("route")
        logger.error(
            "http_request_complete method=%s route=%s status=%s outcome=error exception_type=%s duration_ms=%.1f",
            request.method,
            getattr(route, "path", "unmatched"),
            500,
            type(exc).__name__,
            (time.perf_counter() - started) * 1000,
        )
        raise
    route = request.scope.get("route")
    logger.info(
        "http_request_complete method=%s route=%s status=%s outcome=%s exception_type=none duration_ms=%.1f",
        request.method,
        getattr(route, "path", "unmatched"),
        response.status_code,
        "success" if response.status_code < 400 else "rejected",
        (time.perf_counter() - started) * 1000,
    )
    return response

@app.middleware("http")
async def prevent_auth_response_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

# Chrome extension IDs differ between "Load unpacked" (local dev) and the
# Web Store's published copy, so both need to be listed explicitly here -
# there's no wildcard for extension origins the way there is for domains.
#
# ALLOWED_ORIGINS in .env is a comma-separated list, e.g.:
#   ALLOWED_ORIGINS=chrome-extension://<dev-id>,chrome-extension://<prod-id>
#
# Right now only the local dev ID is known. Once the extension is first
# uploaded to the Web Store dashboard, Chrome assigns the permanent
# published ID (shown on the dashboard, and later on the extension's
# chrome://extensions card for real installs) - add it as a second entry
# in .env at that point. That's a config change, not a code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.web_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

@app.get("/")
def read_root():
    return {"status": "backend is alive"}


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Process liveness only; dependencies are intentionally not consulted."""
    return {"status": "alive"}


@lru_cache(maxsize=1)
def _expected_database_revisions() -> frozenset[str]:
    backend_root = Path(__file__).resolve().parents[1]
    config = AlembicConfig(str(backend_root / "alembic.ini"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


@app.get("/readyz", include_in_schema=False)
def readyz():
    """Confirm PostgreSQL is reachable and its schema is at repository head."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = frozenset(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
        expected = _expected_database_revisions()
        if current != expected:
            logger.warning(
                "readiness_check outcome=not_ready component=database reason=migration_mismatch current_count=%s expected_count=%s",
                len(current),
                len(expected),
            )
            return JSONResponse(status_code=503, content={"status": "not_ready", "component": "database", "reason": "migration_mismatch"})
    except Exception as exc:
        logger.warning(
            "readiness_check outcome=not_ready component=database reason=unavailable exception_type=%s",
            type(exc).__name__,
        )
        return JSONResponse(status_code=503, content={"status": "not_ready", "component": "database", "reason": "unavailable"})
    return {"status": "ready"}

app.include_router(ai_router, tags=["AI"])
app.include_router(notes_router, tags=["Notes"])
app.include_router(sources_router, tags=["Sources"])
app.include_router(documents_router, tags=["Documents"])
app.include_router(quizzes_router, tags=["Quizzes"])
app.include_router(auth_router, tags=["Authentication"])
app.include_router(ingestion_router, tags=["Ingestion"])
app.include_router(routing_router, tags=["Routing"])
app.include_router(step_through_router, tags=["Development"])
app.include_router(learn_router, tags=["Learn"])









        



    
