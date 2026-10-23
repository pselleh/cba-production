"""Verify approved activity requirements using LMS evidence."""

from django.core.exceptions import ValidationError
from opaque_keys.edx.keys import UsageKey

from .activity_requirements import validate_activity_requirements
from .assignment_evidence import passing_assignment_evidence
from .discussion_evidence import native_discussion_evidence


def _load_learner_block(*, learner, block_key):
    from lms.djangoapps.courseware import block_render
    from xmodule.modulestore.django import modulestore

    key = UsageKey.from_string(block_key)
    store = modulestore()
    course = store.get_course(key.course_key)
    if course is None:
        raise ValidationError("The required course does not exist.")
    descriptor = store.get_item(key)
    cache = block_render.FieldDataCache.cache_for_block_descendents(
        key.course_key, learner, descriptor, read_only=True,
    )
    block = block_render.get_block_for_descriptor(
        user=learner,
        request=None,
        block=descriptor,
        field_data_cache=cache,
        course_key=key.course_key,
        disable_staff_debug_info=True,
        course=course,
    )
    if block is None:
        raise ValidationError("The required activity could not be loaded.")
    return block


def _native_forum_available(course_key):
    from django.apps import apps
    from forum.backend import get_backend, MySQLBackend

    configuration = apps.get_model(
        "discussions", "DiscussionsConfiguration"
    )
    if not configuration.objects.filter(
        context_key=course_key,
        enabled=True,
        provider_type="openedx",
    ).exists():
        return False
    return isinstance(get_backend(course_key)(), MySQLBackend)


def collect_activity_evidence(*, learner, plan):
    rules = plan.activity_requirements
    try:
        validate_activity_requirements(
            rules, plan.course_key, plan.required_block_keys,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if plan.activity_minutes["other"] != 0:
        raise ValidationError(
            "Other activities require an additional evidence verifier."
        )

    categories = {rule["category"] for rule in rules}
    for category in ("assignments", "discussions"):
        if plan.activity_minutes[category] != 0 and category not in categories:
            raise ValidationError(
                "Missing approved evidence requirements for " + category + "."
            )

    covered = {rule["block_key"] for rule in rules}
    for value in plan.required_block_keys:
        key = UsageKey.from_string(value)
        if (
            key.block_type in {"openassessment", "discussion"}
            and value not in covered
        ):
            raise ValidationError(
                "Missing evidence requirement for required activity: " + value
            )

    evidence = []
    for rule in rules:
        if (
            rule["kind"] == "discussion_participation"
            and not _native_forum_available(plan.course_key)
        ):
            raise ValidationError(
                "This discussion backend is not supported by the evidence reader."
            )

        block = _load_learner_block(
            learner=learner, block_key=rule["block_key"],
        )
        if (
            str(block.scope_ids.usage_id) != rule["block_key"]
            or str(block.scope_ids.user_id) != str(learner.pk)
        ):
            raise ValidationError(
                "The loaded activity is not bound to the expected learner."
            )

        try:
            if rule["kind"] == "ora_score":
                result = passing_assignment_evidence(
                    block=block,
                    learner=learner,
                    minimum_fraction=rule["minimum_fraction"],
                )
            else:
                result = native_discussion_evidence(
                    block=block,
                    learner=learner,
                    requirement=rule,
                )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if result is None:
            raise ValidationError(
                "Activity evidence does not satisfy its approved requirement: "
                + rule["block_key"]
            )
        evidence.append(result)

    return evidence
