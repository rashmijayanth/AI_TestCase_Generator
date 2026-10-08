"""Gemini chat model access for the generation agents.

Real, working ChatGoogleGenerativeAI configuration -- its constructor field names
(model, google_api_key, temperature, response_mime_type, response_schema) and the
fact it genuinely overrides bind_tools were all verified against the installed
langchain-google-genai 4.3.6 SDK by introspection. Structured output is requested
via Gemini's native response_schema (a plain JSON-schema dict, e.g.
SomeModel.model_json_schema()) rather than LangChain's .with_structured_output()
helper -- that helper requires bind_tools-based emulation that the standard
LangChain fake chat models used in this project's tests don't implement, and the
native-response_schema route is just as real/idiomatic while staying trivially
testable with a plain fake .invoke().

Same caveat as GeminiEmbedder (Phase 3): not live-tested -- no GEMINI_API_KEY is
available in this environment. Smoke-test once a real key is configured.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from testgen.platform.config import Settings, get_settings


def get_chat_model(
    settings: Settings | None = None,
    *,
    response_schema: dict[str, Any] | None = None,
    temperature: float = 0.0,
    use_pro_model: bool = False,
) -> BaseChatModel:
    settings = settings or get_settings()
    model_name = settings.gemini_model_pro if use_pro_model else settings.gemini_model
    kwargs: dict[str, Any] = {
        "model": model_name,
        "google_api_key": settings.gemini_api_key,
        "temperature": temperature,
    }
    if response_schema is not None:
        kwargs["response_mime_type"] = "application/json"
        kwargs["response_schema"] = response_schema
    return ChatGoogleGenerativeAI(**kwargs)


def content_str(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    raise TypeError(f"Expected plain-text model content, got {type(content).__name__}")


def extract_usage(message: BaseMessage) -> tuple[int, int]:
    """Returns (input_tokens, output_tokens) from a Gemini response's
    usage_metadata. ChatGoogleGenerativeAI populates AIMessage.usage_metadata
    with input_tokens/output_tokens/total_tokens (confirmed against the
    installed langchain-google-genai SDK); falls back to (0, 0) against any
    fake/test double that doesn't set it, so tracking is additive and never
    breaks a node that has no real usage data (e.g. unit tests)."""
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return 0, 0
    return usage.get("input_tokens", 0) or 0, usage.get("output_tokens", 0) or 0
