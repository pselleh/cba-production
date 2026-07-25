from tutor import hooks

# =============================
# CONFIG DEFAULTS
# =============================
hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("SECURITY_ENABLE_HSTS", True),
        ("SECURITY_ENABLE_HSTS_PRELOAD", False),

        ("CBA_RECAPTCHA_PROJECT_ID", ""),
        ("CBA_RECAPTCHA_API_KEY", ""),
        ("CBA_RECAPTCHA_WEB_SITE_KEY", ""),
    ]
)

# =============================
# CADDY PATCHES (SAFE ONLY)
# =============================
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
