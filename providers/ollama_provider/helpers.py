"""Standalone helper functions for validation, client building, and parsing."""

from __future__ import annotations

from typing import Any

try:
    from ollama import Client  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'ollama' package is required by the Ollama provider. "
        "Install it or configure a different provider."
    ) from exc

from providers.ollama_provider.config import MIN_CONTEXT_TOKENS
from providers.ollama_provider.exceptions import OllamaConfigError, OllamaModelError


def validate_non_empty_string(value: Any, name: str) -> str:
    """Validate and sanitize required string parameters."""
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise OllamaConfigError(f"{name} must not be empty")
    return cleaned


def build_auth_headers(api_key: str | None) -> dict[str, str] | None:
    """Construct HTTP authorization headers if an API key is provided."""
    if api_key is None:
        return None

    token = api_key.strip()
    if not token:
        raise OllamaConfigError("api_key must not be empty when provided")
    return {"Authorization": f"Bearer {token}"}


def build_client(host: str, api_key: str | None, timeout: float | None) -> Client:
    """Create and return an authenticated Ollama Client instance."""
    headers = build_auth_headers(api_key)
    return Client(host=host, headers=headers, timeout=timeout)


def extract_context_length(modelinfo: dict[str, Any]) -> int:
    """Extract context_length integer from Ollama modelinfo mapping."""
    for key, value in modelinfo.items():
        if key.endswith("context_length") and isinstance(value, int):
            return value

    raise OllamaModelError(
        "Model did not report a context_length in modelinfo; "
        "only models that expose this field are supported"
    )


def validate_context_length(model: str, ctx_len: int) -> int:
    """Ensure context window meets or exceeds the required minimum threshold."""
    if ctx_len < MIN_CONTEXT_TOKENS:
        raise OllamaModelError(
            f"Model {model!r} context window is {ctx_len:,} tokens; "
            f"minimum required is {MIN_CONTEXT_TOKENS:,} (125 K)"
        )
    return ctx_len
