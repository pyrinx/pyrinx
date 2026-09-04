"""Command-line argument parsing for the Pyrinx application.

This module provides a small, well-typed wrapper around argparse that returns
a dataclass with the parsed CLI values used by the application entrypoint.

The parsing behaviour is unchanged: all four flags are required and argparse's
built-in error/usage handling remains in place.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
from typing import List, Optional

__all__ = ["Args", "parse_args"]


@dataclass
class Args:
    """Container for parsed command-line arguments.

    Attributes:
        llm_base_url: Base URL for the LLM provider.
        llm_model: Model identifier, typically in the form "provider/model".
        llm_api_key: API key used to authenticate to the LLM provider.
        target: Target URL or host to analyze.
    """

    llm_base_url: str
    llm_model: str
    llm_api_key: str
    target: str


def parse_args(argv: Optional[List[str]] = None) -> Args:
    """Parse command-line arguments and return an Args object.

    Args:
        argv: Optional list of arguments to parse. If None, the arguments are
            taken from sys.argv (argparse default).

    Returns:
        An Args instance populated from the parsed CLI flags.

    Notes:
        All flags are required. argparse will print usage and exit on missing
        required flags or on explicit parse errors.
    """
    parser = argparse.ArgumentParser(
        prog="pyrinx",
        description="Directed Autonomous Security Research Agent",
    )

    parser.add_argument(
        "--llm-base-url",
        required=True,
        help="Base URL for the LLM provider (e.g. https://api.example.com)",
    )

    parser.add_argument(
        "--llm-model",
        required=True,
        help="Model identifier in the form '<provider>/<model>' (example: openai/gpt-4)",
    )

    parser.add_argument(
        "--llm-api-key",
        required=True,
        help="API key for authenticating to the LLM provider",
    )

    parser.add_argument(
        "--target",
        required=True,
        help="Target URL or host to analyze (for example: https://example.com)",
    )

    namespace = parser.parse_args(argv)
    return Args(**vars(namespace))


if __name__ == "__main__":
    # Simple runtime example; argparse will enforce required flags when invoked
    # from the command line.
    args = parse_args()
    print(args)
