import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.ingestion import RawContentBlock, RawDocument
from app.ingestion.base import BoundingBox
from app.normalization.schema import SuppressedArtifact


FURNITURE_EDGE_POINTS = 72.0
FURNITURE_POSITION_TOLERANCE = 24.0
FURNITURE_MAX_CHARACTERS = 120
MIN_FURNITURE_PAGES = 3
MIN_FURNITURE_PAGE_RATIO = 0.5
ADJACENT_BLOCK_MAX_VERTICAL_GAP = 18.0
ADJACENT_BLOCK_ALIGNMENT_TOLERANCE = 12.0
SUSPICIOUS_TOKEN_LENGTH = 28

PAGE_NUMBER_PATTERN = re.compile(r"^(?:page\s+)?(?P<number>\d{1,4})(?:\s+of\s+\d{1,4})?$", re.IGNORECASE)
CAPTION_PATTERN = re.compile(r"^(?:figure|fig\.|table)\s+\d+[a-z]?(?:\s*[:.\-]|\s+)", re.IGNORECASE)
NUMBERED_HEADING_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s+[A-Z][^.!?]{0,98}$")
LIST_PATTERN = re.compile(r"^(?:[-*•‣▪◦]|\d+[.)])\s+")
MARKDOWN_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")
PRESERVED_COMPOUND_SECOND_WORDS = {
    "based", "being", "entry", "input", "level", "line", "order", "oriented", "output", "point", "term", "time", "wide"
}


@dataclass(frozen=True)
class TextTransformation:
    text: str
    line_joins: int = 0
    hyphenation_repairs: int = 0
    whitespace_repairs: int = 0
    table_prose_conversions: int = 0


def _candidate_zone(block: RawContentBlock, page_blocks: list[RawContentBlock]) -> str | None:
    if not block.bbox:
        return None
    positioned = [candidate.bbox for candidate in page_blocks if candidate.bbox]
    if not positioned:
        return None
    top = min(box[1] for box in positioned)
    bottom = max(box[3] for box in positioned)
    if block.bbox[1] <= top + FURNITURE_EDGE_POINTS:
        return "header"
    if block.bbox[3] >= bottom - FURNITURE_EDGE_POINTS:
        return "footer"
    return None


def _furniture_key(text: str) -> str:
    lines = [" ".join(line.casefold().split()) for line in text.splitlines() if line.strip()]
    normalized = [
        "<page>" if re.fullmatch(r"(?:page\s+)?\d{1,4}(?:\s*/\s*\d{1,4})?", line) else line
        for line in lines
    ]
    if "<page>" in normalized:
        normalized = sorted(normalized, key=lambda line: line == "<page>")
    return " ".join(normalized)


def detect_page_furniture(document: RawDocument) -> tuple[set[str], list[SuppressedArtifact]]:
    candidates: dict[tuple[str, str], list[RawContentBlock]] = defaultdict(list)
    numeric: list[tuple[RawContentBlock, int, str]] = []
    for page in document.pages:
        text_blocks = [block for block in page.blocks if block.type == "text" and block.text and block.bbox]
        for block in text_blocks:
            text = " ".join((block.text or "").split())
            zone = _candidate_zone(block, text_blocks)
            if not zone or not text or len(text) > FURNITURE_MAX_CHARACTERS:
                continue
            number_match = PAGE_NUMBER_PATTERN.fullmatch(text)
            if number_match:
                numeric.append((block, int(number_match.group("number")), zone))
                continue
            candidates[(zone, _furniture_key(block.text or ""))].append(block)

    minimum_pages = max(MIN_FURNITURE_PAGES, math.ceil(document.page_count * MIN_FURNITURE_PAGE_RATIO))
    suppressed: set[str] = set()
    artifacts: list[SuppressedArtifact] = []
    for (zone, _key), blocks in candidates.items():
        pages = sorted({block.page_number for block in blocks})
        positions = [block.bbox[1] if zone == "header" else block.bbox[3] for block in blocks if block.bbox]
        if len(pages) < minimum_pages or max(positions) - min(positions) > FURNITURE_POSITION_TOLERANCE:
            continue
        artifact_id = f"suppressed-{zone}-{len(artifacts) + 1}"
        suppressed.update(block.id for block in blocks)
        artifacts.append(
            SuppressedArtifact(artifact_id, zone, blocks[0].text or "", pages, [block.id for block in blocks])
        )

    offsets = Counter(value - block.page_number for block, value, _zone in numeric)
    if offsets:
        common_offset, frequency = offsets.most_common(1)[0]
        if frequency >= max(2, math.ceil(document.page_count * MIN_FURNITURE_PAGE_RATIO)):
            matching = [item for item in numeric if item[1] - item[0].page_number == common_offset]
            artifact_id = f"suppressed-page-number-{len(artifacts) + 1}"
            suppressed.update(block.id for block, _value, _zone in matching)
            artifacts.append(
                SuppressedArtifact(
                    artifact_id,
                    "page_number",
                    "sequential standalone page numbers",
                    [block.page_number for block, _value, _zone in matching],
                    [block.id for block, _value, _zone in matching],
                )
            )
    return suppressed, artifacts


