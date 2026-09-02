"""Hand-labeled segmentation dataset. Deliberately small (13 examples) and
carefully reviewed rather than large and generated - each example's
`expected_starts` was written by inspecting what a person would consider one
coherent unit, not derived from running the algorithm and copying its output.

The dev/holdout split below is fixed *before* any evaluation is run or
compared, so results are never used to pick which examples land where.
"""

from app.ingestion.base import SourceLocation
from app.normalization.schema import (
    NormalizationMetadata,
    NormalizedBlock,
    NormalizedDocument,
    NormalizedImage,
    NormalizedPage,
    SourceReference,
)
from app.segmentation.evaluation import SegmentationExample


def _block(id: str, type: str, text: str | None, *, page=None, location=None, source_image_id=None) -> NormalizedBlock:
    return NormalizedBlock(
        id=id, type=type, text=text,
        source=SourceReference(page_start=page, page_end=page, raw_block_ids=[id], bboxes=[], locations=[location] if location else []),
        source_image_id=source_image_id,
    )


def _document(pages: list[NormalizedPage], images: list[NormalizedImage] | None = None, source_type: str = "pdf") -> NormalizedDocument:
    return NormalizedDocument(
        source_type=source_type, filename="fixture", page_count=len(pages), pages=pages, images=images or [],
        normalization_metadata=NormalizationMetadata(version="test", suppressed_artifacts=[], events=[], unresolved_artifacts=[], counters={}),
    )


def _pdf_loc(page: int) -> SourceLocation:
    return SourceLocation(kind="page", index=page)


def _slide_loc(index: int, shape: str) -> SourceLocation:
    return SourceLocation(kind="slide", index=index, sequence_id=shape)


def _docx_loc(sequence_id: str) -> SourceLocation:
    return SourceLocation(kind="document", sequence_id=sequence_id)


# --- PDF technical prose -----------------------------------------------

pdf_prose_01 = SegmentationExample(
    id="pdf_prose_01", category="pdf_technical_prose",
    document=_document([NormalizedPage(1, "", [
        _block("h1", "heading", "Cache Associativity", page=1, location=_pdf_loc(1)),
        _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location.", page=1, location=_pdf_loc(1)),
        _block("p2", "paragraph", "Set-associative caches allow a block to reside in any of several locations within a set.", page=1, location=_pdf_loc(1)),
        _block("p3", "paragraph", "The tradeoff is hit rate against lookup complexity and hardware cost.", page=1, location=_pdf_loc(1)),
    ])]),
    expected_starts=set(),  # single coherent unit - no internal boundary expected
)

pdf_prose_02 = SegmentationExample(
    id="pdf_prose_02", category="pdf_technical_prose",
    document=_document([NormalizedPage(1, "", [
        _block("h1", "heading", "TCP", page=1, location=_pdf_loc(1)),
        _block("p1", "paragraph", "TCP provides reliable, ordered delivery of a stream of bytes.", page=1, location=_pdf_loc(1)),
        _block("h2", "heading", "UDP", page=1, location=_pdf_loc(1)),
        _block("p2", "paragraph", "UDP favors low overhead and tolerates missing packets.", page=1, location=_pdf_loc(1)),
    ])]),
    expected_starts={"h2"},
)

# --- PDF lecture notes (page-spanning, numbered subsections) -----------

pdf_lecture_01 = SegmentationExample(
    id="pdf_lecture_01", category="pdf_lecture_notes",
    document=_document([
        NormalizedPage(1, "", [
            _block("h1", "heading", "Cache Associativity", page=1, location=_pdf_loc(1)),
            _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location.", page=1, location=_pdf_loc(1)),
        ], location=_pdf_loc(1)),
        NormalizedPage(2, "", [
            _block("p2", "paragraph", "This paragraph continues the same topic on the next physical page.", page=2, location=_pdf_loc(2)),
            _block("h2", "heading", "Virtual Memory", page=2, location=_pdf_loc(2)),
            _block("p3", "paragraph", "Virtual memory decouples logical addresses from physical addresses.", page=2, location=_pdf_loc(2)),
        ], location=_pdf_loc(2)),
    ]),
    expected_starts={"h2"},  # p2 continues h1's section across the page break
)

