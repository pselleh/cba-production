"""Create private course shells and draft credit plans; never publish lessons."""
import inspect
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from cba_production.learning_credits.catalog_import import catalog_plan_records
from cba_production.learning_credits.models import CourseCreditPlan


def native_environment():
    from common.djangoapps.student.roles import CourseInstructorRole
    from xmodule.course_block import CourseBlock
    from xmodule.modulestore.django import modulestore
    return modulestore(), CourseBlock.fields, CourseInstructorRole


class Command(BaseCommand):
    help = "Validate or create private Studio course shells and draft credit plans. Catalog JSON does not contain lesson content."

    def add_arguments(self, parser):
        parser.add_argument("catalog_file", type=Path)
        parser.add_argument("--author", required=True)
        selected = parser.add_mutually_exclusive_group(required=True)
        selected.add_argument("--course-key")
        selected.add_argument("--all-courses", action="store_true")
        parser.add_argument("--apply", action="store_true", help="Create missing private shells. Without this flag, validate only.")

    def handle(self, *args, **options):
        try:
            payload = json.loads(options["catalog_file"].read_text(encoding="utf-8"))
            mapped = catalog_plan_records(payload)
        except (OSError, ValueError, TypeError, InvalidKeyError) as exc:
            raise CommandError(str(exc)) from exc
        records = payload.get("microcourses") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise CommandError("A catalog microcourses array is required to create course shells.")
        by_key = {row["course_key"]: row for row in records}
        if options.get("course_key"):
            mapped = [row for row in mapped if row["course_key"] == options["course_key"]]
            if not mapped:
                raise CommandError("The selected course is not in this package.")
        users = get_user_model()
        try:
            author = users.objects.get(**{users.USERNAME_FIELD: options["author"]})
        except users.DoesNotExist as exc:
            raise CommandError("The author account does not exist.") from exc
        if not author.is_active or not (author.is_staff or author.is_superuser):
            raise CommandError("Course shell creation requires an active staff author.")
        store, native_fields, instructor_role = native_environment()
        if not {"display_name", "catalog_visibility", "invitation_only"} <= set(native_fields):
            raise CommandError("Installed course fields cannot guarantee private course shells. No courses were created.")
        prepared = []
        for values in mapped:
            key = CourseKey.from_string(values["course_key"])
            title = by_key[str(key)].get("title")
            if not isinstance(title, str) or not title.strip() or key.deprecated:
                raise CommandError("Each course needs a title and a canonical course-v1 key.")
            fields = {"display_name": title.strip(), "catalog_visibility": "none", "invitation_only": True}
            arguments = {"org": key.org, "course": key.course, "run": key.run, "fields": fields, "user_id": author.pk}
            try:
                inspect.signature(store.create_course).bind(**arguments)
                inspect.signature(instructor_role(key).add_users).bind(author)
            except TypeError as exc:
                raise CommandError("Installed course creation API differs; no courses were created: " + str(exc)) from exc
            # Validate draft field types before the first MongoDB write.
            candidate = CourseCreditPlan(**values)
            candidate.full_clean(validate_unique=False, validate_constraints=False)
            prepared.append((key, arguments, values))

        if not options["apply"]:
            for key, arguments, values in prepared:
                self.stdout.write(f"VALIDATED {key}: private shell, draft credit plan v{values['version']}")
            self.stdout.write(f"Validated {len(prepared)} course(s); no writes. Lesson content is not included in catalog JSON.")
            return

        created = skipped = plans_created = 0
        for key, arguments, values in prepared:
            if store.get_course(key) is None:
                self.stdout.write("Creating private course shell: " + str(key))
                store.create_course(**arguments)
                created += 1
                instructor_role(key).add_users(author)
            else:
                skipped += 1
            plan, was_created = CourseCreditPlan.objects.get_or_create(
                course_key=str(key), version=values["version"],
                defaults={name: value for name, value in values.items() if name not in {"course_key", "version"}},
            )
            plans_created += int(was_created)
        self.stdout.write(f"Private shells created={created} existing_unchanged={skipped} draft_plans_created={plans_created}")
        self.stdout.write("No lessons were imported or published. Review course content and credit plans before release.")
