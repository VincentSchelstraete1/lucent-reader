import pytest

from app.ingestion import RawContentBlock, RawDocument, RawImage, RawPage
from app.normalization import build_evaluation_report, normalize_document
from app.normalization.stages import (
    classify_block,
    clean_whitespace,
    reconstruct_line_wraps,
    repair_fragmented_prose_table,
    repair_line_hyphenation,
)


def block(block_id: str, page: int, text: str, bbox=(72, 100, 500, 140), order=0):
    return RawContentBlock(block_id, page, "text", bbox, order, text)


def document(pages: list[RawPage], images: list[RawImage] | None = None, markdown: str = "raw markdown"):
    return RawDocument("pdf", "fixture.pdf", len(pages), markdown, pages, images or [])


def furniture_document():
    pages = []
    for page_number in range(1, 5):
        pages.append(
            RawPage(
                page_number,
                "",
                [
                    block(f"h{page_number}", page_number, "EE392C: Lecture #7", (72, 12, 300, 28), 0),
                    block(f"b{page_number}", page_number, f"Legitimate body paragraph {page_number}.", (72, 100, 500, 140), 1),
                    block(f"f{page_number}", page_number, "Stanford University", (72, 742, 300, 758), 2),
                    block(f"n{page_number}", page_number, str(page_number), (290, 770, 310, 784), 3),
                ],
            )
        )
    return document(pages)


def test_repeated_headers_footers_and_sequential_page_numbers_are_suppressed():
    normalized = normalize_document(furniture_document())
    artifacts = normalized.normalization_metadata.suppressed_artifacts

    assert {artifact.type for artifact in artifacts} == {"header", "footer", "page_number"}
    assert "EE392C: Lecture #7" not in normalized.pages[0].text
    assert "Stanford University" not in normalized.pages[0].text
    assert normalized.pages[0].text == "Legitimate body paragraph 1."
    assert normalized.normalization_metadata.counters["suppressed_page_numbers"] == 4


def test_unique_first_and_last_page_content_is_preserved():
    raw = furniture_document()
    raw.pages[0].blocks.insert(1, block("title", 1, "A Unique Document Title", (72, 45, 400, 70), 1))
    raw.pages[-1].blocks.insert(-1, block("ending", 4, "A unique concluding paragraph.", (72, 700, 500, 730), 2))

    normalized = normalize_document(raw)
    assert "A Unique Document Title" in normalized.pages[0].text
    assert "A unique concluding paragraph." in normalized.pages[-1].text


def test_wrapped_prose_is_reconstructed_but_paragraph_boundary_is_preserved():
    text = "We are entering an era of ubiquitous computing, as technology scales, more and more\napplications demand ever-growing performances.\n\nA second paragraph remains separate."
    reconstructed, joins = reconstruct_line_wraps(text, "paragraph")
    assert reconstructed == (
        "We are entering an era of ubiquitous computing, as technology scales, more and more "
        "applications demand ever-growing performances.\n\nA second paragraph remains separate."
    )
    assert joins == 1


def test_heading_and_list_boundaries_are_not_flattened():
    assert classify_block("2.1 Summary") == "heading"
    assert reconstruct_line_wraps("2.1 Summary", "heading") == ("2.1 Summary", 0)
    assert reconstruct_line_wraps("- first\n- second", "list") == ("- first\n- second", 0)


def test_conservative_hyphenation_repairs_prefix_break_and_preserves_real_compounds():
    assert repair_line_hyphenation("re-\nconfigurable") == ("reconfigurable", 1)
    assert repair_line_hyphenation("com-\nputation") == ("computation", 1)
    assert repair_line_hyphenation("out-of-order processing") == ("out-of-order processing", 0)
    assert repair_line_hyphenation("packet-based network") == ("packet-based network", 0)
    assert repair_line_hyphenation("point-to-point link") == ("point-to-point link", 0)


def test_uncertain_line_break_hyphenation_is_left_untouched():
    assert repair_line_hyphenation("packet-\nbased protocol") == ("packet-\nbased protocol", 0)


