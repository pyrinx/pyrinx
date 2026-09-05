"""Ollama LLM provider client wrapper.

This module provides a thin, well-typed wrapper around the `ollama` client
library used by the project. It exposes a minimal provider class that:
- validates configuration,
- probes the model for a context window,
- and exposes a `chat()` wrapper which forwards messages and tools to Ollama.

The wrapper intentionally validates the model reports a `context_length`
value and enforces a minimum acceptable window. It also translates low-level
client errors into clearer runtime errors for callers.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

try:
    from ollama import Client, Options, RequestError, ResponseError  # type: ignore
    from ollama._types import ChatResponse, Message, Tool  # type: ignore
except Exception as exc:  # pragma: no cover - environment dependent
    raise ImportError(
        "The 'ollama' package is required by the Ollama provider. "
        "Install it or configure a different provider."
    ) from exc

logger = logging.getLogger(__name__)

# Minimum context window (tokens) required by the application.
MIN_CONTEXT_TOKENS: int = 125 * 1024

# Default connection timeout (None => use client's default).
DEFAULT_TIMEOUT: float | None = None


def _extract_context_length(modelinfo: dict[str, Any] | None) -> int | None:
    """Extract a context_length integer from the modelinfo mapping.

    Args:
        modelinfo: Mapping returned by the Ollama client (modelinfo).

    Returns:
        The context length as an int when present, otherwise None.
    """
    if not modelinfo:
        return None

    for key, value in modelinfo.items():
        # Ollama model_info uses keys ending with "context_length".
        if key.endswith("context_length") and isinstance(value, int):
            return value

    return None


def _build_client(host: str, api_key: str | None, timeout: float | None) -> Client:
    """Create and return an authenticated Ollama Client.

    Args:
        host: Base URL of the Ollama server.
        api_key: Optional API key to include as Bearer token.
        timeout: Optional network timeout in seconds.

    Returns:
        Configured Ollama Client instance.

    Raises:
        ValueError: If api_key is provided but empty after stripping.
    """
    headers: dict[str, str] | None = None
    if api_key is not None:
        token = api_key.strip()
        if not token:
            raise ValueError("api_key must not be empty when provided")
        headers = {"Authorization": f"Bearer {token}"}

    return Client(host=host, headers=headers, timeout=timeout)


class OllamaProvider:
    """Provider wrapper around the Ollama client.

    Example usage:
        provider = OllamaProvider(base_url="http://localhost:11434", model="mymodel")
        response = provider.chat(messages, tools=tools_list)
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> None:
        """Create and initialize an OllamaProvider.

        The constructor validates inputs, builds the client and probes the
        model for its context window.

        Args:
            base_url: Host URL for the Ollama server.
            model: Model name to use on Ollama.
            api_key: Optional API key for authenticated Ollama instances.
            timeout: Optional network timeout in seconds.

        Raises:
            ValueError: For invalid base_url or model name, or if the model
                does not report a usable context window.
            RuntimeError: When the Ollama client cannot be contacted.
        """
        base_url_clean = base_url.strip() if isinstance(base_url, str) else ""
        if not base_url_clean:
            raise ValueError("base_url must not be empty")

        model_clean = model.strip() if isinstance(model, str) else ""
        if not model_clean:
            raise ValueError("model must not be empty")

        self._model = model_clean
        self._client = _build_client(base_url_clean, api_key, timeout)
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
        """Send a chat request to the configured Ollama model.

        Args:
            messages: Sequence of Message objects representing the conversation.
            tools: Optional sequence of Tool definitions to expose to the model.

        Returns:
            ChatResponse returned by the Ollama client.

        Raises:
            ValueError: If messages is empty.
            RuntimeError: For Ollama API or connection errors.
        """
        if not messages:
            raise ValueError("messages must not be empty")

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
            raise RuntimeError(f"Ollama API error during chat: {exc}") from exc
        except RequestError as exc:
            logger.error("Ollama connection error during chat: %s", exc)
            raise RuntimeError(f"Ollama connection error during chat: {exc}") from exc

    def _probe_model(self, model: str) -> int:
        """Query the Ollama server for model info and return the context length.

        Args:
            model: Model name.

        Returns:
            Context length (number of tokens) reported by the model.

        Raises:
            RuntimeError: When the model is not found or the server cannot be reached.
            ValueError: When the model does not report a context_length or it
                is smaller than MIN_CONTEXT_TOKENS.
        """
        try:
            info = self._client.show(model)
        except ResponseError as exc:
            logger.error("Ollama ResponseError while probing model %s: %s", model, exc)
            raise RuntimeError(
                f"model {model!r} not found or Ollama error: {exc}"
            ) from exc
        except RequestError as exc:
            logger.error("Ollama RequestError while probing model %s: %s", model, exc)
            raise RuntimeError(
                f"cannot reach Ollama at the configured URL: {exc}"
            ) from exc

        modelinfo: dict[str, Any] | None = (
            dict(info.modelinfo) if info.modelinfo else None
        )
        ctx_len = _extract_context_length(modelinfo)

        if ctx_len is None:
            raise ValueError(
                f"model {model!r} did not report a context_length in modelinfo; "
                "only models that expose this field are supported"
            )

        if ctx_len < MIN_CONTEXT_TOKENS:
            raise ValueError(
                f"model {model!r} context window is {ctx_len:,} tokens; "
                f"minimum required is {MIN_CONTEXT_TOKENS:,} (125 K)"
            )

        logger.info("Model %s reports context length %d", model, ctx_len)
        return ctx_len
