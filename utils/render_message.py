"""Render a message body with automatic syntax highlighting for terminal output.

The module exposes helpers to print role-styled headers and syntax-highlighted
bodies using Pygments and Rich. The visual styling is driven by Role and
RoleStyle values. The module focuses on presentation only and performs no
I/O other than printing to the provided console object from utils.console.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound
from rich.syntax import Syntax
from rich.text import Text

from utils.console import console

__all__ = ["Role", "out_agent", "out_system", "out_user"]

DEFAULT_LEXER = "text"
SYNTAX_BACKGROUND = "#15181D"
ELLIPSIS = "..."
HEADER_PADDING_LEFT = 1
HEADER_PADDING_RIGHT = 1
MAX_STATE_LENGTH = 50


class Role(str, Enum):
    """Enumeration of message roles used for terminal output styling."""

    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    USER = "USER"


@dataclass(frozen=True)
class RoleStyle:
    """Style configuration for a message role header.

    Attributes:
        foreground: Hex or named color for text.
        background: Hex or named color for background.
    """

    foreground: str
    background: str

    @property
    def style(self) -> str:
        """Return a Rich-compatible style string combining foreground and background.

        Returns:
            A style string such as "#FFFFFF bold on #000000".
        """
        return f"{self.foreground} bold on {self.background}"


ROLE_STYLES: dict[Role, RoleStyle] = {
    Role.SYSTEM: RoleStyle("#FBF5E9", "#8A6419"),
    Role.AGENT: RoleStyle("#E9FBEC", "#198A2C"),
    Role.USER: RoleStyle("#E9EFFB", "#193F8A"),
}


def _guess_lexer_name(body: str) -> str:
    """Return a Pygments lexer alias for the given body or a sensible default.

    Args:
        body: Text content to inspect.

    Returns:
        A lexer alias string or the DEFAULT_LEXER when no lexer can be guessed.
    """
    if not body.strip():
        return DEFAULT_LEXER

    try:
        lexer = guess_lexer(body)
        aliases = getattr(lexer, "aliases", None)
        if aliases:
            return aliases[0]
        return DEFAULT_LEXER
    except ClassNotFound:
        return DEFAULT_LEXER


def _truncate_state(state: str, max_length: int = MAX_STATE_LENGTH) -> str:
    """Truncate a state string to max_length and append an ellipsis when needed.

    Args:
        state: The input state string.
        max_length: Maximum allowed length for the returned string.

    Returns:
        The original state if it fits, otherwise a truncated version ending
        with an ellipsis.
    """
    if len(state) <= max_length:
        return state

    truncated_length = max_length - len(ELLIPSIS)
    return state[:truncated_length] + ELLIPSIS


def _print_header(role: Role, state: str) -> None:
    """Print a full-width, styled banner header for a specific role and state.

    Args:
        role: Message origin role.
        state: Sub-label or current process state.
    """
    state = _truncate_state(state, MAX_STATE_LENGTH)

    label = f"[ {role.value} ]"
    if state:
        label += f" ── {state}"

    width = console.width
    padded_label = " " * HEADER_PADDING_LEFT + label
    line = padded_label.ljust(
        max(width - HEADER_PADDING_RIGHT, len(padded_label)),
    )
    line += " " * HEADER_PADDING_RIGHT

    console.print(Text(line, style=ROLE_STYLES[role].style))


def _print_body(text: object) -> None:
    """Print syntax-highlighted body text with automatic lexer detection.

    Args:
        text: Object convertible to string containing body content.
    """
    body = str(text).strip()
    if not body:
        return

    console.print(
        Syntax(
            body,
            _guess_lexer_name(body),
            background_color=SYNTAX_BACKGROUND,
            word_wrap=True,
        )
    )


def _out(state: str, text: object, *, role: Role) -> None:
    """Format and print an output section with header and highlighted body.

    Args:
        state: Banner subtitle/state description.
        text: Main content to print.
        role: Role determining visual style.
    """
    _print_header(role, state)
    console.print()
    _print_body(text)
    console.print()


def out_system(state: str, text: object) -> None:
    """Print a system-level message banner and body.

    Args:
        state: System state description.
        text: Log or message payload.
    """
    _out(state, text, role=Role.SYSTEM)


def out_agent(state: str, text: object) -> None:
    """Print an agent response banner and body.

    Args:
        state: Agent action or state description.
        text: Output payload, code, or message.
    """
    _out(state, text, role=Role.AGENT)


def out_user(state: str, text: object) -> None:
    """Print a user input banner and body.

    Args:
        state: Input category or instruction label.
        text: User payload or request content.
    """
    _out(state, text, role=Role.USER)


if __name__ == "__main__":
    out_user(
        "Instruction",
        "POST /api/session HTTP/1.1\nHost: app.example.com\n"
        "Content-Type: application/x-www-form-urlencoded\n"
        "Cookie: session=ACED00057372000F73657373696F6E2E53657373696F6E\n"
        "User-Agent: Mozilla/5.0\n\nusername=test&password=test",
    )

    out_agent(
        "Build Request",
        "curl -i 'https://app.example.com/api/session' \\\n  -X POST \\\n"
        "  -H 'Content-Type: application/x-www-form-urlencoded' \\\n"
        "  -H 'Cookie: session=ACED00057372000F73657373696F6E2E53657373696F6E' \\\n"
        "  --data 'username=test&password=test'",
    )

    out_agent(
        "HTTP Response",
        "HTTP/1.1 200 OK\nContent-Type: application/json\n\n"
        '{\n  "status": "authenticated",\n  "user": "test"\n}',
    )

    out_agent(
        "Analysis",
        "The session cookie contains data matching the Java\n"
        "Object Serialization format.\n\nDetected:\n"
        "  Format   : Java Serialization\n  Location : Cookie: session\n"
        "  Signature: AC ED 00 05\n\n"
        "The serialized object is supplied by the client and reaches\n"
        "the application's session handling logic.",
    )
