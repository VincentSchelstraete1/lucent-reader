from app.ingestion.base import SourceLocation
from app.normalization.schema import NormalizedBlock, NormalizedDocument, NormalizedImage, NormalizedPage, SourceReference
from app.segmentation import SegmentationConfig, paragraph_only_baseline, segment_document
from app.segmentation.stages import group_structurally, heading_depth


def block(id: str, type: str, text: str | None, *, raw_id: str | None = None, page=None, location=None, source_image_id=None) -> NormalizedBlock:
    return NormalizedBlock(
        id=id, type=type, text=text,
        source=SourceReference(page_start=page, page_end=page, raw_block_ids=[raw_id or id], bboxes=[], locations=[location] if location else []),
        source_image_id=source_image_id,
    )


def document(pages: list[NormalizedPage], images: list[NormalizedImage] | None = None, source_type: str = "pdf") -> NormalizedDocument:
    from app.normalization.schema import NormalizationMetadata
    return NormalizedDocument(
        source_type=source_type, filename="fixture", page_count=len(pages), pages=pages, images=images or [],
        normalization_metadata=NormalizationMetadata(version="test", suppressed_artifacts=[], events=[], unresolved_artifacts=[], counters={}),
    )


def test_heading_depth_reads_numeric_prefix_and_defaults_to_one():
    assert heading_depth("3 Memory Systems") == 1
    assert heading_depth("3.1 Cache Associativity") == 2
    assert heading_depth("3.1.2 Set Associativity") == 3
    assert heading_depth("Unnumbered Title") == 1


def test_heading_only_group_is_dropped_but_still_contributes_ancestry():
    pages = [NormalizedPage(1, "", [
        block("h0", "heading", "Cache Systems"),
        block("h1", "heading", "3.1 Associativity"),
        block("p1", "paragraph", "Direct-mapped caches place a block in one location."),
    ])]
    blocks = segment_document(document(pages))
    assert len(blocks) == 1
    assert blocks[0].title == "3.1 Associativity"
    # "Cache Systems" is unnumbered (depth 1); "3.1 Associativity" is depth 2,
    # so it correctly becomes an ancestor even though it never got its own
    # LearningBlock (no body content preceded the next heading).
    assert blocks[0].heading_ancestry == ["Cache Systems"]


def test_pdf_coherent_block_spans_a_physical_page_boundary():
    page1 = NormalizedPage(1, "", [
        block("h1", "heading", "Cache Associativity", page=1, location=SourceLocation(kind="page", index=1)),
        block("p1", "paragraph", "Direct-mapped caches place a block in one location.", page=1, location=SourceLocation(kind="page", index=1)),
    ], location=SourceLocation(kind="page", index=1))
    page2 = NormalizedPage(2, "", [
        block("p2", "paragraph", "This continues the same topic with no new heading.", page=2, location=SourceLocation(kind="page", index=2)),
        block("h2", "heading", "Virtual Memory", page=2, location=SourceLocation(kind="page", index=2)),
        block("p3", "paragraph", "Virtual memory decouples addresses.", page=2, location=SourceLocation(kind="page", index=2)),
    ], location=SourceLocation(kind="page", index=2))
    blocks = segment_document(document([page1, page2]))
    assert len(blocks) == 2
    assert blocks[0].title == "Cache Associativity"
    assert blocks[0].source.page_start == 1
    assert blocks[0].source.page_end == 2
    assert "continues the same topic" in blocks[0].text
    assert blocks[1].title == "Virtual Memory"
    assert blocks[1].source.page_start == blocks[1].source.page_end == 2


def test_pptx_slide_can_produce_multiple_learning_blocks():
    slide = NormalizedPage(None, "", [
        block("t1", "heading", "Topic A", location=SourceLocation(kind="slide", index=1, sequence_id="shape-1")),
        block("b1", "paragraph", "Explanation of topic A.", location=SourceLocation(kind="slide", index=1, sequence_id="shape-2")),
        block("t2", "heading", "Topic B", location=SourceLocation(kind="slide", index=1, sequence_id="shape-3")),
        block("b2", "paragraph", "Explanation of topic B.", location=SourceLocation(kind="slide", index=1, sequence_id="shape-4")),
    ], location=SourceLocation(kind="slide", index=1))
    blocks = segment_document(document([slide], source_type="pptx"))
    assert [b.title for b in blocks] == ["Topic A", "Topic B"]
    assert blocks[0].source.page_start is None
    assert [loc.sequence_id for loc in blocks[0].source.locations] == ["shape-1", "shape-2"]


def test_pptx_coherent_unit_can_span_slides_when_no_new_heading():
    slide1 = NormalizedPage(None, "", [
        block("t1", "heading", "Memory Hierarchy", location=SourceLocation(kind="slide", index=1, sequence_id="shape-1")),
        block("b1", "paragraph", "Registers are fastest but smallest.", location=SourceLocation(kind="slide", index=1, sequence_id="shape-2")),
    ], location=SourceLocation(kind="slide", index=1))
    slide2 = NormalizedPage(None, "", [
        block("b2", "paragraph", "Cache sits between registers and main memory.", location=SourceLocation(kind="slide", index=2, sequence_id="shape-1")),
    ], location=SourceLocation(kind="slide", index=2))
    blocks = segment_document(document([slide1, slide2], source_type="pptx"))
    assert len(blocks) == 1
    assert [loc.index for loc in blocks[0].source.locations] == [1, 1, 2]


