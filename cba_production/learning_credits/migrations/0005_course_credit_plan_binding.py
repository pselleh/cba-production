from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cba_learning_credits", "0004_award_activity_evidence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseCreditPlanBinding",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("course_key", models.CharField(
                    db_index=True, max_length=255,
                )),
                ("plan_snapshot", models.JSONField()),
                ("source_event_id", models.CharField(
                    blank=True, max_length=255,
                )),
                ("bound_at", models.DateTimeField(auto_now_add=True)),
                ("learner", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cba_credit_plan_bindings",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="learner_bindings",
                    to="cba_learning_credits.coursecreditplan",
                )),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("learner", "course_key"),
                        name="cba_unique_learner_course_plan",
                    ),
                ],
            },
        ),
    ]
