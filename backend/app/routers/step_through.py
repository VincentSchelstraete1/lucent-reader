from __future__ import annotations

import json
import logging
import re
import time
from hashlib import sha256
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError

from app.auth_dependencies import get_current_user, require_csrf
from app.models.auth import User
from app.schemas.step_through import StepThroughMechanism
from app.services.anthropic_service import _run_structured_tool

router = APIRouter(prefix="/dev/step-through", tags=["Development"])
logger = logging.getLogger(__name__)
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "dev_fixtures" / "step_through"
MODEL = "claude-haiku-4-5-20251001"
SCHEMA_VERSION = "step-through-v2"
PROMPT_VERSION = "step-through-generation-v1"

SOURCE_FIXTURES = {
    "gram-schmidt": "Gram-Schmidt starts with a set of vectors. Keep the first vector as the first basis direction. For each later vector, project it onto every earlier orthogonal direction, subtract those projections, and keep the remaining perpendicular component. Normalize the resulting vectors when an orthonormal basis is needed.",
    "tcp-handshake": "A TCP connection begins when the client sends SYN. The server responds with SYN-ACK. The client completes the handshake by sending ACK, after which both sides can exchange data.",
    "bubble-sort": "Bubble sort repeatedly compares adjacent elements. If a pair is out of order, swap it. After one pass the largest remaining element bubbles to the end; repeat passes until no swaps are needed.",
    "cache-lookup": "A processor checks the fastest cache level first. On a hit it returns the data quickly. On a miss it checks the next level, eventually fetching from main memory and placing the result in a closer cache when possible.",
    "photosynthesis": "Photosynthesis uses light energy to split water and build energy-rich molecules. The light reactions produce ATP and NADPH. The Calvin cycle uses those molecules to fix carbon dioxide into sugars.",
}


class StepThroughRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_name: str = Field(min_length=1, max_length=80)
    source_text: str = Field(min_length=1, max_length=12000)
    mode: Literal["replay", "live"] = "replay"
    save_fixture: bool = False


class StepThroughFixture(BaseModel):
    name: str
    source_text: str
    source_hash: str
    replay_available: bool


class StepThroughMetadata(BaseModel):
    fixture_name: str
    source_hash: str
    mode: Literal["replay", "live"]
    fixture_kind: Literal["golden_manual", "recorded_live"]
    cache_hit: bool
    model_call_count: Literal[0, 1]
    model: str | None = None
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    validation: Literal["passed", "failed"]
    error: str | None = None


class StepThroughResponse(BaseModel):
    mechanism: StepThroughMechanism
    metadata: StepThroughMetadata


