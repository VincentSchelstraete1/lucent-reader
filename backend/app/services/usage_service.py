from datetime import date
from fastapi import HTTPException

DAILY_LIMIT = 100

# In-memory usage tracking: { install_id: {"date": "2026-08-07", "count": 3} }
usage_tracker = {}

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
