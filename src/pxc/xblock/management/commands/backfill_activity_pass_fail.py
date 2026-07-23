"""Retroactively apply the pass/fail gating rule to existing PXC LLM-graded
submissions (see each activity's sandbox.js ``recomputeGrade()``/submit
handler for the authoritative logic this mirrors).

Before this rule existed, every submission -- pass or fail -- set
submitted=true and unconditionally published a grade/completion to the LMS.
That meant failing submissions still showed up as 100%/complete, and passing
submissions below a perfect score could end up stuck incomplete if an
earlier attempt's publish had failed. This command recomputes each row's
correct pass/fail status from its raw scores/criteria (never trusting a
stored "passed" -- older rows predate that field) and makes the DB and the
LMS gradebook/completion tracker consistent with it:

  PASS -- force submitted=true, publish the correct score (SCORE_PUBLISHED),
          mark the unit complete (BlockCompletion completion=1.0).
  FAIL -- force submitted=false (unlocked -- the learner can revise and
          resubmit on their own, no staff reset needed), revoke any
          previously-published score (SCORE_PUBLISHED score_deleted=True)
          and completion (BlockCompletion completion=0.0).

Passing thresholds (must match each activity's sandbox.js exactly):
  m1l8-email-prompt-craft:      weighted_total >= 55   (C or above)
  m2l3-meeting-documentation:   y_count >= 2 of 4      (50%)
  m2l5-presentation-builder:    y_count >= 4 of 6      (66.7%)
  m2l6-visual-story:            y_count >= 4 of 6      (66.7%)

Safe to re-run: republish/revoke is attempted for every valid row on every
run, even when the stored JSON already looked correct -- see
fix_m1l8_grading_arithmetic.py's docstring for why (a prior run can patch
the DB but fail to reach the LMS signal, e.g. a bad usage key at the time;
retrying is a harmless no-op when nothing was actually wrong).

The exact effect of SCORE_PUBLISHED(score_deleted=True) depends on your
edx-platform version's grades signal handler -- run with --dry-run first
and spot-check a couple of known learners (one pass, one fail) before
running for real.

Usage (LMS only -- SCORE_PUBLISHED/BlockCompletion are LMS-side concerns):

    python manage.py lms backfill_activity_pass_fail --dry-run
    python manage.py lms backfill_activity_pass_fail
"""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from pxc.xblock.models import FieldEntry


def _recompute_m1l8(grade):
    # type: (dict) -> dict | None
    scores = grade.get("scores") or {}
    points = {1: 50, 2: 75, 3: 100}
    a, b, c = scores.get("a"), scores.get("b"), scores.get("c")
    if a not in points or b not in points or c not in points:
        return None
    weighted = points[a] * 0.5 + points[b] * 0.25 + points[c] * 0.25
    if weighted >= 85:
        letter = "A"
    elif weighted >= 70:
        letter = "B"
    elif weighted >= 55:
        letter = "C"
    else:
        letter = "F"
    return {"weighted_total": weighted, "letter_grade": letter, "passed": weighted >= 55}


def _make_binary_recompute(criteria_keys, passing_y_count, letter_at):
    def recompute(grade):
        # type: (dict) -> dict | None
        criteria = grade.get("criteria") or {}
        if not all(criteria.get(k) in ("Y", "N") for k in criteria_keys):
            return None
        y_count = sum(1 for k in criteria_keys if criteria.get(k) == "Y")
        weighted = round((y_count / float(len(criteria_keys))) * 1000) / 10
        return {
            "y_count": y_count,
            "weighted_total": weighted,
            "letter_grade": letter_at(y_count),
            "passed": y_count >= passing_y_count,
        }

    return recompute


def _letter_out_of_4(y_count):
    if y_count == 4:
        return "A"
    if y_count == 3:
        return "B"
    if y_count == 2:
        return "C"
    return "F"


def _letter_out_of_6(y_count):
    if y_count == 6:
        return "A"
    if y_count == 5:
        return "B"
    if y_count == 4:
        return "C"
    return "F"


ACTIVITY_CONFIGS = {
    "m1l8-email-prompt-craft": {
        "legacy_slugs": ["email-prompt-craft"],
        "recompute": _recompute_m1l8,
    },
    "m2l3-meeting-documentation": {
        "legacy_slugs": [],
        "recompute": _make_binary_recompute(
            [
                "c1_transcript_or_notes",
                "c2_prompt_template_design",
                "c3_five_section_output",
                "c4_action_item_completeness",
            ],
            2,
            _letter_out_of_4,
        ),
    },
    "m2l5-presentation-builder": {
        "legacy_slugs": [],
        "recompute": _make_binary_recompute(
            [
                "c1_slide_count",
                "c2_narrative_structure",
                "c3_technique_usage",
                "c4_prompt_stages",
                "c5_slide_text_quality",
                "c6_topic_validity",
            ],
            4,
            _letter_out_of_6,
        ),
    },
    "m2l6-visual-story": {
        "legacy_slugs": [],
        "recompute": _make_binary_recompute(
            [
                "c1_image_count",
                "c2_prompt_elements",
                "c3_style_anchor",
                "c4_caption_narrative",
                "c5_topic_match",
                "c6_submission_format",
            ],
            4,
            _letter_out_of_6,
        ),
    },
}


