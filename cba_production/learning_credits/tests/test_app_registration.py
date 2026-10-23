from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase


class CreditAppRegistrationTests(SimpleTestCase):
    def test_lms_startup_registers_handlers(self):
        config = apps.get_app_config("cba_learning_credits")
        with patch.object(config, "apps") as registry, patch(
            "cba_production.learning_credits.events.register_handlers",
        ) as register:
            registry.is_installed.return_value = True
            config.ready()
        register.assert_called_once_with()

    def test_non_lms_startup_does_not_register_handlers(self):
        config = apps.get_app_config("cba_learning_credits")
        with patch.object(config, "apps") as registry, patch(
            "cba_production.learning_credits.events.register_handlers",
        ) as register:
            registry.is_installed.return_value = False
            config.ready()
        register.assert_not_called()