pdf_lecture_02 = SegmentationExample(
    id="pdf_lecture_02", category="pdf_lecture_notes",
    document=_document([NormalizedPage(1, "", [
        _block("h0", "heading", "3 Memory Systems", page=1, location=_pdf_loc(1)),
        _block("h1", "heading", "3.1 Cache Associativity", page=1, location=_pdf_loc(1)),
        _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location.", page=1, location=_pdf_loc(1)),
        _block("h2", "heading", "3.2 Virtual Memory", page=1, location=_pdf_loc(1)),
        _block("p2", "paragraph", "Virtual memory decouples logical addresses from physical addresses.", page=1, location=_pdf_loc(1)),
    ])]),
    expected_starts={"h1", "h2"},  # bare "3 Memory Systems" divider owns no content of its own
)

# --- PDF table / figure --------------------------------------------------

pdf_table_01 = SegmentationExample(
    id="pdf_table_01", category="pdf_table",
    document=_document([NormalizedPage(1, "", [
        _block("h1", "heading", "Cache Levels", page=1, location=_pdf_loc(1)),
        _block("p1", "paragraph", "Latency grows with each additional level of cache.", page=1, location=_pdf_loc(1)),
        _block("t1", "table", "| Level | Latency |\n| --- | --- |\n| L1 | 4 cycles |\n| L2 | 12 cycles |", page=1, location=_pdf_loc(1)),
    ])]),
    expected_starts=set(),
)

pdf_figure_01 = SegmentationExample(
    id="pdf_figure_01", category="pdf_figure",
    document=_document(
        [NormalizedPage(1, "", [
            _block("h1", "heading", "Associativity Comparison", page=1, location=_pdf_loc(1)),
            _block("p1", "paragraph", "The figure below compares hit rate across associativity levels.", page=1, location=_pdf_loc(1)),
            _block("i1", "image", None, page=1, location=_pdf_loc(1), source_image_id="normalized-image-1"),
        ])],
        images=[NormalizedImage(
            id="normalized-image-1", source_page=1, source_bbox=None, width=10, height=10,
            mime_type="image/png", caption="Figure 4: Associativity comparison",
            asset_reference="data:image/png;base64,AA==", source_image_ids=["raw-1"], location=_pdf_loc(1),
        )],
    ),
    expected_starts=set(),
)

# --- PPTX slides -----------------------------------------------------------

pptx_slides_01 = SegmentationExample(
    id="pptx_slides_01", category="pptx_slides",
    document=_document([
        NormalizedPage(None, "", [
            _block("s1t", "heading", "Introduction", location=_slide_loc(1, "shape-1")),
            _block("s1b", "paragraph", "This deck covers memory hierarchy fundamentals.", location=_slide_loc(1, "shape-2")),
        ], location=_slide_loc(1, None)),
        NormalizedPage(None, "", [
            _block("s2t", "heading", "Registers", location=_slide_loc(2, "shape-1")),
            _block("s2b", "paragraph", "Registers are fastest but smallest.", location=_slide_loc(2, "shape-2")),
        ], location=_slide_loc(2, None)),
        NormalizedPage(None, "", [
            _block("s3t", "heading", "Cache", location=_slide_loc(3, "shape-1")),
            _block("s3b", "paragraph", "Cache sits between registers and main memory.", location=_slide_loc(3, "shape-2")),
        ], location=_slide_loc(3, None)),
    ], source_type="pptx"),
    expected_starts={"s2t", "s3t"},
)

pptx_slides_02 = SegmentationExample(
    id="pptx_slides_02", category="pptx_slides",
    document=_document([NormalizedPage(None, "", [
        _block("t1", "heading", "Topic A", location=_slide_loc(1, "shape-1")),
        _block("b1", "paragraph", "Explanation of topic A.", location=_slide_loc(1, "shape-2")),
        _block("t2", "heading", "Topic B", location=_slide_loc(1, "shape-3")),
        _block("b2", "paragraph", "Explanation of topic B.", location=_slide_loc(1, "shape-4")),
    ], location=_slide_loc(1, None))], source_type="pptx"),
    expected_starts={"t2"},  # one slide, two coherent units
)