def test_docx_ancestry_uses_document_locations_with_no_pages_or_bboxes():
    page = NormalizedPage(None, "", [
        block("h1", "heading", "3 Memory Systems", location=SourceLocation(kind="document", sequence_id="paragraph-1")),
        block("h2", "heading", "3.1 Cache Associativity", location=SourceLocation(kind="document", sequence_id="paragraph-2")),
        block("p1", "paragraph", "Direct-mapped caches place a block in one location.", location=SourceLocation(kind="document", sequence_id="paragraph-3")),
    ], location=SourceLocation(kind="document"))
    blocks = segment_document(document([page], source_type="docx"))
    assert len(blocks) == 1
    assert blocks[0].title == "3.1 Cache Associativity"
    assert blocks[0].heading_ancestry == ["3 Memory Systems"]
    assert blocks[0].source.page_start is None
    assert blocks[0].source.bboxes == []


def test_table_and_image_are_attached_within_a_segmented_block():
    image = NormalizedImage(
        id="normalized-image-1", source_page=1, source_bbox=None, width=10, height=10,
        mime_type="image/png", caption="Figure 1", asset_reference="data:image/png;base64,AA==", source_image_ids=["raw-1"],
    )
    page = NormalizedPage(1, "", [
        block("h1", "heading", "Cache Levels"),
        block("p1", "paragraph", "Latency grows with each level."),
        block("t1", "table", "| L1 | 4 cycles |\n| --- | --- |"),
        block("i1", "image", None, source_image_id="normalized-image-1"),
    ])
    blocks = segment_document(document([page], images=[image]))
    assert len(blocks) == 1
    assert blocks[0].attached_table_ids == ["t1"]
    assert blocks[0].attached_image_ids == ["normalized-image-1"]
    assert "L1" not in blocks[0].text
    assert "t1" in blocks[0].normalized_block_ids
    assert "i1" in blocks[0].normalized_block_ids


def test_size_constraint_splits_oversized_section_preserving_ancestry():
    long_text = "This is a long explanatory sentence about memory systems. " * 4  # ~240 chars
    page = NormalizedPage(1, "", [
        block("h1", "heading", "Long Section"),
        *[block(f"p{i}", "paragraph", long_text) for i in range(6)],
    ])
    config = SegmentationConfig(preferred_min_characters=50, preferred_max_characters=300, hard_max_characters=600)
    blocks = segment_document(document([page]), config)
    assert len(blocks) > 1
    assert blocks[0].title == "Long Section"
    assert all(b.segmentation.method == "structural+size_constraint" for b in blocks)
    for continuation in blocks[1:]:
        assert continuation.title is None
        assert continuation.heading_ancestry == ["Long Section"]
    assert all(b.character_count <= config.hard_max_characters for b in blocks)


def test_size_constraints_never_merge_across_a_heading_boundary_to_hit_minimum():
    page = NormalizedPage(1, "", [
        block("h1", "heading", "Short Section A"),
        block("p1", "paragraph", "One short sentence."),
        block("h2", "heading", "Short Section B"),
        block("p2", "paragraph", "Another short sentence."),
    ])
    config = SegmentationConfig(preferred_min_characters=1000, preferred_max_characters=2000, hard_max_characters=4000)
    blocks = segment_document(document([page]), config)
    assert [b.title for b in blocks] == ["Short Section A", "Short Section B"]


def test_structural_only_disables_size_constraints():
    page = NormalizedPage(1, "", [
        block("h1", "heading", "Section"),
        *[block(f"p{i}", "paragraph", "A short sentence about caches.") for i in range(5)],
    ])
    tiny_config = SegmentationConfig(preferred_min_characters=10, preferred_max_characters=40, hard_max_characters=60)
    structural_only = segment_document(document([page]), tiny_config, apply_size_constraints=False)
    with_size = segment_document(document([page]), tiny_config, apply_size_constraints=True)
    assert len(structural_only) == 1
    assert len(with_size) > 1


def test_paragraph_only_baseline_produces_one_block_per_normalized_block():
    page = NormalizedPage(1, "", [
        block("h1", "heading", "Cache Associativity"),
        block("p1", "paragraph", "Direct-mapped caches place a block in one location."),
        block("p2", "paragraph", "Set-associative caches allow several locations."),
    ])
    blocks = paragraph_only_baseline(document([page]))
    assert len(blocks) == 3
    assert [b.normalized_block_ids for b in blocks] == [["h1"], ["p1"], ["p2"]]


def test_segmentation_ids_are_deterministic_across_runs():
    page = NormalizedPage(1, "", [block("h1", "heading", "Section"), block("p1", "paragraph", "Body text.")])
    first = segment_document(document([page]))
    second = segment_document(document([page]))
    assert first == second
    assert [b.id for b in first] == ["learning-block-1"]


def test_leading_content_before_first_heading_is_its_own_block():
    page = NormalizedPage(1, "", [
        block("p0", "paragraph", "Introductory text with no heading yet."),
        block("h1", "heading", "First Section"),
        block("p1", "paragraph", "Body."),
    ])
    blocks = segment_document(document([page]))
    assert len(blocks) == 2
    assert blocks[0].title is None
    assert blocks[0].segmentation.boundary_reason == "Leading content before the first heading in the document."
    assert blocks[1].title == "First Section"
