from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.normalization import SourceReference
from app.routers import ai as ai_router
from app.routers import ingestion as ingestion_router
from app.segmentation import LearningBlock, SegmentationMetadata
from app.services.usage_service import FixedWindowLimiter, LimitPolicy, UsageClass, limiter
import app.services.usage_service as usage_service


def _block(index: int, text: str, *, title: str | None = None) -> LearningBlock:
    return LearningBlock(
        id=f"block-{index}",
        block_type="section",
        text=text,
        character_count=len(text),
        normalized_block_ids=[],
        source=SourceReference(page_start=1, page_end=1, raw_block_ids=[], bboxes=[], locations=[]),
        segmentation=SegmentationMetadata(method="fixture", boundary_reason="fixture"),
        title=title or f"Section {index}",
        heading_ancestry=[],
        attached_table_ids=[],
        attached_image_ids=[],
        token_count=None,
    )


def test_fixed_window_limit_is_per_user_and_resets():
    local = FixedWindowLimiter()
    policy = LimitPolicy(user_limit=2, global_limit=10, window_seconds=60)
    local.consume(UsageClass.PROVIDER_GENERATION, user_key="one", policy=policy, now=1)
    local.consume(UsageClass.PROVIDER_GENERATION, user_key="one", policy=policy, now=2)
    with pytest.raises(HTTPException) as denied:
        local.consume(UsageClass.PROVIDER_GENERATION, user_key="one", policy=policy, now=3)
    assert denied.value.status_code == 429
    assert denied.value.detail["code"] == "usage_limit_reached"
    assert denied.value.headers["Retry-After"] == "57"
    local.consume(UsageClass.PROVIDER_GENERATION, user_key="two", policy=policy, now=3)
    local.consume(UsageClass.PROVIDER_GENERATION, user_key="one", policy=policy, now=61)


def test_fixed_window_limiter_prunes_expired_user_counters():
    local = FixedWindowLimiter()
    policy = LimitPolicy(user_limit=2, global_limit=200, window_seconds=60)
    for index in range(100):
        local.consume(UsageClass.PROVIDER_GENERATION, user_key=str(index), policy=policy, now=1)
    assert len(local._counters) == 101

    local.consume(UsageClass.PROVIDER_GENERATION, user_key="current", policy=policy, now=61)

    assert len(local._counters) == 2
    assert set(local._counters) == {
        (UsageClass.PROVIDER_GENERATION.value, "global"),
        (UsageClass.PROVIDER_GENERATION.value, "user:current"),
    }


def test_global_limit_is_atomic_under_concurrency():
    local = FixedWindowLimiter()
    policy = LimitPolicy(user_limit=100, global_limit=20, window_seconds=60)

    def attempt(index: int) -> bool:
        try:
            local.consume(UsageClass.DOCUMENT_INGESTION, user_key=str(index), policy=policy, now=1)
            return True
        except HTTPException:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(attempt, range(100)))
    assert sum(outcomes) == 20


def test_generation_endpoint_uses_authenticated_user_limit(client, monkeypatch):
    monkeypatch.setattr(usage_service, "settings", replace(usage_service.settings, usage_generation_user_limit=1))
    monkeypatch.setattr(ai_router, "simplify_text", lambda *args: "safe result")
    payload = {"text": "fixture", "target_grade_level": 8, "target_length": "same", "install_id": "spoofable"}
    assert client.post("/simplify", json=payload).status_code == 200
    denied = client.post("/simplify", json={**payload, "install_id": "different"})
    assert denied.status_code == 429
    assert denied.headers["Retry-After"]
    assert denied.json()["detail"] == {
        "code": "usage_limit_reached",
        "message": "Lucent has reached a temporary usage limit. Please try again later.",
        "limitClass": "provider_generation",
    }


def test_ingestion_workload_caps_source_characters_without_provider_calls(monkeypatch):
    private_source = "x" * 101
    monkeypatch.setattr(
        ingestion_router,
        "settings",
        replace(ingestion_router.settings, ingestion_max_source_characters=100),
    )
    with pytest.raises(HTTPException) as denied:
        ingestion_router.enforce_ingestion_workload([_block(1, private_source)])
    assert denied.value.status_code == 413
    assert denied.value.detail["code"] == "source_text_too_large"
    assert private_source not in str(denied.value.detail)


def test_ingestion_workload_caps_estimated_provider_fanout(monkeypatch):
    blocks = [_block(index, f"A plain definition for concept {index}.") for index in range(5)]
    monkeypatch.setattr(
        ingestion_router,
        "settings",
        replace(ingestion_router.settings, ingestion_max_provider_requests=4),
    )
    workload = ingestion_router.estimate_ingestion_workload(blocks)
    assert workload["fallback_candidates"] == 5
    assert workload["provider_requests"] > 4
    with pytest.raises(HTTPException) as denied:
        ingestion_router.enforce_ingestion_workload(blocks)
    assert denied.value.status_code == 422
    assert denied.value.detail["code"] == "ingestion_workload_too_large"


def test_small_ingestion_workload_is_accepted():
    workload = ingestion_router.enforce_ingestion_workload([
        _block(1, "First, the client sends SYN. Then the server returns SYN-ACK. Finally, the client sends ACK."),
    ])
    assert workload["source_characters"] > 0
    assert workload["provider_requests"] <= ingestion_router.settings.ingestion_max_provider_requests


@pytest.mark.parametrize("fixture_name", ["pendulum", "satire", "cache"])
def test_authorized_cc0_fixtures_fit_default_ingestion_budget(fixture_name):
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "rag_v1" / "sources" / f"{fixture_name}.json").read_text()
    )
    blocks = [_block(index, item["text"], title=item["title"]) for index, item in enumerate(fixture["blocks"])]
    workload = ingestion_router.enforce_ingestion_workload(blocks)
    assert workload["provider_requests"] <= 25
    assert workload["provider_requests"] <= ingestion_router.settings.ingestion_max_provider_requests
