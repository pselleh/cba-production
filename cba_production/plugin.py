from tutor import hooks
from . import security

CBA_COOKIE_DOMAIN = ".centerforbusinessacceleration.com"

#
# LMS Production Settings
#
hooks.Filters.ENV_PATCHES.add_item((
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
"""
))

#
# CMS Production Settings
#
hooks.Filters.ENV_PATCHES.add_item((
    "openedx-cms-common-settings",
    f"""
DEBUG = False

SESSION_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"
CSRF_COOKIE_DOMAIN = "{CBA_COOKIE_DOMAIN}"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
"""
))
