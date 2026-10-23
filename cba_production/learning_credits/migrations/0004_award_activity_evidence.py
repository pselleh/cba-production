from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cba_learning_credits", "0003_activity_requirements"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecreditaward",
            name="activity_evidence",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
