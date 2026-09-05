from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.schemas.learn import (
    LearnEvaluation, LearnPlan, LearnStep, LearnStepView, LearningObjective, MultipleChoiceStep, VisualSpec,
    OrderingStep, PredictionStep, ProblemStep, ShortAnswerStep, TeachStep, WalkthroughStep, MatchingStep, LabelingStep, FillBlankStep, TeachBackStep, WorkedStepStep,
)
from app.services.learner_content import learner_text_quality_issues, student_facing_quality_issues, student_text


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", value.lower()) if len(word) > 2}


def _bounded_plan_id(prefix: str, *parts: object) -> str:
    """Build stable Learn plan IDs without copying arbitrary source IDs."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()[:14]
    return f"{prefix}-{digest}"


def _components(section: dict) -> list[dict]:
    return [item for item in section.get("components", []) if isinstance(item, dict)]


def _source_ids(section: dict) -> tuple[list[str], list[str]]:
    return list(section.get("id") and [str(section["id"])] or []), [str(item) for item in section.get("sourceBlockIds", [])]


def synthesize_visual_spec(component: dict, title: str, section_ids: list[str], block_ids: list[str]) -> VisualSpec | None:
    """Translate grounded SectionNote structure into the constrained visual DSL."""
    kind = str(component.get("kind", ""))
    raw_nodes = component.get("nodes") or component.get("items") or []
    generated_edges: list[dict] = []
    if kind == "structure" and not raw_nodes:
        root = component.get("root") or {}
        # Flatten nested containment into explicit relationships. This gives
        # the renderer enough meaning to show composition, not just indentation.
        def flatten(item: dict, parent: str | None = None) -> None:
            if not isinstance(item, dict) or not item.get("id"):
                return
            raw_nodes.append(item)
            if parent:
                generated_edges.append({"source": parent, "target": str(item["id"]), "label": "contains"})
            for child in item.get("children", []) or []:
                flatten(child, str(item["id"]))
        if root:
            flatten(root)
    nodes = []
    for item in raw_nodes[:16]:
        if isinstance(item, dict) and item.get("id") and (item.get("label") or item.get("name")):
            values = item.get("values") if isinstance(item.get("values"), dict) else {}
            value_detail = "; ".join(f"{key}: {value}" for key, value in list(values.items())[:4])
            group = _clean(item.get("group")) or None
            if kind == "comparison" and not group:
                # Comparisons are two semantic sides, not one vertical list.
                group = "left" if len(nodes) < max(1, len(raw_nodes) // 2) else "right"
            nodes.append({"id": str(item["id"]), "label": _clean(item.get("label") or item.get("name")), "detail": _clean(item.get("detail") or item.get("description") or value_detail) or None, "group": group})
    if len(nodes) < 2:
        return None
    edges = []
    for edge in ((component.get("edges") or []) + generated_edges)[:24]:
        if isinstance(edge, dict) and edge.get("source") and edge.get("target"):
            edges.append({"source": str(edge["source"]), "target": str(edge["target"]), "label": _clean(edge.get("label") or edge.get("relation")) or None})
    valid_ids = {node["id"] for node in nodes}; edges = [edge for edge in edges if edge["source"] in valid_ids and edge["target"] in valid_ids]
    structure_type = str(component.get("structureType", "hierarchy"))
    visual_type = {"flow": "process_flow", "relationship_map": "relationship_map", "comparison": "comparison", "structure": "hierarchy" if structure_type == "hierarchy" else "spatial_structure"}.get(kind, "diagram")
    stages = []
    if visual_type in {"process_flow", "comparison"}:
        for node in nodes[:8]:
            outgoing = next((edge for edge in edges if edge["source"] == node["id"]), None)
            incoming = next((edge for edge in edges if edge["target"] == node["id"]), None)
            relation = outgoing or incoming
            if node.get("detail"):
                narration = node["detail"]
            elif relation and outgoing:
                target = next((item["label"] for item in nodes if item["id"] == outgoing["target"]), "the next state")
                narration = f"{node['label']} leads to {target}" + (f" through {outgoing['label']}" if outgoing.get("label") else "") + "."
            elif relation:
                source = next((item["label"] for item in nodes if item["id"] == incoming["source"]), "the prior state")
                narration = f"{node['label']} follows {source}" + (f" through {incoming['label']}" if incoming.get("label") else "") + "."
            else:
                narration = f"Compare the role of {node['label']} with the other source-supported parts shown here."
            stages.append({"title": f"Focus on {node['label']}", "explanation": narration, "activeNodeIds": [node["id"]]})
    animations = [{"operation": "flow", "targetIds": [edge["source"], edge["target"]], "durationMs": 850, "explanation": edge.get("label") or "Follow the relationship."} for edge in edges[:16]] if visual_type in {"process_flow", "causal_chain", "sequence", "hierarchy", "spatial_structure"} else []
    if visual_type == "comparison" and len(nodes) >= 2:
        animations = [{"operation": "compare", "targetIds": [node["id"] for node in nodes[:2]], "durationMs": 1400, "explanation": "Compare the two mechanisms side by side."}]
    return VisualSpec(type=visual_type, title=_clean(component.get("title") or title), purpose="See the relationships that make this concept work.", nodes=nodes, edges=edges, stages=stages, animations=animations, sourceSectionIds=section_ids, sourceBlockIds=block_ids)


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
        section_identity = str(section.get("id", len(objectives)))
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
            refresher = TeachStep(id=_bounded_plan_id("teach", section_identity), type="teach", title="Quick refresher" if familiarity == "reviewing" else "Build the mental model", content=big_idea, sourceSectionIds=section_ids, sourceBlockIds=block_ids)
            visual_candidate = next((c for c in comps if c.get("kind") in {"flow", "structure", "relationship_map", "comparison"}), None)
            if visual_candidate:
                refresher.visual_spec = synthesize_visual_spec(visual_candidate, title, section_ids, block_ids)
            steps.append(refresher)
            comparison = next((c for c in comps if c.get("kind") == "comparison" and len(c.get("items", [])) >= 2), None)
            if comparison:
                pairs = [{"id": str(item.get("id")), "label": _clean(item.get("name"))} for item in comparison.get("items", [])[:8] if item.get("id") and item.get("name")]
                dimension = (comparison.get("dimensions") or ["key distinction"])[0]
                matches = {pair["id"]: _clean(next((item.get("values", {}).get(dimension) for item in comparison.get("items", []) if str(item.get("id")) == pair["id"]), "")) for pair in pairs}
                values = [value for value in dict.fromkeys(matches.values()) if value]
                if len(pairs) >= 2 and len(values) >= 2:
                    steps.append(MatchingStep(id=_bounded_plan_id("match", section_identity), type="matching", title="Compare the two cases", prompt=f"Match each part of {title} with the effect described in the material.", pairs=pairs, matches=matches, sourceSectionIds=section_ids, sourceBlockIds=block_ids, hints=[f"Compare how each part of {title} changes function.", f"Look for the consequence described for each pathway."], feedbackIncorrect=f"Keep the two effects in {title} separate, then match each cause with its consequence."))
            walkthrough_index = next((i for i, c in enumerate(comps) if c.get("kind") == "walkthrough" and c.get("mechanism")), None)
            if walkthrough_index is not None and goal == "understand":
                steps.append(WalkthroughStep(id=_bounded_plan_id("visual", section_identity), type="walkthrough", title="See the mechanism change", sectionId=str(section.get("id")), componentIndex=walkthrough_index, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            elif any(c.get("kind") == "flow" and len(c.get("nodes", [])) >= 2 for c in comps):
                flow = next(c for c in comps if c.get("kind") == "flow" and len(c.get("nodes", [])) >= 2)
                node_ids = [str(node.get("id")) for node in flow.get("nodes", []) if node.get("id")]
                options = [{"id": node_id, "label": _clean(next((node.get("label") for node in flow.get("nodes", []) if str(node.get("id")) == node_id), node_id))} for node_id in node_ids]
                steps.append(OrderingStep(id=_bounded_plan_id("order", section_identity), type="ordering", title="Put the process in order", prompt=f"What is the sequence for {title}?", items=options[:8], correctOrder=node_ids[:8], feedbackIncorrect="Follow the transition from one step to the next in the process.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                if goal == "understand" and len(options) >= 3:
                    steps.append(PredictionStep(id=_bounded_plan_id("predict", section_identity), type="prediction", title="Predict the next transition", prompt=f"What happens immediately after {_clean(options[0]['label'])}?", options=options[1:4], answerId=options[1]["id"], reveal=f"The process continues with {_clean(options[1]['label'])}, which sets up the next transition.", feedbackIncorrect="Trace the direction of the process from the first step.", hints=["Look at the first outgoing transition.", "Ask what state must be established next."], sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            elif goal == "understand" and any(c.get("kind") == "key_definition" for c in comps):
                definition = next(c for c in comps if c.get("kind") == "key_definition")
                answer = _clean(definition.get("definition")) or big_idea
                term = _clean(definition.get('term')) or title
                steps.append(ShortAnswerStep(id=_bounded_plan_id("free", section_identity), type="short_answer", title="Say it in your own words", prompt=f"What does {term} mean?", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect=f"Include what {term} is and what it does.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(TeachBackStep(id=_bounded_plan_id("teachback", section_identity), type="teach_back", title="Teach it back", prompt=f"Explain {term} to a classmate in one or two sentences.", requiredConcepts=list(_words(answer))[:5], hints=[f"Start with what {term} changes.", "Then explain why that change matters."], feedbackIncorrect=f"Connect {term} to its effect.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            elif any(c.get("kind") == "structure" and c.get("root") for c in comps):
                structure = next(c for c in comps if c.get("kind") == "structure" and c.get("root"))
                targets = []
                def collect(node: dict):
                    if node.get("id") and node.get("label"): targets.append({"id": str(node["id"]), "label": _clean(node["label"])})
                    for child in node.get("children", []) or []: collect(child)
                collect(structure["root"])
                targets = targets[:6]; labels = [{"id": item["id"], "label": item["label"]} for item in targets]
                if len(targets) >= 2:
                    steps.append(LabelingStep(id=_bounded_plan_id("label", section_identity), type="labeling", title="Label the structure", prompt=f"Name the important parts of {title}.", targets=targets, labels=labels, answerMap={item["id"]: item["id"] for item in targets}, sourceSectionIds=section_ids, sourceBlockIds=block_ids, hints=["Start with the outermost part.", "Use the labels from the diagram."], feedbackIncorrect="Match each label to the part it names."))
            else:
                answer = takeaways[0] if takeaways else big_idea
                steps.append(MultipleChoiceStep(id=_bounded_plan_id("check", section_identity), type="multiple_choice", title="Check the central idea", prompt=f"Which statement accurately describes {title}?", options=[{"id": "a", "label": answer[:160]}, {"id": "b", "label": f"{title} has the opposite effect: {answer[:120]}"}, {"id": "c", "label": f"{title} changes a different part of the system."}], answerId="a", feedbackIncorrect=f"Return to this claim about {title}: {answer[:260]}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                if goal == "exam":
                    steps.append(ShortAnswerStep(id=_bounded_plan_id("exam", section_identity), type="short_answer", title="Explain the distinction", prompt=f"State the exam-relevant point about {title}.", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect=f"State the claim about {title} and its consequence.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
        elif goal == "memorize":
            definition = next((c for c in comps if c.get("kind") == "key_definition" and _clean(c.get("term")) and _clean(c.get("definition"))), None)
            term = _clean(definition.get("term")) if definition else title
            answer = _clean(definition.get("definition")) if definition else (takeaways[0] if takeaways else big_idea)
            steps.append(TeachStep(id=_bounded_plan_id("definition", section_identity), type="teach", title=term, content=answer, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            steps.append(MultipleChoiceStep(id=_bounded_plan_id("recognize", section_identity), type="multiple_choice", title="Recognize it", prompt=f"Which statement defines {term}?", options=[{"id": "a", "label": answer[:160]}, {"id": "b", "label": f"{term} produces the opposite effect."}, {"id": "c", "label": f"{term} changes a different part of the system."}], answerId="a", feedbackIncorrect=f"The definition of {term} is: {answer[:220]}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            steps.append(ShortAnswerStep(id=_bounded_plan_id("recall", section_identity), type="short_answer", title="Retrieve it", prompt=f"In your own words, what is {term}?", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect=f"State what {term} means and what it affects.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            steps.append(FillBlankStep(id=_bounded_plan_id("fill", section_identity), type="fill_blank", title="Fill the key term", prompt=f"Complete: {term} means ____.", acceptedAnswers=[answer], hints=[f"Recall what {term} changes."], feedbackIncorrect=f"Use the definition of {term}: {answer[:220]}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            # Keep a final unaided recall check after the fill-in interaction;
            # recognition/partial completion must not be treated as durable
            # recall evidence.
            steps.append(ShortAnswerStep(id=_bounded_plan_id("recall-final", section_identity), type="short_answer", title="Recall it without a cue", prompt=f"In your own words, what is {term}?", acceptedAnswers=[answer], requiredConcepts=list(_words(answer))[:5], feedbackIncorrect=f"State what {term} means and what it affects.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
        else:  # solve
            example = next((c for c in comps if c.get("kind") in {"worked_example", "equation"}), None)
            if example and _clean(example.get("result")):
                problem = _clean(example.get("problem") or example.get("equation") or title)
                result = _clean(example.get("result"))
                steps.append(TeachStep(id=_bounded_plan_id("worked", section_identity), type="teach", title="See one worked path", content=f"{problem} → {result}", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(ProblemStep(id=_bounded_plan_id("apply", section_identity), type="problem", title="Try the key step", prompt=f"What result should this method produce for: {problem}?", responseType="short_answer", acceptedAnswers=[result], solution=result, hints=[f"Start with the operation used for {problem}.", "Keep the same operation order."], feedbackIncorrect=f"Rework {problem} one operation at a time.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(WorkedStepStep(id=_bounded_plan_id("worked-step", section_identity), type="worked_step", title="Complete the next step", prompt=f"Complete the next step for: {problem}.", acceptedAnswers=[result], solution=result, hints=[f"Reuse the operation shown for {problem}.", "Check each quantity before combining them."], feedbackIncorrect=f"Use the worked operation for {problem}, then try the step again.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))
            else:
                answer = takeaways[0] if takeaways else big_idea
                steps.append(TeachStep(id=_bounded_plan_id("method", section_identity), type="teach", title="Choose the method", content=big_idea, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
                steps.append(ProblemStep(id=_bounded_plan_id("apply", section_identity), type="problem", title="Apply the idea", prompt=f"State the key move used in {title}.", responseType="short_answer", acceptedAnswers=[answer], solution=answer, hints=[f"Start with the claim about {title}.", f"Use the terms that describe how {title} works."], feedbackIncorrect=f"Use the stated claim about {title} as your starting point.", sourceSectionIds=section_ids, sourceBlockIds=block_ids))

        # Never persist a contextless meta interaction.  If a future provider
        # emits one, replace it with a grounded explanation from this section
        # rather than leaking the placeholder to the learner.
        safe_steps = []
        for candidate in steps:
            grounded_id = f"grounded-{hashlib.sha256(f'{title}|{candidate.id}'.encode()).hexdigest()[:16]}"
            source_text = " ".join([title, big_idea, *takeaways, json.dumps(comps, default=str)])
            safe_steps.append(candidate if not student_facing_quality_issues(candidate, source_text) else TeachStep(id=grounded_id, type="teach", title=f"Understand {title}", content=big_idea, sourceSectionIds=section_ids, sourceBlockIds=block_ids))
        steps = safe_steps
        outcome = {"understand": f"Explain how {title} works.", "solve": f"Apply {title} to a new step.", "memorize": f"Recall the essential facts about {title}.", "exam": f"Recognize and use {title} under exam conditions."}[goal]
        objectives.append(LearningObjective(id=_bounded_plan_id("objective", section_identity), title=title, outcome=outcome, bottleneck=bottleneck, sourceSectionIds=section_ids, sourceBlockIds=block_ids, steps=steps))

    if not objectives:
        objectives = [LearningObjective(id="objective-overview", title="Material overview", outcome="Recall the main idea.", bottleneck="Identify what matters most.", steps=[TeachStep(id="overview-teach", type="teach", title="Main idea", content=_clean(note_payload.get("title")) or "Review the material.")])]
    return LearnPlan(goal=goal, familiarity=familiarity, objectives=objectives)


def plan_fingerprint(note_payload: dict, goal: str, familiarity: str) -> str:
    source = json.dumps(note_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"learn-v1:{goal}:{familiarity}:{source}".encode()).hexdigest()


def public_step(step: LearnStep, hints_used: int = 0) -> LearnStepView:
    data = step.model_dump(by_alias=True, exclude_none=True)
    options = data.get("options", [])
    if data["type"] == "matching":
        options = [{"id": str(value), "label": str(value)} for value in dict.fromkeys((data.get("matches") or {}).values())]
    if data["type"] == "labeling": options = data.get("labels", []); data["items"] = data.get("targets", [])
    visual_ref = data.get("visualRef")
    if data["type"] == "walkthrough":
        visual_ref = {"sectionId": data.get("sectionId"), "componentIndex": data.get("componentIndex")}
    items = data.get("items", [])
    if data["type"] == "matching":
        items = data.get("pairs", [])
    return LearnStepView(id=data["id"], type=data["type"], title=data["title"], prompt=data.get("prompt"), content=data.get("content"), options=options, items=items, visualSpec=data.get("visualSpec"), visualRef=visual_ref, sectionId=data.get("sectionId"), componentIndex=data.get("componentIndex"), hintsAvailable=max(0, len(step.hints) - hints_used), sourceSectionIds=list(getattr(step, "source_section_ids", [])), sourceBlockIds=list(getattr(step, "source_block_ids", [])))


def evaluate_step(step: LearnStep, *, response: str | None, option_id: str | None, ordered_ids: list[str] | None = None) -> LearnEvaluation:
    """Deterministic first-pass evaluator used by the adaptive runtime."""
    answer = _clean(option_id or response)
    if isinstance(step, (TeachStep, WalkthroughStep)):
        return LearnEvaluation(result="insufficient_evidence", confidence=0.15, evidence=f"Let's check what you noticed about {step.title}.", remediationCategory="none")
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
    if isinstance(step, MatchingStep):
        try: submitted = json.loads(response or "{}")
        except json.JSONDecodeError: submitted = {}
        hits = sum(1 for key, value in step.matches.items() if str(submitted.get(key)) == str(value)); result = "correct" if hits == len(step.matches) else "partially_correct" if hits else "incorrect"
        return LearnEvaluation(result=result, confidence=0.95 if result == "correct" else 0.7, evidence=f"Matched {hits} of {len(step.matches)} relationships.", misconception=None if result == "correct" else "Some relationships need to be distinguished.", remediationCategory="simplify" if result != "correct" else "none")
    if isinstance(step, LabelingStep):
        try: submitted = json.loads(response or "{}")
        except json.JSONDecodeError: submitted = {}
        hits = sum(1 for key, value in step.answer_map.items() if str(submitted.get(key)) == str(value)); result = "correct" if hits == len(step.answer_map) else "partially_correct" if hits else "incorrect"
        return LearnEvaluation(result=result, confidence=0.95 if result == "correct" else 0.7, evidence=f"Placed {hits} of {len(step.answer_map)} labels correctly.", misconception=None if result == "correct" else "Review which label belongs to each part.", remediationCategory="change_modality" if result != "correct" else "none")
    if isinstance(step, ProblemStep) and step.response_type == "numeric":
        try:
            correct = abs(float(answer) - float(step.answer or 0)) <= float(step.tolerance or 0.01)
        except (TypeError, ValueError):
            correct = False
        return LearnEvaluation(result="correct" if correct else "incorrect", confidence=0.98 if correct else 0.85, evidence="Numeric result is within the accepted tolerance." if correct else "Numeric result is outside the accepted tolerance.", misconception=None if correct else "Check the operation and units before calculating again.", remediationCategory="none" if correct else "example")
    normalized = _words(answer)
    accepted = any((bool(_words(item)) and _words(item) <= normalized) or _clean(item).casefold() == answer.casefold() for item in getattr(step, "accepted_answers", []))
    required = set(getattr(step, "required_concepts", []))
    if accepted or (bool(required) and required <= normalized):
        result = "correct"
    elif normalized and required and normalized.intersection(required):
        result = "partially_correct"
    else:
        result = "incorrect"
    return LearnEvaluation(result=result, confidence=0.9 if result == "correct" else 0.65 if result == "partially_correct" else 0.82, evidence="Response captures the key source-grounded idea." if result == "correct" else "Response captures only part of the key idea." if result == "partially_correct" else "Response does not yet show the key idea.", misconception=None if result == "correct" else (getattr(step, "feedback_incorrect", None) or "State what changes and what effect it produces."), remediationCategory="none" if result == "correct" else "simplify")


_student_text = student_text


def grade_step(step: LearnStep, *, response: str | None, option_id: str | None) -> tuple[bool | None, str]:
    evaluation = evaluate_step(step, response=response, option_id=option_id)
    if evaluation.result == "insufficient_evidence":
        return None, "Continue when you are ready."
    return evaluation.result == "correct", evaluation.evidence if evaluation.result == "correct" else (step.feedback_incorrect or step.remediation or evaluation.misconception or "Not quite. Try a different way of thinking about it.")
