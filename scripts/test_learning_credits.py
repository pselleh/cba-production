"""Run the credit suite without loading live Open edX settings or databases."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from django.conf import settings

settings.configure(
    SECRET_KEY="isolated-credit-tests-only",
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        "cba_production.learning_credits.apps.LearningCreditsConfig",
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField", USE_TZ=True,
)
import django
django.setup()
from django.core.management import call_command
call_command("test", "cba_production.learning_credits.tests", verbosity=2, interactive=False)
