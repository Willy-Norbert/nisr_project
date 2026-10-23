"""Thin client for any OpenAI-compatible chat completions API."""

import json
import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def enabled() -> bool:
    return bool(get_settings().llm_api_key)


def chat(messages: list[dict], temperature: float = 0.2, json_mode: bool = False) -> str:
    s = get_settings()
    body: dict = {"model": s.llm_model, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        res = httpx.post(
            f"{s.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {s.llm_api_key}"},
            json=body,
            timeout=s.llm_timeout_s,
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"] or ""
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.warning("LLM request failed: %s", exc)
        raise LLMError(str(exc)) from exc


def chat_json(messages: list[dict]) -> dict:
    text = chat(messages, temperature=0, json_mode=True)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise LLMError("No JSON object in model response")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(str(exc)) from exc
