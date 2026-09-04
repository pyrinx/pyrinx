"""Interactive multiline terminal input component

This module provides read_input(), a small prompt_toolkit-based UI that allows the
user to type optional multiline instructions and submit them with Alt+Enter
(Escape+Enter). The function returns the submitted text stripped of surrounding
whitespace, or None if the user cancels (Ctrl+C or EOF).

The component is presentation-only and raises RuntimeError only when the prompt
display or runtime fails unexpectedly.
"""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

__all__ = ["read_input"]

_STYLE = Style.from_dict(
    {
        "frame.border": "#A30000",
        "cursor": "reverse",
        "bottom-toolbar": "bg:#FFE6E6 fg:#A30000",
    }
)

_TITLE = "Instruction (optional)"
_HEIGHT = 5

_TOOLBAR = HTML(
    " <b>Alt+Enter</b> send   <b>Enter</b> newline   <b>Ctrl+C</b> stop/exit ",
)


def read_input() -> str | None:
    """Read optional multiline input from the terminal using prompt_toolkit UI.

    The UI shows a small editor with a single-line title, a framed text area,
    and a bottom toolbar describing keys. The user submits with Alt+Enter
    (Escape followed by Enter) and cancels with Ctrl+C or an EOF/KeyboardInterrupt.

    Returns:
        The submitted string with surrounding whitespace removed, or ``None`` if
        the user cancelled.

    Raises:
        RuntimeError: If displaying or running the input application fails for
            unexpected reasons.
    """
    text_area = TextArea(
        multiline=True,
        height=_HEIGHT,
        wrap_lines=True,
    )

    root_container = HSplit(
        [
            Window(
                content=FormattedTextControl([("class:title", _TITLE)]),
                height=1,
            ),
            Frame(text_area),
            Window(
                content=FormattedTextControl(_TOOLBAR),
                height=1,
                style="class:bottom-toolbar",
            ),
        ]
    )

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _handle_cancel(event: KeyPressEvent) -> None:
        """Handle Ctrl+C to exit the application and return ``None``."""
        event.app.exit(result=None)

    @bindings.add("escape", "enter")
    def _handle_submit(event: KeyPressEvent) -> None:
        """Handle Alt+Enter (Escape+Enter) to submit the trimmed text."""
        event.app.exit(result=text_area.text.strip())

    application: Application[str | None] = Application(
        layout=Layout(root_container, focused_element=text_area),
        key_bindings=bindings,
        style=_STYLE,
        full_screen=False,
        erase_when_done=True,
    )

    try:
        return application.run()
    except KeyboardInterrupt, EOFError:
        # Treat user interrupt or EOF as cancellation.
        return None
    except Exception as exc:
        # Fail with a clear domain-level error while preserving the cause.
        raise RuntimeError("failed to read terminal input") from exc


if __name__ == "__main__":
    # Minimal runtime example. Use logging in production; keep simple here.
    result = read_input()
    print(result)
