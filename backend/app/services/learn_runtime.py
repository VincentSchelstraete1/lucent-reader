"""Authoritative Learn session runtime.

Phase 2 establishes persisted scene ownership and the one-way adapter. Response
decision/execution is added in the following migration phase; this module is
already the only place allowed to normalize or persist scene revisions.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.schemas.learn import LearnPlan, LearnStep, LearningScene, LearningSceneBlock, LearningVisualState, ScenePrivateState, TutorAction, TutorDecision, TutorObservation, ShortAnswerStep, TeachBackStep, TeachStep

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


def _required_concepts(text: str) -> list[str]:
    """Return normalized concept tokens for generated teach-back grading."""
    filler = {
        "because", "continuously", "between", "through", "their", "there",
        "which", "while", "where", "when", "each", "instant", "using",
        "works", "result", "predicts", "described", "material", "concept",
    }
    words = [
        word for word in re.findall(r"[a-z][a-z-]{3,}", str(text).casefold())
        if word not in filler
    ]
    return list(dict.fromkeys(words))[:6]


def _visual_supports_remediation(scene: LearningScene, interaction) -> bool:
    """Whether the current visual can express the failed interaction's idea.

    A visual should not advance merely because one exists. Matching failures
    are especially prone to this: a process diagram about one mechanism does
    not necessarily explain a comparison between two different cases.
    """
    visual = next((block.visual_spec for block in scene.blocks if block.kind in {"visual", "animation"} and block.visual_spec), None)
    if visual is None or not visual.stages:
        return False
    if getattr(interaction, "type", None) != "matching":
        return True
    pair_words = set()
    for pair in getattr(interaction, "pairs", []) or []:
        pair_words.update(_required_concepts(getattr(pair, "label", "")))
    visual_words = set()
    for node in visual.nodes:
        visual_words.update(_required_concepts(f"{node.label} {node.detail or ''}"))
    return bool(pair_words.intersection(visual_words))


def _state(session) -> dict[str, Any]:
    return dict(session.state or {})


def _answered_interaction_ids(session, state: dict[str, Any] | None = None) -> set[str]:
    """Return the durable answered-interaction set.

    A legacy response path could persist ``LearnAttempt`` before updating the
    JSON compatibility list. Selection therefore consults both durable
    sources, preventing an answered interaction from becoming active again.
    """
    state = state if state is not None else _state(session)
    answered = {str(item) for item in (state.get("answeredInteractionIds") or [])}
    for attempt in getattr(session, "attempts", None) or []:
        step_id = getattr(attempt, "step_id", None)
        if step_id:
            answered.add(str(step_id))
    return answered


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
    # Legacy sessions are backfilled into runtime-v2 without a cursor. Start
    # from the first authored candidate; scene state is now authoritative.
    cursor = 0
    if not steps:
        raise ValueError("objective has no candidate assets")
    cursor = max(0, min(cursor, len(steps) - 1))
    parsed = None
    adapter = __import__("pydantic", fromlist=["TypeAdapter"]).TypeAdapter(LearnStep)
    parsed_candidates = []
    for raw in steps[cursor:] + steps[:cursor]:
        try:
            candidate = _coerce_step(raw, objective)
        except Exception:
            continue
        parsed_candidates.append(candidate)
    answered = _answered_interaction_ids(session, state)
    used_teaching = set(state.get("usedTeachingIds") or [])
    revisit = str(objective.get("id")) in {str(item) for item in state.get("revisitQueue", [])}
    if revisit:
        # A revisit is a retrieval opportunity, not a replay of the original
        # introduction. Prefer an unanswered interactive asset so the learner
        # must recall/apply the idea in a different surface.
        parsed = next((candidate for candidate in parsed_candidates if candidate.id not in answered and candidate.type not in {"teach", "walkthrough"}), None)
    else:
        parsed = next((candidate for candidate in parsed_candidates if candidate.type in {"teach", "walkthrough"} and candidate.id not in used_teaching), None)
    parsed = parsed or next((candidate for candidate in parsed_candidates if candidate.id not in answered and not (candidate.type in {"teach", "walkthrough"} and candidate.id in used_teaching)), None)
    if parsed is None and revisit:
        # Once authored assets have all been answered, a due revisit still
        # needs a real retrieval opportunity. Compose it in scene-private
        # state rather than resurrecting an answered candidate or mutating the
        # LearnPlan asset list.
        from app.schemas.learn import TeachBackStep
        outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
        concept_attempts = next((int(item.get("attempts", 0) or 0) for item in state.get("concepts", []) if str(item.get("conceptId")) == str(objective.get("id"))), 0)
        review_id = bounded_id("review", session.id, objective.get("id"), concept_attempts, len(state.get("recentAttempts", [])), len(state.get("sceneHistory", [])))
        parsed = TeachBackStep(id=review_id, type="teach_back", title="Recall it without the original prompt", prompt=f"Without looking back at the earlier question, explain how {objective.get('title', 'this concept')} works and what result it predicts.", requiredConcepts=_required_concepts(outcome), hints=[f"Use this source-supported idea: {outcome[:220]}"], feedbackIncorrect=f"Start with the central relationship: {outcome[:260]}", sourceSectionIds=list(objective.get("sourceSectionIds", [])), sourceBlockIds=list(objective.get("sourceBlockIds", [])))
    if parsed is None and parsed_candidates:
        # Never resurrect an answered authored interaction when a scene is
        # rebuilt after candidate exhaustion.  Compose a bounded, grounded
        # retrieval target instead; the authored plan remains an asset catalog,
        # not a finite cursor that can replay the first question forever.
        from app.schemas.learn import TeachBackStep
        outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
        generated_id = bounded_id("autonomous", session.id, objective.get("id"), len(state.get("recentAttempts", [])), len(state.get("sceneHistory", [])))
        parsed = TeachBackStep(
            id=generated_id,
            type="teach_back",
            title=f"Apply {objective.get('title', 'this idea')} in your own words",
            prompt=f"Explain how {objective.get('title', 'this idea')} works in a new situation, using the source-supported relationship.",
            requiredConcepts=_required_concepts(outcome),
            hints=[f"Start from this source-supported idea: {outcome[:220]}"],
            feedbackIncorrect=f"Use the central relationship described in the material: {outcome[:260]}",
            sourceSectionIds=list(objective.get("sourceSectionIds", [])),
            sourceBlockIds=list(objective.get("sourceBlockIds", [])),
        )
    if parsed is None:
        raise ValueError("objective has no valid candidate asset")
    # The compiler may pair a teaching asset with a later practice asset.  Do
    # not offer interactions that durable attempt history says were already
    # answered, even if an older JSON compatibility list is stale.
    available_steps = [
        raw for raw in steps
        if not isinstance(raw, dict)
        or raw.get("type") in {"teach", "walkthrough"}
        or str(raw.get("id")) not in answered
    ]
    scene = compose_learning_scene(session_id=str(session.id), objective=objective, steps=available_steps, step_index=cursor, current_step=parsed, action=None, decision=None, concept={}, state=state)
    scene = scene.model_copy(update={"revision": max(1, int(scene.revision or 0))})
    scene_data = scene.model_dump(by_alias=True)
    # The scene compiler can keep an authored teaching asset visible while
    # attaching a separate practice interaction.  Private grading/hint state
    # must therefore follow the interaction the learner actually sees, not
    # the asset originally selected to seed the scene.
    private = _private_for_rendered_scene(
        scene,
        objective_id=str(objective.get("id")),
        fallback_step=parsed,
        objective=objective,
    )
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
    state.update({"runtimeVersion": RUNTIME_VERSION, "planSemanticsVersion": PLAN_SEMANTICS_VERSION, "currentObjectiveId": str(objective.get("id")), "currentScene": scene.model_dump(by_alias=True), "currentScenePrivate": private})
    concepts = list(state.get("concepts") or [])
    if not any(str(item.get("conceptId")) == str(objective.get("id")) for item in concepts):
        concepts.append({"conceptId": str(objective.get("id")), "title": objective.get("title", "Concept"), "state": "INTRODUCED", "attempts": 0, "correct": 0, "incorrect": 0, "partiallyCorrect": 0, "assistedSuccesses": 0, "independentSuccesses": 0, "scaffold": "FULL", "scaffoldingLevel": "FULL", "misconceptions": [], "interactionTypes": []})
        state["concepts"] = concepts
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
    evidence_keys = (
        "state", "attempts", "correct", "incorrect", "partiallyCorrect",
        "insufficientEvidence", "hintsUsed", "hintDependence", "scaffold",
        "scaffoldingLevel", "scaffoldDependence", "lastResult",
        "recognitionEvidence", "recallEvidence", "explanationEvidence",
        "applicationEvidence", "transferEvidence", "assistedSuccesses",
        "independentSuccesses", "uncertaintyCount",
    )
    evidence = {key: concept.get(key) for key in evidence_keys if key in concept}
    evidence["answeredInteractionIds"] = list(state.get("answeredInteractionIds") or [])[-16:]
    evidence["usedTeachingIds"] = list(state.get("usedTeachingIds") or [])[-8:]
    evidence["sceneRevision"] = scene.revision
    evidence["sceneBlockKinds"] = [block.kind for block in scene.blocks]
    visual_block = next((block for block in scene.blocks if block.kind in {"visual", "animation"} and (block.visual_spec is not None or block.visual_ref is not None)), None)
    current_visual = scene.visual_state.model_dump(by_alias=True) if scene.visual_state else None
    if visual_block is not None:
        current_visual = {"state": current_visual, "spec": visual_block.visual_spec.model_dump(by_alias=True) if visual_block.visual_spec else None, "ref": visual_block.visual_ref}
    return TutorObservation(sessionId=str(session.id), objectiveId=scene.objective_id, currentConcept=scene.objective, learnerGoal=session.goal, evidence=evidence, recentAttempts=list(state.get("recentAttempts", []))[-8:], misconceptions=list(concept.get("misconceptions", []))[-6:], previousDiagnoses=list(concept.get("previousDiagnoses", []))[-6:], successfulStrategies=list(concept.get("successfulStrategies", []))[-8:], failedStrategies=list(concept.get("failedStrategies", []))[-8:], successfulModalities=list(concept.get("successfulModalities", []))[-8:], failedModalities=list(concept.get("failedModalities", []))[-8:], previousTutorActions=list(state.get("previousTutorActions", []))[-8:], currentTeachingSurface=next((block.kind for block in scene.blocks if block.kind == "practice"), None), currentVisual=current_visual, currentVisualStage=scene.visual_state.stage if scene.visual_state else 0, reviewState=concept.get("reviewDue"), sourceBlocks=(source_blocks or [])[:8], sourceSectionIds=scene.source_section_ids[:8], sourceBlockIds=scene.source_block_ids[:12], candidateSteps=[])


def select_target_objective(session, *, exclude_concept_id: str | None = None) -> str | None:
    """Choose the next objective the runtime should transition to.

    A revisit is deliberately deferred when another objective still has
    untouched candidate material. This gives the learner intervening work
    before retrieval while retaining the bounded queue fallback when no
    other objective can make progress. An objective is only selectable while
    it still has an unanswered/unused candidate; exhausted objectives must
    not bounce the learner back and forth forever.
    """
    state = _state(session)
    concepts = {str(item.get("conceptId")): item for item in state.get("concepts", [])}
    objectives_by_id = {str(item.get("id")): item for item in (session.plan or {}).get("objectives", [])}
    queued_ids = {str(item) for item in state.get("revisitQueue", [])}
    # Prefer genuinely new objective material before a queued revisit. This
    # is the minimum delay required for within-session spaced retrieval.
    for objective in (session.plan or {}).get("objectives", []):
        objective_id = str(objective.get("id"))
        if objective_id == str(exclude_concept_id) or objective_id in queued_ids:
            continue
        concept = concepts.get(objective_id, {})
        if concept.get("state", "NOT_SEEN") != "DEMONSTRATED" and _objective_has_remaining_candidates(objective, state, session):
            return objective_id
    for concept_id in state.get("revisitQueue", []):
        concept_id = str(concept_id)
        if concept_id == str(exclude_concept_id):
            continue
        objective = objectives_by_id.get(concept_id)
        concept = concepts.get(concept_id, {})
        if objective is not None and (_objective_has_remaining_candidates(objective, state, session) or int(concepts.get(concept_id, {}).get("reviewVisits", 0) or 0) < 1):
            # Consume the queue entry when selecting the revisit. A later
            # response may schedule it again, but only while a real candidate
            # remains; exhausted objectives cannot oscillate indefinitely.
            state["revisitQueue"] = [item for item in state.get("revisitQueue", []) if str(item) != concept_id]
            for item in state.get("concepts", []):
                if str(item.get("conceptId")) == concept_id:
                    item["reviewVisits"] = int(item.get("reviewVisits", 0) or 0) + 1
            session.state = state
            return concept_id
    for objective in (session.plan or {}).get("objectives", []):
        objective_id = str(objective.get("id"))
        if objective_id == str(exclude_concept_id):
            continue
        concept = concepts.get(objective_id, {})
        if concept.get("state", "NOT_SEEN") != "DEMONSTRATED" and _objective_has_remaining_candidates(objective, state, session):
            return objective_id
    return None


def _private_for_rendered_scene(scene: LearningScene, *, objective_id: str, decision: TutorDecision | None = None, fallback_step=None, objective: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Build grading state for the scene's actual active practice block.

    Teaching scenes may include a supporting practice block; its ID, rather
    than the selected teaching asset, is the response target.
    """
    interaction_id = scene.response_interaction_id
    if not interaction_id:
        return None
    # The rendered scene block only ever carries the public LearnStepView,
    # which omits answer-bearing fields (answerId, acceptedAnswers,
    # correctOrder, matches, answerMap, ...). Grading state must be built from
    # the real private step object, never from that public view. Prefer the
    # executor's own selected step, then the objective's authored candidate by
    # ID; only fall back to coercing the public view for step types that
    # genuinely carry no private-only fields (e.g. teach/walkthrough).
    step = None
    if fallback_step is not None and getattr(fallback_step, "id", None) == interaction_id:
        step = fallback_step
    if step is None and objective:
        raw = next((item for item in objective.get("steps", []) if str(item.get("id")) == str(interaction_id)), None)
        if raw:
            try:
                step = _coerce_step(raw, objective)
            except Exception:
                step = None
    if step is None:
        block_step = next((block.step for block in scene.blocks if block.kind == "practice" and block.step and block.step.id == interaction_id), None)
        if block_step is not None:
            try:
                step = _coerce_step(block_step.model_dump(by_alias=True), objective)
            except Exception:
                step = None
    if step is None:
        return None
    return ScenePrivateState(sceneId=scene.id, revision=scene.revision, interaction=step.model_dump(by_alias=True), objectiveId=objective_id, targetConceptIds=[objective_id], strategy=decision.pedagogical_strategy if decision else "DIRECT_INSTRUCTION", scaffoldLevel=decision.scaffold_level if decision else "FULL", decisionId=bounded_id("decision", objective_id, scene.id)).model_dump(by_alias=True)


