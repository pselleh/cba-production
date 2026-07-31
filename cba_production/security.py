from tutor import hooks


hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("SECURITY_ENABLE_HSTS", True),
        ("SECURITY_ENABLE_HSTS_PRELOAD", False),

        ("CBA_RECAPTCHA_ENABLED", True),
        ("CBA_RECAPTCHA_PROJECT_ID", ""),
        ("CBA_RECAPTCHA_API_KEY", ""),
        ("CBA_RECAPTCHA_WEB_SITE_KEY", ""),
        ("CBA_RECAPTCHA_SCORE_THRESHOLD", 0.5),
        ("CBA_RECAPTCHA_EXPECTED_ACTION", "LOGIN"),
        ("CBA_RECAPTCHA_HTTP_TIMEOUT", 5.0),
        ("CBA_RECAPTCHA_FAIL_CLOSED", True),
    ]
)


hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "caddyfile-global",
            """
    admin off
""",
        ),
    ]
)
