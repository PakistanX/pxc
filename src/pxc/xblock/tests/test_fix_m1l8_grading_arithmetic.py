"""Tests for the recompute() helper in the fix_m1l8_grading_arithmetic
management command -- the pure arithmetic, not the DB/SCORE_PUBLISHED side
effects (those need a real LMS environment, see the command's docstring)."""

import pytest

try:
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            INSTALLED_APPS=["pxc.xblock"],
            DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        )
        django.setup()

    _DJANGO_AVAILABLE = True
except ImportError:
    _DJANGO_AVAILABLE = False


pytestmark = pytest.mark.skipif(not _DJANGO_AVAILABLE, reason="Django not available")


def _recompute(scores):
    from pxc.xblock.management.commands.fix_m1l8_grading_arithmetic import recompute

    return recompute(scores)


def test_perfect_score_is_exactly_100_not_98() -> None:
    # The exact bug report: the LLM grader reported 98% for a straight 3/3/3,
    # which the rubric's point map (3->100 each, weighted 0.5/0.25/0.25) can
    # never actually produce.
    weighted, letter = _recompute({"a": 3, "b": 3, "c": 3})
    assert weighted == 100
    assert letter == "A"


def test_all_ones_is_50_percent_f() -> None:
    # 1/1/1 -> 50pts each -> weighted 50, below the 55 C threshold -> F.
    weighted, letter = _recompute({"a": 1, "b": 1, "c": 1})
    assert weighted == 50
    assert letter == "F"


def test_mixed_scores() -> None:
    # a=3 (100pts, *0.5=50), b=2 (75pts, *0.25=18.75), c=1 (50pts, *0.25=12.5)
    weighted, letter = _recompute({"a": 3, "b": 2, "c": 1})
    assert weighted == 81.25
    assert letter == "B"


def test_out_of_range_score_returns_none_not_a_silent_default() -> None:
    # A pre-fix row (or a hallucinated grader response) with a score outside
    # 1-3 must be rejected, not silently treated as if it were a 1.
    assert _recompute({"a": 0, "b": 3, "c": 3}) is None


def test_string_typed_score_returns_none_not_a_silent_default() -> None:
    # Pre-fix sandbox.js never validated that scores.a/b/c were numbers, so
    # historical rows can have e.g. "3" (string) instead of 3 (int) -- must
    # not silently fall back to a wrong default.
    assert _recompute({"a": "3", "b": 3, "c": 3}) is None


def test_missing_score_key_returns_none() -> None:
    assert _recompute({"a": 3, "b": 3}) is None