def _coerce_step(raw: dict[str, Any], objective: dict[str, Any] | None = None):
    """Validate authored/generated interaction data at the runtime boundary.

    Older plan generators emitted problem prompts without the newer response
    contract.  Normalize that legacy shape once, using the objective's own
    grounded outcome, instead of allowing an invalid private interaction to
    silently become an unanswered repeat.
    """
    from pydantic import TypeAdapter
    from app.schemas.learn import LearnStep
    data = dict(raw)
    if data.get("type") == "problem":
        data.setdefault("responseType", "short_answer")
        if not data.get("acceptedAnswers"):
            outcome = str((objective or {}).get("outcome") or (objective or {}).get("bottleneck") or "")
            if outcome:
                data["acceptedAnswers"] = [outcome]
        data.setdefault("solution", str((objective or {}).get("outcome") or data.get("prompt") or "Work through the stated relationship."))
    elif data.get("type") == "worked_step":
        if not data.get("acceptedAnswers"):
            outcome = str((objective or {}).get("outcome") or "")
            if outcome:
                data["acceptedAnswers"] = [outcome]
        data.setdefault("solution", str((objective or {}).get("outcome") or data.get("prompt") or "Work through the stated relationship."))
    return TypeAdapter(LearnStep).validate_python(data)


def validate_branch_proposal(session, *, original_concept_id: str, prerequisite_concept_id: str, depth: int) -> bool:
    """Validate an agent-proposed prerequisite branch against the saved plan."""
    if depth < 1 or depth > 3 or original_concept_id == prerequisite_concept_id:
        return False
    objective_ids = {str(item.get("id")) for item in (session.plan or {}).get("objectives", [])}
    if original_concept_id not in objective_ids or prerequisite_concept_id not in objective_ids:
        return False
    # Branch records use ``prerequisiteConceptId``; older runtime snapshots
    # used ``targetConceptId``.  Check both keys so a nested branch cannot
    # cycle back into a prerequisite that is already on the stack.
    return all(
        str(item.get("prerequisiteConceptId", item.get("targetConceptId"))) != prerequisite_concept_id
        for item in (_state(session).get("branchStack") or [])
    )


def push_prerequisite_branch(session, *, original_concept_id: str, prerequisite_concept_id: str, reason: str, return_scene_id: str) -> dict[str, Any] | None:
    state = _state(session)
    depth = len(state.get("branchStack") or []) + 1
    if not validate_branch_proposal(session, original_concept_id=original_concept_id, prerequisite_concept_id=prerequisite_concept_id, depth=depth):
        return None
    branch = {"originalConceptId": original_concept_id, "prerequisiteConceptId": prerequisite_concept_id, "reason": reason[:240], "depth": depth, "returnSceneId": return_scene_id, "returnObjectiveId": original_concept_id}
    state.setdefault("branchStack", []).append(branch)
    state["currentObjectiveId"] = prerequisite_concept_id
    session.state = state
    return branch


def return_from_prerequisite(session) -> dict[str, Any] | None:
    state = _state(session)
    stack = list(state.get("branchStack") or [])
    if not stack:
        return None
    branch = stack.pop()
    state["branchStack"] = stack
    state["currentObjectiveId"] = branch.get("returnObjectiveId")
    session.state = state
    return branch


def completion_met(session) -> bool:
    state = _state(session)
    concepts = list(state.get("concepts") or [])
    objectives = list((session.plan or {}).get("objectives") or [])
    if not objectives or state.get("revisitQueue") or state.get("branchStack"):
        return False
    by_id = {str(item.get("conceptId")): item for item in concepts}
    return all(
        by_id.get(str(item.get("id")), {}).get("state") == "DEMONSTRATED"
        and _objective_evidence_sufficient(item, by_id.get(str(item.get("id")), {}))
        for item in objectives
    )


def _objective_evidence_sufficient(objective: dict[str, Any], concept: dict[str, Any]) -> bool:
    """Require stronger evidence when an objective tests doing, not just naming.

    Authored plans do not always carry an explicit content policy. Infer the
    minimum evidence requirement from their interaction assets so a pair of
    recognition checks cannot complete a procedural/process objective before
    the learner has demonstrated application (and, where possible, transfer).
    """
    types = {str(step.get("type")) for step in (objective.get("steps") or []) if isinstance(step, dict)}
    title = f"{objective.get('title', '')} {objective.get('outcome', '')}".casefold()
    requires_application = bool(types & {"problem", "numeric", "worked_step", "prediction", "ordering"}) or any(
        token in title for token in ("calculate", "solve", "process", "mechanism", "energy", "force", "application", "apply")
    )
    if requires_application and int(concept.get("applicationEvidence", 0) or 0) < 1:
        return False
    if requires_application:
        # Success while the full/guided teaching surface is visible may justify
        # fading support, but it is not proof of independent application.
        if int(concept.get("independentSuccesses", 0) or 0) < 1:
            return False
        if int(concept.get("transferEvidence", 0) or 0) < 1:
            return False
    return True


