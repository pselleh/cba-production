from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("cba_learning_credits", "0005_course_credit_plan_binding"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CreditProcessingRequest",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("course_key", models.CharField(max_length=255)),
                ("action", models.CharField(
                    max_length=16,
                    choices=[("bind", "Bind plan"), ("check", "Check award")],
                )),
                ("status", models.CharField(
                    max_length=16, default="pending", db_index=True,
                    choices=[
                        ("pending", "Pending"),
                        ("done", "Done"),
                        ("failed", "Failed"),
                    ],
                )),
                ("source_event_id", models.CharField(max_length=255)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("next_attempt_at", models.DateTimeField(
                    db_index=True, default=django.utils.timezone.now,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("learner", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cba_credit_processing_requests",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="processing_requests",
                    to="cba_learning_credits.coursecreditplan",
                )),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "source_event_id", "action",
                            "learner", "course_key",
                        ),
                        name="cba_unique_credit_event_request",
                    ),
                ],
            },
        ),
    ]
