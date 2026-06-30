"""
Entity-matching rules.

Each rule is a pure function that takes two RawRecord instances and returns
a boolean.  The top-level `is_match` function combines them with an OR logic:
*any* single strong signal is enough to link two records to the same person.

Match hierarchy (strongest → weakest):
  1. Exact e-mail match       — globally unique identifier
  2. Exact E.164 phone match  — strong identifier after normalisation
  3. Fuzzy name + location    — fallback when contact data is absent
  4. Fuzzy name only          — loose match for profile-only sources (GitHub, Notes)
"""
from rapidfuzz import fuzz
from domain.models import RawRecord
from core.config import settings


# ─── helpers ──────────────────────────────────────────────────────────────────

def _safe_lower(val: str | None) -> str:
    """Return a stripped lowercase string, or '' if val is falsy."""
    return val.strip().lower() if val and val.strip() else ""


# ─── individual rules ─────────────────────────────────────────────────────────

def match_email(r1: RawRecord, r2: RawRecord) -> bool:
    """Returns True if both records share the same normalised e-mail address."""
    e1, e2 = _safe_lower(r1.email), _safe_lower(r2.email)
    return bool(e1 and e2 and e1 == e2)


def match_phone(r1: RawRecord, r2: RawRecord) -> bool:
    """Returns True if both records share the same E.164 phone number."""
    p1, p2 = _safe_lower(r1.phone), _safe_lower(r2.phone)
    return bool(p1 and p2 and p1 == p2)


def _full_name(record: RawRecord) -> str:
    """Combine first + last name into a single lowercase string."""
    return f"{record.first_name or ''} {record.last_name or ''}".strip().lower()


def match_fuzzy_name_and_location(r1: RawRecord, r2: RawRecord) -> bool:
    """
    Returns True when both records have the *same city/state* AND a fuzzy name
    score at or above the configured threshold.

    This is a strong signal because it requires two independent pieces of data
    to align simultaneously.
    """
    loc1, loc2 = r1.location, r2.location
    if not loc1 or not loc2:
        return False

    city_match = loc1.city and loc2.city and loc1.city.lower() == loc2.city.lower()
    region_match = loc1.region and loc2.region and loc1.region.lower() == loc2.region.lower()
    country_match = loc1.country and loc2.country and loc1.country.lower() == loc2.country.lower()

    if not (city_match or region_match or country_match):
        return False

    n1, n2 = _full_name(r1), _full_name(r2)
    if not n1 or not n2:
        return False

    return fuzz.token_sort_ratio(n1, n2) >= settings.NAME_FUZZY_MATCH_THRESHOLD


def match_fuzzy_name_only(r1: RawRecord, r2: RawRecord) -> bool:
    """
    Loose name-only match used for sources that rarely carry contact data
    (e.g., GitHub, recruiter Notes).

    Uses a *higher* threshold (92) than the name+location rule to compensate
    for the weaker signal — we need near-identical names before linking.
    """
    n1, n2 = _full_name(r1), _full_name(r2)
    if not n1 or not n2:
        return False

    return fuzz.token_sort_ratio(n1, n2) >= 92


# ─── composite rule ───────────────────────────────────────────────────────────

def is_match(r1: RawRecord, r2: RawRecord) -> bool:
    """
    Returns True if any matching rule fires, meaning the two records likely
    describe the same real-world candidate.

    Rules are evaluated cheapest-first so we short-circuit early.
    """
    return (
        match_email(r1, r2)
        or match_phone(r1, r2)
        or match_fuzzy_name_and_location(r1, r2)
        or match_fuzzy_name_only(r1, r2)
    )
