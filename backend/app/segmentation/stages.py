import re
from dataclasses import dataclass, field

from app.normalization.schema import NormalizedBlock, NormalizedDocument
from app.segmentation.schema import LearningBlockType


NUMERIC_HEADING_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)")
_PROSE_TYPES = {"paragraph", "list", "caption", "unknown"}


@dataclass(frozen=True)
class SegmentationConfig:
    """Character-based (not token-based) - V1 has no tokenizer naturally
    available anywhere in the pipeline, and character count is cheap,
    deterministic, and format-independent. All three thresholds are
    intentionally configurable rather than tuned to any one corpus.
    """

    preferred_min_characters: int = 200
    preferred_max_characters: int = 1500
    hard_max_characters: int = 3000


@dataclass
class _Group:
    blocks: list[NormalizedBlock]
    title: str | None
    ancestry: list[str]
    split: bool = False


def heading_depth(text: str) -> int:
    """Depth from a numeric prefix ('2.1.3' -> 3); unnumbered headings default
    to depth 1. classify_block never exposes a heading level directly, so this
    is the smallest signal available without guessing beyond the text itself.
    """

    match = NUMERIC_HEADING_PREFIX.match(text.strip())
    return match.group(1).count(".") + 1 if match else 1


def group_structurally(document: NormalizedDocument) -> list[_Group]:
    """Stage 1: heading blocks are the only structural boundary signal - a new
    heading starts a new group, but page/slide transitions never force a break
    on their own, so a coherent unit may legitimately span PDF pages or PPTX
    slides (per Checkpoint C's explicit instruction for both formats). A
    heading with no body content before the next heading contributes only to
    heading_stack (so descendants still inherit it as an ancestor) and is
    dropped rather than emitted as a trivial standalone LearningBlock.
    """

    groups: list[_Group] = []
    current: list[NormalizedBlock] = []
    current_title: str | None = None
    current_ancestry: list[str] = []
    heading_stack: list[tuple[int, str]] = []

    def flush() -> None:
        if current:
            groups.append(_Group(blocks=list(current), title=current_title, ancestry=list(current_ancestry)))

    for page in document.pages:
        for block in page.blocks:
            if block.type == "heading" and block.text:
                depth = heading_depth(block.text)
                while heading_stack and heading_stack[-1][0] >= depth:
                    heading_stack.pop()
                ancestry_for_new_group = [text for _, text in heading_stack]
                heading_stack.append((depth, block.text))

                flush()
                current = [block]
                current_title = block.text
                current_ancestry = ancestry_for_new_group
            else:
                current.append(block)
    flush()

    # Drop heading-only groups (a bare section divider with no body content) -
    # its text already lives on in heading_stack-derived ancestry for whatever
    # follows, so nothing is lost, it just doesn't become its own trivial block.
    return [group for group in groups if not (group.title is not None and len(group.blocks) == 1)]


def _constituent_length(block: NormalizedBlock) -> int:
    if block.type in {"heading", "table", "image"} or not block.text:
        return 0
    return len(block.text)


def split_for_size(groups: list[_Group], config: SegmentationConfig) -> list[_Group]:
    """Stage 2: force a split only when a group exceeds hard_max_characters -
    never merges across a heading boundary just to hit preferred_min (that
    would cross an obvious structural boundary the checkpoint explicitly
    warned against), so preferred_min is tracked for evaluation/diagnostics
    but does not trigger merging in V1.
    """

    result: list[_Group] = []
    for group in groups:
        total_length = sum(_constituent_length(block) for block in group.blocks)
        if total_length <= config.hard_max_characters:
            result.append(group)
            continue

        chunks: list[list[NormalizedBlock]] = []
        current_chunk: list[NormalizedBlock] = []
        current_length = 0
        for block in group.blocks:
            block_length = _constituent_length(block)
            if current_chunk and current_length + block_length > config.preferred_max_characters and current_length >= config.preferred_min_characters:
                chunks.append(current_chunk)
                current_chunk = []
                current_length = 0
            current_chunk.append(block)
            current_length += block_length
        if current_chunk:
            chunks.append(current_chunk)

        for index, chunk_blocks in enumerate(chunks):
            is_first = index == 0
            ancestry = group.ancestry if is_first else ([*group.ancestry, group.title] if group.title else group.ancestry)
            result.append(_Group(blocks=chunk_blocks, title=group.title if is_first else None, ancestry=ancestry, split=True))
    return result


def infer_block_type(blocks: list[NormalizedBlock], title: str | None, ancestry: list[str]) -> LearningBlockType:
    non_heading_types = {block.type for block in blocks if block.type != "heading"}
    if title is not None or ancestry or (non_heading_types and non_heading_types <= _PROSE_TYPES):
        return "section"
    if non_heading_types == {"table"}:
        return "table"
    if non_heading_types == {"image"}:
        return "figure"
    return "mixed"


def boundary_reason(group: _Group, config: SegmentationConfig, *, is_leading: bool) -> tuple[str, str]:
    """Returns (method, reason)."""

    if group.split:
        method = "structural+size_constraint"
        if group.title is not None:
            reason = (
                f"Started at heading '{group.title}'; split after exceeding the "
                f"{config.hard_max_characters}-character hard maximum."
            )
        else:
            reason = "Continuation of a section split for size; heading ancestry preserved, no title repeated."
        return method, reason

    method = "structural"
    if group.title is not None:
        reason = f"Started at heading '{group.title}'; ended before the next heading of equal or higher level."
    elif is_leading:
        reason = "Leading content before the first heading in the document."
    else:
        reason = "Grouped as a standalone structural unit without an enclosing heading."
    return method, reason


def attached_ids(blocks: list[NormalizedBlock]) -> tuple[list[str], list[str]]:
    tables = [block.id for block in blocks if block.type == "table"]
    images = [block.source_image_id for block in blocks if block.type == "image" and block.source_image_id]
    return tables, images
