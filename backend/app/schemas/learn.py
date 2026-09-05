from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


LearnGoal = Literal["understand", "solve", "memorize", "exam"]
Familiarity = Literal["new", "somewhat_familiar", "reviewing"]
LearnStatus = Literal["active", "completed", "stopped", "abandoned"]
EvaluationResult = Literal["correct", "partially_correct", "incorrect", "insufficient_evidence"]
RemediationCategory = Literal["none", "simplify", "example", "prerequisite", "change_modality", "revisit"]
ConceptStateName = Literal["NOT_SEEN", "INTRODUCED", "DEVELOPING", "DEMONSTRATED", "NEEDS_REVIEW", "STRUGGLING"]
PedagogicalStrategy = Literal["DIRECT_INSTRUCTION", "SOCRATIC_PROBE", "CONCEPTUAL_EXPLANATION", "VISUAL_MODEL", "ANIMATED_MECHANISM", "WORKED_EXAMPLE", "SCAFFOLDED_PRACTICE", "GUIDED_DISCOVERY", "ANALOGY", "CONCRETE_EXAMPLE", "COUNTEREXAMPLE", "CONTRAST_CASE", "EXAMPLE_NONEXAMPLE", "PREREQUISITE_REPAIR", "ERROR_CORRECTION", "RETRIEVAL_PRACTICE", "TEACH_BACK", "TRANSFER_PRACTICE", "DELAYED_RECHECK"]
ScaffoldLevel = Literal["FULL", "GUIDED", "PARTIAL", "INDEPENDENT", "TRANSFER"]
ReviewDue = Literal["LATER_THIS_SESSION", "NEXT_SESSION", "FUTURE_REVIEW"]
ContentPolicy = Literal["CONCEPTUAL", "PROCESS", "QUANTITATIVE", "MEMORIZATION", "CS_SYSTEMS"]
TutorActionType = Literal[
    "teach_concept", "clarify_definition", "give_example", "give_analogy",
    "ask_multiple_choice", "ask_free_response", "ask_prediction", "ask_ordering",
    "give_hint", "revisit_prerequisite", "revisit_concept", "increase_difficulty",
    "decrease_difficulty", "advance_to_related_concept",
    "give_worked_example", "show_process_visual", "show_diagram", "show_visual", "show_animation", "show_comparison", "show_process", "simplify_explanation", "give_counterexample", "ask_matching", "ask_labeling", "ask_fill_blank", "ask_worked_step", "ask_teach_back", "schedule_revisit",
]
PedagogicalGoal = Literal[
    "BUILD_INTUITION", "EXPLAIN_CONCEPT", "CORRECT_MISCONCEPTION",
    "REPAIR_PREREQUISITE", "DEMONSTRATE_PROCEDURE", "GUIDE_PRACTICE",
    "REDUCE_SCAFFOLDING", "STRENGTHEN_RECALL", "TEST_APPLICATION",
    "TEST_TRANSFER", "DELAYED_REVIEW", "VERIFY_UNDERSTANDING",
]
TutorToolName = Literal[
    "retrieve_source", "inspect_learner_memory", "inspect_prerequisites",
    "explain_concept", "give_example", "give_counterexample", "give_analogy",
    "show_visual", "set_visual_stage", "highlight_visual_element", "animate_visual",
    "focus_visual_region", "show_worked_example", "guide_problem_step",
    "ask_question", "ask_prediction", "ask_free_response", "ask_numeric",
    "ask_teach_back", "ask_transfer", "give_hint", "branch_to_prerequisite",
    "return_from_prerequisite", "schedule_revisit", "advance_objective", "finish_session",
]
VisualType = Literal["diagram", "process", "process_flow", "hierarchy", "causal_chain", "labeled_diagram", "relationship_map", "comparison", "sequence", "cycle", "spatial_structure", "state_transition", "timeline", "quantitative", "worked_derivation", "labeling", "ordering", "prediction", "staged_visual", "step_through"]
AnimationOperation = Literal["highlight", "move", "appear", "disappear", "transform", "pulse", "connect", "flow", "change_value", "focus", "compare"]


class VisualNode(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=100)
    detail: str | None = Field(default=None, max_length=260)
    group: str | None = Field(default=None, max_length=60)


class VisualEdge(BaseModel):
    source: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=40)
    label: str | None = Field(default=None, max_length=80)


