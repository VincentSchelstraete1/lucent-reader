import asyncio
from types import SimpleNamespace

import pytest

from app.config import settings
from app.database import engine
import app.routers.ingestion as ingestion_router
import app.services.anthropic_service as anthropic_service


def test_shared_anthropic_client_has_bounded_defaults():
    assert anthropic_service.client.max_retries == settings.anthropic_max_retries
    assert anthropic_service.client.timeout == settings.anthropic_timeout_seconds


def test_database_engine_has_production_pool_safety():
    assert engine.pool._pre_ping is True
    assert engine.pool.size() == settings.database_pool_size
    assert engine.pool._max_overflow == settings.database_max_overflow
    assert engine.pool._recycle == settings.database_pool_recycle_seconds
    assert engine.pool._timeout == settings.database_pool_timeout_seconds


@pytest.mark.parametrize("generator", ["note", "quiz"])
def test_document_generation_prompts_use_the_bounded_source_budget(monkeypatch, generator):
    source = "BEGIN " + ("middle-source " * 8_000) + " END"
    seen = {}

    def fake_tool(prompt, *args, **kwargs):
        seen["prompt"] = prompt
        if generator == "note":
            return {"title": "Bounded", "summary": "Summary", "key_points": [], "concepts": [], "sections": []}
        return {"questions": []}

    monkeypatch.setattr(anthropic_service, "_run_structured_tool", fake_tool)
    if generator == "note":
        anthropic_service.generate_structured_note("Fixture", source)
    else:
        anthropic_service.generate_quiz_questions("Fixture", source)

    bounded = anthropic_service._bounded_document_content(source)
    assert len(bounded) == anthropic_service.DOCUMENT_PROMPT_MAX_CHARS
    assert bounded.startswith("BEGIN")
    assert bounded.endswith("END")
    assert anthropic_service.DOCUMENT_PROMPT_OMISSION.strip() in seen["prompt"]
    assert source not in seen["prompt"]


def test_progressive_job_failure_becomes_terminal_without_leaking_details(monkeypatch):
    job_id = "failed-production-job"
    ingestion_router._PROGRESSIVE_JOBS[job_id] = {
        "status": "processing",
        "filename": "fixture.pdf",
        "base": None,
        "result": None,
        "error": None,
        "user_id": 1,
        "depth": "balanced",
        "sections": [{
            "id": "section-1",
            "title": "Fixture",
            "learning_block_ids": ["block-1"],
            "status": "generating",
            "section_note": None,
            "error": None,
        }],
    }

    async def fail_generation(*args, **kwargs):
        raise RuntimeError("private provider detail")

    logged = {}
    monkeypatch.setattr(ingestion_router.logger, "error", lambda message, *args: logged.update(message=message, args=args))
    monkeypatch.setattr(ingestion_router, "generate_sections_progressively", fail_generation)
    try:
        asyncio.run(ingestion_router._run_progressive_job(job_id, None, [], {}, SimpleNamespace()))
        job = ingestion_router._PROGRESSIVE_JOBS[job_id]
        assert job["status"] == "failed"
        assert job["result"] is None
        assert job["error"] == "Lucent could not finish processing this document. Please try again."
        assert job["sections"][0]["status"] == "failed"
        assert "private provider detail" not in job["error"]
        assert "progressive_ingestion_failed" in logged["message"]
        assert logged["args"] == (job_id, "RuntimeError")
    finally:
        ingestion_router._PROGRESSIVE_JOBS.pop(job_id, None)
