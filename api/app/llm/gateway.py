"""LiteLLM gateway — the single choke point for all LLM calls (docs/07 §2.4).

Provider-agnostic (OpenAI default, Ollama swappable), with centralized retry and
timeout. Implements the `LLMGateway` port. `litellm` is imported lazily so the
dependency only loads when an LLM call is actually made.
"""

from __future__ import annotations

import json
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings

log = get_logger("llm.gateway")


class LiteLLMGateway:
    """Concrete `LLMGateway`. Routes through LiteLLM to the configured model."""

    def __init__(self, model: str | None = None, timeout: float = 60.0) -> None:
        settings = get_settings()
        self.model = model or settings.llm_extract_model
        self.timeout = timeout
        self.api_key = settings.openai_api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _call(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        import litellm

        resp = litellm.completion(
            model=self.model,
            messages=messages,
            api_key=self.api_key or None,
            timeout=self.timeout,
            **kwargs,
        )
        return resp.choices[0].message.content or ""

    def complete(self, prompt: str, **kwargs: object) -> str:
        return self._call([{"role": "user", "content": prompt}], **kwargs)

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        """Request a JSON object and parse it. Returns {} on unparseable output."""
        content = self._call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            log.warning("llm.json_parse_failed", head=content[:120])
            return {}
