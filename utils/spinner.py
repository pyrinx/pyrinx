"""Terminal spinner indicator.

This module provides a small Spinner class that displays a Rich status spinner
with an associated message. The Spinner is usable as a context manager:

    with Spinner("Working..."):
        do_work()

The runtime behavior is unchanged: the spinner starts when requested and stops
when stopped or when the context is exited.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from rich.status import Status
from rich.text import Text

from utils.console import console

__all__ = ["Spinner"]

DEFAULT_TEXT = "Reasoning..."
DEFAULT_SPINNER = "dots"
SPINNER_STYLE = "#7C8594"
TEXT_STYLE = "#7C8594 italic"


class Spinner:
    """Display a spinner with a status message.

    The spinner is a thin wrapper around rich.console.Console.status that
    provides explicit start/update/stop methods and context-manager support.
    """

    def __init__(
        self,
        text: str = DEFAULT_TEXT,
        spinner: str = DEFAULT_SPINNER,
    ) -> None:
        """Create a Spinner.

        Args:
            text: Initial message to display next to the spinner.
            spinner: Spinner style name supported by Rich.
        """
        self._status: Status = console.status(
            Text(text, style=TEXT_STYLE),
            spinner=spinner,
            spinner_style=SPINNER_STYLE,
        )
        self._active: bool = False

    def start(self, text: str | None = None) -> None:
        """Start the spinner.

        If `text` is provided it updates the displayed message before starting.

        Args:
            text: Optional message to display before starting.
        """
        if text is not None:
            self.update(text)

        if not self._active:
            self._status.start()
            self._active = True

    def update(self, text: str) -> None:
        """Update the spinner message.

        Args:
            text: New message to display next to the spinner.
        """
        self._status.update(Text(text, style=TEXT_STYLE))

    def stop(self) -> None:
        """Stop the spinner if it is active."""
        if self._active:
            self._status.stop()
            self._active = False

    def __enter__(self) -> Self:
        """Enter context: start and return self."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit context: ensure the spinner is stopped."""
        self.stop()


if __name__ == "__main__":
    import time

    from utils.render_message import out_agent, out_system

    out_system("init", "Server started on port 8080")

    with Spinner("Loading skill: insecure_deserialization/baseline.md") as spinner:
        time.sleep(1)
        spinner.update("Thinking...")
        time.sleep(1)
        out_agent(
            "hypothesis",
            "H1: session cookie deserializes attacker-controlled data",
        )
        time.sleep(1)
        spinner.update("Testing hypothesis #1")
        time.sleep(1)
