"""Real row-lock tests; deliberately skipped by the SQLite suite."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from cba_production.learning_credits.awards import award_course_credits
from cba_production.learning_credits.models import (
    CourseCreditAward, CourseCreditPlan, CourseCreditPlanBinding, CreditProcessingRequest,
)
from cba_production.learning_credits.processing import process_credit_request


@skipUnlessDBFeature("has_select_for_update_skip_locked")
class CreditMySQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="concurrent-learner")
        self.plan = CourseCreditPlan.objects.create(
            course_key="course-v1:CBA+LOCK+2027", status="approved",
            instruction_minutes=60, assignments_minutes=0, assessments_minutes=0,
            discussions_minutes=0, other_minutes=0,
            instructional_design_reference="IDP-LOCK", learning_outcomes=["Assess risk."],
            required_block_keys=["block-v1:CBA+LOCK+2027+type@html+block@instruction"],
            approved_by=self.user, approved_at=timezone.now(),
        )
        CourseCreditPlanBinding.objects.create(
            learner=self.user, plan=self.plan, course_key=self.plan.course_key,
            plan_snapshot=self.plan.snapshot,
        )

    def test_two_workers_create_exactly_one_award(self):
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                award, created = award_course_credits(learner=self.user, plan_id=self.plan.pk)
                return award.pk, created
            finally:
                connections.close_all()

        with patch("cba_production.learning_credits.awards.currently_passing", return_value=True), patch(
            "cba_production.learning_credits.awards.missing_required_blocks", return_value=[],
        ), patch("cba_production.learning_credits.awards.collect_activity_evidence", return_value=[]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker) for _ in range(2)]
                results = [future.result(timeout=25) for future in futures]
        self.assertEqual(CourseCreditAward.objects.count(), 1)
        self.assertEqual(len({pk for pk, created in results}), 1)
        self.assertEqual(sum(created for pk, created in results), 1)

    def test_locked_queue_request_is_skipped_by_second_worker(self):
        request = CreditProcessingRequest.objects.create(
            learner=self.user, plan=self.plan, course_key=self.plan.course_key,
            action="check", source_event_id="lock-event",
        )
        acquired, release = Event(), Event()

        def holder():
            close_old_connections()
            try:
                with transaction.atomic():
                    CreditProcessingRequest.objects.select_for_update().get(pk=request.pk)
                    acquired.set()
                    if not release.wait(timeout=15):
                        raise RuntimeError("Lock test timed out.")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(holder)
            try:
                self.assertTrue(acquired.wait(timeout=10))
                self.assertEqual(process_credit_request(request.pk), "skipped")
            finally:
                release.set()
            future.result(timeout=20)
        request.refresh_from_db()
        self.assertEqual(request.attempts, 0)
