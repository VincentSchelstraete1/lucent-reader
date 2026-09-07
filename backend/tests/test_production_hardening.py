import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.config import settings
from app.database import engine
from app.schemas.learn import LearnEvaluation
import app.routers.ingestion as ingestion_router
import app.services.anthropic_service as anthropic_service
import app.services.learn_tutor as learn_tutor


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


def test_terminal_progressive_jobs_are_evicted_after_ttl(monkeypatch):
    original = dict(ingestion_router._PROGRESSIVE_JOBS)
    monkeypatch.setattr(ingestion_router, "settings", replace(settings, progressive_job_ttl_seconds=10))
    ingestion_router._PROGRESSIVE_JOBS.clear()
    ingestion_router._PROGRESSIVE_JOBS.update({
        "expired": {"status": "complete", "finished_at": 10.0},
        "recent": {"status": "failed", "finished_at": 95.0},
        "active": {"status": "processing", "finished_at": None},
    })
    try:
        ingestion_router._prune_progressive_jobs(now=100.0)
        assert set(ingestion_router._PROGRESSIVE_JOBS) == {"recent", "active"}
    finally:
        ingestion_router._PROGRESSIVE_JOBS.clear()
        ingestion_router._PROGRESSIVE_JOBS.update(original)


def test_progressive_ingestion_rejects_new_work_at_active_job_cap(client, monkeypatch):
    original = dict(ingestion_router._PROGRESSIVE_JOBS)
    monkeypatch.setattr(ingestion_router, "settings", replace(settings, progressive_job_max_entries=1))
    ingestion_router._PROGRESSIVE_JOBS.clear()
    ingestion_router._PROGRESSIVE_JOBS["active"] = {"status": "processing", "finished_at": None}
    try:
        response = client.post(
            "/ingestion/progressive",
            files={"file": ("fixture.pdf", b"%PDF-1.4\nfixture", "application/pdf")},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "ingestion_capacity_reached"
    finally:
        ingestion_router._PROGRESSIVE_JOBS.clear()
        ingestion_router._PROGRESSIVE_JOBS.update(original)


def test_structured_provider_failure_log_excludes_prompt_and_exception_text(monkeypatch):
    class Messages:
        def create(self, **kwargs):
            raise RuntimeError("private prompt fragment")

    fake_client = SimpleNamespace(messages=Messages())
    logged = {}
    monkeypatch.setattr(anthropic_service, "client", fake_client)
    monkeypatch.setattr(anthropic_service.logger, "warning", lambda message, *args: logged.update(message=message, args=args))

    with pytest.raises(RuntimeError):
        anthropic_service._run_structured_tool("SECRET SOURCE", "test_tool", {}, 10)

    assert logged["args"] == ("test_tool", "RuntimeError")
    assert "SECRET SOURCE" not in str(logged)
    assert "private prompt fragment" not in str(logged)


def test_tutor_provider_failure_is_logged_safely_and_uses_fallback(monkeypatch):
    fallback = LearnEvaluation(result="incorrect", confidence=0.5, evidence="fallback", remediationCategory="simplify")
    logged = {}

    def fail_provider(*args, **kwargs):
        raise RuntimeError("private learner response")

    monkeypatch.setattr(learn_tutor.logger, "warning", lambda message, *args: logged.update(message=message, args=args))
    learn_tutor.set_tutor_provider(fail_provider)
    try:
        result = learn_tutor.diagnose_response(
            prompt="SECRET PROMPT",
            expected="expected",
            response="private response",
            source_context="private source",
            fallback=fallback,
        )
    finally:
        learn_tutor.set_tutor_provider(None)

    assert result is fallback
    assert logged["args"] == ("diagnose_response", "request_or_validation", "RuntimeError")
    assert "SECRET PROMPT" not in str(logged)
    assert "private learner response" not in str(logged)
