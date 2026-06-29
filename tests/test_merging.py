"""
Test suite: MergeEngine

Validates that the MergeEngine correctly:
  - Honours source priority for scalar fields (full_name)
  - Union-merges array fields with case-insensitive deduplication (skills)
  - Deduplicates fuzzy-matched experience entries
  - Builds the flat provenance array correctly
"""
import pytest

from domain.models import RawRecord, Location, Experience
from merging.engine import MergeEngine


@pytest.fixture()
def engine() -> MergeEngine:
    return MergeEngine()


class TestScalarPriority:
    def test_resume_wins_over_workday(self, engine):
        """
        resume_pdf has a higher priority than workday.
        The name on the resume should be chosen.
        """
        r_workday = RawRecord(source_system="workday",    original_id="1", first_name="John")
        r_resume  = RawRecord(source_system="resume_pdf", original_id="2", first_name="Jonathan")

        merged = engine.merge([r_workday, r_resume])
        assert merged.full_name == "Jonathan"

    def test_provenance_tracks_winning_source(self, engine):
        r_workday = RawRecord(source_system="workday",    original_id="1", first_name="John")
        r_resume  = RawRecord(source_system="resume_pdf", original_id="2", first_name="Jonathan")

        merged = engine.merge([r_workday, r_resume])
        name_provs = [p for p in merged.provenance if p.field == "full_name"]
        assert len(name_provs) == 1
        assert name_provs[0].source == "resume_pdf"


class TestSkillsMerge:
    def test_case_insensitive_deduplication(self, engine):
        """'java' from greenhouse should not duplicate 'Java' from workday."""
        r1 = RawRecord(source_system="workday",    original_id="1", skills=["Python", "Java"])
        r2 = RawRecord(source_system="greenhouse", original_id="2", skills=["java", "Go"])

        merged = engine.merge([r1, r2])
        skill_lower = {s.lower() for s in merged.skills}
        assert skill_lower == {"python", "java", "go"}
        assert len(merged.skills) == 3

    def test_python3_is_normalized_to_python(self, engine):
        """Python3 from GitHub should deduplicate against Python from workday."""
        r1 = RawRecord(source_system="workday", original_id="1", skills=["Python"])
        r2 = RawRecord(source_system="github",  original_id="2", skills=["Python3"])

        merged = engine.merge([r1, r2])
        # After normalisation Python3 → Python, so only one Python entry
        assert merged.skills.count("Python") == 1


class TestExperienceMerge:
    def test_fuzzy_company_name_deduplication(self, engine):
        """
        'Google' and 'google inc' describe the same employer.
        The engine must produce only one Experience entry for Google.
        """
        e1 = Experience(company="Google",     title="Software Engineer")
        e2 = Experience(company="Google Inc", title="Software Engineer")
        e3 = Experience(company="Amazon",     title="SDE")

        r1 = RawRecord(source_system="workday",    original_id="1", experience=[e1])
        r2 = RawRecord(source_system="greenhouse", original_id="2", experience=[e2, e3])

        merged = engine.merge([r1, r2])
        assert len(merged.experience) == 2
        companies = {e.company.lower() for e in merged.experience}
        assert "google" in companies or "google inc" in companies
        assert "amazon" in companies

    def test_tata_steel_across_sources(self, engine):
        """Exact scenario from the assignment brief."""
        e_csv    = Experience(company="Tata Steel", title="Software Engineer")
        e_github = Experience(company="Tata Steel", title="Software Engineer")

        r_csv    = RawRecord(source_system="workday", original_id="1", experience=[e_csv])
        r_github = RawRecord(source_system="github",  original_id="2", experience=[e_github])

        merged = engine.merge([r_csv, r_github])
        assert len(merged.experience) == 1, "Same company from two sources must not duplicate"


class TestConfidenceScore:
    def test_single_source_score(self, engine):
        r = RawRecord(source_system="workday", original_id="1", first_name="Alice")
        merged = engine.merge([r])
        # Single workday source → base 0.8, no bonus
        assert merged.overall_confidence == pytest.approx(0.8, abs=0.05)

    def test_multi_source_increases_confidence(self, engine):
        r1 = RawRecord(source_system="resume_pdf", original_id="1", first_name="Alice")
        r2 = RawRecord(source_system="workday",    original_id="2", first_name="Alice")
        r3 = RawRecord(source_system="github",     original_id="3", first_name="Alice")

        merged = engine.merge([r1, r2, r3])
        single = engine.merge([r1])
        assert merged.overall_confidence > single.overall_confidence
