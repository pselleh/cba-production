from tutor import hooks

from . import security

hooks.Filters.MOUNTED_DIRECTORIES.add_item(
    (
        "openedx",
        r"^cba-production$",
    )
)

CBA_COOKIE_DOMAIN = ".centerforbusinessacceleration.com"

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        f"""
DEBUG = False

SESSION_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"
CSRF_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(
    list(globals().get("CSRF_TRUSTED_ORIGINS", [])) + [
        "https://learn.centerforbusinessacceleration.com",
        "https://studio.centerforbusinessacceleration.com",
        "https://apps.learn.centerforbusinessacceleration.com",
        "https://centerforbusinessacceleration.com",
        "https://www.centerforbusinessacceleration.com",
    ]
))

CORS_ORIGIN_WHITELIST = list(dict.fromkeys(
    list(globals().get("CORS_ORIGIN_WHITELIST", [])) + [
        "https://apps.learn.centerforbusinessacceleration.com",
        "https://centerforbusinessacceleration.com",
        "https://www.centerforbusinessacceleration.com",
    ]
))

LOGIN_REDIRECT_WHITELIST = list(dict.fromkeys(
    list(globals().get("LOGIN_REDIRECT_WHITELIST", [])) + [
        "apps.learn.centerforbusinessacceleration.com",
        "centerforbusinessacceleration.com",
        "www.centerforbusinessacceleration.com",
    ]
))

RECAPTCHA_PROJECT_ID = "{{{{ CBA_RECAPTCHA_PROJECT_ID }}}}"
RECAPTCHA_PRIVATE_KEY = "{{{{ CBA_RECAPTCHA_API_KEY }}}}"

RECAPTCHA_SITE_KEYS = {{
    "web": "{{{{ CBA_RECAPTCHA_WEB_SITE_KEY }}}}",
    "ios": None,
    "android": None,
}}

INSTALLED_APPS = list(globals().get("INSTALLED_APPS", []))
if "cba_production.recaptcha" not in INSTALLED_APPS:
    INSTALLED_APPS.append("cba_production.recaptcha")

MIDDLEWARE = list(globals().get("MIDDLEWARE", []))
if (
    "cba_production.recaptcha.middleware.RecaptchaEnterpriseMiddleware"
    not in MIDDLEWARE
):
    MIDDLEWARE.insert(
        0,
        "cba_production.recaptcha.middleware.RecaptchaEnterpriseMiddleware",
    )

CBA_RECAPTCHA_ENABLED = {{{{ CBA_RECAPTCHA_ENABLED }}}}
CBA_RECAPTCHA_SCORE_THRESHOLD = float(
    "{{{{ CBA_RECAPTCHA_SCORE_THRESHOLD }}}}"
)
CBA_RECAPTCHA_EXPECTED_ACTION = (
    "{{{{ CBA_RECAPTCHA_EXPECTED_ACTION }}}}"
)
CBA_RECAPTCHA_HTTP_TIMEOUT = float(
    "{{{{ CBA_RECAPTCHA_HTTP_TIMEOUT }}}}"
)
CBA_RECAPTCHA_FAIL_CLOSED = {{{{ CBA_RECAPTCHA_FAIL_CLOSED }}}}

CBA_RECAPTCHA_PROTECTED_PATHS = (
    "/login_ajax",
    "/login_ajax/",
    "/api/user/v1/account/login",
    "/api/user/v1/account/login/",
    "/api/user/v2/account/login_session",
    "/api/user/v2/account/login_session/",
)
""",
    )
)


hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-cms-common-settings",
        f"""
DEBUG = False

SESSION_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"
CSRF_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
""",
    )
)
