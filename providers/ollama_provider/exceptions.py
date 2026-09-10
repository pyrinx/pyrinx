"""Domain-specific exceptions for the Ollama provider."""


class OllamaError(Exception):
    """Base exception for all Ollama provider domain errors."""


class OllamaConfigError(OllamaError, ValueError):
    """Raised when provider configuration or runtime input parameters are invalid."""


class OllamaConnectionError(OllamaError, RuntimeError):
    """Raised when unable to reach or connect to the Ollama server."""


class OllamaModelError(OllamaError, ValueError):
    """Raised when model capabilities or metadata fail validation requirements."""


class OllamaResponseError(OllamaError, RuntimeError):
    """Raised when the Ollama API returns an error during execution."""
