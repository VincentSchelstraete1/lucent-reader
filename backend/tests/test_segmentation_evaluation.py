from app.segmentation import SegmentationConfig, paragraph_only_baseline, segment_document
from app.segmentation.eval_dataset import DEV_EXAMPLES, HOLDOUT_EXAMPLES
from app.segmentation.evaluation import evaluate_segmentation


def _structural_only(document):
    return segment_document(document, apply_size_constraints=False)


def _structural_and_size(document):
    return segment_document(document, SegmentationConfig())


def test_dataset_is_stratified_and_split_before_any_evaluation():
    dev_categories = {example.category for example in DEV_EXAMPLES}
    assert {"pdf_technical_prose", "pdf_lecture_notes", "pdf_table", "pdf_figure", "pptx_slides", "docx_structured_notes"} <= dev_categories
    assert len(DEV_EXAMPLES) == 9
    assert len(HOLDOUT_EXAMPLES) == 4
    assert set(e.id for e in DEV_EXAMPLES).isdisjoint(e.id for e in HOLDOUT_EXAMPLES)


def test_dev_paragraph_only_baseline_has_perfect_recall_but_poor_precision():
    metrics = evaluate_segmentation(DEV_EXAMPLES, paragraph_only_baseline)
    assert metrics.recall == 1.0
    assert metrics.precision < 0.3  # every block boundary is "predicted", most are wrong


def test_dev_structural_segmentation_is_perfect_on_the_curated_dev_set():
    metrics = evaluate_segmentation(DEV_EXAMPLES, _structural_only)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0


def test_dev_size_constraints_do_not_change_results_when_nothing_is_oversized():
    structural = evaluate_segmentation(DEV_EXAMPLES, _structural_only)
    with_size = evaluate_segmentation(DEV_EXAMPLES, _structural_and_size)
    assert structural == with_size


def test_holdout_run_once_structural_and_size_is_the_selected_candidate():
    # This is the one holdout run. mixed_hard_01 (zero structural signal) and
    # mixed_hard_02 (an upstream classify_block heading misclassification -
    # see eval_dataset.py's comment) are the two deliberately adversarial
    # examples; pdf_lecture_02 and pptx_slides_03 - numbered-heading ancestry
    # and cross-slide spanning - are both exactly right.
    metrics = evaluate_segmentation(HOLDOUT_EXAMPLES, _structural_and_size)
    assert (metrics.true_positives, metrics.false_positives, metrics.false_negatives) == (2, 1, 1)
    assert metrics.precision == 0.6667
    assert metrics.recall == 0.6667
    assert metrics.f1 == 0.6667


def test_holdout_paragraph_only_baseline_for_comparison():
    metrics = evaluate_segmentation(HOLDOUT_EXAMPLES, paragraph_only_baseline)
    assert metrics.recall == 1.0
    assert metrics.precision < 0.4
