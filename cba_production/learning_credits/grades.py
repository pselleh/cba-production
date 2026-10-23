"""Read the LMS passing decision for learning-credit eligibility."""


def _load_current_grade(*, learner, course_key):
    from django.apps import apps
    from opaque_keys.edx.keys import CourseKey
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

    key = CourseKey.from_string(course_key)
    model = apps.get_model("grades", "PersistentCourseGrade")

    if not model.objects.filter(
        user_id=learner.pk, course_id=key
    ).exists():
        return None

    return CourseGradeFactory().read(learner, course_key=key)


def currently_passing(*, learner, course_key):
    """Use the current LMS passing decision, not passed_timestamp."""
    grade = _load_current_grade(
        learner=learner, course_key=course_key
    )
    return grade is not None and grade.passed is True
