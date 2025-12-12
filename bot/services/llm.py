# bot/ai/llm.py
import json
from typing import Any, Dict

from openai import OpenAI

from bot.config import Settings


def _extract_json_from_text(content: str) -> str:
    text = (content or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        text = text[start: end + 1].strip()

    return text


def call_llm_as_json(
        settings: Settings,
        *,
        system_prompt: str,
        user_prompt: str,
) -> Dict[str, Any]:
    client = OpenAI(api_key=settings.openai_api_key)

    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    content = resp.choices[0].message.content or ""
    cleaned = _extract_json_from_text(content)

    try:
        return json.loads(cleaned)
    except Exception as e:
        short = cleaned[:1000]
        raise RuntimeError(f"LLM JSON qaytarmadi: {e}. Content (truncated): {short!r}")
