import os
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

DAILY_LIMIT = 0

# In-memory usage tracking: { install_id: {"date": "2026-08-07", "count": 3} }
# Resets on server restart - acceptable for now, see note above.
usage_tracker = {}


class SimplifyRequest(BaseModel):
    text: str
    target_grade_level: int
    install_id: str


def check_and_increment(install_id: str):
    today = str(date.today())
    record = usage_tracker.get(install_id)

    if record is None or record["date"] != today:
        record = {"date": today, "count": 0}

    if record["count"] >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached."
        )

    record["count"] += 1
    usage_tracker[install_id] = record


@app.get("/")
def read_root():
    return {"status": "backend is alive"}


@app.post("/simplify")
def simplify(request: SimplifyRequest):
    check_and_increment(request.install_id)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Rewrite the following paragraph so it reads at approximately "
                    f"a US grade {request.target_grade_level} reading level. "
                    f"Keep the meaning accurate. Return only the rewritten text, "
                    f"nothing else.\n\n{request.text}"
                )
            }
        ]
    )

    return {"simplified": message.content[0].text}