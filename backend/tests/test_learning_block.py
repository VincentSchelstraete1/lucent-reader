from app.ingestion.base import SourceLocation
from app.normalization.schema import NormalizedBlock, SourceReference
from app.segmentation import SegmentationMetadata, build_learning_block, merge_source_references


def normalized_block(
    id: str,
    type: str,
    text: str | None,
    *,
    page: int | None = None,
    bbox=None,
    location: SourceLocation | None = None,
    raw_id: str | None = None,
) -> NormalizedBlock:
    return NormalizedBlock(
        id=id,
        type=type,
        text=text,
        source=SourceReference(
            page_start=page,
            page_end=page,
            raw_block_ids=[raw_id or id.removeprefix("normalized-")],
            bboxes=[bbox] if bbox else [],
            locations=[location] if location else [],
        ),
    )


def test_source_aggregation_unions_raw_ids_bboxes_and_locations():
    a = normalized_block("normalized-a", "paragraph", "First.", page=1, bbox=(0, 0, 10, 10), raw_id="a")
    b = normalized_block("normalized-b", "paragraph", "Second.", page=1, bbox=(0, 10, 10, 20), raw_id="b")
    merged = merge_source_references([a.source, b.source])
    assert merged.raw_block_ids == ["a", "b"]
    assert merged.bboxes == [(0, 0, 10, 10), (0, 10, 10, 20)]
    assert merged.page_start == 1
    assert merged.page_end == 1


def test_source_aggregation_computes_min_max_page_range():
    a = normalized_block("normalized-a", "paragraph", "First.", page=3, raw_id="a")
    b = normalized_block("normalized-b", "paragraph", "Second.", page=4, raw_id="b")
    merged = merge_source_references([a.source, b.source])
    assert merged.page_start == 3
    assert merged.page_end == 4


def test_pdf_provenance_spans_multiple_pages():
    heading = normalized_block(
        "normalized-h", "heading", "Cache Associativity",
        page=3, bbox=(72, 40, 300, 60),
        location=SourceLocation(kind="page", index=3), raw_id="page-3-block-1",
    )
    para_page3 = normalized_block(
        "normalized-p1", "paragraph", "Direct-mapped caches place a block in one location.",
        page=3, bbox=(72, 70, 500, 120),
        location=SourceLocation(kind="page", index=3), raw_id="page-3-block-2",
    )
    para_page4 = normalized_block(
        "normalized-p2", "paragraph", "This continues onto the next physical page.",
        page=4, bbox=(72, 60, 500, 100),
        location=SourceLocation(kind="page", index=4), raw_id="page-4-block-1",
    )
    block = build_learning_block(
        "learning-block-1",
        constituents=[heading, para_page3, para_page4],
        block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
        title="Cache Associativity",
    )
    assert block.source.page_start == 3
    assert block.source.page_end == 4
    assert block.source.locations == [
        SourceLocation(kind="page", index=3),
        SourceLocation(kind="page", index=3),
        SourceLocation(kind="page", index=4),
    ]
    assert block.source.raw_block_ids == ["page-3-block-1", "page-3-block-2", "page-4-block-1"]
    assert "Direct-mapped" in block.text
    assert "continues onto the next" in block.text
    assert "Cache Associativity" not in block.text  # heading text lives in `title`, not duplicated into body


def test_pptx_provenance_spans_multiple_shapes_on_one_slide():
    title = normalized_block(
        "normalized-t", "heading", "Memory Hierarchy",
        location=SourceLocation(kind="slide", index=5, sequence_id="shape-1"), raw_id="slide-5-shape-1",
    )
    body_a = normalized_block(
        "normalized-a", "paragraph", "Registers are fastest but smallest.",
        location=SourceLocation(kind="slide", index=5, sequence_id="shape-2"), raw_id="slide-5-shape-2",
    )
    body_b = normalized_block(
        "normalized-b", "paragraph", "Cache sits between registers and main memory.",
        location=SourceLocation(kind="slide", index=5, sequence_id="shape-3"), raw_id="slide-5-shape-3",
    )
    block = build_learning_block(
        "learning-block-2",
        constituents=[title, body_a, body_b],
        block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
        title="Memory Hierarchy",
    )
    assert block.source.page_start is None  # PPTX never populates the legacy PDF page field
    assert block.source.page_end is None
    assert [location.sequence_id for location in block.source.locations] == ["shape-1", "shape-2", "shape-3"]
    assert all(location.kind == "slide" and location.index == 5 for location in block.source.locations)


