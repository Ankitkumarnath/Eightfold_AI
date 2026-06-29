"""
Test suite: Normalizers

Covers every normalizer function with both happy-path and edge-case inputs.
All tests are pure (no I/O, no network) and run in milliseconds.
"""
import pytest

from normalizers.email import normalize_email
from normalizers.phone import normalize_phone
from normalizers.text import normalize_text, normalize_skill
from normalizers.location import parse_location_string, normalize_location
from domain.models import Location


# ─── Email ────────────────────────────────────────────────────────────────────

class TestNormalizeEmail:
    def test_strips_whitespace_and_lowercases(self):
        assert normalize_email(" TEST@EXAMPLE.com  ") == "test@example.com"

    def test_returns_none_for_invalid_email(self):
        assert normalize_email("not-an-email") is None

    def test_returns_none_for_none_input(self):
        assert normalize_email(None) is None

    def test_returns_none_for_empty_string(self):
        assert normalize_email("") is None


# ─── Phone ────────────────────────────────────────────────────────────────────

class TestNormalizePhone:
    def test_us_number_with_dashes(self):
        assert normalize_phone("415-555-1234", default_region="US") == "+14155551234"

    def test_uk_international(self):
        assert normalize_phone("+44 20 7123 1234") == "+442071231234"

    def test_india_local_number(self):
        """9876543210 is a valid Indian mobile without the country prefix."""
        assert normalize_phone("9876543210", default_region="IN") == "+919876543210"

    def test_india_with_prefix_variants(self):
        """All three representations of the same number should normalize identically."""
        canonical = "+919876543210"
        assert normalize_phone("+91-9876543210") == canonical
        assert normalize_phone("+91 9876543210") == canonical

    def test_returns_none_for_garbage_input(self):
        assert normalize_phone("invalid") is None

    def test_returns_none_for_none_input(self):
        assert normalize_phone(None) is None


# ─── Text ─────────────────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_collapses_internal_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_lowercase_flag(self):
        assert normalize_text("UPPER", lowercase=True) == "upper"

    def test_titlecase_flag(self):
        assert normalize_text("lower case text", titlecase=True) == "Lower Case Text"

    def test_returns_none_for_none(self):
        assert normalize_text(None) is None

    def test_returns_none_for_blank_string(self):
        assert normalize_text("   ") is None


# ─── Skill ────────────────────────────────────────────────────────────────────

class TestNormalizeSkill:
    def test_title_cases_normal_skill(self):
        assert normalize_skill("machine learning") == "Machine Learning"

    def test_strips_whitespace(self):
        assert normalize_skill("  python  ") == "Python"

    def test_python3_alias(self):
        """Python3 should normalize to Python via the alias table."""
        assert normalize_skill("Python3") == "Python"
        assert normalize_skill("python3") == "Python"

    def test_golang_alias(self):
        assert normalize_skill("golang") == "Go"

    def test_returns_none_for_empty(self):
        assert normalize_skill("") is None
        assert normalize_skill(None) is None


# ─── Location ─────────────────────────────────────────────────────────────────

class TestLocationParsing:
    def test_three_part_string(self):
        loc = parse_location_string("San Francisco, CA, USA")
        assert loc.city == "San Francisco"
        assert loc.state == "CA"
        assert loc.country == "USA"

    def test_two_part_string(self):
        loc = parse_location_string("New York, NY")
        assert loc.city == "New York"
        assert loc.state == "NY"
        assert loc.country is None

    def test_dict_input(self):
        loc = normalize_location({"city": " San Jose ", "state": "CA"})
        assert loc.city == "San Jose"
        assert loc.state == "CA"
        assert loc.country is None

    def test_returns_none_for_none_input(self):
        assert normalize_location(None) is None
