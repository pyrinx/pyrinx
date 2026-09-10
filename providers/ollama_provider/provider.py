"""Ollama LLM provider class implementation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

try:
    from ollama import Options, RequestError, ResponseError  # type: ignore
    from ollama._types import ChatResponse, Message, Tool  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The 'ollama' package is required by the Ollama provider. "
        "Install it or configure a different provider."
    ) from exc

from providers.ollama_provider.config import DEFAULT_TIMEOUT
from providers.ollama_provider.exceptions import (
    OllamaConfigError,
    OllamaConnectionError,
    OllamaModelError,
    OllamaResponseError,
)
from providers.ollama_provider.helpers import (
    build_client,
    extract_context_length,
    validate_context_length,
    validate_non_empty_string,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Provider wrapper around the Ollama client."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize provider, build client connection, and validate model context window."""
        base_url_clean = validate_non_empty_string(base_url, "base_url")
        self._model = validate_non_empty_string(model, "model")
        self._client = build_client(base_url_clean, api_key, timeout)
        self._context_length = self._probe_model(self._model)

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

    @property
    def context_length(self) -> int:
        """Return the discovered model context length in tokens."""
        return self._context_length

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[Tool] | None = None,
    ) -> ChatResponse:
        """Send a chat request to the configured Ollama model."""
        if not messages:
            raise OllamaConfigError("messages must not be empty")

        options = Options(num_ctx=self._context_length)

        try:
            return self._client.chat(
                model=self._model,
                messages=list(messages),
                tools=list(tools) if tools else None,
                options=options,
            )
        except ResponseError as exc:
            logger.error("Ollama API error during chat: %s", exc)
            raise OllamaResponseError(f"Ollama API error during chat: {exc}") from exc
        except RequestError as exc:
            logger.error("Ollama connection error during chat: %s", exc)
            raise OllamaConnectionError(
                f"Ollama connection error during chat: {exc}"
            ) from exc

    def _fetch_model_info(self, model: str) -> dict[str, Any]:
        """Query Ollama API directly for raw model metadata."""
        try:
            info = self._client.show(model)
        except ResponseError as exc:
            logger.error("Ollama ResponseError while probing model %s: %s", model, exc)
            raise OllamaResponseError(
                f"Model {model!r} not found or Ollama error: {exc}"
            ) from exc
        except RequestError as exc:
            logger.error("Ollama RequestError while probing model %s: %s", model, exc)
            raise OllamaConnectionError(
                f"Cannot reach Ollama at the configured URL: {exc}"
            ) from exc

        if not info.modelinfo:
            raise OllamaModelError(f"Model {model!r} returned no modelinfo metadata.")

        return dict(info.modelinfo)

    def _probe_model(self, model: str) -> int:
        """Query Ollama for model metadata, parse, and validate context window requirements."""
        modelinfo = self._fetch_model_info(model)
        ctx_len = extract_context_length(modelinfo)
        validated_len = validate_context_length(model, ctx_len)

        logger.info("Model %s reports context length %d", model, validated_len)
        return validated_len
