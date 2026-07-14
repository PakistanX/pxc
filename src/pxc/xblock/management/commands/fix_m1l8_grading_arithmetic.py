"""One-off fix for m1l8-email-prompt-craft submissions graded before the
sandbox started recomputing weighted_total/letter_grade itself.

The LLM grader was asked to compute weighted_total from its own per-
criterion scores, and that arithmetic was unreliable (e.g. a straight
3/3/3 -- which can only ever total exactly 100 under the rubric's point
map -- was sometimes reported as 98%). The sandbox now recomputes this
deterministically (see samples/m1l8-email-prompt-craft/sandbox.js's
recomputeGrade()), but that only affects *new* submissions. This command
retroactively fixes existing ones: patches the stored grade_result JSON so
it displays correctly, and re-publishes the corrected score to each
affected learner's LMS grade (the wrong number is already recorded there
via SCORE_PUBLISHED, so a DB-only fix would leave the gradebook wrong).

Deliberately a management command, not a schema migration: this is a
one-off administrative fix a human runs and inspects, not something that
should silently re-run as part of every deploy.

Safe to re-run: republish is attempted for every valid row on every run,
even if the stored JSON was already correct (SCORE_PUBLISHED with the same
value is a no-op) -- a prior run that patched the DB but failed to
republish (e.g. a since-fixed bad usage key) gets a real second attempt
instead of being silently skipped forever because "the JSON already looks
right".

Usage (LMS only -- SCORE_PUBLISHED/grade persistence are LMS-side concerns):

    python manage.py lms fix_m1l8_grading_arithmetic --dry-run
    python manage.py lms fix_m1l8_grading_arithmetic
"""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from pxc.xblock.models import FieldEntry

# Current slug, plus the pre-rename slug (see commit 394456e) in case any
# rows are still parked under the old name in this deployment.
SLUGS = ["m1l8-email-prompt-craft", "email-prompt-craft"]
SCORE_POINTS = {1: 50, 2: 75, 3: 100}


def recompute(scores):
    # type: (dict) -> tuple
    """Returns (weighted_total, letter_grade), or None if scores.a/b/c
    aren't each exactly 1, 2, or 3 -- historical rows can have values the
    old (pre-fix) sandbox never validated (e.g. a string "3", or an
    out-of-range hallucinated value), and those must not be silently
    coerced into a plausible-looking but wrong grade."""
    a, b, c = scores.get("a"), scores.get("b"), scores.get("c")
    if a not in SCORE_POINTS or b not in SCORE_POINTS or c not in SCORE_POINTS:
        return None
    weighted = SCORE_POINTS[a] * 0.5 + SCORE_POINTS[b] * 0.25 + SCORE_POINTS[c] * 0.25
    if weighted >= 85:
        letter = "A"
    elif weighted >= 70:
        letter = "B"
    elif weighted >= 55:
        letter = "C"
    else:
        letter = "F"
    return weighted, letter


class Command(BaseCommand):
    help = (
        "Recompute weighted_total/letter_grade for existing "
        "m1l8-email-prompt-craft submissions and re-publish the corrected "
        "score to each learner's LMS grade."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing or publishing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Imported here (not at module scope) so this file can still be
        # collected/loaded even in a context missing the grades app (e.g.
        # accidentally run under CMS) -- but fail loudly up front, before
        # touching any data, rather than partway through the loop.
        try:
            from lms.djangoapps.grades.signals.signals import SCORE_PUBLISHED
            from opaque_keys import InvalidKeyError
            from opaque_keys.edx.keys import UsageKey
            from xmodule.modulestore.django import modulestore
        except ImportError as e:
            self.stderr.write(
                "Could not import LMS grading internals ({0}) -- this command "
                "must be run as an LMS management command, not CMS.".format(e)
            )
            return

        rows = FieldEntry.objects.filter(activity_name__in=SLUGS, key="grade_result")
        user_model = get_user_model()
        db_patched = 0
        republished = 0
        republish_failed = 0
        invalid = 0

        for row in rows:
            try:
                grade = json.loads(row.value)
            except ValueError:
                self.stderr.write("Row {0}: unreadable grade_result JSON, skipping".format(row.pk))
                invalid += 1
                continue

            scores = grade.get("scores")
            if not scores or not all(k in scores for k in ("a", "b", "c")):
                invalid += 1
                continue

            result = recompute(scores)
            if result is None:
                self.stderr.write(
                    "Row {0}: scores {1!r} outside the expected 1-3 range, skipping".format(row.pk, scores)
                )
                invalid += 1
                continue
            new_weighted, new_letter = result

            old_weighted = grade.get("weighted_total")
            old_letter = grade.get("letter_grade")
            needs_db_patch = old_weighted != new_weighted or old_letter != new_letter

            if needs_db_patch:
                self.stdout.write(
                    "user={0} activity={1}: {2}% ({3}) -> {4}% ({5})".format(
                        row.user_id, row.activity_id, old_weighted, old_letter, new_weighted, new_letter
                    )
                )

            if dry_run:
                if needs_db_patch:
                    db_patched += 1
                continue

            if needs_db_patch:
                grade["weighted_total"] = new_weighted
                grade["letter_grade"] = new_letter
                row.value = json.dumps(grade)
                row.save(update_fields=["value"])
                db_patched += 1

            # Always attempt republish, even when the DB value was already
            # correct -- a previous run may have patched the DB but failed
            # to republish, and resending the same (already-correct) score
            # to SCORE_PUBLISHED is a harmless no-op.
            try:
                usage_key = UsageKey.from_string(row.activity_id)
            except InvalidKeyError:
                self.stderr.write(
                    "Row {0}: invalid usage key {1!r} -- grade NOT republished".format(row.pk, row.activity_id)
                )
                republish_failed += 1
                continue
            try:
                student = user_model.objects.get(pk=row.user_id)
            except user_model.DoesNotExist:
                self.stderr.write(
                    "Row {0}: user_id {1!r} not found -- grade NOT republished".format(row.pk, row.user_id)
                )
                republish_failed += 1
                continue

            block = modulestore().get_item(usage_key)
            SCORE_PUBLISHED.send(
                sender=None,
                user=student,
                block=block,
                raw_earned=new_weighted / 100,
                raw_possible=1.0,
                only_if_higher=False,
                score_deleted=False,
            )
            republished += 1

        prefix = "[dry-run] " if dry_run else ""
        if dry_run:
            self.stdout.write("{0}{1} row(s) would be patched, {2} invalid/skipped".format(prefix, db_patched, invalid))
        else:
            self.stdout.write(
                "{0}{1} row(s) DB-patched, {2} republished to the gradebook, "
                "{3} republish failures (see stderr), {4} invalid/skipped".format(
                    prefix, db_patched, republished, republish_failed, invalid
                )
            )