def test_docx_sequence_provenance_has_no_pages_or_bboxes():
    heading = normalized_block(
        "normalized-h", "heading", "Virtual Memory",
        location=SourceLocation(kind="document", sequence_id="paragraph-1"), raw_id="docx-paragraph-1",
    )
    body = normalized_block(
        "normalized-b", "paragraph", "Virtual memory decouples logical from physical addresses.",
        location=SourceLocation(kind="document", sequence_id="paragraph-2"), raw_id="docx-paragraph-2",
    )
    block = build_learning_block(
        "learning-block-3",
        constituents=[heading, body],
        block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
        title="Virtual Memory",
    )
    assert block.source.page_start is None
    assert block.source.bboxes == []
    assert [location.sequence_id for location in block.source.locations] == ["paragraph-1", "paragraph-2"]
    assert all(location.kind == "document" for location in block.source.locations)


def test_table_and_image_attachment_excluded_from_text_but_kept_in_provenance():
    heading = normalized_block("normalized-h", "heading", "Cache Levels", raw_id="a")
    para = normalized_block("normalized-p", "paragraph", "Latency grows with each level.", raw_id="b")
    table = normalized_block("normalized-t", "table", "| L1 | 4 cycles |\n| --- | --- |", raw_id="c")
    image = NormalizedBlock(
        id="normalized-i", type="image", text=None,
        source=SourceReference(page_start=None, page_end=None, raw_block_ids=["d"], bboxes=[]),
        source_image_id="normalized-image-1",
    )
    block = build_learning_block(
        "learning-block-4",
        constituents=[heading, para, table, image],
        block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
        title="Cache Levels",
        attached_table_ids=["normalized-t"],
        attached_image_ids=["normalized-image-1"],
    )
    assert "Latency grows" in block.text
    assert "L1" not in block.text  # table text is attached, not inlined into prose
    assert "normalized-t" in block.normalized_block_ids  # but full provenance is preserved
    assert "normalized-i" in block.normalized_block_ids
    assert block.attached_table_ids == ["normalized-t"]
    assert block.attached_image_ids == ["normalized-image-1"]


def test_consecutive_list_blocks_join_with_single_newline_not_blank_line():
    para = normalized_block("normalized-p", "paragraph", "Supporting techniques include:", raw_id="a")
    item1 = normalized_block("normalized-l1", "list", "- Demand paging", raw_id="b")
    item2 = normalized_block("normalized-l2", "list", "- Page replacement", raw_id="c")
    block = build_learning_block(
        "learning-block-5",
        constituents=[para, item1, item2],
        block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
    )
    assert block.text == "Supporting techniques include:\n\n- Demand paging\n- Page replacement"


def test_learning_block_construction_is_deterministic():
    a = normalized_block("normalized-a", "paragraph", "Same content.", page=1, raw_id="a")
    segmentation = SegmentationMetadata(method="structural", boundary_reason="test")
    first = build_learning_block("learning-block-1", constituents=[a], block_type="section", segmentation=segmentation)
    second = build_learning_block("learning-block-1", constituents=[a], block_type="section", segmentation=segmentation)
    assert first == second
    assert first.id == second.id == "learning-block-1"


def test_character_count_matches_assembled_text_length():
    a = normalized_block("normalized-a", "paragraph", "Twelve chars.", raw_id="a")
    block = build_learning_block(
        "learning-block-1", constituents=[a], block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
    )
    assert block.character_count == len(block.text) == len("Twelve chars.")
