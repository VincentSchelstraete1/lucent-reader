"""Authoritative Learn session runtime.

Phase 2 establishes persisted scene ownership and the one-way adapter. Response
decision/execution is added in the following migration phase; this module is
already the only place allowed to normalize or persist scene revisions.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.schemas.learn import LearnPlan, LearningScene, ScenePrivateState, TutorObservation

RUNTIME_VERSION = 2
PLAN_SEMANTICS_VERSION = 2


@dataclass(frozen=True)
class AuthorizedAssetCatalog:
    objective_ids: tuple[str, ...]
    concept_ids: tuple[str, ...]
    candidate_interactions: dict[str, dict[str, Any]]
    visual_assets: dict[str, Any]
    source_section_ids: tuple[str, ...]
    source_block_ids: tuple[str, ...]


def bounded_id(prefix: str, *parts: object, max_length: int = 60) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:14]
    return f"{prefix}-{digest}"[:max_length]


def _state(session) -> dict[str, Any]:
    return dict(session.state or {})


def load_current_scene(session) -> LearningScene | None:
    raw = _state(session).get("currentScene")
    if not raw:
        return None
    try:
        return LearningScene.model_validate(raw)
    except Exception:
        return None


def _objective(plan: dict[str, Any], objective_id: str | None) -> dict[str, Any] | None:
    objectives = list(plan.get("objectives") or [])
    return next((item for item in objectives if str(item.get("id")) == str(objective_id)), None)


def build_authorized_asset_catalog(session) -> AuthorizedAssetCatalog:
    objectives = list((session.plan or {}).get("objectives") or [])
    interactions: dict[str, dict[str, Any]] = {}
    visuals: dict[str, Any] = {}
    sections: set[str] = set()
    blocks: set[str] = set()
    objective_ids: list[str] = []
    for objective in objectives:
        objective_id = str(objective.get("id"))
        objective_ids.append(objective_id)
        sections.update(str(value) for value in objective.get("sourceSectionIds", []))
        blocks.update(str(value) for value in objective.get("sourceBlockIds", []))
        for raw in objective.get("steps", []):
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            item_id = str(raw["id"])
            interactions[item_id] = dict(raw)
            if raw.get("visualSpec"):
                visuals[item_id] = raw["visualSpec"]
            sections.update(str(value) for value in raw.get("sourceSectionIds", []))
            blocks.update(str(value) for value in raw.get("sourceBlockIds", []))
    return AuthorizedAssetCatalog(tuple(objective_ids), tuple(objective_ids), interactions, visuals, tuple(sorted(sections)), tuple(sorted(blocks)))


def _legacy_scene(session, objective: dict[str, Any]) -> tuple[LearningScene, dict[str, Any] | None]:
    from app.schemas.learn import LearnStep
    from app.services.learn_engine import public_step
    from app.services.learn_scene import compose_learning_scene

    steps = list(objective.get("steps") or [])
    state = _state(session)
    cursor = int(getattr(session, "step_index", 0) or 0)
    if not steps:
        raise ValueError("objective has no candidate assets")
    cursor = max(0, min(cursor, len(steps) - 1))
    parsed = None
    adapter = __import__("pydantic", fromlist=["TypeAdapter"]).TypeAdapter(LearnStep)
    for raw in steps[cursor:] + steps[:cursor]:
        try:
            candidate = adapter.validate_python(raw)
        except Exception:
            continue
        parsed = candidate
        if candidate.type not in {"teach", "walkthrough"}:
            break
    if parsed is None:
        raise ValueError("objective has no valid candidate asset")
    scene = compose_learning_scene(session_id=str(session.id), objective=objective, steps=steps, step_index=cursor, current_step=parsed, action=None, decision=None, concept={}, state=state)
    scene_data = scene.model_dump(by_alias=True)
    private = None if parsed.type in {"teach", "walkthrough"} else ScenePrivateState(sceneId=scene.id, revision=scene.revision, interaction=parsed.model_dump(by_alias=True), objectiveId=str(objective.get("id")), targetConceptIds=[str(objective.get("id"))]).model_dump(by_alias=True)
    return scene, private


def ensure_runtime_state(session, db=None) -> tuple[LearningScene, dict[str, Any] | None]:
    current = load_current_scene(session)
    state = _state(session)
    if int(state.get("runtimeVersion", 0) or 0) == RUNTIME_VERSION and current is not None:
        private = state.get("currentScenePrivate")
        if private is not None:
            try:
                private = ScenePrivateState.model_validate(private).model_dump(by_alias=True)
            except Exception:
                private = None
        return current, private

    plan = session.plan or {}
    objective_id = state.get("currentObjectiveId")
    objective = _objective(plan, objective_id)
    if objective is None:
        objectives = list(plan.get("objectives") or [])
        objective = objectives[0] if objectives else None
    if objective is None:
        raise ValueError("Learn session has no valid objective")
    scene, private = _legacy_scene(session, objective)
    scene = scene.model_copy(update={"revision": max(1, int(scene.revision or 0))})
    state.update({"runtimeVersion": RUNTIME_VERSION, "planSemanticsVersion": PLAN_SEMANTICS_VERSION, "currentObjectiveId": str(objective.get("id")), "currentScene": scene.model_dump(by_alias=True), "currentScenePrivate": private})
    state.pop("sceneRevision", None)
    state.pop("sceneInterruption", None)
    session.state = state
    if db is not None:
        db.flush()
    return scene, private


def build_tutor_observation(session, *, event: dict[str, Any] | None = None, source_blocks: list[dict[str, Any]] | None = None) -> TutorObservation:
    scene = load_current_scene(session)
    if scene is None:
        scene, _ = ensure_runtime_state(session)
    state = _state(session)
    concept = next((item for item in state.get("concepts", []) if item.get("conceptId") == scene.objective_id), {})
    return TutorObservation(sessionId=str(session.id), objectiveId=scene.objective_id, currentConcept=scene.objective, learnerGoal=session.goal, evidence={key: concept.get(key) for key in ("state", "attempts", "correct", "incorrect", "hintsUsed", "scaffold", "lastResult")}, recentAttempts=list(state.get("recentAttempts", []))[-8:], misconceptions=list(concept.get("misconceptions", []))[-6:], successfulStrategies=list(concept.get("successfulStrategies", []))[-8:], failedStrategies=list(concept.get("failedStrategies", []))[-8:], successfulModalities=list(concept.get("successfulModalities", []))[-8:], failedModalities=list(concept.get("failedModalities", []))[-8:], previousTutorActions=list(state.get("previousTutorActions", []))[-8:], currentTeachingSurface=next((block.kind for block in scene.blocks if block.kind == "practice"), None), currentVisual=scene.visual_state.model_dump(by_alias=True) if scene.visual_state else None, currentVisualStage=scene.visual_state.stage if scene.visual_state else 0, reviewState=concept.get("reviewDue"), sourceBlocks=(source_blocks or [])[:8], sourceSectionIds=scene.source_section_ids[:8], sourceBlockIds=scene.source_block_ids[:12], candidateSteps=[])


def select_target_objective(session) -> str | None:
    state = _state(session)
    concepts = {item.get("conceptId"): item for item in state.get("concepts", [])}
    for concept_id in state.get("revisitQueue", []):
        if concept_id in concepts:
            return str(concept_id)
    for objective in (session.plan or {}).get("objectives", []):
        concept = concepts.get(objective.get("id"), {})
        if concept.get("state", "NOT_SEEN") != "DEMONSTRATED":
            return str(objective.get("id"))
    return None


def persist_scene_revision(session, scene: LearningScene, private: dict[str, Any] | None = None, *, event_id: str | None = None, db=None) -> LearningScene:
    state = _state(session)
    previous = load_current_scene(session)
    next_revision = max(int(scene.revision or 0), int(previous.revision if previous else 0) + 1)
    scene = scene.model_copy(update={"revision": next_revision})
    history = list(state.get("sceneHistory") or [])
    history.append({"sceneId": scene.id, "revision": scene.revision, "objectiveId": scene.objective_id, "eventId": event_id, "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()})
    state.update({"runtimeVersion": RUNTIME_VERSION, "planSemanticsVersion": PLAN_SEMANTICS_VERSION, "currentScene": scene.model_dump(by_alias=True), "currentScenePrivate": private, "sceneHistory": history[-8:], "currentObjectiveId": scene.objective_id})
    session.state = state
    if db is not None:
        db.flush()
    return scene


def apply_evaluation(session, evaluation: Any, *, interaction_id: str | None = None) -> dict[str, Any]:
    """Phase-2 seam: evidence mutation is completed by the Phase-3 runtime."""
    return {"evaluation": evaluation, "interactionId": interaction_id}


def build_student_feedback(evaluation: Any, *, interaction_id: str, source_blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"result": getattr(evaluation, "result", "insufficient_evidence"), "message": getattr(evaluation, "evidence", "Let's look at this together."), "respondsToInteractionId": interaction_id, "sourceSectionIds": [str(item) for block in (source_blocks or []) for item in block.get("sectionIds", [])][:8], "sourceBlockIds": [str(item) for block in (source_blocks or []) for item in block.get("blockIds", [])][:12]}


def process_tutor_event(session, event: Any, *, db=None, source_blocks: list[dict[str, Any]] | None = None):
    """Single runtime seam; full observe/decide/execute arrives in Phase 3."""
    scene, private = ensure_runtime_state(session, db=db)
    return scene, private
