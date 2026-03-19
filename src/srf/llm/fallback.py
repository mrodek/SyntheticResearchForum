"""LLM provider fallback client — used only when tracker is None.

The primary execution path for all LLM calls is tracker.execute(). This module
exists solely for tracker=None contexts (offline dev, CI without PL credentials).
Provider SDKs are imported lazily inside call_provider_directly() — never at
module level — so the module imports cleanly regardless of which SDKs are installed.
"""

from __future__ import annotations

import structlog

from srf.config import ConfigurationError, SRFConfig

logger = structlog.get_logger(__name__)


class LLMError(RuntimeError):
    """Raised when the provider SDK returns an error response."""


async def call_provider_directly(
    messages: list[dict],
    config: SRFConfig,
) -> str:
    """Call the configured LLM provider without PromptLedger.

    Only used when tracker is None. Never call this when tracker is not None.

    Args:
        messages: OpenAI-compatible message list, e.g.
                  [{"role": "user", "content": "hello"}]
        config:   SRFConfig with llm_provider, llm_model, llm_api_key.

    Returns:
        The model's response as a plain string.

    Raises:
        ConfigurationError: If the provider is not supported.
        LLMError:           If the provider SDK raises an API error.
    """
    provider = config.llm_provider

    if provider == "anthropic":
        return await _call_anthropic(messages, config)
    elif provider == "openai":
        return await _call_openai(messages, config)
    else:
        raise ConfigurationError(
            f"llm_provider={provider!r} is not supported by call_provider_directly(). "
            f"Supported providers: anthropic, openai"
        )


async def _call_anthropic(messages: list[dict], config: SRFConfig) -> str:
    """Call the Anthropic API directly (lazy SDK import)."""
    import anthropic  # lazy import — only when provider=anthropic

    client = anthropic.AsyncAnthropic(api_key=config.llm_api_key)
    try:
        response = await client.messages.create(
            model=config.llm_model,
            max_tokens=1024,
            messages=messages,
        )
    except Exception as exc:
        raise LLMError(f"Anthropic API error: {exc}") from exc

    return response.content[0].text


async def _call_openai(messages: list[dict], config: SRFConfig) -> str:
    """Call the OpenAI API directly (lazy SDK import)."""
    import openai  # lazy import — only when provider=openai

    client = openai.AsyncOpenAI(api_key=config.llm_api_key)
    try:
        response = await client.chat.completions.create(
            model=config.llm_model,
            messages=messages,
        )
    except Exception as exc:
        raise LLMError(f"OpenAI API error: {exc}") from exc

    return response.choices[0].message.content