class Command(BaseCommand):
    help = (
        "Retroactively apply pass/fail gating (correct grade + completion, "
        "unlock failing submissions) across all 4 PXC LLM-graded activities."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing or publishing/revoking anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            from completion import waffle as completion_waffle
            from completion.models import BlockCompletion
            from lms.djangoapps.grades.signals.signals import SCORE_PUBLISHED
            from opaque_keys import InvalidKeyError
            from opaque_keys.edx.keys import UsageKey
            from xmodule.modulestore.django import modulestore
        except ImportError as e:
            self.stderr.write(
                "Could not import LMS grading/completion internals ({0}) -- this "
                "command must be run as an LMS management command, not CMS.".format(e)
            )
            return

        completion_enabled = completion_waffle.waffle().is_enabled(
            completion_waffle.ENABLE_COMPLETION_TRACKING
        )
        user_model = get_user_model()

        db_patched = 0
        submitted_flag_changed = 0
        republished = 0
        republish_failed = 0
        invalid = 0

        for slug, config in ACTIVITY_CONFIGS.items():
            slugs = [slug] + config["legacy_slugs"]
            rows = FieldEntry.objects.filter(activity_name__in=slugs, key="grade_result")

            for row in rows:
                try:
                    grade = json.loads(row.value)
                except ValueError:
                    self.stderr.write(
                        "Row {0} ({1}): unreadable grade_result JSON, skipping".format(row.pk, slug)
                    )
                    invalid += 1
                    continue

                patch = config["recompute"](grade)
                if patch is None:
                    self.stderr.write(
                        "Row {0} ({1}): grade JSON missing/invalid fields, skipping".format(row.pk, slug)
                    )
                    invalid += 1
                    continue

                passed = patch["passed"]
                needs_db_patch = any(grade.get(k) != v for k, v in patch.items())

                submitted_row, _ = FieldEntry.objects.get_or_create(
                    course_id=row.course_id,
                    activity_name=row.activity_name,
                    activity_id=row.activity_id,
                    user_id=row.user_id,
                    key="submitted",
                    defaults={"value": "false"},
                )
                try:
                    current_submitted = json.loads(submitted_row.value)
                except ValueError:
                    current_submitted = None
                needs_submitted_patch = current_submitted != passed

                if needs_db_patch or needs_submitted_patch:
                    self.stdout.write(
                        "user={0} activity={1} row={2}: passed={3} weighted_total={4} "
                        "(was submitted={5})".format(
                            row.user_id, slug, row.pk, passed, patch.get("weighted_total"), current_submitted
                        )
                    )

                if dry_run:
                    if needs_db_patch:
                        db_patched += 1
                    if needs_submitted_patch:
                        submitted_flag_changed += 1
                    continue

                if needs_db_patch:
                    grade.update(patch)
                    row.value = json.dumps(grade)
                    row.save(update_fields=["value"])
                    db_patched += 1

                if needs_submitted_patch:
                    submitted_row.value = json.dumps(passed)
                    submitted_row.save(update_fields=["value"])
                    submitted_flag_changed += 1

                # Always attempt republish/revoke, even when nothing above
                # needed a DB patch -- a previous run may have patched the DB
                # but failed to reach the LMS (e.g. a since-fixed bad usage
                # key), and resending an already-correct signal is a
                # harmless no-op.
                try:
                    usage_key = UsageKey.from_string(row.activity_id)
                except InvalidKeyError:
                    self.stderr.write(
                        "Row {0} ({1}): invalid usage key {2!r} -- LMS not updated".format(
                            row.pk, slug, row.activity_id
                        )
                    )
                    republish_failed += 1
                    continue
                try:
                    student = user_model.objects.get(pk=row.user_id)
                except user_model.DoesNotExist:
                    self.stderr.write(
                        "Row {0} ({1}): user_id {2!r} not found -- LMS not updated".format(
                            row.pk, slug, row.user_id
                        )
                    )
                    republish_failed += 1
                    continue

                block = modulestore().get_item(usage_key)
                weighted_total = patch.get("weighted_total") or 0.0
                if passed:
                    SCORE_PUBLISHED.send(
                        sender=None,
                        user=student,
                        block=block,
                        raw_earned=weighted_total / 100,
                        raw_possible=1.0,
                        only_if_higher=False,
                        score_deleted=False,
                    )
                    if completion_enabled:
                        BlockCompletion.objects.submit_completion(
                            user=student, block_key=usage_key, completion=1.0
                        )
                else:
                    SCORE_PUBLISHED.send(
                        sender=None,
                        user=student,
                        block=block,
                        raw_earned=0.0,
                        raw_possible=1.0,
                        only_if_higher=False,
                        score_deleted=True,
                    )
                    if completion_enabled:
                        BlockCompletion.objects.submit_completion(
                            user=student, block_key=usage_key, completion=0.0
                        )
                republished += 1

        prefix = "[dry-run] " if dry_run else ""
        if dry_run:
            self.stdout.write(
                "{0}{1} grade row(s) would be patched, {2} submitted-flag change(s), "
                "{3} invalid/skipped".format(prefix, db_patched, submitted_flag_changed, invalid)
            )
        else:
            self.stdout.write(
                "{0}{1} grade row(s) patched, {2} submitted-flag change(s), {3} republished/revoked "
                "to the LMS, {4} republish failures (see stderr), {5} invalid/skipped".format(
                    prefix, db_patched, submitted_flag_changed, republished, republish_failed, invalid
                )
            )
