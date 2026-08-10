from django.test import SimpleTestCase

from cba_production.registration_forms import CBARegistrationExtensionForm


class CBARegistrationExtensionFormTest(SimpleTestCase):
    """Regression tests for CBA registration extension fields."""

    def test_organization_code_is_optional(self):
        form = CBARegistrationExtensionForm(data={})

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data["organization_code"], "")

    def test_blank_organization_code_is_accepted(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": ""}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(form.cleaned_data["organization_code"], "")

    def test_valid_organization_code_is_accepted(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": "CBA-2026_test.01"}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(
            form.cleaned_data["organization_code"],
            "CBA-2026_test.01",
        )

    def test_organization_code_is_trimmed(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": "  CBA-2026  "}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(
            form.cleaned_data["organization_code"],
            "CBA-2026",
        )

    def test_save_returns_unsaved_enterprise_profile(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": "CBA-2026_test.01"}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())

        profile = form.save(commit=False)

        self.assertEqual(
            profile.organization_code,
            "CBA-2026_test.01",
        )
        self.assertIsNone(profile.user_id)
        self.assertIsNone(profile.pk)

    def test_save_preserves_blank_organization_code(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": ""}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())

        profile = form.save(commit=False)

        self.assertEqual(profile.organization_code, "")
        self.assertIsNone(profile.user_id)
        self.assertIsNone(profile.pk)

    def test_save_rejects_commit_true(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": "CBA-2026"}
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())

        with self.assertRaisesRegex(
            ValueError,
            "requires commit=False",
        ):
            form.save(commit=True)

    def test_invalid_organization_code_is_rejected(self):
        form = CBARegistrationExtensionForm(
            data={"organization_code": "CBA CODE!"}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("organization_code", form.errors)

        self.assertIn(
            (
                "Organization Code may contain only letters, numbers, "
                "periods, hyphens, and underscores."
            ),
            form.errors["organization_code"],
        )
