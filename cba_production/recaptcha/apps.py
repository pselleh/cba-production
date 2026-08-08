from django.apps import AppConfig


class CbaRecaptchaConfig(AppConfig):
    """
    Open edX Django App Plugin configuration for CBA reCAPTCHA Enterprise.
    """

    name = "cba_production.recaptcha"
    label = "cba_recaptcha"
    verbose_name = "CBA reCAPTCHA Enterprise"

    # String constants are intentionally used here so this module remains
    # safe during the early plugin discovery phase.
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {
                    "relative_path": "settings.common",
                },
                "production": {
                    "relative_path": "settings.common",
                },
                "devstack": {
                    "relative_path": "settings.common",
                },
            },
        },
    }

    def ready(self):
        """
        Apply CBA runtime patches after Django starts.
        """
        from cba_production.registration_patch import (
            apply_registration_patch,
        )

        apply_registration_patch()
