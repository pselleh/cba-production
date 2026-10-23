from django.apps import AppConfig


class LearningCreditsConfig(AppConfig):
    name = "cba_production.learning_credits"
    label = "cba_learning_credits"
    verbose_name = "CBA Learning Credits"
    default_auto_field = "django.db.models.BigAutoField"
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "cba_learning_credits",
                "regex": r"^cba/learning-credits/",
                "relative_path": "urls",
            },
        },
    }

    def ready(self):
        if self.apps.is_installed("lms.djangoapps.grades"):
            from .events import register_handlers
            register_handlers()

