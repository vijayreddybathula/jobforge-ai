"""Unit tests: SalaryRange validator + RulesEngine salary guard.

Covers the '$100 instead of $100k' bug that caused good jobs to be
hard-rejected with verdict=REJECTED.
"""

import pytest
from packages.schemas.jd_schema import SalaryRange, ParsedJD, LocationType
from services.scoring.rules_engine import RulesEngine
from unittest.mock import Mock


# ── SalaryRange.normalise_salary validator ────────────────────────────────────

class TestSalaryNormalisation:
    def test_value_under_1000_scaled_to_thousands(self):
        """100 → 100_000 (the exact bug we hit)."""
        r = SalaryRange(min=100, max=150)
        assert r.min  == 100_000
        assert r.max  == 150_000

    def test_value_already_annual_unchanged(self):
        r = SalaryRange(min=120_000, max=180_000)
        assert r.min  == 120_000
        assert r.max  == 180_000

    def test_zero_becomes_none(self):
        r = SalaryRange(min=0, max=0)
        assert r.min is None
        assert r.max is None

    def test_negative_becomes_none(self):
        r = SalaryRange(min=-50_000, max=-1)
        assert r.min is None
        assert r.max is None

    def test_none_stays_none(self):
        r = SalaryRange()
        assert r.min is None
        assert r.max is None

    def test_boundary_999_scaled(self):
        """999 is still under 1000, should scale."""
        r = SalaryRange(max=999)
        assert r.max == 999_000

    def test_boundary_1000_not_scaled(self):
        """1000 and above should NOT be scaled."""
        r = SalaryRange(max=1_000)
        assert r.max == 1_000


# ── RulesEngine salary constraint ─────────────────────────────────────────────

class TestRulesEngineSalary:
    def _prefs(self, salary_min=100_000, visa="H1B", remote_only=False):
        p = Mock()
        p.salary_min_usd        = salary_min
        p.visa_status           = visa
        p.location_preferences  = {"remote_only": remote_only}
        return p

    def _jd(self, salary_max=None, location_type=LocationType.HYBRID, red_flags=None):
        return ParsedJD(
            role="Senior GenAI Engineer",
            location_type=location_type,
            salary_range={"max": salary_max} if salary_max else None,
            red_flags=red_flags or [],
        )

    def test_good_salary_passes(self):
        jd    = self._jd(salary_max=180_000)
        prefs = self._prefs(salary_min=100_000)
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is True
        assert reason is None

    def test_salary_below_floor_rejected(self):
        jd    = self._jd(salary_max=80_000)
        prefs = self._prefs(salary_min=100_000)
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is False
        assert "80,000" in reason

    def test_suspicious_low_salary_not_rejected(self):
        """$100 (bad parse) must NOT hard-reject the job."""
        # Note: SalaryRange validator will scale 100 → 100_000,
        # but we test the credibility guard by passing raw low value directly.
        from packages.schemas.jd_schema import SalaryRange
        jd = ParsedJD(
            role="Senior Engineer",
            salary_range=SalaryRange(min=None, max=None),  # simulate stripped bad val
        )
        # Manually set max below credibility threshold to test the guard
        jd.salary_range = SalaryRange.construct(min=None, max=50)  # bypass validator
        prefs = self._prefs(salary_min=100_000)
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is True, f"Expected pass but got rejection: {reason}"

    def test_no_salary_in_jd_passes(self):
        jd    = self._jd(salary_max=None)
        prefs = self._prefs(salary_min=100_000)
        ok, _ = RulesEngine().check_constraints(jd, prefs)
        assert ok is True

    def test_no_salary_pref_passes(self):
        jd    = self._jd(salary_max=50_000)
        prefs = self._prefs(salary_min=None)
        prefs.salary_min_usd = None
        ok, _ = RulesEngine().check_constraints(jd, prefs)
        assert ok is True

    def test_citizenship_rejects_h1b(self):
        jd    = self._jd(red_flags=["US Citizenship required"])
        prefs = self._prefs(visa="H1B")
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is False
        assert "H1B" in reason

    def test_remote_only_rejects_onsite(self):
        from packages.schemas.jd_schema import LocationType
        jd    = self._jd(location_type=LocationType.ONSITE)
        prefs = self._prefs(remote_only=True)
        ok, reason = RulesEngine().check_constraints(jd, prefs)
        assert ok is False

    def test_remote_only_allows_remote(self):
        from packages.schemas.jd_schema import LocationType
        jd    = self._jd(location_type=LocationType.REMOTE)
        prefs = self._prefs(remote_only=True)
        ok, _ = RulesEngine().check_constraints(jd, prefs)
        assert ok is True

    def test_remote_only_allows_unknown_location(self):
        from packages.schemas.jd_schema import LocationType
        jd    = self._jd(location_type=LocationType.UNKNOWN)
        prefs = self._prefs(remote_only=True)
        ok, _ = RulesEngine().check_constraints(jd, prefs)
        assert ok is True