def classify_block(text: str) -> str:
    stripped = text.strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not stripped:
        return "unknown"
    if CAPTION_PATTERN.match(stripped):
        return "caption"
    if looks_like_markdown_table(stripped):
        return "table"
    if lines and all(LIST_PATTERN.match(line) for line in lines):
        return "list"
    if len(lines) == 2 and re.fullmatch(r"\d+(?:\.\d+)*", lines[0]) and len(lines[1]) <= 100:
        return "heading"
    if len(lines) == 1 and len(lines[0]) <= 100 and not re.search(r"[.!?]$", lines[0]):
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", lines[0])
        title_case_ratio = sum(word[:1].isupper() for word in words) / len(words) if words else 0
        if NUMBERED_HEADING_PATTERN.fullmatch(lines[0]) or lines[0].isupper() or (len(words) <= 12 and title_case_ratio >= 0.6):
            return "heading"
    return "paragraph"


def repair_line_hyphenation(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    output: list[str] = []
    repairs = 0
    index = 0
    while index < len(lines):
        current = lines[index]
        while index + 1 < len(lines) and re.search(r"[A-Za-z]+-$", current) and re.match(r"^[a-z]", lines[index + 1].lstrip()):
            next_line = lines[index + 1].lstrip()
            fragment = re.search(r"([A-Za-z]+(?:-[A-Za-z]+)*)-$", current)
            left_fragment = fragment.group(1).casefold() if fragment else ""
            next_word_match = re.match(r"([a-z]+)", next_line)
            next_word = next_word_match.group(1) if next_word_match else ""
            if "-" in left_fragment or next_word in PRESERVED_COMPOUND_SECOND_WORDS:
                break
            current = current[:-1] + next_line
            repairs += 1
            index += 1
        output.append(current)
        index += 1
    return "\n".join(output), repairs


def reconstruct_line_wraps(text: str, block_type: str) -> tuple[str, int]:
    if block_type in {"heading", "list", "table", "caption", "unknown"}:
        return text, 0
    paragraphs = re.split(r"\n\s*\n", text)
    joins = 0
    rebuilt: list[str] = []
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        rebuilt.append(" ".join(lines))
        joins += max(0, len(lines) - 1)
    return "\n\n".join(rebuilt), joins


def clean_whitespace(text: str) -> tuple[str, int]:
    original = text
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    text = re.sub(r"([([{]) +", r"\1", text)
    text = re.sub(r" +([)\]}])", r"\1", text)
    text = re.sub(r"\n[ ]+", "\n", text)
    text = re.sub(r"[ ]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(), int(text.strip() != original.strip())


def _table_rows(text: str) -> list[list[str]] | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or not all("|" in line for line in lines):
        return None
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    if len(rows[0]) < 2 or any(len(row) != len(rows[0]) for row in rows):
        return None
    if not all(MARKDOWN_SEPARATOR_CELL.fullmatch(cell) for cell in rows[1]):
        return None
    return rows


def looks_like_markdown_table(text: str) -> bool:
    return _table_rows(text) is not None


def repair_fragmented_prose_table(text: str) -> tuple[str, int, bool]:
    rows = _table_rows(text)
    if not rows:
        return text, 0, False
    content_rows = [rows[0], *rows[2:]]
    if len(content_rows) == 1 and len(content_rows[0]) >= 3:
        joined = " ".join(cell for cell in content_rows[0] if cell)
        short_cells = all(len(cell.split()) <= 4 for cell in content_rows[0])
        if short_cells and re.search(r"[.!?]$", joined):
            return joined, 1, False
    if len(content_rows) >= 2:
        return text, 0, False
    return text, 0, True


def find_markdown_table_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if "|" in line:
            current.append(line)
        else:
            if current and looks_like_markdown_table("\n".join(current)):
                blocks.append("\n".join(current))
            current = []
    if current and looks_like_markdown_table("\n".join(current)):
        blocks.append("\n".join(current))
    return blocks


def normalize_block_text(text: str, block_type: str) -> tuple[TextTransformation, bool]:
    table_text, table_repairs, uncertain_table = repair_fragmented_prose_table(text)
    if table_repairs:
        block_type = "paragraph"
    hyphenated, hyphen_repairs = repair_line_hyphenation(table_text)
    reconstructed, line_joins = reconstruct_line_wraps(hyphenated, block_type)
    cleaned, whitespace_repairs = clean_whitespace(reconstructed)
    return TextTransformation(cleaned, line_joins, hyphen_repairs, whitespace_repairs, table_repairs), uncertain_table


def can_merge_blocks(previous_text: str, current_text: str, previous_bbox: BoundingBox | None, current_bbox: BoundingBox | None) -> bool:
    if not previous_bbox or not current_bbox or not previous_text or not current_text:
        return False
    vertical_gap = current_bbox[1] - previous_bbox[3]
    aligned = abs(current_bbox[0] - previous_bbox[0]) <= ADJACENT_BLOCK_ALIGNMENT_TOLERANCE
    continues_sentence = not re.search(r"[.!?:;]$", previous_text.rstrip()) and current_text.lstrip()[:1].islower()
    return 0 <= vertical_gap <= ADJACENT_BLOCK_MAX_VERTICAL_GAP and aligned and continues_sentence


def union_bboxes(boxes: list[BoundingBox]) -> BoundingBox | None:
    if not boxes:
        return None
    return min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)


def suspicious_concatenated_tokens(text: str) -> list[str]:
    return re.findall(rf"(?<![\w-])[A-Za-z’']{{{SUSPICIOUS_TOKEN_LENGTH},}}(?![\w-])", text)
