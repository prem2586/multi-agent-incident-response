
import os

from backend.llm.base import LLMProvider


def get_llm_provider() -> LLMProvider | None:
    provider = os.getenv(
        "LLM_PROVIDER", "none"
    ).strip().lower()

    if provider == "none":
        return None

    if provider == "gemini":
        from backend.llm.providers.gemini import (
            GeminiProvider,
        )
        return GeminiProvider()

    if provider == "claude":
        from backend.llm.providers.claude import (
            ClaudeProvider,
        )
        return ClaudeProvider()

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )
