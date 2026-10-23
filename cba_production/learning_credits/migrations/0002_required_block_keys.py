from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cba_learning_credits", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecreditplan",
            name="required_block_keys",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
