from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.schemas.learn import (
    LearnEvaluation, LearnPlan, LearnStep, LearnStepView, LearningObjective, MultipleChoiceStep,
    OrderingStep, PredictionStep, ProblemStep, ShortAnswerStep, TeachStep, WalkthroughStep,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", value.lower()) if len(word) > 2}


def _components(section: dict) -> list[dict]:
    return [item for item in section.get("components", []) if isinstance(item, dict)]


def _source_ids(section: dict) -> tuple[list[str], list[str]]:
    return list(section.get("id") and [str(section["id"])] or []), [str(item) for item in section.get("sourceBlockIds", [])]


def build_learn_plan(note_payload: dict, goal: str, familiarity: str) -> LearnPlan:
    """Build a bounded, grounded plan from the persisted SectionNote.

    This is deliberately deterministic for V1: SectionNote generation already
    performed the semantic work, while this layer chooses an interaction
    sequence appropriate to the learner's stated goal.
    """
    sections = [s for s in note_payload.get("sectionNotes", []) if isinstance(s, dict)]
    objectives: list[LearningObjective] = []
    for section in sections[:4]:
        section_ids, block_ids = _source_ids(section)
        title = _clean(section.get("title")) or "Core concept"
        big_idea = _clean(section.get("bigIdea")) or title
        takeaways = [_clean(item) for item in section.get("keyTakeaways", []) if _clean(item)]
        comps = _components(section)
        kinds = {str(c.get("kind")) for c in comps}
        if "worked_example" in kinds or "equation" in kinds:
            bottleneck = "Translate the represented quantities into an ordered procedure."
        elif "flow" in kinds:
            bottleneck = "Follow the causal or process transition from one step to the next."
        elif "comparison" in kinds:
            bottleneck = "Keep the distinguishing dimensions separate instead of blending them together."
        elif "structure" in kinds:
            bottleneck = "See how containment or composition changes the system."
        elif "relationship_map" in kinds:
            bottleneck = "Connect each relationship to the role it plays in the whole idea."
        else:
            bottleneck = "Identify the central idea and connect it to a concrete response."
        steps: list[LearnStep] = []

        if goal in {"understand", "exam"}:
            steps.append(TeachStep(id=f"{section.get('id', 'section')}-teach", type="teach", title="Quick refresher" if familiarity == "reviewing" else "Build the mental model", content=big_idea, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            walkthrough_index = next((i for i, c in enumerate(comps) if c.get("kind") == "walkthrough" and c.get("mechanism")), None)
            if walkthrough_index is not None and goal == "understand":
                steps.append(WalkthroughStep(id=f"{section.get('id', 'section')}-visual", type="walkthrough", title="See the mechanism change", sectionId=str(section.get("id")), componentIndex=walkthrough_index, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            elif any(c.get("kind") == "flow" and len(c.get("nodes", [])) >= 2 for c in comps):
                flow = next(c for c in comps if c.get("kind") == "flow" and len(c.get("nodes", [])) >= 2)
                node_ids = [str(node.get("id")) for node in flow.get("nodes", []) if node.get("id")]
                options = [{"id": node_id, "label": _clean(next((node.get("label") for node in flow.get("nodes", []) if str(node.get("id")) == node_id), node_id))} for node_id in node_ids]
                steps.append(OrderingStep(id=f"{section.get('id', 'section')}-order", type="ordering", title="Put the process in order", prompt=f"What is the sequence for {title}?", items=options[:8], correctOrder=node_ids[:8], feedbackIncorrect="Follow the transition from one step to the next in the process.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            elif goal == "understand" and any(c.get("kind") == "key_definition" for c in comps):
                definition = next(c for c in comps if c.get("kind") == "key_definition")
                answer = _clean(definition.get("definition")) or big_idea
                steps.append(ShortAnswerStep(id=f"{section.get('id', 'section')}-free", type="short_answer", title="Say it in your own words", prompt=f"What does {_clean(definition.get('term')) or title} mean?", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect="Focus on the defining relationship, not a supporting detail.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            else:
                answer = takeaways[0] if takeaways else big_idea
                steps.append(MultipleChoiceStep(id=f"{section.get('id', 'section')}-check", type="multiple_choice", title="Check the central idea", prompt=f"Which statement best captures {title}?", options=[{"id": "a", "label": answer[:160]}, {"id": "b", "label": "A detail not established by this material."}, {"id": "c", "label": "A reversed version of the relationship."}], answerId="a", feedbackIncorrect=f"Return to the central idea: {answer[:260]}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                if goal == "exam":
                    steps.append(ShortAnswerStep(id=f"{section.get('id', 'section')}-exam-recall", type="short_answer", title="Explain the distinction", prompt=f"State the exam-relevant point about {title}.", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect="Use the central idea, not a peripheral detail.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
        elif goal == "memorize":
            definition = next((c for c in comps if c.get("kind") == "key_definition" and _clean(c.get("term")) and _clean(c.get("definition"))), None)
            term = _clean(definition.get("term")) if definition else title
            answer = _clean(definition.get("definition")) if definition else (takeaways[0] if takeaways else big_idea)
            steps.append(TeachStep(id=f"{section.get('id', 'section')}-definition", type="teach", title=term, content=answer, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            steps.append(MultipleChoiceStep(id=f"{section.get('id', 'section')}-recognize", type="multiple_choice", title="Recognize it", prompt=f"Which statement defines {term}?", options=[{"id": "a", "label": answer[:160]}, {"id": "b", "label": "A related but different idea."}, {"id": "c", "label": "A claim not supported by this material."}], answerId="a", feedbackIncorrect="Look for the defining relationship, not a nearby detail.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            steps.append(ShortAnswerStep(id=f"{section.get('id', 'section')}-recall", type="short_answer", title="Retrieve it", prompt=f"In your own words, what is {term}?", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect="Use the definition above, then try the idea again.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
        else:  # solve
            example = next((c for c in comps if c.get("kind") in {"worked_example", "equation"}), None)
            if example and _clean(example.get("result")):
                problem = _clean(example.get("problem") or example.get("equation") or title)
                result = _clean(example.get("result"))
                steps.append(TeachStep(id=f"{section.get('id', 'section')}-worked", type="teach", title="See one worked path", content=f"{problem} → {result}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(ProblemStep(id=f"{section.get('id', 'section')}-apply", type="problem", title="Try the key step", prompt=f"What result should this method produce for: {problem}?", responseType="short_answer", acceptedAnswers=[result], solution=result, hints=["Start from the worked relationship.", "Keep the same operation order."], feedbackIncorrect="Compare your result with the worked path, then try once more.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            else:
                answer = takeaways[0] if takeaways else big_idea
                steps.append(TeachStep(id=f"{section.get('id', 'section')}-method", type="teach", title="Choose the method", content=big_idea, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(ProblemStep(id=f"{section.get('id', 'section')}-apply", type="problem", title="Apply the idea", prompt=f"State the key move used in {title}.", responseType="short_answer", acceptedAnswers=[answer], solution=answer, hints=["Start with the central relationship.", "Use the wording from the teaching point."], feedbackIncorrect="Use the stated relationship as your starting point.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))

        outcome = {"understand": f"Explain how {title} works.", "solve": f"Apply {title} to a new step.", "memorize": f"Recall the essential facts about {title}.", "exam": f"Recognize and use {title} under exam conditions."}[goal]
        objectives.append(LearningObjective(id=f"objective-{section.get('id', len(objectives))}", title=title, outcome=outcome, bottleneck=bottleneck, sourceSectionIds=section_ids, sourceBlockIds=block_ids, steps=steps))

    if not objectives:
        objectives = [LearningObjective(id="objective-overview", title="Material overview", outcome="Recall the main idea.", bottleneck="Identify what matters most.", steps=[TeachStep(id="overview-teach", type="teach", title="Main idea", content=_clean(note_payload.get("title")) or "Review the material.")])]
    return LearnPlan(goal=goal, familiarity=familiarity, objectives=objectives)


def plan_fingerprint(note_payload: dict, goal: str, familiarity: str) -> str:
    source = json.dumps(note_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"learn-v1:{goal}:{familiarity}:{source}".encode()).hexdigest()


def public_step(step: LearnStep, hints_used: int = 0) -> LearnStepView:
    data = step.model_dump(by_alias=True, exclude_none=True)
    options = data.get("options", [])
    visual_ref = data.get("visualRef")
    if data["type"] == "walkthrough":
        visual_ref = {"sectionId": data.get("sectionId"), "componentIndex": data.get("componentIndex")}
    return LearnStepView(id=data["id"], type=data["type"], title=data["title"], prompt=data.get("prompt"), content=data.get("content"), options=options, items=data.get("items", []), visualSpec=data.get("visualSpec"), visualRef=visual_ref, sectionId=data.get("sectionId"), componentIndex=data.get("componentIndex"), hintsAvailable=max(0, len(step.hints) - hints_used))


def evaluate_step(step: LearnStep, *, response: str | None, option_id: str | None, ordered_ids: list[str] | None = None) -> LearnEvaluation:
    """Deterministic first-pass evaluator used by the adaptive runtime."""
    answer = _clean(option_id or response)
    if isinstance(step, (TeachStep, WalkthroughStep)):
        return LearnEvaluation(result="insufficient_evidence", confidence=0.15, evidence="Teaching content does not itself demonstrate recall.", remediationCategory="none")
    if isinstance(step, (MultipleChoiceStep, PredictionStep)):
        correct = answer == step.answer_id
        return LearnEvaluation(result="correct" if correct else "incorrect", confidence=0.98 if correct else 0.9, evidence="Selected option matched the source-grounded answer." if correct else "Selected option did not match the source-grounded answer.", misconception=None if correct else (step.feedback_incorrect or "The distinction needs another explanation."), remediationCategory="none" if correct else "change_modality")
    if isinstance(step, OrderingStep):
        submitted = ordered_ids or ([part.strip() for part in answer.split(",")] if answer else [])
        expected = list(step.correct_order)
        if submitted == expected:
            result, confidence = "correct", 0.98
        elif submitted and set(submitted) == set(expected) and sum(a == b for a, b in zip(submitted, expected)) >= max(1, len(expected) // 2):
            result, confidence = "partially_correct", 0.75
        else:
            result, confidence = "incorrect", 0.9
        return LearnEvaluation(result=result, confidence=confidence, evidence="The ordered sequence reflects the process transitions." if result == "correct" else "The sequence needs the process transition made explicit.", misconception=None if result == "correct" else (step.feedback_incorrect or "Follow the causal transition from one step to the next."), remediationCategory="none" if result == "correct" else "simplify")
    if isinstance(step, ProblemStep) and step.response_type == "numeric":
        try:
            correct = abs(float(answer) - float(step.answer or 0)) <= float(step.tolerance or 0.01)
        except (TypeError, ValueError):
            correct = False
        return LearnEvaluation(result="correct" if correct else "incorrect", confidence=0.98 if correct else 0.85, evidence="Numeric result is within the accepted tolerance." if correct else "Numeric result is outside the accepted tolerance.", misconception=None if correct else "Check the operation and units before calculating again.", remediationCategory="none" if correct else "example")
    normalized = _words(answer)
    accepted = any(_words(item) <= normalized or _clean(item).casefold() == answer.casefold() for item in getattr(step, "accepted_answers", []))
    required = set(getattr(step, "required_concepts", []))
    if accepted or (bool(required) and required <= normalized):
        result = "correct"
    elif normalized and required and normalized.intersection(required):
        result = "partially_correct"
    else:
        result = "incorrect"
    return LearnEvaluation(result=result, confidence=0.9 if result == "correct" else 0.65 if result == "partially_correct" else 0.82, evidence="Response captures the key source-grounded idea." if result == "correct" else "Response captures only part of the key idea." if result == "partially_correct" else "Response does not yet show the key idea.", misconception=None if result == "correct" else (getattr(step, "feedback_incorrect", None) or "Try the defining relationship rather than a supporting detail."), remediationCategory="none" if result == "correct" else "simplify")


def grade_step(step: LearnStep, *, response: str | None, option_id: str | None) -> tuple[bool | None, str]:
    evaluation = evaluate_step(step, response=response, option_id=option_id)
    if evaluation.result == "insufficient_evidence":
        return None, "Continue when you are ready."
    return evaluation.result == "correct", evaluation.evidence if evaluation.result == "correct" else (step.feedback_incorrect or step.remediation or evaluation.misconception or "Not quite. Try a different way of thinking about it.")
