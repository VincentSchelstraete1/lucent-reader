import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()
from app.routers.ai import router as ai_router
from app.routers.notes import router as notes_router
from app.routers.sources import router as sources_router
from app.routers.documents import router as documents_router
from app.routers.quizzes import router as quizzes_router
from app.database import Base, engine
from app.models.note import Note
from app.models.source import Source
from app.models.document import Document
from app.models.quiz import Quiz, QuizAttempt


app = FastAPI()

Base.metadata.create_all(bind=engine)

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
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "backend is alive"}

app.include_router(ai_router, tags=["AI"])
app.include_router(notes_router, tags=["Notes"])
app.include_router(sources_router, tags=["Sources"])
app.include_router(documents_router, tags=["Documents"])
app.include_router(quizzes_router, tags=["Quizzes"])









        



    


