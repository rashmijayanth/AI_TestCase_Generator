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
