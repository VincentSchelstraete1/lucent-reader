"""Compose bounded, source-grounded tutor turns into cohesive learning scenes."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter

from app.schemas.learn import (
    LearnEvaluation,
    LearningScene,
    LearningSceneBlock,
    LearnStep,
    TutorAction,
    TutorDecision,
)
from app.services.learn_engine import learner_text_quality_issues, public_step, student_facing_quality_issues


_STEP_ADAPTER = TypeAdapter(LearnStep)
_INTERACTIVE_TYPES = {
    "multiple_choice", "short_answer", "numeric", "problem", "prediction",
    "ordering", "matching", "labeling", "fill_blank", "worked_step", "teach_back",
}
_ACTION_BLOCKS = {
    "give_example": ("example", "Example"),
    "give_counterexample": ("counterexample", "Contrast"),
    "give_analogy": ("analogy", "Another way to see it"),
    "show_worked_example": ("worked_example", "Worked example"),
    "guide_problem_step": ("guided_step", "Guided step"),
    "clarify_definition": ("explanation", "Clarify"),
    "simplify_explanation": ("explanation", "Simplify"),
}


@dataclass(frozen=True)
class SceneExecutionResult:
    """Private executor result; routers must serialize only its public scene."""

    scene: LearningScene
    private_scene: dict[str, Any] | None = None
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    transition_proposal: dict[str, Any] | None = None
    used_fallback: bool = False
    fallback_reason: str | None = None


def _id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:14]
    return f"{prefix}-{digest}"


def _parse(raw: dict[str, Any]):
    try:
        return _STEP_ADAPTER.validate_python(raw)
    except Exception:
        return None


def _source_text(objective: dict, steps: list[dict]) -> str:
    values = [str(objective.get("title", "")), str(objective.get("outcome", "")), str(objective.get("bottleneck", ""))]
    for raw in steps:
        # Only trust source-derived teaching fields here.  Prompts and
        # fallback wording are learner-facing generated output and must not
        # whitelist their own internal/meta leakage.
        for key in ("content", "feedbackCorrect", "feedbackIncorrect", "solution", "reveal"):
            if raw.get(key):
                values.append(str(raw[key]))
        values.extend(str(item.get("label", "")) for item in raw.get("options", []) if isinstance(item, dict))
        values.extend(str(item.get("label", "")) for item in raw.get("items", []) if isinstance(item, dict))
        values.extend(str(item.get("label", "")) for item in raw.get("pairs", []) if isinstance(item, dict))
    return " ".join(values)


def _block(
    *, scene_seed: str, ordinal: int, kind: str, label: str,
    title: str | None = None, content: str | None = None, step=None,
    visual_spec=None, visual_ref: dict | None = None,
    section_ids: list[str], block_ids: list[str], source_text: str,
) -> LearningSceneBlock | None:
    prose = " ".join(part for part in (label, title, content) if part)
    if learner_text_quality_issues(prose, source_text):
        return None
    if step is not None and student_facing_quality_issues(step, source_text):
        return None
    return LearningSceneBlock(
        id=_id("block", scene_seed, ordinal, kind), kind=kind, label=label,
        title=title, content=content, step=public_step(step) if step is not None else None,
        visualSpec=visual_spec, visualRef=visual_ref,
        sourceSectionIds=section_ids, sourceBlockIds=block_ids,
    )


def compose_learning_scene(
    *, session_id: str, objective: dict, steps: list[dict], step_index: int,
    current_step, action: TutorAction | None, decision: TutorDecision | None,
    concept: dict, state: dict, feedback: str | None = None,
    feedback_kind: str | None = None, evaluation: LearnEvaluation | None = None,
) -> LearningScene:
    """Compose one bounded tutor turn from existing validated teaching assets.

    The model chooses strategy/actions; this deterministic compiler combines
    their validated outputs with source-grounded teaching and interaction
    components. It never lets the model mutate state or emit executable UI.
    """
    source_text = _source_text(objective, steps)
    section_ids = list(dict.fromkeys(list(objective.get("sourceSectionIds", [])) + list(getattr(current_step, "source_section_ids", []) or [])))[:8]
    block_ids = list(dict.fromkeys(list(objective.get("sourceBlockIds", [])) + list(getattr(current_step, "source_block_ids", []) or [])))[:12]
    scene_seed = _id("scene", session_id, objective.get("id"), getattr(current_step, "id", "none"), state.get("sceneRevision", 0))
    blocks: list[LearningSceneBlock] = []

    def add(**kwargs) -> None:
        if len(blocks) >= 6:
            return
        candidate = _block(scene_seed=scene_seed, ordinal=len(blocks), section_ids=section_ids, block_ids=block_ids, source_text=source_text, **kwargs)
        if candidate is not None:
            blocks.append(candidate)

    support = None
    if getattr(current_step, "type", None) in _INTERACTIVE_TYPES:
        prior = [_parse(raw) for raw in steps[: max(0, step_index)]]
        support = next((item for item in reversed(prior) if item and item.type in {"teach", "walkthrough"} and not student_facing_quality_issues(item, source_text)), None)
        if support is None:
            support = next((item for item in (_parse(raw) for raw in steps) if item and item.type in {"teach", "walkthrough"} and not student_facing_quality_issues(item, source_text)), None)

    if feedback:
        result_label = "Feedback"
        specific = evaluation.misconception if evaluation and evaluation.misconception else feedback
        add(kind="feedback", label=result_label, title=None, content=specific, step=None, visual_spec=None, visual_ref=None)

    transition = decision.transition_message if decision else None
    if transition and any(phrase in transition.casefold() for phrase in ("using your response", "changing the approach", "choose the next", "evidence")):
        transition = "Let's try this idea from a different angle."
    if transition and feedback and not learner_text_quality_issues(transition, source_text):
        add(kind="tutor_message", label="Try this", content=transition, step=None, visual_spec=None, visual_ref=None)

    planned_practice = False
    if decision and decision.scene_plan:
        by_step_id = {str(raw.get("id")): _parse(raw) for raw in steps if isinstance(raw, dict)}
        for directive in decision.scene_plan.blocks:
            if len(blocks) >= 5:
                break
            planned_step = by_step_id.get(str(directive.step_id)) if directive.step_id else None
            if directive.kind == "practice" and planned_step is not None:
                add(kind="practice", label=directive.label, title=directive.title or planned_step.title, content=directive.content, step=planned_step, visual_spec=getattr(planned_step, "visual_spec", None), visual_ref=directive.visual_ref)
                planned_practice = True
            elif directive.content or directive.visual_ref:
                add(kind=directive.kind, label=directive.label, title=directive.title, content=directive.content, step=None, visual_spec=None, visual_ref=directive.visual_ref)

    teaching = support or (current_step if getattr(current_step, "type", None) in {"teach", "walkthrough"} else None)
    if teaching is not None:
        if getattr(teaching, "content", None):
            add(kind="explanation", label="Understand", title=teaching.title, content=teaching.content, step=None, visual_spec=None, visual_ref=None)
        visual_spec = getattr(teaching, "visual_spec", None)
        visual_ref = getattr(teaching, "visual_ref", None)
        if visual_ref is None and getattr(teaching, "type", None) == "walkthrough":
            visual_ref = {"sectionId": teaching.section_id, "componentIndex": teaching.component_index}
        if visual_spec is not None or visual_ref is not None:
            add(kind="animation" if getattr(teaching, "type", None) == "walkthrough" else "visual", label="Watch", title=teaching.title, step=None, visual_spec=visual_spec, visual_ref=visual_ref)
        # A teaching-only candidate should still open with the best available
        # grounded representation for the objective. Reuse the next authored
        # walkthrough/visual rather than leaving the learner with prose alone.
        if visual_spec is None and visual_ref is None:
            for raw in steps[step_index + 1:]:
                candidate = _parse(raw)
                if not candidate or student_facing_quality_issues(candidate, source_text):
                    continue
                candidate_spec = getattr(candidate, "visual_spec", None)
                candidate_ref = getattr(candidate, "visual_ref", None)
                if candidate_ref is None and getattr(candidate, "type", None) == "walkthrough":
                    candidate_ref = {"sectionId": candidate.section_id, "componentIndex": candidate.component_index}
                if candidate_spec is not None or candidate_ref is not None:
                    add(kind="animation" if candidate.type == "walkthrough" else "visual", label="Watch", title=None, step=None, visual_spec=candidate_spec, visual_ref=candidate_ref)
                    break
        if not any(block.kind == "practice" for block in blocks):
            for raw in steps[step_index + 1:] + steps[:step_index]:
                candidate = _parse(raw)
                if candidate and candidate.type in _INTERACTIVE_TYPES and not student_facing_quality_issues(candidate, source_text):
                    label = {"prediction": "Predict", "matching": "Compare", "labeling": "Label", "ordering": "Reconstruct", "worked_step": "Solve", "problem": "Try", "numeric": "Solve", "teach_back": "Explain", "fill_blank": "Recall", "short_answer": "Explain", "multiple_choice": "Check"}.get(candidate.type, "Try")
                    add(kind="practice", label=label, title=candidate.title, content=None, step=candidate, visual_spec=getattr(candidate, "visual_spec", None), visual_ref=None)
                    break

    if decision:
        for tool in decision.actions:
            mapping = _ACTION_BLOCKS.get(tool.tool)
            if not mapping or len(blocks) >= 5:
                continue
            kind, label = mapping
            content = getattr(current_step, "feedback_incorrect", None) or objective.get("bottleneck") or objective.get("outcome")
            add(kind=kind, label=label, title=objective.get("title"), content=content, step=None, visual_spec=None, visual_ref=None)

    if getattr(current_step, "type", None) in _INTERACTIVE_TYPES and not planned_practice and not any(block.kind == "practice" for block in blocks):
        label = {
            "prediction": "Predict", "matching": "Compare", "labeling": "Label",
            "ordering": "Reconstruct", "worked_step": "Solve", "problem": "Try",
            "numeric": "Solve", "teach_back": "Explain", "fill_blank": "Recall",
            "short_answer": "Explain", "multiple_choice": "Check",
        }.get(current_step.type, "Practice")
        add(kind="practice", label=label, title=current_step.title, step=current_step, visual_spec=getattr(current_step, "visual_spec", None), visual_ref=None)
    elif not blocks:
        add(kind="explanation", label="Understand", title=objective.get("title"), content=objective.get("outcome") or objective.get("title"), step=None, visual_spec=None, visual_ref=None)

    interruption = state.get("sceneInterruption")
    if isinstance(interruption, dict) and interruption.get("answer"):
        add(kind="tutor_message", label="Ask Lucent", title=interruption.get("question"), content=str(interruption["answer"])[:900], step=None, visual_spec=None, visual_ref=None)

    # Last-resort content is source-specific and can never be a schema/meta template.
    if not blocks:
        blocks.append(LearningSceneBlock(id=_id("block", scene_seed, "fallback"), kind="explanation", label="Understand", title=objective.get("title", "Current concept"), content=objective.get("outcome") or objective.get("title", "Review this idea."), sourceSectionIds=section_ids, sourceBlockIds=block_ids))

    evidence = {
        "multiple_choice": ["recognition"], "prediction": ["application"], "matching": ["comparison"],
        "labeling": ["spatial understanding"], "ordering": ["process reconstruction"],
        "short_answer": ["explanation"], "teach_back": ["explanation", "transfer"],
        "numeric": ["application"], "problem": ["application"], "worked_step": ["procedural reasoning"],
        "fill_blank": ["recall"],
    }.get(getattr(current_step, "type", ""), [])
    response_step_id = next((block.step.id for block in blocks if block.kind == "practice" and block.step), None)
    return LearningScene(
        id=scene_seed, revision=int(state.get("sceneRevision", 0)), objectiveId=str(objective.get("id", "concept")),
        objective=str(objective.get("title", "Current concept")), targetConcepts=[str(objective.get("title", "Current concept"))],
        pedagogicalGoal=(decision.pedagogical_goal if decision else "EXPLAIN_CONCEPT"),
        tutorHypothesis=(decision.hypothesis if decision else ""),
        strategy=(decision.pedagogical_strategy if decision else (action.strategy if action else "DIRECT_INSTRUCTION")),
        scaffoldLevel=str(concept.get("scaffold", "FULL")), blocks=blocks,
            evidenceTargets=evidence, sourceSectionIds=section_ids, sourceBlockIds=block_ids,
            visualState={"stage": int(state.get("visualStage", 0)), **({"highlightedElementIds": [str(state["visualHighlight"])]} if state.get("visualHighlight") else {})},
            completionCondition=(decision.scene_plan.completion_condition if decision and decision.scene_plan and decision.scene_plan.completion_condition else f"Show that you can explain or apply {objective.get('title', 'this idea')} with less support."),
            responseInteractionId=response_step_id,
        )
