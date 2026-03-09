"""Unit tests for ParsedJD schema validation."""

import pytest
from packages.schemas.jd_schema import ParsedJD, SalaryRange, LocationType, SeniorityLevel


class TestParsedJDDefaults:
    def test_lists_default_to_empty(self):
        jd = ParsedJD(role="Engineer")
        assert jd.must_have_skills    == []
        assert jd.nice_to_have_skills == []
        assert jd.responsibilities    == []
        assert jd.ats_keywords        == []
        assert jd.red_flags           == []

    def test_none_lists_coerced_to_empty(self):
        jd = ParsedJD(
            role="Engineer",
            must_have_skills=None,
            nice_to_have_skills=None,
        )
        assert jd.must_have_skills    == []
        assert jd.nice_to_have_skills == []

    def test_string_skill_wrapped_in_list(self):
        jd = ParsedJD(role="Engineer", must_have_skills="Python")
        assert jd.must_have_skills == ["Python"]

    def test_unknown_defaults(self):
        jd = ParsedJD(role="Engineer")
        assert jd.seniority       == SeniorityLevel.UNKNOWN
        assert jd.location_type   == LocationType.UNKNOWN

    def test_salary_range_optional(self):
        jd = ParsedJD(role="Engineer")
        assert jd.salary_range is None

    def test_full_jd_round_trips_via_dict(self):
        jd = ParsedJD(
            role="Senior GenAI Engineer",
            seniority=SeniorityLevel.SENIOR,
            location_type=LocationType.HYBRID,
            must_have_skills=["Python", "LangChain"],
            salary_range={"min": 150_000, "max": 200_000},
        )
        d    = jd.dict()
        jd2  = ParsedJD(**d)
        assert jd2.role                == jd.role
        assert jd2.must_have_skills    == jd.must_have_skills
        assert jd2.salary_range.min    == 150_000
