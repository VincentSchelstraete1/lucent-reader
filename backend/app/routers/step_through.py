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
SCHEMA_VERSION = "step-through-v3"
PROMPT_VERSION = "visual-dsl-v1"

SOURCE_FIXTURES = {
    "gram-schmidt": "Gram-Schmidt starts with a set of vectors. Keep the first vector as the first basis direction. For each later vector, project it onto every earlier orthogonal direction, subtract those projections, and keep the remaining perpendicular component. Normalize the resulting vectors when an orthonormal basis is needed.",
    "tcp-handshake": "A TCP connection begins when the client sends SYN. The server responds with SYN-ACK. The client completes the handshake by sending ACK, after which both sides can exchange data.",
    "bubble-sort": "Bubble sort repeatedly compares adjacent elements. If a pair is out of order, swap it. After one pass the largest remaining element bubbles to the end; repeat passes until no swaps are needed.",
    "insertion-sort": "Insertion sort grows a sorted prefix. Take the next item, compare it with items to its left, shift larger items right, and insert the item into its sorted position.",
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
    fixture_kind: Literal["golden_manual", "sample_manual", "recorded_live"]
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
        "sceneType": "vector_scene",
        "learningGoal": "Understand geometrically why subtracting projections produces orthogonal directions.",
        "entities": [
            {"id": "v1", "kind": "vector", "label": "u₁ = v₁"},
            {"id": "v2", "kind": "vector", "label": "v₂"},
            {"id": "projection", "kind": "vector", "label": "projᵤ₁(v₂)"},
            {"id": "u2", "kind": "vector", "label": "u₂ (orthogonal remainder)"},
        ],
        "stages": [
            {"title": "Start with overlapping directions", "explanation": "v₁ and v₂ share some direction. Keep v₁ as the first basis direction.", "activeEntityIds": ["v1", "v2"], "notice": "v₂ contains both a parallel and a new direction.", "visual": {"type": "vector_scene", "activeEntityIds": ["v1", "v2"], "operations": [{"type": "highlight", "entityIds": ["v1", "v2"], "reason": "Compare v₂ with the direction already kept."}]}, "stateChanges": [{"entityId": "v1", "change": "keep as first direction"}, {"entityId": "v2", "change": "contains a shared component"}]},
            {"title": "Expose the shared component", "explanation": "The projection is the part of v₂ already pointing along u₁—the overlap to remove.", "equation": "projᵤ₁(v₂)", "activeEntityIds": ["v2", "projection"], "notice": "The projection is not a new direction; it is the overlap.", "visual": {"type": "vector_scene", "activeEntityIds": ["v2", "projection"], "operations": [{"type": "project", "entityIds": ["v2", "v1", "projection"], "reason": "Identify the component already along u₁.", "result": "The parallel component is isolated."}], "relationships": [{"source": "projection", "target": "v1", "relation": "parallel_to"}]}, "stateChanges": [{"entityId": "projection", "change": "identify the parallel component", "why": "It captures the part already explained by u₁."}]},
            {"title": "Subtract the overlap", "explanation": "Subtracting the projection removes the part of v₂ parallel to u₁, leaving a new direction.", "equation": "u₂ = v₂ − projᵤ₁(v₂)", "activeEntityIds": ["v2", "projection", "u2"], "notice": "Only the component not explained by u₁ remains.", "visual": {"type": "vector_scene", "activeEntityIds": ["v2", "projection", "u2"], "operations": [{"type": "subtract", "entityIds": ["v2", "projection", "u2"], "reason": "Remove the component already pointing along u₁.", "result": "u₂ is the remaining direction."}]}, "stateChanges": [{"entityId": "v2", "change": "remove the projection"}, {"entityId": "u2", "change": "retain the perpendicular remainder"}]},
            {"title": "The remainder is perpendicular", "explanation": "No u₁ direction remains in u₂, so u₂ is orthogonal to u₁. Repeat against every earlier basis direction.", "equation": "uₖ = vₖ − Σ projᵤⱼ(vₖ)", "activeEntityIds": ["v1", "u2"], "insight": "Removing every previous direction produces a genuinely new orthogonal direction.", "visual": {"type": "vector_scene", "activeEntityIds": ["v1", "u2"], "operations": [{"type": "reveal", "entityIds": ["u2"], "result": "The orthogonal remainder becomes the next basis direction."}], "relationships": [{"source": "u2", "target": "v1", "relation": "perpendicular_to", "explanation": "u₂ has no component left along u₁."}]}, "stateChanges": [{"entityId": "u2", "change": "becomes an orthogonal basis direction"}]},
        ],
        "prediction": {"prompt": "For v₃, which previous directions must be removed?", "options": ["u₁", "u₂", "Both u₁ and u₂"], "answer": 2, "reveal": "Each previous orthogonal direction can contribute an overlap, so subtract both projections before continuing."},
        "conclusion": "Gram–Schmidt builds orthogonal directions by removing components already explained by earlier basis vectors; normalization changes length, not direction.",
    })


