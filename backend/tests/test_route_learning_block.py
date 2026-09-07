from app.normalization.schema import NormalizedBlock, SourceReference
from app.routing import route_learning_block
from app.segmentation import SegmentationMetadata, build_learning_block


def test_route_learning_block_routes_its_text_and_carries_the_block_id():
    block_text = "First the operating system loads the program. Next it initializes the process, then transfers control."
    constituent = NormalizedBlock(
        id="normalized-a", type="paragraph", text=block_text,
        source=SourceReference(page_start=1, page_end=1, raw_block_ids=["a"], bboxes=[]),
    )
    learning_block = build_learning_block(
        "learning-block-1", constituents=[constituent], block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
    )
    decision = route_learning_block(learning_block)
    assert decision.learning_block_id == "learning-block-1"
    assert decision.type == "process"
    assert decision.method == "deterministic"
    assert decision.fallback_used is False
    assert len(decision.scores) == 7
