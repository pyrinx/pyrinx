"""Configuration constants for the Ollama provider."""

# Minimum context window (tokens) required by the application.
MIN_CONTEXT_TOKENS: int = 125 * 1024

# Default connection timeout (None => use client's default).
DEFAULT_TIMEOUT: float | None = None
