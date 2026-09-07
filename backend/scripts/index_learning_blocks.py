"""Retry pending/failed/expired local source indexes without a job service."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.models.learning_block import DocumentSourceIndex
from app.services.source_index import index_document


def main() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        targets = db.execute(
            select(DocumentSourceIndex.document_id, DocumentSourceIndex.generation_id).where(
                or_(
                    DocumentSourceIndex.status.in_(("PENDING", "FAILED")),
                    (DocumentSourceIndex.status == "INDEXING")
                    & (DocumentSourceIndex.lease_expires_at.is_not(None))
                    & (DocumentSourceIndex.lease_expires_at <= now),
                )
            )
        ).all()
    completed = sum(bool(index_document(document_id, generation_id)) for document_id, generation_id in targets)
    print(f"indexed={completed} considered={len(targets)}")
    return 0 if completed == len(targets) else 1


if __name__ == "__main__":
    raise SystemExit(main())