class VisualAnimation(BaseModel):
    operation: AnimationOperation
    target_ids: list[str] = Field(alias="targetIds", min_length=1, max_length=8)
    duration_ms: int = Field(default=700, alias="durationMs", ge=100, le=3000)
    explanation: str | None = Field(default=None, max_length=240)


class VisualSpec(BaseModel):
    type: VisualType
    title: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=240)
    nodes: list[VisualNode] = Field(default_factory=list, max_length=16)
    edges: list[VisualEdge] = Field(default_factory=list, max_length=24)
    stages: list[dict] = Field(default_factory=list, max_length=8)
    animations: list[VisualAnimation] = Field(default_factory=list, max_length=16)
    answer_id: str | None = Field(default=None, alias="answerId")
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")

    @model_validator(mode="after")
    def references_are_valid(self):
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("visual node ids must be unique")
        if any(edge.source not in node_ids or edge.target not in node_ids for edge in self.edges):
            raise ValueError("visual edges must reference known nodes")
        if self.type in {"diagram", "process", "process_flow", "hierarchy", "causal_chain", "labeled_diagram", "relationship_map", "comparison", "sequence", "cycle", "spatial_structure", "state_transition", "timeline", "quantitative", "worked_derivation", "labeling", "ordering"} and not self.nodes:
            raise ValueError("structured visuals require nodes")
        if any(target not in node_ids for animation in self.animations for target in animation.target_ids):
            raise ValueError("visual animations must reference known nodes")
        return self


class LearnOption(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=160)


class LearnStepBase(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    feedback_correct: str | None = Field(default=None, alias="feedbackCorrect", max_length=500)
    feedback_incorrect: str | None = Field(default=None, alias="feedbackIncorrect", max_length=500)
    hints: list[str] = Field(default_factory=list, max_length=3)
    remediation: str | None = Field(default=None, max_length=500)
    visual_spec: VisualSpec | None = Field(default=None, alias="visualSpec")


class TeachStep(LearnStepBase):
    type: Literal["teach"]
    content: str = Field(min_length=1, max_length=900)
    visual_ref: dict | None = Field(default=None, alias="visualRef")


class MultipleChoiceStep(LearnStepBase):
    type: Literal["multiple_choice"]
    prompt: str = Field(min_length=1, max_length=500)
    options: list[LearnOption] = Field(min_length=2, max_length=5)
    answer_id: str = Field(alias="answerId", min_length=1, max_length=40)

    @model_validator(mode="after")
    def answer_exists(self):
        if self.answer_id not in {option.id for option in self.options}:
            raise ValueError("answerId must reference an option")
        return self


class ShortAnswerStep(LearnStepBase):
    type: Literal["short_answer"]
    prompt: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(alias="acceptedAnswers", min_length=1, max_length=8)
    required_concepts: list[str] = Field(default_factory=list, alias="requiredConcepts", max_length=6)


class NumericAnswerStep(LearnStepBase):
    type: Literal["numeric"]
    prompt: str = Field(min_length=1, max_length=500)
    answer: float
    tolerance: float = Field(default=0.01, ge=0, le=1000000)
    unit: str | None = Field(default=None, max_length=30)


class PredictionStep(LearnStepBase):
    type: Literal["prediction"]
    prompt: str = Field(min_length=1, max_length=500)
    options: list[LearnOption] = Field(min_length=2, max_length=5)
    answer_id: str = Field(alias="answerId", min_length=1, max_length=40)
    reveal: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def answer_exists(self):
        if self.answer_id not in {option.id for option in self.options}:
            raise ValueError("answerId must reference an option")
        return self


class OrderingStep(LearnStepBase):
    type: Literal["ordering"]
    prompt: str = Field(min_length=1, max_length=500)
    items: list[LearnOption] = Field(min_length=2, max_length=8)
    correct_order: list[str] = Field(alias="correctOrder", min_length=2, max_length=8)

    @model_validator(mode="after")
    def order_contract(self):
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)) or len(self.correct_order) != len(ids) or set(self.correct_order) != set(ids):
            raise ValueError("correctOrder must reference every ordering item exactly once")
        return self

class MatchingStep(LearnStepBase):
    type: Literal["matching"]
    prompt: str = Field(min_length=1, max_length=500)
    pairs: list[LearnOption] = Field(min_length=2, max_length=8)
    matches: dict[str, str] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def matching_contract(self):
        ids = {item.id for item in self.pairs}
        if set(self.matches) != ids or any(not str(value).strip() for value in self.matches.values()):
            raise ValueError("matches must reference every pair")
        return self

