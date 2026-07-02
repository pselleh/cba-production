from tutor import hooks
from . import security

#
# LMS Production Settings
#
hooks.Filters.ENV_PATCHES.add_item((
    "openedx-lms-common-settings",
    """
DEBUG = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"
"""
))

#
# CMS Production Settings
#
hooks.Filters.ENV_PATCHES.add_item((
    "openedx-cms-common-settings",
    """
DEBUG = False
"""
))
