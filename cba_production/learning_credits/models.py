"""Approved learning-time plans and completion-based credit records."""

from copy import deepcopy

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .activity_requirements import validate_activity_requirements

from .calculations import (
    ACTIVITY_CATEGORIES,
    CREDIT_POLICY_VERSION,
    calculate_credits,
)


class CourseCreditPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"

    course_key = models.CharField(max_length=255, db_index=True)
    version = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT,
    )
    instruction_minutes = models.PositiveIntegerField(null=True, blank=True)
    assignments_minutes = models.PositiveIntegerField(null=True, blank=True)
    assessments_minutes = models.PositiveIntegerField(null=True, blank=True)
    discussions_minutes = models.PositiveIntegerField(null=True, blank=True)
    other_minutes = models.PositiveIntegerField(null=True, blank=True)
    instructional_design_reference = models.CharField(max_length=1024, blank=True)
    learning_outcomes = models.JSONField(default=list, blank=True)
    required_block_keys = models.JSONField(default=list, blank=True)
    activity_requirements = models.JSONField(default=list, blank=True)
    policy_version = models.CharField(
        max_length=64, default=CREDIT_POLICY_VERSION,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.PROTECT,
        related_name="approved_cba_credit_plans",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_key", "version"],
                name="cba_unique_course_credit_plan",
            ),
        ]
        permissions = [
            ("approve_course_credit_plan", "Can approve course credit plans"),
        ]

    @property
    def activity_minutes(self):
        return {
            category: getattr(self, category + "_minutes")
            for category in ACTIVITY_CATEGORIES
        }

    @property
    def credit_totals(self):
        return calculate_credits(self.activity_minutes)

    @property
    def snapshot(self):
        if self.status != self.Status.APPROVED:
            raise ValidationError("Only approved plans have award snapshots.")
        self.clean()
        return {
            "course_key": self.course_key,
            "version": self.version,
            "policy_version": self.policy_version,
            "activity_minutes": deepcopy(self.activity_minutes),
            "required_block_keys": deepcopy(self.required_block_keys),
            "activity_requirements": deepcopy(self.activity_requirements),
            "instructional_design_reference": self.instructional_design_reference,
            "learning_outcomes": deepcopy(self.learning_outcomes),
            "approved_by_id": self.approved_by_id,
            "approved_at": self.approved_at.isoformat(),
        }

    def clean(self):
        super().clean()
        try:
            totals = self.credit_totals
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if not isinstance(self.learning_outcomes, list) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.learning_outcomes
        ):
            raise ValidationError({
                "learning_outcomes": "Use an array of nonempty outcome strings.",
            })

        if not isinstance(self.required_block_keys, list) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.required_block_keys
        ):
            raise ValidationError({
                "required_block_keys": "Use an array of nonempty block keys.",
            })
        if len(self.required_block_keys) != len(set(self.required_block_keys)):
            raise ValidationError({
                "required_block_keys": "Duplicate required blocks are not allowed.",
            })

        try:
            validate_activity_requirements(
                self.activity_requirements,
                self.course_key,
                self.required_block_keys,
            )
        except ValueError as exc:
            raise ValidationError({
                "activity_requirements": str(exc),
            }) from exc

        if self.status == self.Status.APPROVED:
            errors = {}
            if not self.required_block_keys:
                errors["required_block_keys"] = (
                    "Approval requires explicit completion requirements."
                )
            for value in self.required_block_keys:
                try:
                    key = UsageKey.from_string(value)
                    valid = (
                        str(key) == value
                        and str(key.course_key) == self.course_key
                    )
                except (InvalidKeyError, TypeError, ValueError, AttributeError):
                    valid = False
                if not valid:
                    errors["required_block_keys"] = (
                        "Required blocks must be canonical keys from this course run."
                    )
                    break
            if totals.eligible_minutes is None or totals.eligible_minutes <= 0:
                errors["instruction_minutes"] = (
                    "Approval requires complete activity times and a positive total."
                )
            if not self.instructional_design_reference.strip():
                errors["instructional_design_reference"] = (
                    "Approval requires an instructional design reference."
                )
            if not self.learning_outcomes:
                errors["learning_outcomes"] = "Approval requires learning outcomes."
            if self.approved_by_id is None:
                errors["approved_by"] = "Approval requires an approver."
            if self.approved_at is None:
                errors["approved_at"] = "Approval requires a timestamp."
            if self.policy_version != CREDIT_POLICY_VERSION:
                errors["policy_version"] = "Unsupported credit policy version."
            if errors:
                raise ValidationError(errors)
        elif self.approved_by_id is not None or self.approved_at is not None:
            raise ValidationError("Draft plans cannot contain approval details.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(
            pk=self.pk, status=self.Status.APPROVED,
        ).exists():
            raise ValidationError(
                "Approved plans cannot be edited; create a new version."
            )
        self.full_clean()
        return super().save(*args, **kwargs)


class CourseCreditAward(models.Model):
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cba_credit_awards",
    )
    plan = models.ForeignKey(
        CourseCreditPlan,
        on_delete=models.PROTECT,
        related_name="awards",
    )
    course_key = models.CharField(max_length=255, db_index=True)
    completed_at = models.DateTimeField()
    awarded_at = models.DateTimeField(auto_now_add=True)
    eligible_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    pdu = models.DecimalField(
        max_digits=12, decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    ceu = models.DecimalField(
        max_digits=12, decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    policy_version = models.CharField(max_length=64)
    plan_snapshot = models.JSONField()
    activity_evidence = models.JSONField(default=list, blank=True)
    source_event_id = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "course_key"],
                name="cba_unique_learner_course_credit",
            ),
        ]

    def clean(self):
        super().clean()
        if self.plan_id is None:
            return
        plan = self.plan
        if plan.status != CourseCreditPlan.Status.APPROVED:
            raise ValidationError("Credits require an approved plan.")
        totals = plan.credit_totals
        if (
            self.course_key != plan.course_key
            or self.policy_version != plan.policy_version
            or self.eligible_minutes != totals.eligible_minutes
            or self.pdu != totals.pdu
            or self.ceu != totals.ceu
        ):
            raise ValidationError("Award values must match the approved plan.")
        if self.plan_snapshot != plan.snapshot:
            raise ValidationError("Award snapshot must match the approved plan.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(
                "Credit awards cannot be edited through save()."
            )
        self.full_clean()
        return super().save(*args, **kwargs)