def test_whitespace_cleanup_does_not_guess_concatenated_words():
    cleaned, repairs = clean_whitespace("It’sablock-orientedsysteminallmodesofoperations  ,  unchanged.")
    assert cleaned == "It’sablock-orientedsysteminallmodesofoperations, unchanged."
    assert repairs == 1


def test_obvious_fragmented_prose_table_is_reconstructed():
    raw = "| The answer | is | Polymorphous | Architecture. |\n| --- | --- | --- | --- |"
    repaired, conversions, uncertain = repair_fragmented_prose_table(raw)
    assert repaired == "The answer is Polymorphous Architecture."
    assert conversions == 1
    assert uncertain is False


def test_real_and_uncertain_tables_are_preserved():
    real = "| Level | Latency |\n| --- | --- |\n| L1 | 4 cycles |\n| L2 | 12 cycles |"
    uncertain = "| Alpha | Beta |\n| --- | --- |"
    assert repair_fragmented_prose_table(real) == (real, 0, False)
    assert repair_fragmented_prose_table(uncertain) == (uncertain, 0, True)


def test_probable_markitdown_prose_table_is_flagged_without_losing_raw_markdown():
    markdown = "| The answer | is | Polymorphous | Architecture. |\n| --- | --- | --- | --- |"
    normalized = normalize_document(document([RawPage(1, "The answer is Polymorphous Architecture.", [])], markdown=markdown))
    artifact = normalized.normalization_metadata.unresolved_artifacts[0]
    assert artifact.type == "markitdown_probable_prose_table"
    assert artifact.page_number is None
    assert normalized.normalization_metadata.counters["markitdown_table_artifacts_flagged"] == 1


def test_adjacent_layout_fragments_merge_and_preserve_all_provenance():
    raw = document(
        [
            RawPage(
                1,
                "",
                [
                    block("raw-a", 1, "The processor requests", (72, 100, 300, 120), 0),
                    block("raw-b", 1, "data from memory.", (73, 124, 300, 144), 1),
                ],
            )
        ]
    )
    normalized = normalize_document(raw)
    result = normalized.pages[0].blocks[0]
    assert result.text == "The processor requests data from memory."
    assert result.source.page_start == result.source.page_end == 1
    assert result.source.raw_block_ids == ["raw-a", "raw-b"]
    assert result.source.bboxes == [(72, 100, 300, 120), (73, 124, 300, 144)]
    assert normalized.normalization_metadata.counters["reconstructed_blocks"] == 1


def test_image_metadata_and_source_identity_survive_normalization():
    raw_image = RawImage(
        "raw-image", 2, (10, 20, 210, 180), 400, 320, "image/png", "data:image/png;base64,AA==", "Figure 1"
    )
    normalized = normalize_document(document([RawPage(1, "", []), RawPage(2, "", [])], [raw_image]))
    image = normalized.images[0]
    assert image.source_page == 2
    assert image.source_bbox == raw_image.bbox
    assert image.asset_reference == raw_image.asset_reference
    assert image.caption == "Figure 1"
    assert image.source_image_ids == ["raw-image"]


def test_unresolved_concatenation_is_auditable_not_rewritten():
    text = "Itsablockorientedsysteminallmodesofoperations"
    normalized = normalize_document(document([RawPage(1, text, [block("raw-1", 1, text)])]))
    assert normalized.pages[0].text == text
    assert normalized.normalization_metadata.unresolved_artifacts[0].type == "possible_concatenated_words"


def test_evaluation_report_exposes_task_specific_counts():
    raw = furniture_document()
    normalized = normalize_document(raw)
    report = build_evaluation_report(raw, normalized)
    assert report["page_count"] == 4
    assert report["raw_text_blocks"] == 16
    assert report["normalized_text_blocks"] == 4
    assert report["counters"]["suppressed_headers"] == 1


@pytest.mark.parametrize("text", ["out-of-order", "point-to-point", "packet-based"])
def test_legitimate_hyphenated_terms_remain_stable(text):
    normalized = normalize_document(document([RawPage(1, text, [block("raw-1", 1, text)])]))
    assert normalized.pages[0].text == text
