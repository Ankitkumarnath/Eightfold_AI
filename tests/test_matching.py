"""
Test suite: Entity-matching rules and graph resolution.

Tests confirm that:
  - individual rules fire correctly for the signals they target
  - the fuzzy-name-only rule links profile-only sources (GitHub, Notes)
  - the connected-components graph correctly groups transitive matches
"""
import pytest

from domain.models import RawRecord, Location
from matching.rules import is_match, match_email, match_phone, match_fuzzy_name_and_location, match_fuzzy_name_only
from matching.graph import build_connected_components


# ─── E-mail rule ──────────────────────────────────────────────────────────────

class TestMatchEmail:
    def test_case_insensitive_exact_match(self):
        r1 = RawRecord(source_system="workday",    original_id="1", email="test@example.com")
        r2 = RawRecord(source_system="greenhouse", original_id="2", email="TEST@example.com")
        assert match_email(r1, r2) is True

    def test_different_emails_no_match(self):
        r1 = RawRecord(source_system="workday",    original_id="1", email="a@example.com")
        r2 = RawRecord(source_system="greenhouse", original_id="2", email="b@example.com")
        assert match_email(r1, r2) is False

    def test_missing_email_no_match(self):
        r1 = RawRecord(source_system="workday",    original_id="1")
        r2 = RawRecord(source_system="greenhouse", original_id="2", email="b@example.com")
        assert match_email(r1, r2) is False


# ─── Phone rule ───────────────────────────────────────────────────────────────

class TestMatchPhone:
    def test_identical_e164_numbers_match(self):
        r1 = RawRecord(source_system="s1", original_id="1", phone="+919876543210")
        r2 = RawRecord(source_system="s2", original_id="2", phone="+919876543210")
        assert match_phone(r1, r2) is True

    def test_different_numbers_no_match(self):
        r1 = RawRecord(source_system="s1", original_id="1", phone="+919876543210")
        r2 = RawRecord(source_system="s2", original_id="2", phone="+919999999999")
        assert match_phone(r1, r2) is False


# ─── Fuzzy name + location ────────────────────────────────────────────────────

class TestMatchFuzzyNameAndLocation:
    loc_sf = Location(city="San Francisco", state="CA", country="USA")
    loc_ny = Location(city="New York", state="NY")

    def test_minor_name_typo_same_city_matches(self):
        r1 = RawRecord(source_system="s1", original_id="1", first_name="John", last_name="Doe",  location=self.loc_sf)
        r2 = RawRecord(source_system="s2", original_id="2", first_name="Jon",  last_name="Doe",  location=self.loc_sf)
        assert match_fuzzy_name_and_location(r1, r2) is True

    def test_same_name_different_city_no_match(self):
        r1 = RawRecord(source_system="s1", original_id="1", first_name="John", last_name="Doe", location=self.loc_sf)
        r2 = RawRecord(source_system="s2", original_id="2", first_name="John", last_name="Doe", location=self.loc_ny)
        assert match_fuzzy_name_and_location(r1, r2) is False

    def test_missing_location_no_match(self):
        r1 = RawRecord(source_system="s1", original_id="1", first_name="John", last_name="Doe")
        r2 = RawRecord(source_system="s2", original_id="2", first_name="John", last_name="Doe")
        assert match_fuzzy_name_and_location(r1, r2) is False


# ─── Fuzzy name only ─────────────────────────────────────────────────────────

class TestMatchFuzzyNameOnly:
    def test_identical_names_match(self):
        """GitHub/Notes records have no location — name-only rule must fire."""
        r1 = RawRecord(source_system="workday", original_id="1", first_name="Ankit", last_name="Nath")
        r2 = RawRecord(source_system="github",  original_id="2", first_name="Ankit", last_name="Nath")
        assert match_fuzzy_name_only(r1, r2) is True

    def test_completely_different_names_no_match(self):
        r1 = RawRecord(source_system="workday", original_id="1", first_name="Ankit", last_name="Nath")
        r2 = RawRecord(source_system="notes",   original_id="2", first_name="Alice", last_name="Johnson")
        assert match_fuzzy_name_only(r1, r2) is False


# ─── Composite is_match ───────────────────────────────────────────────────────

class TestIsMatch:
    def test_email_wins(self):
        r1 = RawRecord(source_system="s1", original_id="1", email="a@b.com", first_name="John")
        r2 = RawRecord(source_system="s2", original_id="2", email="a@b.com", first_name="Jane")
        assert is_match(r1, r2) is True  # email match overrides different name


# ─── Graph / connected components ────────────────────────────────────────────

class TestConnectedComponents:
    def test_transitive_grouping(self):
        """
        r1 ──(email)── r2 ──(phone)── r3     r4 (isolated)
        All three should form one group; r4 is separate.
        """
        r1 = RawRecord(source_system="s1", original_id="1", email="a@b.com")
        r2 = RawRecord(source_system="s2", original_id="2", email="a@b.com", phone="+11234567890")
        r3 = RawRecord(source_system="s3", original_id="3", phone="+11234567890")
        r4 = RawRecord(source_system="s4", original_id="4", email="z@y.com")

        groups = build_connected_components([r1, r2, r3, r4])
        assert len(groups) == 2

        sizes = sorted(len(g) for g in groups)
        assert sizes == [1, 3]

    def test_ankit_nath_four_sources_merge(self):
        """
        The canonical assignment scenario: Ankit Nath appears in 4 sources
        with slightly different contact representations.
        All four records must collapse into one group.
        """
        # Source 1: CSV — raw Indian phone
        r_csv = RawRecord(
            source_system="workday", original_id="W-1005",
            first_name="Ankit", last_name="Nath",
            email="ankit@gmail.com", phone="+919876543210",
        )
        # Source 2: ATS JSON — same email, no phone
        r_ats = RawRecord(
            source_system="greenhouse", original_id="G-9001",
            first_name="Ankit", last_name="Nath",
            email="ankit@gmail.com",
        )
        # Source 3: GitHub JSON — name only
        r_gh = RawRecord(
            source_system="github", original_id="gh-ankit",
            first_name="Ankit", last_name="Nath",
        )
        # Source 4: Recruiter Notes — name only
        r_notes = RawRecord(
            source_system="notes", original_id="notes-1",
            first_name="Ankit", last_name="Nath",
        )

        groups = build_connected_components([r_csv, r_ats, r_gh, r_notes])
        assert len(groups) == 1, "All four Ankit sources should collapse into one group"
        assert len(groups[0]) == 4