class LabelingStep(LearnStepBase):
    type: Literal["labeling"]
    prompt: str = Field(min_length=1, max_length=500)
    targets: list[LearnOption] = Field(min_length=2, max_length=8)
    labels: list[LearnOption] = Field(min_length=2, max_length=8)
    answer_map: dict[str, str] = Field(alias="answerMap", min_length=2, max_length=8)

    @model_validator(mode="after")
    def labeling_contract(self):
        target_ids = {item.id for item in self.targets}
        label_ids = {item.id for item in self.labels}
        if set(self.answer_map) != target_ids or not set(self.answer_map.values()) <= label_ids:
            raise ValueError("answerMap must reference every target and known label")
        return self

class FillBlankStep(LearnStepBase):
    type: Literal["fill_blank"]
    prompt: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(alias="acceptedAnswers", min_length=1, max_length=8)

class TeachBackStep(LearnStepBase):
    type: Literal["teach_back"]
    prompt: str = Field(min_length=1, max_length=500)
    required_concepts: list[str] = Field(default_factory=list, alias="requiredConcepts", max_length=8)

class WorkedStepStep(LearnStepBase):
    type: Literal["worked_step"]
    prompt: str = Field(min_length=1, max_length=500)
    accepted_answers: list[str] = Field(alias="acceptedAnswers", min_length=1, max_length=8)
    solution: str = Field(min_length=1, max_length=700)


class ProblemStep(LearnStepBase):
    type: Literal["problem"]
    prompt: str = Field(min_length=1, max_length=500)
    response_type: Literal["short_answer", "numeric"] = Field(alias="responseType")
    accepted_answers: list[str] = Field(default_factory=list, alias="acceptedAnswers", max_length=8)
    answer: float | None = None
    tolerance: float | None = Field(default=None, ge=0, le=1000000)
    solution: str = Field(min_length=1, max_length=700)

    @model_validator(mode="after")
    def response_contract(self):
        if self.response_type == "numeric" and self.answer is None:
            raise ValueError("numeric problem steps require an answer")
        if self.response_type == "short_answer" and not self.accepted_answers:
            raise ValueError("short-answer problem steps require accepted answers")
        return self


class WalkthroughStep(LearnStepBase):
    type: Literal["walkthrough"]
    section_id: str = Field(alias="sectionId", min_length=1)
    component_index: int = Field(alias="componentIndex", ge=0)


LearnStep = Annotated[Union[TeachStep, MultipleChoiceStep, ShortAnswerStep, NumericAnswerStep, PredictionStep, OrderingStep, MatchingStep, LabelingStep, FillBlankStep, TeachBackStep, WorkedStepStep, ProblemStep, WalkthroughStep], Field(discriminator="type")]


class LearningObjective(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=160)
    outcome: str = Field(min_length=1, max_length=300)
    bottleneck: str = Field(min_length=1, max_length=300)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    prerequisite_ids: list[str] = Field(default_factory=list, alias="prerequisiteIds", max_length=8)
    content_policy: ContentPolicy | None = Field(default=None, alias="contentPolicy")
    steps: list[LearnStep] = Field(min_length=1, max_length=8)


class LearnPlan(BaseModel):
    goal: LearnGoal
    familiarity: Familiarity
    objectives: list[LearningObjective] = Field(min_length=1, max_length=6)


