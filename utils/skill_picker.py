"""Interactive specialist skill selection menu.

This module discovers available specialist skills from the repository `skills`
directory (each skill is a directory that contains a non-empty `baseline.md`)
and prompts the user to pick one using questionary.

Public API:
- SkillEntry: Dataclass pairing a skill name with its directory Path.
- pick_skill: Interactively select a skill and return the chosen SkillEntry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import questionary

from utils.render_message import out_system

__all__ = ["SkillEntry", "pick_skill"]

_BASELINE_FILENAME = "baseline.md"
_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

_SKILL_STYLE = questionary.Style(
    [
        ("qmark", "fg:#A30000 bold"),
        ("answer", "fg:#ffffff bg:#A30000 bold"),
        ("highlighted", "fg:#ffffff bg:#A30000 bold"),
        ("selected", "fg:#ffffff bg:#A30000 bold"),
        ("pointer", "fg:#A30000 bold"),
    ],
)


@dataclass(frozen=True)
class SkillEntry:
    """Represent an available specialist skill.

    Attributes:
        name: Human-readable skill name (directory name).
        path: Filesystem path to the skill directory.
    """

    name: str
    path: Path


def _find_skills() -> List[SkillEntry]:
    """Discover specialist skills with a non-empty baseline file.

    Returns:
        A sorted list of SkillEntry objects for directories that contain a
        non-empty baseline file.

    Raises:
        RuntimeError: If the skills directory does not exist or cannot be read.
    """
    if not _SKILLS_DIR.is_dir():
        raise RuntimeError(f"skills directory does not exist: {_SKILLS_DIR}")

    try:
        entries: List[SkillEntry] = []
        for skill_dir in sorted(
            _SKILLS_DIR.iterdir(),
            key=lambda p: p.name.casefold(),
        ):
            if not skill_dir.is_dir():
                continue

            baseline_file = skill_dir / _BASELINE_FILENAME
            if not baseline_file.is_file():
                continue

            try:
                content = baseline_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                # If a single baseline file cannot be read, surface a clear error.
                raise RuntimeError(f"failed to read {baseline_file}") from exc

            if content:
                entries.append(
                    SkillEntry(
                        name=skill_dir.name,
                        path=skill_dir,
                    ),
                )

        return entries
    except OSError as exc:
        raise RuntimeError(
            f"failed to inspect skills directory: {_SKILLS_DIR}"
        ) from exc


def _select_skill(entries: List[SkillEntry]) -> Optional[SkillEntry]:
    """Prompt the user to select a skill using questionary.

    Args:
        entries: Available skill entries to present.

    Returns:
        The selected SkillEntry, or None if the user cancels the prompt.

    Raises:
        RuntimeError: If the selection UI fails unexpectedly.
    """
    choices = [questionary.Choice(title=entry.name, value=entry) for entry in entries]

    try:
        return questionary.select(
            "Pick skill:",
            choices=choices,
            style=_SKILL_STYLE,
        ).ask()
    except KeyboardInterrupt:
        # Treat explicit keyboard interrupt as cancellation.
        return None
    except Exception as exc:
        raise RuntimeError("failed to display skill selection") from exc


def pick_skill() -> SkillEntry:
    """Interactively select a specialist skill.

    The function prints a system-level error and exits the program with a non-
    zero status when discovery fails or no valid skills are found.

    Returns:
        The selected SkillEntry.

    Raises:
        SystemExit:
            - Exit code 1 when discovery failed or no skills available.
            - Exit code 0 when the user cancelled the selection.
    """
    try:
        entries = _find_skills()
    except RuntimeError as exc:
        out_system("error", str(exc))
        raise SystemExit(1) from exc

    if not entries:
        out_system(
            "error",
            f"no skills with a non-empty {_BASELINE_FILENAME} found in {_SKILLS_DIR}",
        )
        raise SystemExit(1)

    selected = _select_skill(entries)

    if selected is None:
        # User cancelled selection.
        raise SystemExit(0)

    return selected


if __name__ == "__main__":
    skill = pick_skill()
    print(f"name : {skill.name}")
    print(f"path : {skill.path}")
