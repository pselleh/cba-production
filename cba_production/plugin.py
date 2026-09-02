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
    "/account/password",
    "/account/password/",
    "/api/user/v2/account/registration/",
)

CBA_RECAPTCHA_ACTION_BY_PATH = {{
    "/login_ajax": "LOGIN",
    "/login_ajax/": "LOGIN",
    "/api/user/v1/account/login": "LOGIN",
    "/api/user/v1/account/login/": "LOGIN",
    "/api/user/v2/account/login_session": "LOGIN",
    "/api/user/v2/account/login_session/": "LOGIN",
    "/account/password": "PASSWORD_RESET_REQUEST",
    "/account/password/": "PASSWORD_RESET_REQUEST",
    "/api/user/v2/account/registration/": "REGISTER",
}}
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

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-production-settings",
        """
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "common.djangoapps.util.password_policy_validators."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 15,
        },
    },
    {
        "NAME": (
            "common.djangoapps.util.password_policy_validators."
            "MaximumLengthValidator"
        ),
        "OPTIONS": {
            "max_length": 75,
        },
    },
]
ENABLE_DYNAMIC_REGISTRATION_FIELDS = True
FEATURES["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True

# Interactive registration field validation.
#
# Open edX upstream defaults REGISTRATION_VALIDATION_RATELIMIT
# to a very restrictive multi-day limit. CBA protects actual
# account creation separately with reCAPTCHA Enterprise, so
# field validation retains rate limiting without interfering
# with legitimate registration flows or shared NAT addresses.
REGISTRATION_VALIDATION_RATELIMIT = "60/minute"

# CBA authentication abuse controls.
ENABLE_MAX_FAILED_LOGIN_ATTEMPTS = True
MAX_FAILED_LOGIN_ATTEMPTS_ALLOWED = 10
MAX_FAILED_LOGIN_ATTEMPTS_LOCKOUT_PERIOD_SECS = 1800

# Layered login throttling using Open edX native rate limiters.
#
# Per-account throttling limits credential guessing against a
# specific learner account. Per-IP throttling limits distributed
# attempts originating from the same client/network.
LOGISTRATION_PER_EMAIL_RATELIMIT_RATE = "10/5m"
LOGISTRATION_RATELIMIT_RATE = "50/5m"

# Password-reset links are intentionally short-lived.
PASSWORD_RESET_TIMEOUT = 900

# Do not disclose password-reset failure/account state by email.
ENABLE_PASSWORD_RESET_FAILURE_EMAIL = False

# CBA compromised-password policy.
ENABLE_AUTHN_REGISTER_HIBP_POLICY = True
ENABLE_AUTHN_RESET_PASSWORD_HIBP_POLICY = True
ENABLE_AUTHN_LOGIN_NUDGE_HIBP_POLICY = True

# Block login when the submitted password is known to be compromised.
ENABLE_AUTHN_LOGIN_BLOCK_HIBP_POLICY = True

MFE_CONFIG["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True

REGISTRATION_EXTENSION_FORM = (
    "cba_production.registration_forms.CBARegistrationExtensionForm"
)

REGISTRATION_EXTRA_FIELDS["first_name"] = "required"
REGISTRATION_EXTRA_FIELDS["last_name"] = "required"
REGISTRATION_EXTRA_FIELDS["name"] = "hidden"
REGISTRATION_EXTRA_FIELDS["country"] = "optional"
REGISTRATION_EXTRA_FIELDS["honor_code"] = "hidden"
REGISTRATION_EXTRA_FIELDS["terms_of_service"] = "required"
MFE_CONFIG["TOS_LINK"] = 'https://centerforbusinessacceleration.com/contact/'
MFE_CONFIG["PASSWORD_RESET_SUPPORT_LINK"] = 'https://centerforbusinessacceleration.com/contact/'
MFE_CONFIG["LOGIN_ISSUE_SUPPORT_LINK"] = 'https://centerforbusinessacceleration.com/contact/'

# CBA ACE/Django email template overrides.
_CBA_TEMPLATE_DIR = "/mnt/cba-production/cba_production/templates"
for _template_engine in TEMPLATES:
    if (
        _template_engine.get("BACKEND")
        == "django.template.backends.django.DjangoTemplates"
        and _CBA_TEMPLATE_DIR not in _template_engine["DIRS"]
    ):
        _template_engine["DIRS"].insert(0, _CBA_TEMPLATE_DIR)
""",
    )
)
