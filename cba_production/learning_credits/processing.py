"""Process durable credit requests with transactional retries."""

import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from .awards import award_course_credits
from .bindings import bind_credit_plan, _has_active_enrollment
from .models import CreditProcessingRequest


logger = logging.getLogger(__name__)


def process_credit_request(request_id):
    with transaction.atomic():
        queryset = CreditProcessingRequest.objects
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()

        request = queryset.filter(pk=request_id).first()
        if request is None:
            return "skipped"
        if (
            request.status != CreditProcessingRequest.Status.PENDING
            or request.next_attempt_at > timezone.now()
        ):
            return "skipped"

        request.attempts += 1
        learner = request.learner
        plan = request.plan

        if (
            request.action not in CreditProcessingRequest.Action.values
            or request.course_key != plan.course_key
        ):
            request.status = CreditProcessingRequest.Status.FAILED
            request.last_error = "Invalid request action or course-plan mismatch."
            request.processed_at = timezone.now()
            request.save()
            return "failed"

        try:
            # Keep database errors inside a savepoint so retry state can
            # still be saved by the outer transaction.
            with transaction.atomic():
                if not _has_active_enrollment(
                    learner=learner, course_key=request.course_key,
                ):
                    raise ValidationError(
                        "Active enrollment is required for automatic processing."
                    )
                if request.action == CreditProcessingRequest.Action.BIND:
                    bind_credit_plan(
                        learner=learner,
                        plan_id=request.plan_id,
                        source_event_id=request.source_event_id,
                    )

            # A failed award check must not roll back a successful binding.
            with transaction.atomic():
                award_course_credits(
                    learner=learner,
                    plan_id=request.plan_id,
                    source_event_id=request.source_event_id,
                )

        except ValidationError as exc:
            request.status = CreditProcessingRequest.Status.PENDING
            request.last_error = "Eligibility: " + str(exc)[:2000]
            request.next_attempt_at = timezone.now() + timedelta(minutes=15)
            request.processed_at = None

        except Exception as exc:
            logger.exception(
                "Credit processing failed for request %s", request.pk,
            )
            delay = min(3600, 60 * 2 ** min(request.attempts - 1, 6))
            request.status = CreditProcessingRequest.Status.PENDING
            request.last_error = "Technical failure: " + type(exc).__name__
            request.next_attempt_at = timezone.now() + timedelta(seconds=delay)
            request.processed_at = None

        else:
            request.status = CreditProcessingRequest.Status.DONE
            request.last_error = ""
            request.processed_at = timezone.now()

        request.save()
        return request.status


def process_pending_requests(*, limit=100):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Limit must be an integer between 1 and 1000.")

    ids = list(
        CreditProcessingRequest.objects.filter(
            status=CreditProcessingRequest.Status.PENDING,
            next_attempt_at__lte=timezone.now(),
        ).order_by(
            "next_attempt_at", "pk",
        ).values_list("pk", flat=True)[:limit]
    )
    counts = {"done": 0, "pending": 0, "failed": 0, "skipped": 0}
    for request_id in ids:
        counts[process_credit_request(request_id)] += 1
    return counts
