from app.services.learn_engine import build_learn_plan, evaluate_step, grade_step
from app.schemas.learn import MultipleChoiceStep, OrderingStep, ShortAnswerStep


def _note():
    return {"title": "Vectors", "sectionNotes": [{
        "id": "s1", "title": "Projection", "bigIdea": "Projection keeps the component along a direction.",
        "sourceBlockIds": ["b1"], "keyTakeaways": ["Projection isolates the parallel component."],
        "components": [{"kind": "key_definition", "term": "Projection", "definition": "The component along a direction."}],
    }]}


def test_goal_changes_the_learning_strategy():
    understand = build_learn_plan(_note(), "understand", "new")
    solve = build_learn_plan(_note(), "solve", "new")
    memorize = build_learn_plan(_note(), "memorize", "new")
    exam = build_learn_plan(_note(), "exam", "new")
    assert [step.type for step in understand.objectives[0].steps] != [step.type for step in memorize.objectives[0].steps]
    assert [step.type for step in solve.objectives[0].steps] != [step.type for step in memorize.objectives[0].steps]
    assert [step.type for step in exam.objectives[0].steps] == ["teach", "multiple_choice", "short_answer"]
    assert memorize.objectives[0].steps[-1].type == "short_answer"


def test_short_answer_accepts_concept_words_without_exact_sentence_match():
    step = ShortAnswerStep(id="s", type="short_answer", title="Recall", prompt="What is it?", acceptedAnswers=["component along a direction"], requiredConcepts=["component", "direction"])
    assert grade_step(step, response="The component along that direction", option_id=None)[0] is True


def test_multiple_choice_rejects_unknown_option():
    step = MultipleChoiceStep(id="s", type="multiple_choice", title="Check", prompt="Choose", options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], answerId="a")
    assert grade_step(step, response=None, option_id="unknown")[0] is False


def test_ordering_evaluation_reports_partial_understanding():
    step = OrderingStep(id="flow", type="ordering", title="Order", prompt="Order", items=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}], correctOrder=["a", "b", "c"])
    evaluation = evaluate_step(step, response=None, option_id=None, ordered_ids=["a", "c", "b"])
    assert evaluation.result == "partially_correct"
    assert evaluation.remediation_category == "simplify"
