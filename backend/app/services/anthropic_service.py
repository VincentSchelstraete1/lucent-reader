import os
import logging
import time
from dataclasses import dataclass
from anthropic import Anthropic
from pydantic import ValidationError

from app.schemas.generated_note import GeneratedNote
from app.schemas.quiz import GeneratedQuizQuestions
from app.config import settings


client = Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    timeout=settings.anthropic_timeout_seconds,
    max_retries=settings.anthropic_max_retries,
)
logger = logging.getLogger(__name__)

# Document note and quiz generation share a deterministic, approximately
# 12k-token input budget (using the conservative four-characters-per-token
# estimate). Keeping both the beginning and end retains introductions,
# conclusions, and late source sections without an unbounded prompt path.
DOCUMENT_PROMPT_MAX_CHARS = 48_000
DOCUMENT_PROMPT_OMISSION = "\n\n[Middle of source omitted to fit the generation context budget.]\n\n"


def _bounded_document_content(content: str, *, max_chars: int = DOCUMENT_PROMPT_MAX_CHARS) -> str:
    normalized = str(content or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    available = max_chars - len(DOCUMENT_PROMPT_OMISSION)
    head_chars = int(available * 0.7)
    tail_chars = available - head_chars
    return f"{normalized[:head_chars].rstrip()}{DOCUMENT_PROMPT_OMISSION}{normalized[-tail_chars:].lstrip()}"


@dataclass(frozen=True)
class StructuredToolResult:
    data: dict
    model: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None


class StructuredToolTruncatedError(ValueError):
    """Raised when a structured tool response exhausts its output budget."""

    def __init__(self, *, input_tokens: int | None, output_tokens: int | None, max_tokens: int, top_level_keys: list[str] | None = None):
        super().__init__("Structured tool output was truncated at max_tokens")
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.max_tokens = max_tokens
        self.stop_reason = "max_tokens"
        self.top_level_keys = top_level_keys or []


LENGTH_INSTRUCTIONS = {
    "much_shorter": "Condense it significantly - cut anything that isn't essential to the main point.",
    "shorter": "Make it noticeably shorter than the original while keeping the key details.",
    "same": "Keep the length roughly the same as the original.",
    "more_detail": "Expand it with a bit more explanatory detail than the original."
}


def strip_markdown_heading(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()

def simplify_text(text: str, target_grade_level: int, target_length: str):
    length_instruction = LENGTH_INSTRUCTIONS.get(
            target_length, LENGTH_INSTRUCTIONS["same"]
        )
    
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Rewrite the following paragraph so it reads at approximately "
                    f"a US grade {target_grade_level} reading level. "
                    f"{length_instruction} "
                    f"Keep the meaning accurate. Where it genuinely improves "
                    f"clarity - a list of items, steps, or comparisons, or a "
                    f"handful of important terms - use bullet points (lines "
                    f"starting with \"- \") and **bold** on the key term "
                    f"itself, sparingly. Don't force bullets or bold onto "
                    f"text that reads fine as plain prose. If the rewrite "
                    f"covers more than one distinct idea, separate them into "
                    f"short paragraphs with a blank line between them rather "
                    f"than one long block. Return only the rewritten text - "
                    f"no heading, no title, no preamble, and no markdown "
                    f"besides the bullet points and bold described "
                    f"above.\n\n{text}"
                )
            }
        ]
    )
    
    
    simplified = strip_markdown_heading(message.content[0].text)
    return simplified

def explain_text(text: str, context: str, target_grade_level: int, target_length: str):
    length_instruction = LENGTH_INSTRUCTIONS.get(
            target_length, LENGTH_INSTRUCTIONS["same"]
        )
    
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Explain the selected text below so it is understandable to "
                    f"someone reading at approximately a US grade "
                    f"{target_grade_level} level. "
                    f"Use the surrounding context to understand what the selected "
                    f"text means, but focus your explanation only on the selected text. "
                    f"Define unfamiliar terms when helpful and explain the idea clearly "
                    f"rather than simply rewording it. "
                    f"For the length and level of detail of your explanation: "
                    f"{length_instruction} "
                    f"Apply this length instruction to the explanation you produce, "
                    f"not to the length of the selected text. "
                    f"Return only the explanation with no heading or preamble.\n\n"
                    f"Selected text:\n{text}\n\n"
                    f"Surrounding context:\n{context}"
                )
            }
        ]
    )
    
    explanation = strip_markdown_heading(message.content[0].text)
    return explanation

def summarize_text(text: str, target_grade_level: int, target_length: str):
    length_instruction = LENGTH_INSTRUCTIONS.get(
            target_length, LENGTH_INSTRUCTIONS["same"]
        )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize the following section so it reads at approximately "
                    f"a US grade {target_grade_level} reading level. "
                    f"{length_instruction} "
                    f"Capture only the main point(s) - this is a summary, not a "
                    f"rewrite, so it should be noticeably more condensed than the "
                    f"original regardless of the length instruction above. "
                    f"Return only the summary - no heading, no title, no preamble, "
                    f"and no markdown.\n\n{text}"
                )
            }
        ]
    )

    summary = strip_markdown_heading(message.content[0].text)
    return summary


# ---- Structured output (generated notes, quizzes) ----
#
# Schemas are written out by hand rather than derived from the Pydantic
# models' own .model_json_schema() - that method emits $defs/$ref for
# nested models, and this keeps the tool input_schema sent to the model
# as plain nested object/array JSON schema instead of relying on Claude's
# JSON Schema $ref support. Pydantic validation below is still the real
# gate on correctness either way.

