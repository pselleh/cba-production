import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from opaque_keys import InvalidKeyError

from cba_production.learning_credits.catalog_import import catalog_plan_records
from cba_production.learning_credits.models import CourseCreditPlan


def course_exists(course_key):
    from opaque_keys.edx.keys import CourseKey
    from xmodule.modulestore.django import modulestore
    return modulestore().get_course(CourseKey.from_string(course_key)) is not None


class Command(BaseCommand):
    help = "Import catalog learning-credit plans as drafts; never create courses or approve plans."

    def add_arguments(self, parser):
        parser.add_argument("catalog_file", type=Path)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--update-drafts", action="store_true")
        parser.add_argument("--course-key")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            payload = json.loads(options["catalog_file"].read_text(encoding="utf-8"))
            records = catalog_plan_records(payload)
        except (OSError, ValueError, TypeError, InvalidKeyError) as exc:
            raise CommandError(str(exc)) from exc
        if options.get("course_key"):
            records = [row for row in records if row["course_key"] == options["course_key"]]
            if not records:
                raise CommandError("The selected course does not occur in this package.")
        counts = {"created": 0, "updated": 0, "unchanged": 0, "locked": 0}
        for values in records:
            key = values["course_key"]
            if not course_exists(key):
                raise CommandError(f"Studio course {key} is missing. Import its draft course content first.")
            existing = CourseCreditPlan.objects.select_for_update().filter(
                course_key=key, version=values["version"],
            ).first()
            if existing is not None and existing.status == CourseCreditPlan.Status.APPROVED:
                counts["locked"] += 1
                continue
            if existing is not None and all(getattr(existing, name) == value for name, value in values.items()):
                counts["unchanged"] += 1
                continue
            if existing is not None and not options["update_drafts"]:
                raise CommandError(f"Draft {key} v{values['version']} differs. Review it before using --update-drafts.")
            plan = existing or CourseCreditPlan()
            for name, value in values.items():
                setattr(plan, name, value)
            plan.status = CourseCreditPlan.Status.DRAFT
            try:
                plan.full_clean()
                if not options["validate_only"]:
                    plan.save()
            except ValidationError as exc:
                raise CommandError(f"{key}: {exc}") from exc
            counts["updated" if existing else "created"] += 1
        prefix = "Validated; no writes. " if options["validate_only"] else "Draft credit-plan import complete. "
        self.stdout.write(prefix + " ".join(f"{name}={value}" for name, value in counts.items()))
