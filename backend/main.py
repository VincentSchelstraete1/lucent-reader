import os
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

app = FastAPI()

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


client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

DAILY_LIMIT = 50

# In-memory usage tracking: { install_id: {"date": "2026-08-07", "count": 3} }
# Resets on server restart - acceptable for now, see note above.
usage_tracker = {}


class SimplifyRequest(BaseModel):
    text: str
    target_grade_level: int
    target_length: str = "same"
    install_id: str


LENGTH_INSTRUCTIONS = {
    "much_shorter": "Condense it significantly - cut anything that isn't essential to the main point.",
    "shorter": "Make it noticeably shorter than the original while keeping the key details.",
    "same": "Keep the length roughly the same as the original.",
    "more_detail": "Expand it with a bit more explanatory detail than the original."
}


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


def strip_markdown_heading(text: str) -> str:
    # Claude sometimes prepends a heading like "# Rewritten Paragraph" even
    # when told to return only the rewritten text - seen most often on the
    # lead paragraph, likely because it reads like it could use a title.
    # The prompt now explicitly forbids this, but LLM output isn't
    # perfectly reliable, so this is a defensive backstop.
    lines = text.strip().splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


@app.post("/simplify")
def simplify(request: SimplifyRequest):
    check_and_increment(request.install_id)

    length_instruction = LENGTH_INSTRUCTIONS.get(
        request.target_length, LENGTH_INSTRUCTIONS["same"]
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Rewrite the following paragraph so it reads at approximately "
                    f"a US grade {request.target_grade_level} reading level. "
                    f"{length_instruction} "
                    f"Keep the meaning accurate. Return only the rewritten "
                    f"paragraph as plain text - no heading, no title, no "
                    f"markdown formatting, no preamble.\n\n{request.text}"
                )
            }
        ]
    )

    simplified = strip_markdown_heading(message.content[0].text)
    return {"simplified": simplified}