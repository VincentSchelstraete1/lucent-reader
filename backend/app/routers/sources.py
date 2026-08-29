from fastapi import APIRouter, Depends, HTTPException
from app.schemas.source import SourceCreateRequest, SourceResponse, SourceUpdateRequest
from app.database import get_db
from app.models.source import Source
from sqlalchemy import select
from urllib.parse import urlsplit, urlunsplit
router = APIRouter()

def normalize_source_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    if parts.username:
        credentials = parts.username + (f":{parts.password}" if parts.password else "")
        hostname = f"{credentials}@{hostname}"
    return urlunsplit((parts.scheme.lower(), hostname, parts.path or "", parts.query, ""))

@router.post("/sources", response_model=SourceResponse)
def create_source(source_request: SourceCreateRequest, db = Depends(get_db)):
    normalized_url = normalize_source_url(source_request.url)
    if normalized_url:
        existing = db.execute(
            select(Source).where(Source.type == source_request.type, Source.url == normalized_url)
        ).scalar_one_or_none()
        if existing:
            return existing
    source = Source(
        type=source_request.type,
        url=normalized_url
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source

@router.get("/sources", response_model=list[SourceResponse])
def get_sources(db = Depends(get_db)):
    statement = select(Source)
    result = db.execute(statement)
    sources = result.scalars().all()
    return sources

@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

@router.delete("/sources/{source_id}", response_model=SourceResponse)
def delete_source(source_id: int, db = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(source)
    db.commit()
    return source

@router.patch("/sources/{source_id}", response_model=SourceResponse)
def update_source(source_id: int, source_request: SourceUpdateRequest, db = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    updates = source_request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source