class TutorAction(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    type: TutorActionType
    concept_id: str = Field(alias="conceptId", min_length=1, max_length=60)
    step_id: str | None = Field(default=None, alias="stepId")
    rationale: str = Field(min_length=1, max_length=300)
    strategy: PedagogicalStrategy = "DIRECT_INSTRUCTION"


class TutorToolCall(BaseModel):
    tool: TutorToolName
    arguments: dict = Field(default_factory=dict)


class TutorObservation(BaseModel):
    """Bounded learner context supplied to one tutor replanning decision."""
    session_id: str = Field(alias="sessionId", min_length=1, max_length=64)
    objective_id: str = Field(alias="objectiveId", min_length=1, max_length=60)
    current_concept: str = Field(alias="currentConcept", min_length=1, max_length=180)
    content_type: ContentPolicy = Field(alias="contentType", default="CONCEPTUAL")
    learner_goal: LearnGoal = Field(alias="learnerGoal")
    evidence: dict = Field(default_factory=dict)
    recent_attempts: list[dict] = Field(default_factory=list, alias="recentAttempts", max_length=8)
    misconceptions: list[str] = Field(default_factory=list, max_length=6)
    previous_diagnoses: list[str] = Field(default_factory=list, alias="previousDiagnoses", max_length=6)
    successful_strategies: list[str] = Field(default_factory=list, alias="successfulStrategies", max_length=8)
    failed_strategies: list[str] = Field(default_factory=list, alias="failedStrategies", max_length=8)
    successful_modalities: list[str] = Field(default_factory=list, alias="successfulModalities", max_length=8)
    failed_modalities: list[str] = Field(default_factory=list, alias="failedModalities", max_length=8)
    prerequisite_evidence: dict = Field(default_factory=dict, alias="prerequisiteEvidence")
    previous_tutor_actions: list[str] = Field(default_factory=list, alias="previousTutorActions", max_length=8)
    current_teaching_surface: str | None = Field(default=None, alias="currentTeachingSurface", max_length=120)
    current_visual: dict | None = Field(default=None, alias="currentVisual")
    current_visual_stage: int | None = Field(default=None, alias="currentVisualStage", ge=0, le=32)
    review_state: str | None = Field(default=None, alias="reviewState", max_length=32)
    source_blocks: list[dict] = Field(default_factory=list, alias="sourceBlocks", max_length=8)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds", max_length=8)
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds", max_length=12)
    candidate_steps: list[dict] = Field(default_factory=list, alias="candidateSteps", max_length=12)


class TutorDecision(BaseModel):
    """Bounded model output for one next-action decision."""
    hypothesis: str = Field(default="", max_length=500)
    diagnosis: str = Field(default="", max_length=240)
    confidence: float = Field(default=0.5, ge=0, le=1)
    pedagogical_goal: PedagogicalGoal = Field(default="VERIFY_UNDERSTANDING", alias="pedagogicalGoal")
    pedagogical_strategy: PedagogicalStrategy = Field(default="DIRECT_INSTRUCTION", alias="pedagogicalStrategy")
    teaching_action: TutorActionType = Field(default="teach_concept", alias="teachingAction")
    target_concept: str = Field(default="concept", alias="targetConcept", min_length=1, max_length=60)
    interaction_type: str | None = Field(default=None, alias="interactionType", max_length=32)
    scaffold_level: ScaffoldLevel = Field(default="FULL", alias="scaffoldLevel")
    visual_action: str | None = Field(default=None, alias="visualAction", max_length=40)
    prerequisite_branch: str | None = Field(default=None, alias="prerequisiteBranch", max_length=60)
    actions: list[TutorToolCall] = Field(default_factory=list, max_length=4)
    expected_evidence: str = Field(default="A response that demonstrates the target concept.", alias="expectedEvidence", max_length=300)
    transition_message: str = Field(default="Let's try a different way to build this understanding.", alias="transitionMessage", max_length=240)
    next_step_id: str | None = Field(default=None, alias="nextStepId", max_length=60)
    rationale: str = Field(default="A bounded action selected for the learner's current evidence.", max_length=300)


class ConceptEvidence(BaseModel):
    concept_id: str = Field(alias="conceptId")
    title: str
    state: ConceptStateName
    attempts: int = 0
    correct: int = 0
    partially_correct: int = Field(default=0, alias="partiallyCorrect")
    incorrect: int = 0
    insufficient_evidence: int = Field(default=0, alias="insufficientEvidence")
    hints_used: int = Field(default=0, alias="hintsUsed")
    interaction_types: list[str] = Field(default_factory=list, alias="interactionTypes")
    misconceptions: list[str] = Field(default_factory=list)
    immediate_success: bool = Field(default=False, alias="immediateSuccess")
    delayed_success: bool = Field(default=False, alias="delayedSuccess")
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    first_seen: str | None = Field(default=None, alias="firstSeen")
    last_seen: str | None = Field(default=None, alias="lastSeen")
    last_result: EvaluationResult | None = Field(default=None, alias="lastResult")
    diagnosis_type: str | None = Field(default=None, alias="diagnosisType")
    failed_strategies: list[str] = Field(default_factory=list, alias="failedStrategies")
    successful_strategies: list[str] = Field(default_factory=list, alias="successfulStrategies")
    failed_modalities: list[str] = Field(default_factory=list, alias="failedModalities")
    successful_modalities: list[str] = Field(default_factory=list, alias="successfulModalities")
    recognition_evidence: int = Field(default=0, alias="recognitionEvidence")
    recall_evidence: int = Field(default=0, alias="recallEvidence")
    explanation_evidence: int = Field(default=0, alias="explanationEvidence")
    application_evidence: int = Field(default=0, alias="applicationEvidence")
    transfer_evidence: int = Field(default=0, alias="transferEvidence")
    scaffolding_level: int = Field(default=0, alias="scaffoldingLevel", ge=0, le=4)
    scaffold: ScaffoldLevel = "FULL"
    review_due: ReviewDue | None = Field(default=None, alias="reviewDue")


class LearnEvaluation(BaseModel):
    result: EvaluationResult
    confidence: float = Field(ge=0, le=1)
    misconception: str | None = None
    evidence: str = Field(min_length=1, max_length=500)
    remediation_category: RemediationCategory = Field(alias="remediationCategory")


class LearnSessionReport(BaseModel):
    covered: list[str] = Field(default_factory=list)
    demonstrated: list[str] = Field(default_factory=list)
    developing: list[str] = Field(default_factory=list)
    struggles: list[str] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list, alias="needsReview")
    not_covered: list[str] = Field(default_factory=list, alias="notCovered")
    next_focus: list[str] = Field(default_factory=list, alias="nextFocus")
    misconceptions: list[str] = Field(default_factory=list)
    stopped: bool = False


