"""Normalize legacy Learn sessions before dropping the cursor column.

Usage: python backend/scripts/backfill_learn_runtime_v2.py --check|--apply
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.models.learn import LearnSession
from app.services.learn_runtime import ensure_runtime_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not (args.check or args.apply):
        parser.error("choose --check or --apply")
    with SessionLocal() as db:
        sessions = db.execute(select(LearnSession).where(LearnSession.status.in_(["active", "stopped"]))).scalars().all()
        scanned = len(sessions)
        pending = 0
        migrated = 0
        already = 0
        failed = []
        for session in sessions:
            if int((session.state or {}).get("runtimeVersion", 0) or 0) < 2:
                pending += 1
                if args.apply:
                    try:
                        ensure_runtime_state(session, db=db)
                        migrated += 1
                    except Exception as exc:
                        db.rollback()
                        failed.append({"session": str(session.id), "reason": type(exc).__name__})
            else:
                already += 1
        if args.apply:
            db.commit()
        print(f"scanned={scanned} pending={pending} backfilled={migrated} already_migrated={already} failed={len(failed)}")
        for item in failed:
            print(f"failed_session={item['session']} reason={item['reason']}")
        return 1 if (args.check and pending) or failed else 0


if __name__ == "__main__":
    sys.exit(main())