pptx_slides_03 = SegmentationExample(
    id="pptx_slides_03", category="pptx_slides",
    document=_document([
        NormalizedPage(None, "", [
            _block("s1t", "heading", "Memory Hierarchy", location=_slide_loc(1, "shape-1")),
            _block("s1b", "paragraph", "Registers are fastest but smallest.", location=_slide_loc(1, "shape-2")),
        ], location=_slide_loc(1, None)),
        NormalizedPage(None, "", [
            _block("s2b", "paragraph", "Cache sits between registers and main memory, continuing the same topic.", location=_slide_loc(2, "shape-1")),
        ], location=_slide_loc(2, None)),
    ], source_type="pptx"),
    expected_starts=set(),  # coherent unit spans both slides - no new heading on slide 2
)

# --- DOCX structured notes ---------------------------------------------

docx_structured_01 = SegmentationExample(
    id="docx_structured_01", category="docx_structured_notes",
    document=_document([NormalizedPage(None, "", [
        _block("h1", "heading", "Virtual Memory", location=_docx_loc("paragraph-1")),
        _block("p1", "paragraph", "Virtual memory decouples logical addresses from physical addresses.", location=_docx_loc("paragraph-2")),
        _block("l1", "list", "- Demand paging", location=_docx_loc("paragraph-3")),
        _block("l2", "list", "- Page replacement policies", location=_docx_loc("paragraph-4")),
    ], location=_docx_loc(None))], source_type="docx"),
    expected_starts=set(),
)

docx_structured_02 = SegmentationExample(
    id="docx_structured_02", category="docx_structured_notes",
    document=_document([NormalizedPage(None, "", [
        _block("p0", "paragraph", "Course notes prepared for the memory systems unit.", location=_docx_loc("paragraph-1")),
        _block("h1", "heading", "Cache Associativity", location=_docx_loc("paragraph-2")),
        _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location.", location=_docx_loc("paragraph-3")),
    ], location=_docx_loc(None))], source_type="docx"),
    expected_starts={"h1"},  # headerless intro paragraph is its own leading unit
)

# --- Deliberately hard cases (adversarial, for the decision gate) -----

mixed_hard_01 = SegmentationExample(
    id="mixed_hard_01", category="mixed_hard_no_headings",
    document=_document([NormalizedPage(1, "", [
        _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location, which is simple to implement.", page=1, location=_pdf_loc(1)),
        _block("p2", "paragraph", "Switching topics entirely, TCP provides reliable ordered delivery over an unreliable network.", page=1, location=_pdf_loc(1)),
    ])]),
    # A human reader would split these into two topics, but nothing in the
    # text is a structural signal (no heading) - deliberately included to
    # test whether purely structural segmentation degrades honestly.
    expected_starts={"p2"},
)

mixed_hard_02 = SegmentationExample(
    id="mixed_hard_02", category="mixed_hard_false_heading",
    document=_document([NormalizedPage(1, "", [
        _block("h1", "heading", "Cache Associativity", page=1, location=_pdf_loc(1)),
        _block("p1", "paragraph", "Direct-mapped caches place a block in exactly one location.", page=1, location=_pdf_loc(1)),
        # classify_block("IBM Research Division") really does return "heading"
        # (short, title-case, no terminal punctuation) - verified directly
        # against the real classifier, not assumed. This block is typed
        # "heading" here to faithfully reflect what normalization would
        # actually hand to segmentation, not what we'd prefer it handed over.
        _block("p2", "heading", "IBM Research Division", page=1, location=_pdf_loc(1)),
        _block("p3", "paragraph", "published the original paper describing this technique in 1988.", page=1, location=_pdf_loc(1)),
    ])]),
    # A person reading this would treat "IBM Research Division" as a
    # mid-sentence attribution, not a new section - this is a genuine
    # upstream misclassification (normalization's classify_block heuristic,
    # not segmentation) that segmentation has no way to see through.
    expected_starts=set(),
)


DEV_EXAMPLES: list[SegmentationExample] = [
    pdf_prose_01, pdf_prose_02, pdf_lecture_01, pdf_table_01, pdf_figure_01,
    pptx_slides_01, pptx_slides_02, docx_structured_01, docx_structured_02,
]

HOLDOUT_EXAMPLES: list[SegmentationExample] = [
    pdf_lecture_02, pptx_slides_03, mixed_hard_01, mixed_hard_02,
]

ALL_EXAMPLES: list[SegmentationExample] = DEV_EXAMPLES + HOLDOUT_EXAMPLES
