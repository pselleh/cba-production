from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cba_learning_credits", "0002_required_block_keys"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecreditplan",
            name="activity_requirements",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
