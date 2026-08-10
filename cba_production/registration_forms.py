"""
CBA extensions to the Open edX registration form.

These fields are exposed through REGISTRATION_EXTENSION_FORM so that the
LMS registration metadata remains authoritative for frontend clients.
"""

import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from orgcode_enterprise.models import EnterpriseLearnerProfile


ORGANIZATION_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")


class CBARegistrationExtensionForm(forms.Form):
    """
    Additional fields required by CBA during account registration.
    """

    organization_code = forms.CharField(
        required=False,
        min_length=2,
        max_length=64,
        label=_("Organization Code"),
        help_text=_(
            "Enter the Organization Code provided by your organization."
        ),
        error_messages={
            "required": _("Enter your Organization Code."),
            "min_length": _("Organization Code is too short."),
            "max_length": _("Organization Code is too long."),
        },
    )

    def clean_organization_code(self):
        """
        Normalize and validate the organization code server-side.
        """
        value = self.cleaned_data.get("organization_code", "").strip()

        if not value:
            return ""

        if not ORGANIZATION_CODE_PATTERN.fullmatch(value):
            raise ValidationError(
                _(
                    "Organization Code may contain only letters, numbers, "
                    "periods, hyphens, and underscores."
                )
            )

        return value

    def save(self, commit=False):
        """
        Build the enterprise profile for the newly registered user.

        Open edX calls registration extension forms with commit=False,
        assigns the newly created user, and then saves the returned model.
        """
        if commit:
            raise ValueError(
                "CBARegistrationExtensionForm requires commit=False"
            )

        return EnterpriseLearnerProfile(
            organization_code=self.cleaned_data.get(
                "organization_code",
                "",
            )
        )
