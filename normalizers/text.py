"""
Text and Skill normalization utilities.
"""
import re
from typing import Optional


def normalize_text(text: Optional[str], lowercase: bool = False, titlecase: bool = False) -> Optional[str]:
    """
    Strips whitespace from text and optionally changes casing.

    Args:
        text: Raw string input.
        lowercase: If True, converts result to lowercase.
        titlecase: If True, converts result to Title Case.

    Returns:
        Normalized string, or None if the input is empty/None.
    """
    if not text or not str(text).strip():
        return None

    # Strip and collapse internal whitespace
    cleaned = " ".join(str(text).strip().split())

    if lowercase:
        cleaned = cleaned.lower()
    elif titlecase:
        cleaned = cleaned.title()

    return cleaned


# Known skill aliases to canonicalize
_SKILL_ALIASES: dict[str, str] = {
    "python3": "Python",
    "golang": "Go",
    "js": "JavaScript",
    "ts": "TypeScript",
    "node": "Node.Js",
    "node.js": "Node.Js",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "postgresql": "Postgresql",
    "postgres": "Postgresql",
    "mysql": "Mysql",
}


def normalize_skill(skill: Optional[str]) -> Optional[str]:
    """
    Standardizes a skill label for consistent deduplication.

    Handles:
      - Leading/trailing whitespace
      - Known aliases (e.g., Python3 → Python, golang → Go)
      - Title-casing for all other skills

    Args:
        skill: Raw skill string from any source.

    Returns:
        Canonicalized skill name, or None if the input is empty.
    """
    cleaned = normalize_text(skill)
    if not cleaned:
        return None

    lower = cleaned.lower()

    # Resolve known aliases first
    if lower in _SKILL_ALIASES:
        return _SKILL_ALIASES[lower]

    # Title-case everything else
    return cleaned.title()