def persist_scene_revision(session, scene: LearningScene, private: dict[str, Any] | None = None, *, event_id: str | None = None, db=None) -> LearningScene:
    state = _state(session)
    previous = load_current_scene(session)
    next_revision = max(int(scene.revision or 0), int(previous.revision if previous else 0) + 1)
    scene = scene.model_copy(update={"revision": next_revision})
    history = list(state.get("sceneHistory") or [])
    history.append({"sceneId": scene.id, "revision": scene.revision, "objectiveId": scene.objective_id, "eventId": event_id, "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()})
    # Visual state is owned by the persisted scene. Any transient composer
    # handoff under state.visualState must not survive this boundary as a
    # competing source of truth.
    state.pop("visualState", None)
    state.update({"runtimeVersion": RUNTIME_VERSION, "planSemanticsVersion": PLAN_SEMANTICS_VERSION, "currentScene": scene.model_dump(by_alias=True), "currentScenePrivate": private, "sceneHistory": history[-8:], "currentObjectiveId": scene.objective_id})
    session.state = state
    if db is not None:
        db.flush()
    return scene


def apply_evaluation(session, evaluation: Any, *, interaction_id: str | None = None) -> dict[str, Any]:
    """Phase-2 seam: evidence mutation is completed by the Phase-3 runtime."""
    return {"evaluation": evaluation, "interactionId": interaction_id}


def apply_scene_message(session, *, message: str, answer: str, source_section_ids: list[str] | None = None, source_block_ids: list[str] | None = None, visual_action: dict[str, Any] | None = None, block_kind: str = "tutor_message", block_label: str = "Ask Lucent", db=None) -> LearningScene | None:
    """Apply an Ask Lucent response to the same persisted LearningScene."""
    from app.schemas.learn import LearningSceneBlock, LearningVisualState
    scene = load_current_scene(session)
    if scene is None:
        return None
    blocks = list(scene.blocks)
    block = LearningSceneBlock(id=bounded_id("ask", session.id, message[:80]), kind=block_kind, label=block_label, title=None, content=answer[:900], sourceSectionIds=list(source_section_ids or [])[:8], sourceBlockIds=list(source_block_ids or [])[:12])
    # Reframes are one active teaching surface. Older sessions may contain
    # reframe blocks under different kinds (e.g. explanation then analogy),
    # so remove those prior variants before writing the new one.
    if block_kind in {"analogy", "explanation", "tutor_message"} and re.search(r"another way|reframe|ask lucent", f"{block_label} {message}", re.I):
        blocks = [existing for existing in blocks if not (
            existing.kind == "analogy" or
            (existing.kind in {"explanation", "tutor_message"} and re.search(r"another way|reframe|ask lucent", str(existing.label or ""), re.I))
        )]
    # Ask/tutor interruptions refine the current teaching surface. Keep one
    # learner-facing block for a given role instead of stacking every prior
    # explanation/analogy into a long column of competing text boxes.
    existing_message = next((index for index in range(len(blocks) - 1, -1, -1) if blocks[index].kind == block_kind), None)
    if existing_message is not None:
        blocks[existing_message] = block
    else:
        blocks.append(block)
    visual_state = scene.visual_state
    if visual_action:
        # Ask Lucent may introduce a grounded visual when the active scene has
        # none.  The spec is carried through the validated candidate step;
        # arbitrary model-generated visual JSON is never accepted here.
        visual_spec = visual_action.get("visualSpec")
        visual_ref = visual_action.get("visualRef")
        can_add_visual = bool(visual_spec or visual_ref)
        if can_add_visual:
            try:
                from app.schemas.learn import VisualSpec
                visual_block = LearningSceneBlock(id=bounded_id("ask-visual", session.id, message[:80]), kind="visual", label="Watch", title=None, content="Watch the source-supported relationship change.", visualSpec=VisualSpec.model_validate(visual_spec) if visual_spec else None, visualRef=visual_ref if visual_ref else None, sourceSectionIds=list(source_section_ids or [])[:8], sourceBlockIds=list(source_block_ids or [])[:12])
                # One authoritative visual surface: a new grounded view
                # replaces the prior visual block in place so the scene does
                # not grow a second competing visual card.
                visual_index = next((index for index, existing in enumerate(blocks) if existing.visual_spec is not None or existing.visual_ref is not None), None)
                if visual_index is None:
                    blocks.append(visual_block)
                else:
                    blocks[visual_index] = visual_block
            except Exception:
                pass
        updates: dict[str, Any] = {"stage": int(visual_action.get("stage", visual_state.stage if visual_state else 0))}
        if visual_action.get("nodeId"):
            updates["highlightedElementIds"] = [str(visual_action["nodeId"])]
        visual_state = visual_state.model_copy(update=updates) if visual_state else LearningVisualState(**updates)
    scene = scene.model_copy(update={"blocks": blocks[-8:], "visual_state": visual_state})
    return persist_scene_revision(session, scene, _state(session).get("currentScenePrivate"), event_id=bounded_id("ask-event", session.id, message[:80]), db=db)


def apply_visual_event(session, *, event: str, stage: int | None = None, element_id: str | None = None, db=None) -> LearningScene | None:
    """Mutate only the canonical visual state and persist a new scene revision."""
    from app.schemas.learn import LearningVisualState
    scene = load_current_scene(session)
    if scene is None:
        return None
    current = scene.visual_state or LearningVisualState()
    updates: dict[str, Any] = {}
    if event in {"set_stage", "replay"}:
        updates["stage"] = 0 if event == "replay" else int(stage if stage is not None else current.stage)
    if event == "highlight":
        updates["highlightedElementIds"] = [str(element_id)] if element_id else []
    visual = current.model_copy(update=updates)
    return persist_scene_revision(session, scene.model_copy(update={"visual_state": visual}), _state(session).get("currentScenePrivate"), event_id=bounded_id("visual-event", session.id, event, stage, element_id), db=db)


def build_student_feedback(evaluation: Any, *, interaction_id: str, source_blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"result": getattr(evaluation, "result", "insufficient_evidence"), "message": getattr(evaluation, "evidence", "Let's look at this together."), "respondsToInteractionId": interaction_id, "sourceSectionIds": [str(item) for block in (source_blocks or []) for item in block.get("sectionIds", [])][:8], "sourceBlockIds": [str(item) for block in (source_blocks or []) for item in block.get("blockIds", [])][:12]}


def _objective_has_remaining_candidates(objective: dict[str, Any], state: dict[str, Any], session=None) -> bool:
    """Whether an objective still has an unanswered/unused authored candidate.

    Selecting an objective by "not DEMONSTRATED" alone is not enough: a
    struggling objective that has already exhausted its own candidate pool is
    also "not DEMONSTRATED", so two such objectives would bounce the learner
    back and forth between them forever instead of ever completing.
    """
    answered = _answered_interaction_ids(session, state) if session is not None else set(state.get("answeredInteractionIds") or [])
    used_teaching = set(state.get("usedTeachingIds") or [])
    for raw in objective.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        step_id = str(raw.get("id"))
        if raw.get("type") in {"teach", "walkthrough"}:
            if step_id not in used_teaching:
                return True
        elif step_id not in answered:
            return True
    return False


def _advance_objective_or_complete(session, state: dict[str, Any], inert_scene: LearningScene, *, exclude_concept_id: str, event_id: str | None, db=None) -> tuple[LearningScene, dict[str, Any] | None]:
    """Move on once an objective's candidate pool is exhausted.

    Without this, a scene with no remaining practice/teaching candidates is
    re-persisted unchanged (only the revision bumps), so Continue never
    reaches the next objective or a completed session -- it just dead-ends on
    the same inert scene forever.
    """
    # persist_scene_revision() (and _legacy_scene()'s own composition) re-read
    # session.state from scratch, so the caller's in-memory evidence mutations
    # must be committed onto the session before any persistence call below --
    # otherwise a response that happens to exhaust the last candidate has its
    # graded evidence silently discarded.
    # Feedback/hints are scoped to the objective that produced them; carrying
    # them across a transition shows the learner a message about a concept
    # that is no longer on screen.
    state.pop("lastFeedback", None)
    state.pop("lastFeedbackKind", None)
    session.state = state
    next_objective_id = select_target_objective(session, exclude_concept_id=exclude_concept_id)
    next_objective = _objective(session.plan or {}, next_objective_id) if next_objective_id is not None else None
    if next_objective is not None:
        scene, private = _legacy_scene(session, next_objective)
        state["currentObjectiveId"] = str(next_objective.get("id"))
        session.state = state
        scene = persist_scene_revision(session, scene, private, event_id=event_id, db=db)
        return scene, private
    # Candidate exhaustion is not evidence of mastery. Keep the session active
    # and schedule one bounded retrieval scene when the objective still lacks
    # its required evidence, instead of presenting a misleading completion.
    if not completion_met(session):
        current_objective = _objective(session.plan or {}, exclude_concept_id)
        concept = next((item for item in state.get("concepts", []) if str(item.get("conceptId")) == str(exclude_concept_id)), None)
        if current_objective is not None and concept is not None and int(concept.get("reviewVisits", 0) or 0) < 1:
            concept["state"] = "NEEDS_REVIEW"
            concept["reviewDue"] = "LATER_THIS_SESSION"
            state["revisitQueue"] = list(dict.fromkeys([*state.get("revisitQueue", []), str(exclude_concept_id)]))[:12]
            state["revisitMode"] = True
            session.state = state
            review_scene, review_private = _legacy_scene(session, current_objective)
            review_scene = persist_scene_revision(session, review_scene, review_private, event_id=event_id, db=db)
            return review_scene, review_private
    scene = persist_scene_revision(session, inert_scene, None, event_id=event_id, db=db)
    session.status = "completed"
    session.ended_reason = "evidence_sufficient" if completion_met(session) else "objectives_exhausted"
    if db is not None:
        db.flush()
    return scene, None


def process_tutor_event(session, event: Any, *, db=None, source_blocks: list[dict[str, Any]] | None = None):
    """Process one bounded event and return the authoritative scene/private pair.

    This is intentionally the only response/continue decision seam.  Phase 3
    extends the operation vocabulary, but all persistence already flows through
    this function rather than a cursor-based router branch.
    """
    from pydantic import TypeAdapter
    from app.models.learn import LearnAttempt
    from app.services.learn_engine import build_remediation_step, evaluate_step, is_explicit_uncertainty, public_step
    from app.services.learn_scene import compose_learning_scene
    from app.services.learn_tutor import choose_tutor_decision, diagnose_response

    scene, private = ensure_runtime_state(session, db=db)
    state = _state(session)
    # Carry the authoritative scene visual into the composer as a transient
    # handoff for this turn.  The scene remains the sole persisted owner;
    # persist_scene_revision() removes this compatibility handoff before
    # writing session.state, while subsequent scene revisions retain the
    # current stage/highlights instead of resetting to stage zero.
    if scene.visual_state is not None:
        state["visualState"] = scene.visual_state.model_dump(by_alias=True)
    event_type = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else "CONTINUE")
    if event_type == "ASK_INTERACTION_RESPONSE":
        payload = event if isinstance(event, dict) else {}
        inline = scene.inline_interaction
        interaction_id = str(payload.get("interactionId") or "")
        if inline is None or str(inline.id) != interaction_id:
            raise ValueError("That Ask Lucent interaction is no longer active")
        objective = _objective(session.plan or {}, scene.objective_id)
        if objective is None:
            raise ValueError("The learning objective is no longer active")
        from app.services.learn_engine import evaluate_step
        private_inline = state.get("askInlinePrivate") or {}
        step = _coerce_step(private_inline, objective) if str(private_inline.get("id")) == interaction_id else _coerce_step(inline.model_dump(by_alias=True), objective)
        response = payload.get("response")
        response_text = response.get("response") if isinstance(response, dict) else response
        option_id = response.get("optionId") if isinstance(response, dict) else payload.get("optionId")
        ordered_ids = response.get("orderedIds") if isinstance(response, dict) else payload.get("orderedIds")
        evaluation = evaluate_step(step, response=response_text, option_id=option_id, ordered_ids=ordered_ids)
        # Inline Ask practice is intentionally outside the primary evidence
        # progression, but open responses still need the same original-source
        # grounding as the primary interaction. Retrieve with the inline
        # interaction's own anchors (never the primary practice's private
        # payload) before asking the diagnosis model to interpret the answer.
        source_context_text = ""
        source_generation = state.get("sourceGeneration")
        if db is not None and source_generation:
            from uuid import UUID
            from app.services.retrieval import (
                RetrievalStatus,
                SourceContextUnavailable,
                build_source_query,
                retrieve_source,
                serialize_source_context,
            )

            query = build_source_query(
                purpose="ask_inline_response",
                objective_title=str(objective.get("title") or ""),
                objective_outcome=str(objective.get("outcome") or ""),
                active_prompt=str(getattr(step, "prompt", "") or ""),
                learner_text=str(response_text or ""),
                objective_id=str(objective.get("id") or ""),
            )
            retrieved = retrieve_source(
                db,
                user_id=session.user_id,
                document_id=session.document_id,
                expected_generation=UUID(str(source_generation)),
                query=query,
                anchor_block_ids=list(getattr(step, "source_block_ids", []) or []),
            )
            if retrieved.status != RetrievalStatus.SUPPORTED:
                raise SourceContextUnavailable(retrieved.status)
            source_context_text = serialize_source_context(retrieved, max_chars=5000)
        if evaluation.result != "correct" and response_text and not is_explicit_uncertainty(str(response_text)) and step.type in {
            "short_answer", "problem", "numeric", "fill_blank", "teach_back", "worked_step",
        }:
            expected = " ".join(getattr(step, "accepted_answers", []) or []) or str(getattr(step, "answer", ""))
            if not expected and getattr(step, "required_concepts", None):
                expected = " ".join(str(item) for item in step.required_concepts)
            evaluation = diagnose_response(
                prompt=getattr(step, "prompt", ""),
                expected=expected,
                response=str(response_text),
                source_context=source_context_text,
                fallback=evaluation,
            )
        feedback = "That’s right—your answer matches the idea we’re practicing." if evaluation.result == "correct" else "Not quite. Recheck the explanation above and look for the relationship it emphasizes."
        feedback_block = LearningSceneBlock(
            id=bounded_id("ask-feedback", session.id, interaction_id, scene.revision),
            kind="feedback",
            label="Feedback",
            content=feedback,
            sourceSectionIds=list(getattr(step, "source_section_ids", []) or scene.source_section_ids),
            sourceBlockIds=list(getattr(step, "source_block_ids", []) or scene.source_block_ids),
        )
        updated = scene.model_copy(update={"inline_interaction": None, "blocks": [*scene.blocks, feedback_block][-6:]})
        state.pop("askInlinePrivate", None)
        session.state = state
        private = state.get("currentScenePrivate")
        return persist_scene_revision(session, updated, private, event_id=bounded_id("ask-response", session.id, interaction_id), db=db), private
    if event_type == "ASK_LUCENT":
        # Ask Lucent is an interruption in the same tutor runtime. The route
        # performs auth, retrieval, and provider validation, then supplies the
        # bounded learner-facing result here for authoritative scene execution.
        payload = event if isinstance(event, dict) else {}
        updated = apply_scene_message(
            session,
            message=str(payload.get("message") or "Explain this another way"),
            answer=str(payload.get("answer") or "Let's look at this together."),
            source_section_ids=list(payload.get("sourceSectionIds") or []),
            source_block_ids=list(payload.get("sourceBlockIds") or []),
            visual_action=payload.get("visualAction"),
            block_kind=str(payload.get("blockKind") or "tutor_message"),
            block_label=str(payload.get("blockLabel") or "Ask Lucent"),
            db=db,
        )
        inline_raw = payload.get("inlineInteraction")
        if updated is not None and isinstance(inline_raw, dict):
            try:
                inline = _coerce_step(inline_raw, _objective(session.plan or {}, updated.objective_id) or {})
                updated = updated.model_copy(update={"inline_interaction": public_step(inline)})
                state["askInlinePrivate"] = inline.model_dump(by_alias=True)
                session.state = state
                # Keep the primary private interaction untouched.  The inline
                # Ask question is an interruption, not a second progression
                # cursor; its answer is evaluated by the dedicated Ask
                # interaction endpoint.
                current_private = _state(session).get("currentScenePrivate")
                updated = persist_scene_revision(session, updated, current_private, event_id=bounded_id("ask-inline", session.id, inline.id), db=db)
                return updated, current_private
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Ask inline interaction rejected: %s", exc)
        replacement_raw = payload.get("replacementStep")
        if updated is not None and isinstance(replacement_raw, dict):
            try:
                replacement = _coerce_step(replacement_raw, _objective(session.plan or {}, updated.objective_id) or {})
                from app.services.learn_engine import public_step
                practice = LearningSceneBlock(id=bounded_id("practice", session.id, replacement.id), kind="practice", label="Try", title=replacement.title, content=getattr(replacement, "prompt", None) or getattr(replacement, "content", None), step=public_step(replacement), sourceSectionIds=list(getattr(replacement, "source_section_ids", []) or []), sourceBlockIds=list(getattr(replacement, "source_block_ids", []) or []))
                blocks = [block for block in updated.blocks if block.kind != "practice"] + [practice]
                updated = updated.model_copy(update={"blocks": blocks[-6:], "response_interaction_id": replacement.id})
                objective_for_private = _objective(session.plan or {}, updated.objective_id) or {}
                private = _private_for_rendered_scene(updated, objective_id=str(updated.objective_id), fallback_step=replacement, objective=objective_for_private)
                updated = persist_scene_revision(session, updated, private, event_id=bounded_id("ask-recompose", session.id, replacement.id), db=db)
                return updated, private
            except Exception as exc:
                # Invalid Ask replacement is ignored; the conversational scene
                # remains authoritative and usable.
                import logging
                logging.getLogger(__name__).warning("Ask replacement rejected: %s", exc)
        return updated or scene, _state(session).get("currentScenePrivate")
    objective = _objective(session.plan or {}, scene.objective_id)
    if objective is None:
        return scene, private
    steps = list(objective.get("steps") or [])
    adapter = TypeAdapter(LearnStep)
    current = None
    if private and private.get("interaction"):
        try:
            current = _coerce_step(private["interaction"], objective)
        except Exception:
            raw = next((item for item in steps if str(item.get("id")) == str(private.get("interaction", {}).get("id"))), None)
            try:
                current = _coerce_step(raw, objective) if raw else None
            except Exception:
                current = None
    if current is None:
        practice = next((block.step for block in scene.blocks if block.kind == "practice" and block.step), None)
        if practice is not None:
            try:
                current = _coerce_step(practice.model_dump(by_alias=True), objective)
            except Exception:
                raw = next((item for item in steps if str(item.get("id")) == str(getattr(practice, "id", ""))), None)
                try:
                    current = _coerce_step(raw, objective) if raw else None
                except Exception:
                    current = None

    # A continue event acknowledges the currently composed scene; it must not
    # manufacture a second step or rewind to a teaching asset.  Replanning is
    # triggered by a learner response (or an explicit Ask/visual event).
    if event_type := event_type:
        # Continue is a no-op only while a real active practice target is
        # already present. Teaching-only scenes must advance/recompose.
        has_rendered_practice = any(block.kind == "practice" and block.step and str(block.step.id) == str(scene.response_interaction_id) for block in scene.blocks)
        if event_type == "CONTINUE" and private is not None and current is not None and scene.response_interaction_id and has_rendered_practice:
            return scene, private
        if event_type == "CONTINUE" and private is None:
            # A persisted teaching-only scene from an older runtime may not
            # have recorded usedTeachingIds. Mark authored teaching assets as
            # consumed before replanning so Continue cannot replay the same
            # explanation forever.
            state["usedTeachingIds"] = list(dict.fromkeys([*(state.get("usedTeachingIds") or []), *[str(item.get("id")) for item in steps if isinstance(item, dict) and item.get("type") in {"teach", "walkthrough"}]]))
            session.state = state

    event_type = event_type or "CONTINUE"
    response = getattr(event, "response", None) if not isinstance(event, dict) else event.get("response")
    if isinstance(response, dict):
        response_text = response.get("response")
        option_id = response.get("optionId")
        ordered_ids = response.get("orderedIds")
    else:
        response_text = response
        option_id = None
        ordered_ids = None

    source_context_text = ""
    source_generation = state.get("sourceGeneration")
    if source_blocks is None and db is not None and source_generation:
        from uuid import UUID
        from app.services.retrieval import (
            RetrievalStatus, SourceContextUnavailable, build_source_query, retrieve_source, serialize_source_context,
        )
        concept_snapshot = next((item for item in state.get("concepts", []) if item.get("conceptId") == str(objective.get("id"))), {})
        retrieval_query = build_source_query(
            purpose="response" if event_type == "RESPONSE" else "continue",
            objective_title=str(objective.get("title") or ""),
            objective_outcome=str(objective.get("outcome") or ""),
            active_prompt=str(getattr(current, "prompt", "") or getattr(current, "content", "") or ""),
            learner_text=str(response_text or ""),
            misconception=str((concept_snapshot.get("misconceptions") or [""])[-1]),
            objective_id=str(objective.get("id")),
        )
        retrieved = retrieve_source(
            db,
            user_id=session.user_id,
            document_id=session.document_id,
            expected_generation=UUID(str(source_generation)),
            query=retrieval_query,
            anchor_block_ids=list(getattr(current, "source_block_ids", []) or objective.get("sourceBlockIds", [])),
        )
        if retrieved.status != RetrievalStatus.SUPPORTED:
            raise SourceContextUnavailable(retrieved.status)
        source_blocks = retrieved.observation_blocks()
        source_context_text = serialize_source_context(retrieved)
    elif source_blocks:
        source_context_text = "\n\n".join(str(block.get("text") or "") for block in source_blocks)[:8000]

    evaluation = None
    concept_id = str(objective.get("id"))
    concept = next((item for item in state.get("concepts", []) if item.get("conceptId") == concept_id), {"conceptId": concept_id, "title": objective.get("title", "Concept"), "state": "INTRODUCED"})
    if event_type == "RESPONSE" and current is not None:
        from app.services.adaptive_policy import next_scaffold, prerequisite_ids, review_due
        evaluation = evaluate_step(current, response=response_text, option_id=option_id, ordered_ids=ordered_ids)
        if evaluation.result != "correct" and response_text and not is_explicit_uncertainty(response_text) and current.type in {"short_answer", "problem", "numeric", "fill_blank", "teach_back", "worked_step"}:
            expected = " ".join(getattr(current, "accepted_answers", []) or []) or str(getattr(current, "answer", ""))
            if not expected and getattr(current, "required_concepts", None):
                expected = " ".join(str(item) for item in current.required_concepts)
            evaluation = diagnose_response(prompt=getattr(current, "prompt", ""), expected=expected, response=str(response_text), source_context=source_context_text, fallback=evaluation)
        now = datetime.now(timezone.utc).isoformat()
        concept = dict(concept)
        concept.update({"attempts": int(concept.get("attempts", 0)) + 1, "lastSeen": now, "lastResult": evaluation.result})
        hints_used = int((state.get("hints") or {}).get(current.id, 0))
        # A no-hint success can justify one bounded fade, but it is only truly
        # independent evidence when the learner answered on an independent or
        # transfer scene with the worked/guided surface already removed.
        can_fade = hints_used == 0
        current_scaffold = str(concept.get("scaffold") or concept.get("scaffoldingLevel") or "FULL")
        independent = can_fade and current_scaffold in {"INDEPENDENT", "TRANSFER"}
        is_transfer_task = str(current.id).startswith("transfer-")
        transfer = is_transfer_task and current.type in {"problem", "teach_back", "prediction", "numeric"} and independent and evaluation.result == "correct"
        concept["scaffold"] = next_scaffold(concept.get("scaffold"), evaluation.result, hints_used, independent=can_fade)
        concept["scaffoldingLevel"] = concept["scaffold"]
        concept["hintDependence"] = int(concept.get("hintDependence", 0)) + (1 if hints_used else 0)
        concept["scaffoldDependence"] = int(concept.get("scaffoldDependence", 0)) + (1 if not independent else 0)
        concept["reviewDue"] = review_due(evaluation.result, hints=hints_used, scaffold=concept["scaffold"], transfer=transfer, delayed=bool(state.get("revisitMode")))
        if evaluation.result == "correct":
            concept["correct"] = int(concept.get("correct", 0)) + 1
            evidence_counter = "independentSuccesses" if independent else "assistedSuccesses"
            concept[evidence_counter] = int(concept.get(evidence_counter, 0)) + 1
            concept["state"] = "DEVELOPING" if int(concept.get("correct", 0)) < 2 or not _objective_evidence_sufficient(objective, concept) else "DEMONSTRATED"
            evidence_key = {
                "multiple_choice": "recognitionEvidence",
                "prediction": "applicationEvidence",
                "problem": "applicationEvidence",
                "numeric": "applicationEvidence",
                "worked_step": "applicationEvidence",
                "teach_back": "explanationEvidence",
                "short_answer": "recallEvidence",
                "fill_blank": "recallEvidence",
                "ordering": "applicationEvidence",
                "matching": "recognitionEvidence",
                "labeling": "recognitionEvidence",
            }.get(current.type)
            if evidence_key:
                concept[evidence_key] = int(concept.get(evidence_key, 0)) + 1
            if transfer:
                concept["transferEvidence"] = int(concept.get("transferEvidence", 0)) + 1
        elif evaluation.result == "partially_correct":
            concept["partiallyCorrect"] = int(concept.get("partiallyCorrect", 0)) + 1; concept["state"] = "DEVELOPING"
        elif evaluation.result == "incorrect":
            concept["incorrect"] = int(concept.get("incorrect", 0)) + 1; concept["state"] = "STRUGGLING" if int(concept.get("incorrect", 0)) >= 2 else "DEVELOPING"
            if evaluation.misconception and evaluation.misconception not in concept.setdefault("misconceptions", []): concept["misconceptions"].append(evaluation.misconception)
        else:
            concept["insufficientEvidence"] = int(concept.get("insufficientEvidence", 0)) + 1
            concept["uncertaintyCount"] = int(concept.get("uncertaintyCount", 0)) + 1
            concept["state"] = "DEVELOPING"
        state["lastErrorContext"] = current.model_dump(by_alias=True)
        # Lightweight, interpretable review scheduling.  Immediate supported
        # success is revisited later; independent/transfer evidence earns a
        # future review instead of being treated as permanent mastery.
        if evaluation.result in {"incorrect", "partially_correct", "insufficient_evidence"}:
            concept["reviewDue"] = "LATER_THIS_SESSION"
            queue = list(state.get("revisitQueue") or [])
            if concept_id not in queue and int(concept.get("reviewVisits", 0) or 0) < 1:
                queue.append(concept_id)
            state["revisitQueue"] = queue[:12]
        elif evaluation.result == "correct":
            if hints_used:
                concept["reviewDue"] = "LATER_THIS_SESSION"
                queue = list(state.get("revisitQueue") or [])
                if concept_id not in queue:
                    queue.append(concept_id)
                state["revisitQueue"] = queue[:12]
            elif concept.get("state") == "DEMONSTRATED":
                concept["reviewDue"] = "FUTURE_REVIEW"
            else:
                concept["reviewDue"] = "NEXT_SESSION"
            if concept.get("state") == "DEMONSTRATED":
                state["revisitQueue"] = [cid for cid in state.get("revisitQueue", []) if cid != concept_id]
        concept["interactionTypes"] = list(dict.fromkeys(list(concept.get("interactionTypes", [])) + [current.type]))
        existing_concepts = list(state.get("concepts", []))
        if any(item.get("conceptId") == concept_id for item in existing_concepts):
            state["concepts"] = [concept if item.get("conceptId") == concept_id else item for item in existing_concepts]
        else:
            state["concepts"] = existing_concepts + [concept]
        state.setdefault("recentAttempts", []).append({"interactionId": current.id, "conceptId": concept_id, "type": current.type, "result": evaluation.result})
        state["recentAttempts"] = state["recentAttempts"][-8:]
        answered = list(state.get("answeredInteractionIds") or [])
        if current.id not in answered:
            answered.append(current.id)
        state["answeredInteractionIds"] = answered[-32:]
        if db is not None:
            db.add(LearnAttempt(session_id=session.id, objective_id=concept_id, step_id=current.id, step_type=current.type, response=str(response_text or option_id or ",".join(ordered_ids or [])), result=evaluation.result, attempt_number=int(concept.get("attempts", 1)), hints_used=0, evaluation=evaluation.model_dump(by_alias=True)))

        # A successful prerequisite repair returns to the paused parent
        # concept through the same scene runtime.  The branch stack is popped
        # only after evidence is recorded, so the parent replan can observe
        # the repaired prerequisite.
        if evaluation.result == "correct" and state.get("branchStack"):
            branch = return_from_prerequisite(session)
            if branch:
                state = _state(session)
                parent = _objective(session.plan or {}, branch.get("returnObjectiveId"))
                if parent is not None:
                    parent_steps = list(parent.get("steps") or [])
                    parent_candidates = [adapter.validate_python(raw) for raw in parent_steps if isinstance(raw, dict)]
                    answered_parent = set(state.get("answeredInteractionIds") or [])
                    parent_next = next((item for item in parent_candidates if item.id not in answered_parent and item.type not in {"teach", "walkthrough"}), None) or next((item for item in parent_candidates if item.id not in answered_parent), None)
                    if parent_next is None:
                        # Returning from a prerequisite must not depend on an
                        # unanswered authored asset. Compose a bounded parent
                        # application check in scene state instead of replaying
                        # the answered interaction.
                        parent_next = TeachBackStep(
                            id=bounded_id("parent-retry", session.id, branch.get("returnObjectiveId"), len(state.get("recentAttempts", []))),
                            type="teach_back",
                            title="Apply the idea again",
                            prompt=f"Now that the supporting idea is clear, explain how it applies to {parent.get('title', 'the original concept')}.",
                            requiredConcepts=_required_concepts(str(parent.get("outcome") or parent.get("title") or "the concept")),
                            hints=[],
                            sourceSectionIds=list(parent.get("sourceSectionIds", [])),
                            sourceBlockIds=list(parent.get("sourceBlockIds", [])),
                        )
                    if parent_next is not None:
                        parent_concept = next((item for item in state.get("concepts", []) if item.get("conceptId") == branch.get("returnObjectiveId")), {"conceptId": branch.get("returnObjectiveId"), "state": "DEVELOPING", "scaffold": "GUIDED"})
                        parent_action = TutorAction(id=bounded_id("action", branch.get("returnObjectiveId"), parent_next.id, "return"), type="ask_free_response", conceptId=str(branch.get("returnObjectiveId")), stepId=parent_next.id, rationale="Return to the original concept after prerequisite repair.")
                        parent_decision = TutorDecision(targetConcept=str(branch.get("returnObjectiveId")), teachingAction=parent_action.type, pedagogicalGoal="VERIFY_UNDERSTANDING", pedagogicalStrategy="GUIDED_DISCOVERY", scaffoldLevel=parent_concept.get("scaffold", "GUIDED"), nextStepId=parent_next.id, transitionMessage="That supporting idea is in place. Now let’s apply it back to the original concept.", rationale="Prerequisite evidence is sufficient to resume the parent concept.")
                        rendered = compose_learning_scene(session_id=str(session.id), objective=parent, steps=parent_steps, step_index=0, current_step=parent_next, action=parent_action, decision=parent_decision, concept=parent_concept, state=state, feedback="Good — the supporting idea is in place.", feedback_kind="correct", evaluation=evaluation)
                        private_next = _private_for_rendered_scene(rendered, objective_id=str(branch.get("returnObjectiveId")), decision=parent_decision, fallback_step=parent_next, objective=parent)
                        return persist_scene_revision(session, rendered, private_next, event_id=event_id_value if 'event_id_value' in locals() else None, db=db), private_next

    # A bounded prerequisite branch is an agent-proposed transition, validated
    # against the objective graph before any scene is composed.  The branch is
    # only taken when the prerequisite is actually weak; demonstrated
    # prerequisites never interrupt the current concept.
    if evaluation and evaluation.result in {"incorrect", "partially_correct"} and not (state.get("branchStack") or []):
        from app.services.adaptive_policy import prerequisite_ids
        weak_ids = prerequisite_ids(objective, state.get("concepts", []))
        prerequisite_id = next((cid for cid in weak_ids if cid != concept_id), None)
        if prerequisite_id:
            branch = push_prerequisite_branch(session, original_concept_id=concept_id, prerequisite_concept_id=prerequisite_id, reason=evaluation.misconception or "A prerequisite needs a quick check first.", return_scene_id=scene.id)
            state = _state(session)
            prerequisite = _objective(session.plan or {}, prerequisite_id)
            if branch and prerequisite:
                prereq_steps = list(prerequisite.get("steps") or [])
                prereq_candidates = [adapter.validate_python(raw) for raw in prereq_steps if isinstance(raw, dict)]
                prereq_next = next((item for item in prereq_candidates if item.type in {"teach", "walkthrough"}), None) or next((item for item in prereq_candidates if item.id not in set(state.get("answeredInteractionIds") or [])), None)
                if prereq_next:
                    prereq_concept = next((item for item in state.get("concepts", []) if item.get("conceptId") == prerequisite_id), {"conceptId": prerequisite_id, "state": "NOT_SEEN", "scaffold": "FULL"})
                    prereq_action = TutorAction(id=bounded_id("action", prerequisite_id, prereq_next.id, "prerequisite"), type="teach_concept" if prereq_next.type in {"teach", "walkthrough"} else "ask_free_response", conceptId=prerequisite_id, stepId=prereq_next.id, rationale="Repair a prerequisite before returning to the current concept.")
                    prereq_decision = TutorDecision(targetConcept=prerequisite_id, teachingAction=prereq_action.type, pedagogicalGoal="REPAIR_PREREQUISITE", pedagogicalStrategy="PREREQUISITE_REPAIR", scaffoldLevel=prereq_concept.get("scaffold", "FULL"), nextStepId=prereq_next.id, transitionMessage="Let's make sure the supporting idea is clear first.")
                    session.state = state
                    rendered = compose_learning_scene(session_id=str(session.id), objective=prerequisite, steps=prereq_steps, step_index=0, current_step=prereq_next, action=prereq_action, decision=prereq_decision, concept=prereq_concept, state=state, feedback=evaluation.evidence, feedback_kind="info", evaluation=evaluation)
                    private_next = _private_for_rendered_scene(rendered, objective_id=prerequisite_id, decision=prereq_decision, fallback_step=prereq_next, objective=prerequisite)
                    return persist_scene_revision(session, rendered, private_next, event_id=getattr(event, "id", None) if not isinstance(event, dict) else event.get("id"), db=db), private_next

    # A failed or uncertain response becomes one cohesive intervention: a
    # specific teaching surface followed by a new check of that same idea.
    # Previously the runtime selected an unused generic teaching asset and
    # the scene compiler attached the next authored question, producing an
    # unrelated content -> quiz transition despite having the failed private
    # interaction available here.
    if (
        evaluation is not None
        and evaluation.result in {"incorrect", "partially_correct"}
        and (
            int(concept.get("incorrect", 0) or 0)
            + int(concept.get("partiallyCorrect", 0) or 0)
        ) >= 3
    ):
        concept["state"] = "NEEDS_REVIEW"
        concept["reviewDue"] = "NEXT_SESSION"
        state["revisitQueue"] = list(dict.fromkeys([*state.get("revisitQueue", []), concept_id]))[:12]
        state["concepts"] = [concept if item.get("conceptId") == concept_id else item for item in state.get("concepts", [])]
        session.state = state
        review_scene = scene.model_copy(update={"blocks": [block for block in scene.blocks if block.kind != "practice"], "response_interaction_id": None, "progress": {"status": "needs_review"}})
        return _advance_objective_or_complete(
            session, state, review_scene, exclude_concept_id=concept_id,
            event_id=getattr(event, "id", None) if not isinstance(event, dict) else event.get("id"), db=db,
        )

    if evaluation is not None and evaluation.result in {"incorrect", "partially_correct", "insufficient_evidence"} and current is not None:
        from app.services.learn_engine import build_remediation_step

        attempt_no = max(int(concept.get("attempts", 0)), 1)
        repair_id = bounded_id("repair", concept_id, attempt_no, current.id, int(scene.revision or 0) + 1)
        try:
            repair = build_remediation_step(objective, current, repair_id)
        except Exception:
            outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
            repair = ShortAnswerStep(
                id=repair_id,
                type="short_answer",
                title=f"Apply {objective.get('title', 'the idea')}",
                prompt=f"Using what was just explained, describe the key relationship in {objective.get('title', 'this concept')}.",
                acceptedAnswers=[outcome],
                requiredConcepts=_required_concepts(outcome),
                hints=[f"Start from this source-supported idea: {outcome[:220]}"],
                feedbackIncorrect=f"Return to the relationship described here: {outcome[:260]}",
                sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                sourceBlockIds=list(objective.get("sourceBlockIds", [])),
            )

        teaching_content = str(
            evaluation.misconception
            or getattr(current, "feedback_incorrect", None)
            or objective.get("bottleneck")
            or objective.get("outcome")
            or objective.get("title")
        )
        teaching = TeachStep(
            id=bounded_id("teach-repair", concept_id, attempt_no, current.id),
            type="teach",
            title=f"Let's clarify {objective.get('title', 'the idea')}",
            content=teaching_content[:900],
            sourceSectionIds=list(objective.get("sourceSectionIds", [])),
            sourceBlockIds=list(objective.get("sourceBlockIds", [])),
        )
        fallback_action = TutorAction(
            id=bounded_id("action", concept_id, repair.id),
            type="ask_free_response",
            conceptId=concept_id,
            stepId=repair.id,
            rationale="Teach the diagnosed distinction, then check that same distinction.",
        )
        fallback_decision = TutorDecision(
            targetConcept=concept_id,
            teachingAction=fallback_action.type,
            pedagogicalGoal="BUILD_INTUITION" if evaluation.result == "insufficient_evidence" else "CORRECT_MISCONCEPTION",
            pedagogicalStrategy="SCAFFOLDED_PRACTICE" if evaluation.result == "insufficient_evidence" else "CONTRAST_CASE",
            scaffoldLevel=concept.get("scaffold", "FULL"),
            nextStepId=repair.id,
            transitionMessage="Let's make the distinction clear, then use it right away.",
            rationale="The next learner action must depend on the teaching intervention.",
        )
        observation = build_tutor_observation(session, event=event, source_blocks=source_blocks)
        try:
            decision = choose_tutor_decision(
                observation=observation,
                context={"source": source_context_text},
                fallback=fallback_decision,
                allowed_step_ids={repair.id},
            )
        except Exception:
            decision = fallback_decision

        visual_state = scene.visual_state or LearningVisualState()
        if _visual_supports_remediation(scene, current) and (
            evaluation.remediation_category == "change_modality"
            or decision.pedagogical_strategy in {"VISUAL_MODEL", "ANIMATED_MECHANISM"}
            or decision.visual_action
        ):
            visual_block = next((block for block in scene.blocks if block.kind in {"visual", "animation"} and block.visual_spec), None)
            if visual_block is not None and visual_block.visual_spec and visual_block.visual_spec.stages:
                next_stage = min(int(visual_state.stage) + 1, len(visual_block.visual_spec.stages) - 1)
                stage = visual_block.visual_spec.stages[next_stage]
                active_nodes = list((stage.get("activeNodeIds") or stage.get("active_node_ids") or []) if isinstance(stage, dict) else stage.active_node_ids)
                visual_state = visual_state.model_copy(update={"stage": next_stage, "highlighted_element_ids": active_nodes})
                state["visualState"] = visual_state.model_dump(by_alias=True)
                teaching.content = f"{teaching.content[:760]} In the visual, follow the highlighted stage and the relationship connected to it."

        state["usedTeachingIds"] = list(dict.fromkeys([*(state.get("usedTeachingIds") or []), teaching.id]))[-16:]
        state["lastTutorDecision"] = decision.model_dump(by_alias=True)
        state["previousTutorActions"] = (list(state.get("previousTutorActions", [])) + [decision.teaching_action])[-8:]
        state["lastFeedback"] = evaluation.student_message or evaluation.misconception or "Let's work through the key relationship."
        state["lastFeedbackKind"] = "info"
        session.state = state
        rendered = compose_learning_scene(
            session_id=str(session.id), objective=objective, steps=steps, step_index=0,
            current_step=repair, action=fallback_action, decision=decision,
            concept=concept, state=state,
            feedback=state["lastFeedback"], feedback_kind="info", evaluation=evaluation,
            teaching_override=teaching,
        )
        rendered = rendered.model_copy(update={"visual_state": visual_state})
        private_next = _private_for_rendered_scene(rendered, objective_id=concept_id, decision=decision, fallback_step=repair, objective=objective)
        return persist_scene_revision(
            session, rendered, private_next,
            event_id=getattr(event, "id", None) if not isinstance(event, dict) else event.get("id"), db=db,
        ), private_next

    candidates = []
    for raw in steps:
        try:
            candidate = adapter.validate_python(raw)
        except Exception:
            continue
        candidates.append(candidate)
    if evaluation and evaluation.result in {"incorrect", "partially_correct", "insufficient_evidence"}:
        answered_ids = _answered_interaction_ids(session, state)
        used_teaching = set(state.get("usedTeachingIds") or [])
        # Do not replay the same explanation after a failed intervention.
        # Prefer an unused grounded teaching asset, then a different unanswered
        # check, and finally the bounded scene-local fallback below.
        teaching = next((item for item in candidates if item.id != getattr(current, "id", None) and item.type in {"teach", "walkthrough"} and item.id not in used_teaching), None)
        # Do not fall through directly to another ordinary assessment after
        # a miss. If no unused authored teaching asset remains, the bounded
        # generated teaching turn below will run instead.
        next_step = teaching
    else:
        answered_ids = _answered_interaction_ids(session, state)
        used_teaching = set(state.get("usedTeachingIds") or [])
        next_step = next((item for item in candidates if item.id != getattr(current, "id", None) and item.id not in answered_ids and item.type not in {"teach", "walkthrough"}), None) or next((item for item in candidates if item.type in {"teach", "walkthrough"} and item.id not in answered_ids and item.id not in used_teaching), None)
    event_id_value = getattr(event, "id", None) if not isinstance(event, dict) else event.get("id")
    if next_step is None:
        if evaluation is not None and evaluation.result == "correct":
            # A correct recognition/recall response is not sufficient evidence
            # for transfer. Before advancing an objective, compose one new,
            # source-grounded application/transfer check in memory. This is
            # deliberately scene-local: authored plan steps remain assets,
            # never a finite progression cursor.
            if int(concept.get("transferEvidence", 0) or 0) == 0 and int(concept.get("independentSuccesses", 0) or 0) > 0 and concept.get("scaffold") in {"INDEPENDENT", "TRANSFER"}:
                outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
                transfer_id = bounded_id("transfer", concept_id, int(concept.get("attempts", 0)), int(scene.revision or 0))
                transfer_step = TeachBackStep(
                    id=transfer_id,
                    type="teach_back",
                    title="Apply it in a new situation",
                    prompt=f"How would the same idea apply in a new situation involving {objective.get('title', 'this concept')}? Explain the reasoning, not just the label.",
                    requiredConcepts=_required_concepts(outcome),
                    hints=[f"Start from this source-supported idea: {outcome[:220]}"],
                    feedbackIncorrect=f"Use the same mechanism described here: {outcome[:260]}",
                    sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                    sourceBlockIds=list(objective.get("sourceBlockIds", [])),
                )
                transfer_action = TutorAction(id=bounded_id("action", concept_id, transfer_id), type="ask_teach_back", conceptId=concept_id, stepId=transfer_id, rationale="Check whether the learner can transfer the idea beyond the original example.")
                transfer_decision = TutorDecision(targetConcept=concept_id, teachingAction="ask_teach_back", pedagogicalGoal="TEST_TRANSFER", pedagogicalStrategy="TRANSFER_PRACTICE", scaffoldLevel="TRANSFER", nextStepId=transfer_id, transitionMessage="Good. Now let's use the idea in a new situation.", rationale="Application evidence is present; transfer evidence is still needed.")
                concept["scaffold"] = "TRANSFER"
                concept["scaffoldingLevel"] = "TRANSFER"
                state["concepts"] = [concept if item.get("conceptId") == concept_id else item for item in state.get("concepts", [])]
                session.state = state
                rendered = compose_learning_scene(session_id=str(session.id), objective=objective, steps=steps, step_index=0, current_step=transfer_step, action=transfer_action, decision=transfer_decision, concept=concept, state=state, feedback=getattr(evaluation, "student_message", None) or "Good — now let's see whether the idea transfers.", feedback_kind="correct", evaluation=evaluation)
                private_next = _private_for_rendered_scene(rendered, objective_id=concept_id, decision=transfer_decision, fallback_step=transfer_step, objective=objective)
                return persist_scene_revision(session, rendered, private_next, event_id=event_id_value, db=db), private_next
            if int(concept.get("transferEvidence", 0) or 0) == 0 and int(concept.get("applicationEvidence", 0) or 0) > 0 and int(concept.get("independentSuccesses", 0) or 0) == 0:
                # Assisted/guided success earns a lower-support application
                # check before the tutor is allowed to demand transfer.
                independent_id = bounded_id("independent", concept_id, int(concept.get("attempts", 0)), int(scene.revision or 0))
                outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
                independent_step = TeachBackStep(id=independent_id, type="teach_back", title="Apply it with less help", prompt=f"Explain how {objective.get('title', 'this concept')} would work in a concrete situation, using your own reasoning.", requiredConcepts=_required_concepts(outcome), hints=[], feedbackIncorrect=f"Start from the central relationship: {outcome[:260]}", sourceSectionIds=list(objective.get("sourceSectionIds", [])), sourceBlockIds=list(objective.get("sourceBlockIds", [])))
                independent_action = TutorAction(id=bounded_id("action", concept_id, independent_id), type="ask_teach_back", conceptId=concept_id, stepId=independent_id, rationale="Check independent application before transfer.")
                independent_decision = TutorDecision(targetConcept=concept_id, teachingAction="ask_teach_back", pedagogicalGoal="TEST_APPLICATION", pedagogicalStrategy="SCAFFOLDED_PRACTICE", scaffoldLevel="INDEPENDENT", nextStepId=independent_id, transitionMessage="Good progress. Now try the idea with less help.", rationale="Guided success is not yet independent mastery.")
                concept["scaffold"] = "INDEPENDENT"
                concept["scaffoldingLevel"] = "INDEPENDENT"
                state["concepts"] = [concept if item.get("conceptId") == concept_id else item for item in state.get("concepts", [])]
                # Evidence and answered-interaction history were mutated above;
                # persist that state before returning the scene-local
                # independent check so the next response cannot resurrect the
                # original authored interaction.
                session.state = state
                rendered = compose_learning_scene(session_id=str(session.id), objective=objective, steps=steps, step_index=0, current_step=independent_step, action=independent_action, decision=independent_decision, concept=concept, state=state, feedback=getattr(evaluation, "student_message", None) or "Good progress. Now try the idea with less help.", feedback_kind="correct", evaluation=evaluation)
                private_next = _private_for_rendered_scene(rendered, objective_id=concept_id, decision=independent_decision, fallback_step=independent_step, objective=objective)
                return persist_scene_revision(session, rendered, private_next, event_id=event_id_value, db=db), private_next
            completed_scene = scene.model_copy(update={"blocks": [block for block in scene.blocks if block.kind != "practice"], "response_interaction_id": None, "progress": {"status": "demonstrated"}})
            return _advance_objective_or_complete(session, state, completed_scene, exclude_concept_id=concept_id, event_id=event_id_value, db=db)
        # Candidate assets are finite, but the tutor runtime is not.  Compose
        # one bounded, source-grounded follow-up in memory rather than
        # appending a repair step to LearnPlan.  Its stable ID is derived from
        # the concept and attempt count, so repeated replans never create
        # recursive IDs or mutate the authored plan.
        attempt_no = max(int(concept.get("attempts", 0)) + 1, len(state.get("recentAttempts", [])) + 1)
        # Explicit uncertainty is a request for more teaching, never a reason
        # to finish or advance the objective.  Keep the learner in the scene
        # and compose a grounded explanation even after earlier attempts.
        if attempt_no > 3 and evaluation is not None and evaluation.result != "insufficient_evidence":
            concept["state"] = "NEEDS_REVIEW"
            concept["reviewDue"] = "NEXT_SESSION"
            state["revisitQueue"] = list(dict.fromkeys([*state.get("revisitQueue", []), concept_id]))[:12]
            state["concepts"] = [concept if item.get("conceptId") == concept_id else item for item in state.get("concepts", [])]
            session.state = state
            review_scene = scene.model_copy(update={"blocks": [block for block in scene.blocks if block.kind != "practice"], "response_interaction_id": None, "progress": {"status": "needs_review"}})
            return _advance_objective_or_complete(session, state, review_scene, exclude_concept_id=concept_id, event_id=event_id_value, db=db)
        outcome = str(objective.get("outcome") or objective.get("bottleneck") or objective.get("title") or "this concept")
        title = str(objective.get("title", "this concept"))
        error_context = current
        if error_context is None and state.get("lastErrorContext"):
            try:
                error_context = _coerce_step(state["lastErrorContext"], objective)
            except Exception:
                error_context = None
        if error_context is not None and getattr(error_context, "type", None) == "matching":
            pairs = getattr(error_context, "pairs", []) or []
            matches = getattr(error_context, "matches", {}) or {}
            distinctions = [f"{getattr(pair, 'label', pair.id)}: {matches.get(pair.id, '')}" for pair in pairs if matches.get(pair.id)]
            if distinctions:
                outcome = f"{outcome} Key distinctions: {'; '.join(distinctions)}."
        required_concepts = _required_concepts(outcome)
        # A failed/uncertain response must earn a teaching turn before the
        # runtime creates another assessment.  When authored teaching assets
        # are exhausted, compose one bounded, grounded explanation in memory;
        # the following Continue event can then expose a new practice target.
        if evaluation is not None and evaluation.result in {"incorrect", "partially_correct", "insufficient_evidence"}:
            teaching_id = bounded_id("teach-repair", concept_id, int(concept.get("attempts", 0)), getattr(current, "id", "none"))
            teaching_content = str(getattr(error_context, "feedback_incorrect", None) or getattr(error_context, "content", None) or objective.get("bottleneck") or outcome)
            teaching = TeachStep(
                id=teaching_id,
                type="teach",
                title=f"Let's clarify {title}",
                content=teaching_content[:900],
                sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                sourceBlockIds=list(objective.get("sourceBlockIds", [])),
            )
            state["usedTeachingIds"] = list(dict.fromkeys([*(state.get("usedTeachingIds") or []), teaching.id]))[-16:]
            session.state = state
            teaching_action = TutorAction(id=bounded_id("action", concept_id, teaching.id), type="teach_concept", conceptId=concept_id, stepId=teaching.id, rationale="Teach the missing distinction before asking for another response.")
            teaching_decision = TutorDecision(targetConcept=concept_id, teachingAction="teach_concept", pedagogicalGoal="CORRECT_MISCONCEPTION" if evaluation.misconception else "BUILD_INTUITION", pedagogicalStrategy="ERROR_CORRECTION" if evaluation.misconception else "DIRECT_INSTRUCTION", scaffoldLevel=concept.get("scaffold", "FULL"), nextStepId=teaching.id, transitionMessage="Let's clarify the idea before you try it again.", rationale="A teaching intervention is required before another assessment.")
            # When the current scene already has a grounded visual, reuse it
            # for remediation instead of replacing it with a disposable
            # illustration. Advance to the next validated stage and expose
            # its active elements so the explanation and visual point to the
            # same misunderstood relationship.
            # A scene composed from an older persisted revision may contain a
            # visual block but no explicit visualState yet.  Treat that as the
            # initial stage rather than silently skipping the tutor-directed
            # visual intervention.
            visual_state = scene.visual_state or LearningVisualState()
            visual_block = next((block for block in scene.blocks if block.kind in {"visual", "animation"} and block.visual_spec), None)
            if visual_block is not None:
                spec = visual_block.visual_spec
                next_stage = min(int(visual_state.stage) + 1, max(0, len(spec.stages) - 1))
                stage = spec.stages[next_stage] if spec.stages else None
                active_nodes = list((stage.get("activeNodeIds") or stage.get("active_node_ids") or []) if isinstance(stage, dict) else (stage.active_node_ids if stage else []))
                scene = scene.model_copy(update={"visual_state": visual_state.model_copy(update={"stage": next_stage, "highlighted_element_ids": active_nodes})})
                teaching.content = f"{teaching.content[:760]} Watch the highlighted part of the visual as you connect this relationship."
                # compose_learning_scene takes its visual state from the
                # mutable runtime state. Carry the validated scene mutation
                # across that boundary so persistence and the API response
                # cannot silently reset the visual to its prior stage.
                state["visualState"] = scene.visual_state.model_dump(by_alias=True)
            # Always surface a concise learner-facing acknowledgement on the
            # remediation scene.  Model-backed evaluations may provide a
            # student message, while deterministic grading only has its
            # internal evidence/rationale; the misconception is the safest
            # specific fallback and the final sentence keeps the scene
            # usable when neither is available.
            remediation_feedback = (
                evaluation.student_message
                or evaluation.misconception
                or ("Let's look at the key relationship together." if evaluation else None)
            )
            rendered = compose_learning_scene(session_id=str(session.id), objective=objective, steps=steps, step_index=0, current_step=teaching, action=teaching_action, decision=teaching_decision, concept=concept, state=state, feedback=remediation_feedback, evaluation=evaluation)
            if scene.visual_state is not None:
                rendered = rendered.model_copy(update={"visual_state": scene.visual_state})
            private_next = _private_for_rendered_scene(rendered, objective_id=concept_id, decision=teaching_decision, fallback_step=teaching, objective=objective)
            return persist_scene_revision(session, rendered, private_next, event_id=event_id_value, db=db), private_next
        generated_id = bounded_id("repair", concept_id, attempt_no, int(scene.revision or 0) + 1)
        if current is not None and generated_id == current.id:
            generated_id = bounded_id("repair", concept_id, attempt_no + 1)
        # Repeated remediation for the same objective must read as a genuinely
        # different follow-up, not the same canned prompt with a new ID --
        # vary both the interaction type and the phrasing by attempt. The
        # first remediation lands here at attempt_no == 2 (the original
        # response was attempt 1); attempt_no > 3 exits to needs_review
        # above, so 3 is the only other value this branch ever sees.
        generated = None
        if evaluation is not None and evaluation.result == "insufficient_evidence":
            generated = TeachStep(
                id=generated_id,
                type="teach",
                title=f"Let's build {title}",
                content=f"No problem — let's build the idea first. {outcome[:760]}",
                sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                sourceBlockIds=list(objective.get("sourceBlockIds", [])),
            )
        elif attempt_no < 3 and current is not None and getattr(current, "type", None) in {"multiple_choice", "prediction", "matching", "ordering", "labeling"}:
            # A wrong structured answer deserves a targeted contrast built
            # from what the learner actually got wrong, not the generic
            # "explain the main idea" prompt every objective falls back to.
            try:
                generated = build_remediation_step(objective, current, generated_id)
            except Exception:
                generated = None
        if generated is not None:
            pass
        elif attempt_no >= 3:
            generated = TeachBackStep(
                id=generated_id,
                type="teach_back",
                title=f"Teach {title} back",
                prompt=f"Explain {title} to a classmate in one or two sentences, in your own words.",
                requiredConcepts=required_concepts,
                hints=[f"Use this source-supported idea: {outcome[:220]}"],
                feedbackIncorrect=f"Start with this source-supported idea: {outcome[:260]}",
                sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                sourceBlockIds=list(objective.get("sourceBlockIds", [])),
            )
        else:
            generated = ShortAnswerStep(
                id=generated_id,
                type="short_answer",
                title=f"Apply {title}",
                prompt=f"In your own words, explain the main idea of {title}.",
                acceptedAnswers=[outcome],
                requiredConcepts=required_concepts,
                hints=[f"Use this source-supported idea: {outcome[:220]}"],
                feedbackIncorrect=f"Start with this source-supported idea: {outcome[:260]}",
                sourceSectionIds=list(objective.get("sourceSectionIds", [])),
                sourceBlockIds=list(objective.get("sourceBlockIds", [])),
            )
        candidates.append(generated)
        next_step = generated
    fallback_action = TutorAction(id=bounded_id("action", concept_id, next_step.id), type="teach_concept" if next_step.type in {"teach", "walkthrough"} else "ask_free_response", conceptId=concept_id, stepId=next_step.id, rationale="Continue with the next grounded learning move.")
    fallback = TutorDecision(targetConcept=concept_id, teachingAction=fallback_action.type, pedagogicalGoal="BUILD_INTUITION" if not evaluation or evaluation.result != "correct" else "VERIFY_UNDERSTANDING", pedagogicalStrategy="CONCEPTUAL_EXPLANATION" if next_step.type in {"teach", "walkthrough"} else "RETRIEVAL_PRACTICE", scaffoldLevel=concept.get("scaffold", "FULL"), nextStepId=next_step.id, actions=[])
    observation = build_tutor_observation(session, event=event, source_blocks=source_blocks)
    try:
        decision = choose_tutor_decision(observation=observation, context={"source": source_context_text}, fallback=fallback, allowed_step_ids={item.id for item in candidates})
    except Exception:
        decision = fallback
    # The decision selects the next candidate; the fallback is only used when
    # the provider is unavailable or fails validation.
    answered_ids = _answered_interaction_ids(session, state)
    selected = next((item for item in candidates if item.id == decision.next_step_id and item.id not in answered_ids), None)
    if selected is not None:
        next_step = selected
        fallback_action = TutorAction(id=bounded_id("action", concept_id, next_step.id), type="teach_concept" if next_step.type in {"teach", "walkthrough"} else "ask_free_response", conceptId=concept_id, stepId=next_step.id, rationale=decision.rationale or "Continue with the grounded concept.")
    if next_step.type in {"teach", "walkthrough"}:
        state["usedTeachingIds"] = list(dict.fromkeys([*(state.get("usedTeachingIds") or []), next_step.id]))[-16:]
    feedback = None
    if evaluation is not None:
        # `evaluation.evidence` is internal grading rationale (third-person,
        # analytical) and must never render directly; `student_message` is the
        # model's natural, second-person text meant for the learner. The
        # deterministic evaluator never sets student_message, so its evidence
        # text (already written to be learner-appropriate) is the fallback.
        if evaluation.result == "correct":
            feedback = getattr(current, "feedback_correct", None) or "Good — that matches the material."
        else:
            feedback = evaluation.student_message or evaluation.evidence
        state["lastFeedback"] = feedback
    state["lastTutorDecision"] = decision.model_dump(by_alias=True)
    state["previousTutorActions"] = (list(state.get("previousTutorActions", [])) + [decision.teaching_action])[-8:]
    state["lastFeedback"] = feedback
    state["lastFeedbackKind"] = "correct" if evaluation and evaluation.result == "correct" else "incorrect" if evaluation else "info"
    if evaluation is not None and current is not None:
        state["answeredInteractionIds"] = list(dict.fromkeys([*(state.get("answeredInteractionIds") or []), current.id]))[-32:]
    # A misconception should change the teaching surface, not only swap the
    # interaction.  Reuse the scene's grounded visual when it can express a
    # meaningful next stage; otherwise leave it untouched and let the tutor's
    # textual intervention stand on its own.  This runs for both authored and
    # generated remediation paths (the earlier fallback-only mutation missed
    # authored teaching assets).
    if evaluation is not None and evaluation.result in {"incorrect", "partially_correct", "insufficient_evidence"}:
        visual_state = scene.visual_state or LearningVisualState()
        visual_block = next((block for block in scene.blocks if block.kind in {"visual", "animation"} and block.visual_spec), None)
        if visual_block is not None and visual_block.visual_spec and visual_block.visual_spec.stages:
            spec = visual_block.visual_spec
            next_stage = min(int(visual_state.stage) + 1, len(spec.stages) - 1)
            stage = spec.stages[next_stage]
            active_nodes = list((stage.get("activeNodeIds") or stage.get("active_node_ids") or []) if isinstance(stage, dict) else (stage.active_node_ids if stage else []))
            visual_state = visual_state.model_copy(update={"stage": next_stage, "highlighted_element_ids": active_nodes})
            state["visualState"] = visual_state.model_dump(by_alias=True)
            # Keep the explanation and visual semantically coupled.  The
            # sentence is appended only to a remediation teaching turn and
            # remains grounded in the existing visual stage.
            if next_step.type in {"teach", "walkthrough"} and getattr(next_step, "content", None) and "visual" not in str(next_step.content).casefold():
                next_step = next_step.model_copy(update={"content": f"{next_step.content[:760]} Watch the highlighted part of the visual as you connect this relationship."})
    session.state = state
    rendered = compose_learning_scene(session_id=str(session.id), objective=objective, steps=steps, step_index=0, current_step=next_step, action=fallback_action, decision=decision, concept=concept, state=state, feedback=feedback, evaluation=evaluation)
    private_next = _private_for_rendered_scene(rendered, objective_id=concept_id, decision=decision, fallback_step=next_step, objective=objective)
    rendered = persist_scene_revision(session, rendered, private_next, event_id=getattr(event, "id", None) if not isinstance(event, dict) else event.get("id"), db=db)
    return rendered, private_next