class LearnSessionCreateRequest(BaseModel):
    goal: LearnGoal
    familiarity: Familiarity
    restart: bool = False


class LearnResponseRequest(BaseModel):
    response: str | None = None
    option_id: str | None = Field(default=None, alias="optionId")
    ordered_ids: list[str] | None = Field(default=None, alias="orderedIds")


class LearnHintResponse(BaseModel):
    hint: str
    hints_used: int = Field(alias="hintsUsed")

class AskLucentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

class AskLucentResponse(BaseModel):
    answer: str = Field(min_length=1, max_length=1800)
    scope: Literal["IN_SCOPE_SOURCE", "IN_SCOPE_CURRENT_CONCEPT", "IN_SCOPE_PREREQUISITE", "OUT_OF_SCOPE"]
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    tool: Literal["retrieve_source", "inspect_current_concept", "show_visual", "change_visual_stage", "request_explanation", "request_example", "none"] = "none"
    visual_action: dict | None = Field(default=None, alias="visualAction")

class AskLucentToolCall(BaseModel):
    tool: Literal["retrieve_source", "inspect_current_concept", "inspect_relevant_learner_evidence", "show_visual", "change_visual_stage", "highlight_visual_element", "request_example", "request_explanation", "revisit_prerequisite"]
    arguments: dict = Field(default_factory=dict)

class AskLucentModelResponse(BaseModel):
    answer: str = Field(min_length=1, max_length=1800)
    tool_calls: list[AskLucentToolCall] = Field(default_factory=list, alias="toolCalls", max_length=3)
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds", max_length=8)
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds", max_length=12)


class LearnStepView(BaseModel):
    id: str
    type: str
    title: str
    prompt: str | None = None
    content: str | None = None
    options: list[LearnOption] = Field(default_factory=list)
    items: list[LearnOption] = Field(default_factory=list)
    visual_spec: VisualSpec | None = Field(default=None, alias="visualSpec")
    visual_ref: dict | None = Field(default=None, alias="visualRef")
    section_id: str | None = Field(default=None, alias="sectionId")
    component_index: int | None = Field(default=None, alias="componentIndex")
    hints_available: int = Field(default=0, alias="hintsAvailable")
    source_section_ids: list[str] = Field(default_factory=list, alias="sourceSectionIds")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")


class LearnSessionResponse(BaseModel):
    id: str
    document_id: int = Field(alias="documentId")
    goal: LearnGoal
    familiarity: Familiarity
    status: LearnStatus
    objective_index: int = Field(alias="objectiveIndex")
    step_index: int = Field(alias="stepIndex")
    objective_count: int = Field(alias="objectiveCount")
    objective_title: str | None = Field(default=None, alias="objectiveTitle")
    step: LearnStepView | None = None
    feedback: str | None = None
    feedback_kind: Literal["correct", "incorrect", "info"] | None = Field(default=None, alias="feedbackKind")
    hints_used: int = Field(default=0, alias="hintsUsed")
    completed_objectives: int = Field(default=0, alias="completedObjectives")
    weak_objectives: list[str] = Field(default_factory=list, alias="weakObjectives")
    action: TutorAction | None = None
    evaluation: LearnEvaluation | None = None
    concept_states: list[ConceptEvidence] = Field(default_factory=list, alias="conceptStates")
    report: LearnSessionReport | None = None
    ended_reason: str | None = Field(default=None, alias="endedReason")
