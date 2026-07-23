"""Tests for the recompute() helpers in the backfill_activity_pass_fail
management command -- the pure pass/fail arithmetic, not the DB/LMS side
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


def _configs():
    from pxc.xblock.management.commands.backfill_activity_pass_fail import ACTIVITY_CONFIGS

    return ACTIVITY_CONFIGS


def test_m1l8_perfect_score_passes() -> None:
    recompute = _configs()["m1l8-email-prompt-craft"]["recompute"]
    patch = recompute({"scores": {"a": 3, "b": 3, "c": 3}})
    assert patch == {"weighted_total": 100, "letter_grade": "A", "passed": True}


def test_m1l8_exactly_at_threshold_passes() -> None:
    # a=2(75,*0.5=37.5) b=2(75,*0.25=18.75) c=2(75,*0.25=18.75) = 75 -> B, passes
    recompute = _configs()["m1l8-email-prompt-craft"]["recompute"]
    patch = recompute({"scores": {"a": 2, "b": 2, "c": 2}})
    assert patch["passed"] is True
    assert patch["letter_grade"] == "B"


def test_m1l8_all_ones_fails() -> None:
    # 1/1/1 -> 50pts each -> weighted 50, below the 55 threshold -> F, fails.
    recompute = _configs()["m1l8-email-prompt-craft"]["recompute"]
    patch = recompute({"scores": {"a": 1, "b": 1, "c": 1}})
    assert patch == {"weighted_total": 50, "letter_grade": "F", "passed": False}


def test_m1l8_invalid_scores_returns_none() -> None:
    recompute = _configs()["m1l8-email-prompt-craft"]["recompute"]
    assert recompute({"scores": {"a": 0, "b": 3, "c": 3}}) is None
    assert recompute({"scores": {"a": "3", "b": 3, "c": 3}}) is None
    assert recompute({"scores": {"a": 3, "b": 3}}) is None


def test_m2l3_two_of_four_passes() -> None:
    recompute = _configs()["m2l3-meeting-documentation"]["recompute"]
    patch = recompute(
        {
            "criteria": {
                "c1_transcript_or_notes": "Y",
                "c2_prompt_template_design": "Y",
                "c3_five_section_output": "N",
                "c4_action_item_completeness": "N",
            }
        }
    )
    assert patch == {"y_count": 2, "weighted_total": 50, "letter_grade": "C", "passed": True}


def test_m2l3_one_of_four_fails() -> None:
    recompute = _configs()["m2l3-meeting-documentation"]["recompute"]
    patch = recompute(
        {
            "criteria": {
                "c1_transcript_or_notes": "Y",
                "c2_prompt_template_design": "N",
                "c3_five_section_output": "N",
                "c4_action_item_completeness": "N",
            }
        }
    )
    assert patch == {"y_count": 1, "weighted_total": 25, "letter_grade": "F", "passed": False}


def test_m2l3_missing_criterion_returns_none() -> None:
    recompute = _configs()["m2l3-meeting-documentation"]["recompute"]
    assert recompute({"criteria": {"c1_transcript_or_notes": "Y"}}) is None


def test_m2l5_four_of_six_passes() -> None:
    recompute = _configs()["m2l5-presentation-builder"]["recompute"]
    patch = recompute(
        {
            "criteria": {
                "c1_slide_count": "Y",
                "c2_narrative_structure": "Y",
                "c3_technique_usage": "Y",
                "c4_prompt_stages": "Y",
                "c5_slide_text_quality": "N",
                "c6_topic_validity": "N",
            }
        }
    )
    assert patch == {"y_count": 4, "weighted_total": 66.7, "letter_grade": "C", "passed": True}


def test_m2l5_three_of_six_fails() -> None:
    recompute = _configs()["m2l5-presentation-builder"]["recompute"]
    patch = recompute(
        {
            "criteria": {
                "c1_slide_count": "Y",
                "c2_narrative_structure": "Y",
                "c3_technique_usage": "Y",
                "c4_prompt_stages": "N",
                "c5_slide_text_quality": "N",
                "c6_topic_validity": "N",
            }
        }
    )
    assert patch["passed"] is False
    assert patch["letter_grade"] == "F"


def test_m2l6_six_of_six_passes() -> None:
    recompute = _configs()["m2l6-visual-story"]["recompute"]
    patch = recompute(
        {
            "criteria": {
                "c1_image_count": "Y",
                "c2_prompt_elements": "Y",
                "c3_style_anchor": "Y",
                "c4_caption_narrative": "Y",
                "c5_topic_match": "Y",
                "c6_submission_format": "Y",
            }
        }
    )
    assert patch == {"y_count": 6, "weighted_total": 100, "letter_grade": "A", "passed": True}
