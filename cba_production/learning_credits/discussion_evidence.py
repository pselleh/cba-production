"""Participation evidence from the native SQL forum.

Callers must confirm that the course uses this backend before using
this reader. It does not support an external discussion service.
"""

from html import unescape

from django.utils.html import strip_tags

from .activity_requirements import validate_activity_requirements


def _read_native_posts(*, learner, course_key, topic_id):
    from django.apps import apps

    thread_model = apps.get_model("forum", "CommentThread")
    comment_model = apps.get_model("forum", "Comment")

    posts = thread_model.objects.filter(
        author_id=learner.pk,
        course_id=course_key,
        commentable_id=topic_id,
        visible=True,
    ).order_by("pk").values("id", "body")

    responses = comment_model.objects.filter(
        author_id=learner.pk,
        course_id=course_key,
        visible=True,
        parent__isnull=True,
        comment_thread__course_id=course_key,
        comment_thread__commentable_id=topic_id,
        comment_thread__visible=True,
    ).exclude(
        comment_thread__author_id=learner.pk,
    ).order_by("pk").values("id", "body")

    return list(posts), list(responses)


def _nonempty_ids(rows):
    return [
        row["id"] for row in rows
        if unescape(strip_tags(row["body"] or "")).strip()
    ]


def native_discussion_evidence(*, block, learner, requirement):
    """Read participation for a trusted server-loaded discussion block."""
    key = block.scope_ids.usage_id
    course_key = str(key.course_key)
    validate_activity_requirements(
        [requirement], course_key, [str(key)]
    )
    if requirement["kind"] != "discussion_participation":
        raise ValueError("A discussion participation requirement is required.")
    if learner.pk is None:
        raise ValueError("A saved learner is required.")

    topic_id = getattr(block, "discussion_id", None)
    if not isinstance(topic_id, str) or not topic_id.strip():
        raise ValueError("The block must identify a discussion topic.")

    posts, responses = _read_native_posts(
        learner=learner,
        course_key=course_key,
        topic_id=topic_id,
    )
    post_ids = _nonempty_ids(posts)
    response_ids = _nonempty_ids(responses)

    if (
        len(post_ids) < requirement["minimum_posts"]
        or len(response_ids) < requirement["minimum_responses"]
    ):
        return None

    return {
        "provider": "native_sql_forum",
        "course_key": course_key,
        "block_key": str(key),
        "topic_id": topic_id,
        "post_ids": post_ids,
        "response_ids": response_ids,
        "minimum_posts": requirement["minimum_posts"],
        "minimum_responses": requirement["minimum_responses"],
    }
