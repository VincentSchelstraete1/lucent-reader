import os
from anthropic import Anthropic


client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


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