def _hash_source(source: str) -> str:
    return sha256(source.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-") or "fixture"


def _golden_mechanism() -> StepThroughMechanism:
    return StepThroughMechanism.model_validate({
        "title": "Gram–Schmidt: remove overlap to create a perpendicular direction",
        "learningGoal": "Understand geometrically why subtracting projections produces orthogonal directions.",
        "entities": [
            {"id": "v1", "label": "u₁ = v₁"},
            {"id": "v2", "label": "v₂"},
            {"id": "projection", "label": "projᵤ₁(v₂)"},
            {"id": "u2", "label": "u₂ (orthogonal remainder)"},
        ],
        "stages": [
            {"title": "Start with overlapping directions", "explanation": "v₁ and v₂ share some direction. Keep v₁ as the first basis direction.", "activeEntityIds": ["v1", "v2"], "stateChanges": [{"entityId": "v1", "change": "keep as first direction"}, {"entityId": "v2", "change": "contains a shared component"}]},
            {"title": "Expose the shared component", "explanation": "The projection is the part of v₂ already pointing along u₁—the overlap to remove.", "equation": "projᵤ₁(v₂)", "activeEntityIds": ["v2", "projection"], "stateChanges": [{"entityId": "projection", "change": "identify the parallel component", "why": "It captures the part already explained by u₁."}]},
            {"title": "Subtract the overlap", "explanation": "Subtracting the projection removes the part of v₂ parallel to u₁, leaving a new direction.", "equation": "u₂ = v₂ − projᵤ₁(v₂)", "activeEntityIds": ["v2", "projection", "u2"], "stateChanges": [{"entityId": "v2", "change": "remove the projection"}, {"entityId": "u2", "change": "retain the perpendicular remainder"}]},
            {"title": "The remainder is perpendicular", "explanation": "No u₁ direction remains in u₂, so u₂ is orthogonal to u₁. Repeat against every earlier basis direction.", "equation": "uₖ = vₖ − Σ projᵤⱼ(vₖ)", "activeEntityIds": ["v1", "u2"], "stateChanges": [{"entityId": "u2", "change": "becomes an orthogonal basis direction"}]},
        ],
        "prediction": {"prompt": "For v₃, which previous directions must be removed?", "options": ["u₁", "u₂", "Both u₁ and u₂"], "answer": 2, "reveal": "Each previous orthogonal direction can contribute an overlap, so subtract both projections before continuing."},
        "conclusion": "Gram–Schmidt builds orthogonal directions by removing components already explained by earlier basis vectors; normalization changes length, not direction.",
    })


def _fixture_path(name: str, source_hash: str) -> Path:
    return FIXTURE_DIR / f"{_slug(name)}-{source_hash[:16]}.json"


def _load_recorded(name: str, source_hash: str) -> StepThroughMechanism | None:
    path = _fixture_path(name, source_hash)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    return StepThroughMechanism.model_validate(payload["mechanism"])


def _save_recorded(name: str, source_text: str, mechanism: StepThroughMechanism) -> None:
    source_hash = _hash_source(source_text)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    _fixture_path(name, source_hash).write_text(json.dumps({
        "source_name": name,
        "source_hash": source_hash,
        "model": MODEL,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "mechanism": mechanism.model_dump(by_alias=True),
    }, indent=2) + "\n")


def _prompt(source_text: str) -> str:
    return ("Turn this one short source section into a semantic step-through mechanism that teaches the process, not a summary. "
            "Return every required field: title, learningGoal, entities, stages, and conclusion. Use 2-5 ordered stages. Keep labels concise and each stage explanation short. Explain why each important state change matters. "
            "Choose a stage visual grammar when it improves understanding. For actor/message exchanges, use visual.type=sequence_exchange_scene with actors, messages (sender, receiver, short label), visibleMessageIds, and an emphasizedMessageId; do not use coordinates or Cartesian axes. For vector mathematics, visual.type=vector_scene may identify activeEntityIds. "
            "You may include a prediction question when the learner can reason before the reveal. "
            "Generate meaning only: never include coordinates, SVG, HTML, CSS, colors, layout, animation, or pixel positions. Stay grounded in the source.\n\n"
            f"Source section:\n{source_text}")


@router.get("/fixtures", response_model=list[StepThroughFixture])
def list_fixtures(_user: User = Depends(get_current_user)) -> list[StepThroughFixture]:
    result = []
    for name, source in SOURCE_FIXTURES.items():
        result.append(StepThroughFixture(name=name, source_text=source, source_hash=_hash_source(source), replay_available=name == "gram-schmidt" or _load_recorded(name, _hash_source(source)) is not None))
    return result


@router.post("/generate", response_model=StepThroughResponse, dependencies=[Depends(require_csrf)])
def generate_step_through(request: StepThroughRequest, _user: User = Depends(get_current_user)) -> StepThroughResponse:
    source_hash = _hash_source(request.source_text)
    started = time.perf_counter()
    if request.mode == "replay":
        mechanism = _load_recorded(request.fixture_name, source_hash)
        is_golden = mechanism is None and request.fixture_name == "gram-schmidt" and request.source_text == SOURCE_FIXTURES["gram-schmidt"]
        if is_golden:
            mechanism = _golden_mechanism()
        if mechanism is None:
            raise HTTPException(status_code=404, detail={"code": "fixture_not_found", "message": "No replay fixture matches this source. Choose Live generate once."})
        kind = "golden_manual" if is_golden else "recorded_live"
        return StepThroughResponse(mechanism=mechanism, metadata=StepThroughMetadata(fixture_name=request.fixture_name, source_hash=source_hash, mode="replay", fixture_kind=kind, cache_hit=True, model_call_count=0, latency_ms=(time.perf_counter() - started) * 1000, validation="passed"))

    try:
        raw = _run_structured_tool(_prompt(request.source_text), "step_through_mechanism", StepThroughMechanism.generation_schema(), 1800, timeout=15, max_retries=0)
        mechanism = StepThroughMechanism.model_validate(raw)
    except ValidationError as exc:
        logger.warning("step_through_generation_failed fixture=%s stage=validation exception_type=%s", request.fixture_name, type(exc).__name__)
        raise HTTPException(status_code=422, detail={"code": "invalid_generation", "message": "Live generation returned semantic data that failed validation."}) from exc
    except Exception as exc:
        logger.warning("step_through_generation_failed fixture=%s stage=%s exception_type=%s", request.fixture_name, "model_or_validation", type(exc).__name__)
        raise HTTPException(status_code=422, detail={"code": "invalid_generation", "message": f"Live generation failed validation or provider request: {type(exc).__name__}"}) from exc
    latency_ms = (time.perf_counter() - started) * 1000
    if request.save_fixture:
        _save_recorded(request.fixture_name, request.source_text, mechanism)
    return StepThroughResponse(mechanism=mechanism, metadata=StepThroughMetadata(fixture_name=request.fixture_name, source_hash=source_hash, mode="live", fixture_kind="recorded_live", cache_hit=False, model_call_count=1, model=MODEL, latency_ms=latency_ms, validation="passed"))
