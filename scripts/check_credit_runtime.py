"""Read-only probe: run through the installed CMS or LMS manage.py shell."""
import inspect
from importlib.metadata import PackageNotFoundError, version

from django.apps import apps
from django.conf import settings
from django.urls import Resolver404, resolve

print("Settings:", settings.SETTINGS_MODULE)
try:
    print("Installed package:", version("cba-production"))
except PackageNotFoundError:
    print("Installed package: missing")
print("Credit app loaded:", any(config.label == "cba_learning_credits" for config in apps.get_app_configs()))
for path in ("/cba/learning-credits/", "/cba/learning-credits/api/"):
    try:
        print("Route:", path, "->", resolve(path).view_name)
    except Resolver404:
        print("Route:", path, "-> not installed")

from xmodule.modulestore.django import modulestore
store = modulestore()
for name in ("get_courses", "get_course", "get_items", "create_course"):
    method = getattr(store, name, None)
    print("Modulestore:", name, inspect.signature(method) if method else "missing")

from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
print("Course roles:", CourseInstructorRole.__name__, CourseStaffRole.__name__)
print("Instructor assignment:", inspect.signature(CourseInstructorRole.add_users))
if settings.SETTINGS_MODULE.startswith("lms."):
    try:
        from lms.djangoapps.courseware.block_render import get_block_for_descriptor
        print("Learner loader:", inspect.signature(get_block_for_descriptor))
    except ImportError:
        print("Learner loader: unavailable in this service")
print("Read-only runtime probe complete; no courses or records were changed.")
