"""
Application-wide configuration settings.

Uses plain os.getenv() for environment-variable overrides — no pydantic-settings
dependency — so the module loads instantly and never blocks.

All settings are read once at module import time and exposed as a singleton
`settings` object. Override any value by setting the corresponding RE_* env var
before starting the process:

    RE_NAME_FUZZY_MATCH_THRESHOLD=90 python main.py ...
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class Settings:
    """
    All tunable engine parameters in one place.

    Priority / weight values directly influence merge and confidence behaviour,
    so they are exposed as first-class settings rather than hard-coded magic
    numbers scattered across the codebase.
    """

    # ── Entity-Matching ────────────────────────────────────────────────────
    # Minimum fuzz.token_sort_ratio score (0–100) to consider two names
    # identical.  85 tolerates minor typos ("Jon" vs "John") while still
    # rejecting people with clearly different names.
    NAME_FUZZY_MATCH_THRESHOLD: float = field(
        default_factory=lambda: _env_float("RE_NAME_FUZZY_MATCH_THRESHOLD", 85.0)
    )

    # ── Merge Engine ──────────────────────────────────────────────────────
    # Highest priority wins for scalar fields (e.g. name, headline).
    # Sources absent from this list are treated as lowest priority.
    SOURCE_PRIORITY: List[str] = field(default_factory=lambda: [
        "resume_pdf",   # Candidate-authored — most trustworthy
        "linkedin",     # Public professional profile
        "workday",      # HR system of record
        "greenhouse",   # ATS import
        "github",       # Inferred from public repo activity
        "notes",        # Recruiter free-text — most subjective
    ])

    # ── Confidence Scoring ────────────────────────────────────────────────
    # Base score when a profile's primary source is one of these systems.
    CONFIDENCE_BASE_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "resume_pdf": 0.85,
        "linkedin":   0.90,
        "workday":    0.80,
        "greenhouse": 0.70,
        "github":     0.60,
        "notes":      0.50,
    })

    # Each additional corroborating source adds this bonus (capped at 1.0).
    CONFIDENCE_MULTI_SOURCE_BONUS: float = field(
        default_factory=lambda: _env_float("RE_CONFIDENCE_MULTI_SOURCE_BONUS", 0.05)
    )

    # Each detected conflict (same field, different values) deducts this.
    CONFIDENCE_CONFLICT_PENALTY: float = field(
        default_factory=lambda: _env_float("RE_CONFIDENCE_CONFLICT_PENALTY", 0.05)
    )

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = field(default_factory=lambda: _env_str("RE_LOG_LEVEL", "INFO"))
    LOG_FILE:  str = field(default_factory=lambda: _env_str("RE_LOG_FILE", "resolution_engine.log"))


# Singleton — import `settings` everywhere; never instantiate Settings directly.
settings = Settings()
