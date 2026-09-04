"""Module-level Rich Console for application output.

This module exposes a single, application-wide Console instance named
`console`. Import the instance with `from <package>.console import console`.
Keep configuration centralized here so formatting or destination changes are
made in one place.
"""

from __future__ import annotations

from rich.console import Console

__all__ = ["console"]

# Single, shared Console instance used across the application. Configure here
# if you need color system, width, file output, etc.
console: Console = Console()
