from tutor import hooks

# LMS production settings
hooks.Filters.ENV_PATCHES.add_item((
    "openedx-lms-common-settings",
    """
DEBUG = False
"""
))

# CMS production settings
hooks.Filters.ENV_PATCHES.add_item((
    "openedx-cms-common-settings",
    """
DEBUG = False
"""
))
