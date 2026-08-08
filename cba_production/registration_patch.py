"""
Registration form monkey patches.

Hide the legacy Full Name field when the site is configured
to use First Name and Last Name.
"""

from django.conf import settings


def apply_registration_patch():
    """
    Monkey patch RegistrationFormFactory so it respects
    REGISTRATION_EXTRA_FIELDS["name"] == "hidden".
    """

    from openedx.core.djangoapps.user_authn.views.registration_form import (
        RegistrationFormFactory,
    )

    # Prevent applying the patch multiple times.
    if getattr(RegistrationFormFactory, "_cba_name_patch_applied", False):
        return

    original_add_name_field = RegistrationFormFactory._add_name_field

    def patched_add_name_field(self, form_desc, required=True):
        if settings.REGISTRATION_EXTRA_FIELDS.get("name") == "hidden":
            return

        return original_add_name_field(self, form_desc, required)

    RegistrationFormFactory._add_name_field = patched_add_name_field
    RegistrationFormFactory._cba_name_patch_applied = True
