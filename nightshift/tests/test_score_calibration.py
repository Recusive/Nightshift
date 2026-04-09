"""Calibration tests: verify dimension scorers against known-good and known-bad fixtures.

Fixtures live in tests/fixtures/evaluation/ and represent ShiftArtifacts TypedDicts
serialized as JSON.  Each fixture was hand-crafted to exercise specific scorer paths:

  known_good_01.json -- two accepted cycles, 5 structured fixes, 3 categories, all
                        verifications passed, clean repo, rich shift log.
  known_good_02.json -- one accepted cycle, 2 structured fixes, 2 categories, 3 tests
                        written, clean repo.  Breadth scores exactly 6 (floor of pass
                        threshold) to confirm the threshold is inclusive.

  known_bad_01.json  -- runner crashed (exit 1), state is null, no shift log, dirty
                        working tree.  All 10 dimensions score below 6.
  known_bad_02.json  -- runner exited cleanly but both cycles were rejected (failed
                        verifications), shift log is an unfilled template, zero fixes.
                        Six dimensions score below 6, well above the required three.

Calibration invariants (enforced by CI):
  - Every known-good artifact scores >= 6 on ALL dimensions.
  - Every known-bad artifact scores < 6 on AT LEAST 3 dimensions.
  - All individual scores remain in [0, max_score].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from nightshift.core.constants import EVALUATION_SCORE_THRESHOLD
from nightshift.core.types import ShiftArtifacts
from nightshift.owl.eval_runner import score_artifacts

# ---------------------------------------------------------------------------
# Fixture loading helpers
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "evaluation"

_KNOWN_GOOD_FIXTURES = [
    "known_good_01.json",
    "known_good_02.json",
]

_KNOWN_BAD_FIXTURES = [
    "known_bad_01.json",
    "known_bad_02.json",
]


def _load_fixture(name: str) -> ShiftArtifacts:
    """Load a JSON fixture file and return it as a ShiftArtifacts TypedDict.

    The JSON object must contain the keys defined in ShiftArtifacts.  Loading is
    done at JSON deserialization boundary so the raw dict is typed as Any before
    being coerced to the TypedDict.
    """
    path = _FIXTURE_DIR / name
    raw: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    exit_code_raw = raw.get("runner_exit_code", 0)
    exit_code = exit_code_raw if isinstance(exit_code_raw, int) else 0
    return ShiftArtifacts(
        state=raw.get("state"),
        shift_log=str(raw.get("shift_log", "")),
        runner_exit_code=exit_code,
        state_file_valid=bool(raw.get("state_file_valid", False)),
        shift_log_exists=bool(raw.get("shift_log_exists", False)),
        git_status_output=str(raw.get("git_status_output", "")),
        repo_is_clean=bool(raw.get("repo_is_clean", True)),
    )


# ---------------------------------------------------------------------------
# Known-good calibration tests
# ---------------------------------------------------------------------------


class TestKnownGoodFixtures:
    """Every dimension must score >= EVALUATION_SCORE_THRESHOLD for known-good runs."""

    @pytest.mark.parametrize("fixture_name", _KNOWN_GOOD_FIXTURES)
    def test_all_dimensions_pass_threshold(self, fixture_name: str) -> None:
        """All 10 dimension scores must be >= 6 for a known-good artifact set."""
        artifacts = _load_fixture(fixture_name)
        scores = score_artifacts(artifacts)
        below = [(s["name"], s["score"]) for s in scores if s["score"] < EVALUATION_SCORE_THRESHOLD]
        assert below == [], (
            f"Known-good fixture {fixture_name!r} has dimensions below threshold "
            f"({EVALUATION_SCORE_THRESHOLD}): {below}"
        )

    @pytest.mark.parametrize("fixture_name", _KNOWN_GOOD_FIXTURES)
    def test_scores_in_valid_range(self, fixture_name: str) -> None:
        """All scores must be in [0, max_score]."""
        artifacts = _load_fixture(fixture_name)
        scores = score_artifacts(artifacts)
        for s in scores:
            assert 0 <= s["score"] <= s["max_score"], (
                f"Fixture {fixture_name!r} dimension {s['name']!r}: score {s['score']} outside [0, {s['max_score']}]"
            )

    @pytest.mark.parametrize("fixture_name", _KNOWN_GOOD_FIXTURES)
    def test_total_score_is_high(self, fixture_name: str) -> None:
        """Total score across all dimensions should be well above the floor (>= 80)."""
        artifacts = _load_fixture(fixture_name)
        scores = score_artifacts(artifacts)
        total = sum(s["score"] for s in scores)
        assert total >= 80, f"Known-good fixture {fixture_name!r} total score {total} < 80"

    def test_known_good_01_loads_correctly(self) -> None:
        """Sanity-check: fixture state must have the expected counters."""
        artifacts = _load_fixture("known_good_01.json")
        assert artifacts["runner_exit_code"] == 0
        assert artifacts["state_file_valid"] is True
        assert artifacts["shift_log_exists"] is True
        assert artifacts["repo_is_clean"] is True
        state = artifacts["state"]
        assert isinstance(state, dict)
        counters = state["counters"]
        assert isinstance(counters, dict)
        assert counters["fixes"] == 3
        assert counters["tests_written"] == 2

    def test_known_good_02_loads_correctly(self) -> None:
        """Sanity-check: fixture state must have the expected counters."""
        artifacts = _load_fixture("known_good_02.json")
        assert artifacts["runner_exit_code"] == 0
        assert artifacts["state_file_valid"] is True
        assert artifacts["shift_log_exists"] is True
        state = artifacts["state"]
        assert isinstance(state, dict)
        counters = state["counters"]
        assert isinstance(counters, dict)
        assert counters["fixes"] == 2
        assert counters["tests_written"] == 3


# ---------------------------------------------------------------------------
# Known-bad calibration tests
# ---------------------------------------------------------------------------

_MIN_BAD_DIMENSIONS = 3


class TestKnownBadFixtures:
    """At least 3 dimensions must score < EVALUATION_SCORE_THRESHOLD for known-bad runs."""

    @pytest.mark.parametrize("fixture_name", _KNOWN_BAD_FIXTURES)
    def test_at_least_three_dimensions_fail(self, fixture_name: str) -> None:
        """At least 3 dimension scores must be < 6 for a known-bad artifact set."""
        artifacts = _load_fixture(fixture_name)
        scores = score_artifacts(artifacts)
        below = [s["name"] for s in scores if s["score"] < EVALUATION_SCORE_THRESHOLD]
        assert len(below) >= _MIN_BAD_DIMENSIONS, (
            f"Known-bad fixture {fixture_name!r} only has {len(below)} dimension(s) "
            f"below threshold (need >= {_MIN_BAD_DIMENSIONS}): below={below}"
        )

    @pytest.mark.parametrize("fixture_name", _KNOWN_BAD_FIXTURES)
    def test_scores_in_valid_range(self, fixture_name: str) -> None:
        """All scores must be in [0, max_score] regardless of fixture type."""
        artifacts = _load_fixture(fixture_name)
        scores = score_artifacts(artifacts)
        for s in scores:
            assert 0 <= s["score"] <= s["max_score"], (
                f"Fixture {fixture_name!r} dimension {s['name']!r}: score {s['score']} outside [0, {s['max_score']}]"
            )

    def test_known_bad_01_crash_scenario(self) -> None:
        """A crash scenario (exit 1, null state) should fail all 10 dimensions."""
        artifacts = _load_fixture("known_bad_01.json")
        scores = score_artifacts(artifacts)
        below = [s["name"] for s in scores if s["score"] < EVALUATION_SCORE_THRESHOLD]
        assert len(below) == 10, (
            f"Crash scenario fixture should fail all 10 dimensions, "
            f"but only {len(below)} are below threshold: passing={[s['name'] for s in scores if s['score'] >= EVALUATION_SCORE_THRESHOLD]}"
        )

    def test_known_bad_01_startup_fails(self) -> None:
        """A non-zero runner exit code must produce a failing Startup score."""
        artifacts = _load_fixture("known_bad_01.json")
        scores = score_artifacts(artifacts)
        startup = next(s for s in scores if s["name"] == "Startup")
        assert startup["score"] == 0

    def test_known_bad_02_template_log_scores_low(self) -> None:
        """An unfilled template shift log must score < 6 on Shift log dimension."""
        artifacts = _load_fixture("known_bad_02.json")
        scores = score_artifacts(artifacts)
        shift_log = next(s for s in scores if s["name"] == "Shift log")
        assert shift_log["score"] < EVALUATION_SCORE_THRESHOLD

    def test_known_bad_02_failed_verifications_score_zero(self) -> None:
        """All-failed verifications must produce a Verification score of 0."""
        artifacts = _load_fixture("known_bad_02.json")
        scores = score_artifacts(artifacts)
        verification = next(s for s in scores if s["name"] == "Verification")
        assert verification["score"] == 0

    def test_known_bad_02_zero_fixes_discovery_fails(self) -> None:
        """Zero fixes and zero logged issues must produce a Discovery score of 0."""
        artifacts = _load_fixture("known_bad_02.json")
        scores = score_artifacts(artifacts)
        discovery = next(s for s in scores if s["name"] == "Discovery")
        assert discovery["score"] == 0


# ---------------------------------------------------------------------------
# Fixture file existence
# ---------------------------------------------------------------------------


class TestFixtureFilesExist:
    """Ensure all declared fixture files are present on disk."""

    @pytest.mark.parametrize("fixture_name", _KNOWN_GOOD_FIXTURES + _KNOWN_BAD_FIXTURES)
    def test_fixture_file_exists(self, fixture_name: str) -> None:
        path = _FIXTURE_DIR / fixture_name
        assert path.exists(), f"Fixture file missing: {path}"

    @pytest.mark.parametrize("fixture_name", _KNOWN_GOOD_FIXTURES + _KNOWN_BAD_FIXTURES)
    def test_fixture_is_valid_json(self, fixture_name: str) -> None:
        path = _FIXTURE_DIR / fixture_name
        content = path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict), f"Fixture {fixture_name!r} must be a JSON object"