GENERATED_NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "concepts": {"type": "array", "items": {"type": "string"}},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["heading", "content"]
            }
        }
    },
    "required": ["title", "summary", "key_points", "concepts", "sections"]
}

QUIZ_QUESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "section_id": {"type": ["string", "null"]}
                },
                "required": ["question", "choices", "correct_index", "explanation", "section_id"]
            }
        }
    },
    "required": ["questions"]
}


def _run_structured_tool(
    prompt: str,
    tool_name: str,
    schema: dict,
    max_tokens: int,
    timeout: float | None = None,
    max_retries: int | None = None,
    include_metadata: bool = False,
) -> dict | StructuredToolResult:
    started = time.perf_counter()
    request_client = client.with_options(max_retries=max_retries) if max_retries is not None else client
    try:
        message = request_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            tools=[
                {
                    "name": tool_name,
                    "description": f"Return the {tool_name} structured data for the given content.",
                    "input_schema": schema
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": prompt}],
            **({"timeout": timeout} if timeout is not None else {})
        )
    except Exception as exc:
        logger.warning(
            "provider_operation_complete provider=anthropic operation=%s stage=request outcome=error exception_type=%s duration_ms=%.1f",
            tool_name,
            type(exc).__name__,
            (time.perf_counter() - started) * 1000,
        )
        raise

    usage = getattr(message, "usage", None)
    tool_input = next((block.input for block in message.content if block.type == "tool_use"), None)
    if getattr(message, "stop_reason", None) == "max_tokens":
        logger.warning(
            "provider_operation_complete provider=anthropic operation=%s stage=validation outcome=truncated exception_type=%s duration_ms=%.1f",
            tool_name,
            "StructuredToolTruncatedError",
            (time.perf_counter() - started) * 1000,
        )
        raise StructuredToolTruncatedError(
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            max_tokens=max_tokens,
            top_level_keys=sorted(tool_input) if isinstance(tool_input, dict) else [],
        )

    if isinstance(tool_input, dict):
        logger.info(
            "provider_operation_complete provider=anthropic operation=%s stage=validation outcome=success exception_type=none duration_ms=%.1f model=%s stop_reason=%s input_tokens=%s output_tokens=%s max_tokens=%s",
            tool_name,
            (time.perf_counter() - started) * 1000,
            getattr(message, "model", "unknown"),
            getattr(message, "stop_reason", "unknown"),
            getattr(usage, "input_tokens", "unknown"),
            getattr(usage, "output_tokens", "unknown"),
            max_tokens,
        )
        if include_metadata:
            return StructuredToolResult(
                data=tool_input,
                model=getattr(message, "model", "unknown"),
                stop_reason=getattr(message, "stop_reason", None),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            )
        return tool_input

    logger.warning(
        "provider_operation_complete provider=anthropic operation=%s stage=validation outcome=invalid exception_type=%s duration_ms=%.1f",
        tool_name,
        "ValueError",
        (time.perf_counter() - started) * 1000,
    )
    raise ValueError("Model did not return structured tool output")


def generate_structured_note(title: str, content: str) -> GeneratedNote:
    bounded_content = _bounded_document_content(content)
    prompt = (
        "You are turning ingested learning material into a clear, well-organized "
        "study note - not a plain summary. Read the document below and produce:\n"
        "- a short title for the note\n"
        "- a 2-4 sentence summary of what the document covers\n"
        "- key_points: the most important takeaways, as short standalone bullet points\n"
        "- concepts: the important terms or ideas a learner should know, named briefly\n"
        "- sections: break the material into a few logical sections, each with a short "
        "heading and a clear explanation of that part in plain language\n\n"
        f"Document title: {title}\n\n"
        f"Document content:\n{bounded_content}"
    )

    raw = _run_structured_tool(prompt, "generated_note", GENERATED_NOTE_SCHEMA, max_tokens=1500)

    try:
        return GeneratedNote.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Model returned an invalid structured note: {e}") from e


def generate_quiz_questions(title: str, content: str, num_questions: int = 5, *, section_ids: list[str] | None = None) -> GeneratedQuizQuestions:
    bounded_content = _bounded_document_content(content)
    section_instruction = (
        "Each source section begins with a [section:<id>] marker. Set section_id to the exact id for the section that supports the answer. "
        if section_ids else
        "Set section_id to null because no note-section markers are available. "
    )
    prompt = (
        f"Write {num_questions} multiple-choice quiz questions that test understanding "
        "of the document below. Prefer central concepts, mechanisms, relationships, and application over wording trivia. "
        "Each question needs exactly 4 answer choices, the "
        "0-based index of the correct choice, and a short explanation of why that "
        f"answer is correct. {section_instruction}Base every question and explanation only on the document's content. "
        "Do not invent facts, add background knowledge, or fabricate quotations. Do not write phrases such as 'the document explicitly states' unless the supplied text contains those exact words. "
        "Keep explanations to 1–2 concise sentences that explain the reasoning, not a restatement of the entire source.\n\n"
        f"Document title: {title}\n\n"
        f"Document content:\n{bounded_content}"
    )

    raw = _run_structured_tool(prompt, "quiz_questions", QUIZ_QUESTIONS_SCHEMA, max_tokens=2000)

    try:
        return GeneratedQuizQuestions.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Model returned invalid quiz data: {e}") from e
