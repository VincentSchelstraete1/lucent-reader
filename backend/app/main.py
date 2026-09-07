from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
import app.models  # noqa: F401 - register all SQLAlchemy metadata


app = FastAPI()

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









        



    