def _ordered_replay(name: str) -> StepThroughMechanism | None:
    if name == "bubble-sort":
        stages = [
            {"title": "Compare neighboring values", "explanation": "Inspect the first pair before deciding whether their order should change.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "a", "status": "compared"}, {"entityId": "b", "status": "compared"}, {"entityId": "c"}, {"entityId": "d"}], "regions": [{"id": "active-pair", "label": "Current comparison", "entityIds": ["a", "b"], "status": "active"}]}, "operation": {"type": "compare", "entityIds": ["a", "b"], "reason": "5 > 3, so the pair is out of ascending order.", "result": "These two values need to trade places."}, "notice": "The decision comes from comparing 5 with 3."}},
            {"title": "Swap the out-of-order pair", "explanation": "Exchange the selected values so the smaller one comes first.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "a", "status": "selected"}, {"entityId": "b", "status": "selected"}, {"entityId": "c"}, {"entityId": "d"}]}, "operation": {"type": "swap", "entityIds": ["a", "b"], "reason": "5 > 3, so ascending order requires 3 before 5.", "result": "3 now precedes 5."}, "after": {"items": [{"entityId": "b", "status": "changed"}, {"entityId": "a", "status": "changed"}, {"entityId": "c"}, {"entityId": "d"}]}, "notice": "Only the selected pair changes position."}},
            {"title": "Finish the pass", "explanation": "Continue comparing and swapping until the largest active value reaches the end.", "insight": "The completed region grows as later passes settle more values.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "b"}, {"entityId": "a"}, {"entityId": "d"}, {"entityId": "c", "status": "active"}]}, "operation": {"type": "mark_complete", "entityIds": ["c"], "reason": "After the pass, 8 has moved past every value compared with it.", "result": "8 has reached its final position."}, "after": {"items": [{"entityId": "b"}, {"entityId": "a"}, {"entityId": "d"}, {"entityId": "c", "status": "completed"}], "regions": [{"id": "settled-end", "label": "Final position", "entityIds": ["c"], "status": "completed", "explanation": "This value no longer participates in later passes."}]}, "notice": "8 is settled; the remaining values still need work."}},
        ]
        return StepThroughMechanism.model_validate({"sceneType": "ordered_items_scene", "title": "Bubble Sort", "learningGoal": "Understand how a comparison causes a visible state change and how completed positions emerge.", "entities": [{"id": "a", "kind": "item", "label": "5"}, {"id": "b", "kind": "item", "label": "3"}, {"id": "c", "kind": "item", "label": "8"}, {"id": "d", "kind": "item", "label": "2"}], "stages": stages, "conclusion": "Each comparison supplies a reason for keeping or changing the order; repeated passes settle values into final positions."})
    if name == "insertion-sort":
        stages = [
            {"title": "Select the next item", "explanation": "Choose the next item outside the completed prefix.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "a", "status": "completed"}, {"entityId": "b", "status": "selected"}, {"entityId": "c"}], "regions": [{"id": "sorted-prefix", "label": "Ordered prefix", "entityIds": ["a"], "status": "completed"}]}, "operation": {"type": "highlight", "entityIds": ["b"], "reason": "2 is the next item to insert into the ordered prefix."}, "notice": "The prefix is ordered; 2 is not placed yet."}},
            {"title": "Compare with the prefix", "explanation": "Compare the selected value with the values already in order.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "a", "status": "compared"}, {"entityId": "b", "status": "compared"}, {"entityId": "c"}], "regions": [{"id": "sorted-prefix", "label": "Ordered prefix", "entityIds": ["a"], "status": "active"}]}, "operation": {"type": "compare", "entityIds": ["a", "b"], "reason": "2 < 4, so placing 2 before 4 preserves ascending order.", "result": "2 belongs at the start of the prefix."}, "notice": "The comparison identifies the insertion point."}},
            {"title": "Insert and extend the prefix", "explanation": "Move the selected item into position; the ordered prefix grows by one.", "insight": "The unprocessed item becomes part of a larger ordered region.", "visual": {"type": "ordered_items_scene", "before": {"items": [{"entityId": "a", "status": "active"}, {"entityId": "b", "status": "selected"}, {"entityId": "c"}]}, "operation": {"type": "move", "entityIds": ["b"], "reason": "2 belongs before 4.", "result": "The prefix is now 2, 4."}, "after": {"items": [{"entityId": "b", "status": "completed"}, {"entityId": "a", "status": "completed"}, {"entityId": "c"}], "regions": [{"id": "sorted-prefix", "label": "Ordered prefix", "entityIds": ["b", "a"], "status": "completed", "explanation": "These items are now in their correct relative order."}]}, "notice": "The item moved; the prefix expanded."}},
        ]
        return StepThroughMechanism.model_validate({"sceneType": "ordered_items_scene", "title": "Insertion Sort", "learningGoal": "Understand how an ordered region grows by selecting and moving one item into place.", "entities": [{"id": "a", "kind": "item", "label": "4"}, {"id": "b", "kind": "item", "label": "2"}, {"id": "c", "kind": "item", "label": "5"}], "stages": stages, "conclusion": "Each insertion compares a selected item with an ordered region, moves it to the preserving position, and expands that region."})
    return None


def _sequence_replay(name: str) -> StepThroughMechanism | None:
    if name != "tcp-handshake":
        return None
    actors = [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}]
    messages = [
        {"id": "syn", "sender": "client", "receiver": "server", "label": "SYN", "reason": "The client initiates a connection.", "result": "The server learns the client wants to synchronize."},
        {"id": "syn-ack", "sender": "server", "receiver": "client", "label": "SYN-ACK", "reason": "The server acknowledges and synchronizes in return.", "result": "Both sides have now exchanged synchronization information."},
        {"id": "ack", "sender": "client", "receiver": "server", "label": "ACK", "reason": "The client confirms the server response.", "result": "The connection is ready for data."},
    ]
    stages = []
    for index, message in enumerate(messages):
        stages.append({
            "title": ["Client initiates", "Server responds", "Client confirms"][index],
            "explanation": "Follow the highlighted message from its sender to its receiver; earlier messages remain visible for context.",
            "activeEntityIds": [message["sender"], message["receiver"]],
            "visual": {"type": "sequence_exchange_scene", "actors": actors, "messages": messages, "visibleMessageIds": [item["id"] for item in messages[: index + 1]], "emphasizedMessageId": message["id"]},
        })
    return StepThroughMechanism.model_validate({"sceneType": "sequence_exchange_scene", "title": "TCP Three-Way Handshake", "learningGoal": "Understand how two actors establish shared connection state through an ordered exchange.", "entities": [{"id": "client", "kind": "actor", "label": "Client"}, {"id": "server", "kind": "actor", "label": "Server"}], "stages": stages, "conclusion": "The ordered SYN, SYN-ACK, and ACK exchange lets both endpoints confirm that the connection is ready."})


def _fixture_path(name: str, source_hash: str) -> Path:
    return FIXTURE_DIR / f"{_slug(name)}-{source_hash[:16]}.json"


def _load_recorded(name: str, source_hash: str) -> StepThroughMechanism | None:
    path = _fixture_path(name, source_hash)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    try:
        return StepThroughMechanism.model_validate(payload["mechanism"])
    except Exception:
        return None


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
    return f"""Turn this one short source section into a selective semantic visual program that teaches a mechanism.

Return every required field: sceneType, title, learningGoal, entities, stages, and conclusion. Use 2-5 meaningful stages. Every entity needs a stable machine id, a semantic kind, and a learner-facing label. IDs are references only and must never substitute for labels.

Choose exactly one supported sceneType:
- sequence_exchange_scene for ordered exchanges between actors. Messages identify sender, receiver, a short display label, and may separately explain reason and result.
- ordered_items_scene for ordered collections. Each stage visual identifies a before state, one semantic operation (compare, swap, move, highlight, or mark_complete), the operation reason/result, and an after state whenever order or completion changes. Use statuses and named regions to express active, selected, changed, or completed subsets. Do not ask the renderer to infer algorithm-specific completion.
- vector_scene only for genuine vector mathematics. Identify active entities, semantic operations (project, subtract, highlight, reveal), and relationships without coordinates.

Each stage should distinguish what happened from why it happened. Use notice for what the learner should look at and insight for a concise conclusion. A state-changing ordered operation must provide enough before/after semantic state to make the change visible. Prefer fewer stages with visible conceptual change over redundant snapshots. If none of the supported grammars genuinely fits, the request should fail validation rather than forcing unrelated content into a scene.

Generate meaning only. Never include x/y coordinates, dimensions, SVG, HTML, CSS, colors, font sizes, pixel positions, animation instructions, or executable code. Stay grounded in the supplied source and do not invent unsupported rules.

Source section:
{source_text}"""


@router.get("/fixtures", response_model=list[StepThroughFixture])
def list_fixtures(_user: User = Depends(get_current_user)) -> list[StepThroughFixture]:
    result = []
    for name, source in SOURCE_FIXTURES.items():
        result.append(StepThroughFixture(name=name, source_text=source, source_hash=_hash_source(source), replay_available=name in {"gram-schmidt", "tcp-handshake", "bubble-sort", "insertion-sort"} or _load_recorded(name, _hash_source(source)) is not None))
    return result


@router.post("/generate", response_model=StepThroughResponse, dependencies=[Depends(require_csrf)])
def generate_step_through(request: StepThroughRequest, _user: User = Depends(get_current_user)) -> StepThroughResponse:
    source_hash = _hash_source(request.source_text)
    started = time.perf_counter()
    if request.mode == "replay":
        is_builtin_source = request.fixture_name in SOURCE_FIXTURES and request.source_text == SOURCE_FIXTURES[request.fixture_name]
        mechanism = _ordered_replay(request.fixture_name) if is_builtin_source else None
        mechanism = mechanism or (_sequence_replay(request.fixture_name) if is_builtin_source else None)
        mechanism = mechanism or _load_recorded(request.fixture_name, source_hash)
        is_golden = mechanism is None and request.fixture_name == "gram-schmidt" and request.source_text == SOURCE_FIXTURES["gram-schmidt"]
        if is_golden:
            mechanism = _golden_mechanism()
        if mechanism is None:
            raise HTTPException(status_code=404, detail={"code": "fixture_not_found", "message": "No replay fixture matches this source. Choose Live generate once."})
        kind = "golden_manual" if is_golden else "sample_manual" if is_builtin_source and request.fixture_name in {"tcp-handshake", "bubble-sort", "insertion-sort"} else "recorded_live"
        return StepThroughResponse(mechanism=mechanism, metadata=StepThroughMetadata(fixture_name=request.fixture_name, source_hash=source_hash, mode="replay", fixture_kind=kind, cache_hit=True, model_call_count=0, latency_ms=(time.perf_counter() - started) * 1000, validation="passed"))

    try:
        raw = _run_structured_tool(_prompt(request.source_text), "step_through_mechanism", StepThroughMechanism.generation_schema(), 1800, timeout=15, max_retries=0)
        mechanism = StepThroughMechanism.model_validate(raw)
    except ValidationError as exc:
        logger.warning("step_through_generation_failed fixture=%s stage=validation exception_type=%s", request.fixture_name, type(exc).__name__)
        errors = [{"location": ".".join(str(part) for part in error["loc"]), "message": error["msg"], "type": error["type"]} for error in exc.errors(include_url=False, include_input=False)]
        raise HTTPException(status_code=422, detail={"code": "invalid_generation", "message": "Live generation returned semantic data that failed validation.", "validation_errors": errors}) from exc
    except Exception as exc:
        logger.warning("step_through_generation_failed fixture=%s stage=%s exception_type=%s", request.fixture_name, "model_or_validation", type(exc).__name__)
        raise HTTPException(status_code=422, detail={"code": "invalid_generation", "message": f"Live generation failed validation or provider request: {type(exc).__name__}"}) from exc
    latency_ms = (time.perf_counter() - started) * 1000
    if request.save_fixture:
        _save_recorded(request.fixture_name, request.source_text, mechanism)
    return StepThroughResponse(mechanism=mechanism, metadata=StepThroughMetadata(fixture_name=request.fixture_name, source_hash=source_hash, mode="live", fixture_kind="recorded_live", cache_hit=False, model_call_count=1, model=MODEL, latency_ms=latency_ms, validation="passed"))
