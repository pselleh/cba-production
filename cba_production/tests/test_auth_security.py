import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.test import SimpleTestCase, override_settings

from cba_production.recaptcha.middleware import (
    RecaptchaEnterpriseMiddleware,
)


@override_settings(
    CBA_RECAPTCHA_ENABLED=True,
    CBA_RECAPTCHA_EXPECTED_ACTION="LOGIN",
    CBA_RECAPTCHA_PROTECTED_PATHS=(
        "/api/user/v2/account/login_session/",
        "/account/password",
    ),
    CBA_RECAPTCHA_ACTION_BY_PATH={
        "/api/user/v2/account/login_session/": "LOGIN",
        "/account/password": "PASSWORD_RESET_REQUEST",
    },
)
class RecaptchaActionRoutingTest(SimpleTestCase):
    def _request(self, path, action):
        payload = {
            "recaptcha_token": "test-token",
            "recaptcha_action": action,
        }

        return SimpleNamespace(
            path=path,
            method="POST",
            content_type="application/json",
            body=json.dumps(payload).encode("utf-8"),
            encoding="utf-8",
            META={
                "HTTP_USER_AGENT": "CBA security test",
                "REMOTE_ADDR": "127.0.0.1",
            },
            build_absolute_uri=lambda: (
                "https://learn.centerforbusinessacceleration.com"
                + path
            ),
        )

    @patch(
        "cba_production.recaptcha.middleware.create_assessment"
    )
    def test_login_uses_login_action(self, mock_assessment):
        response = JsonResponse({"ok": True})
        middleware = RecaptchaEnterpriseMiddleware(
            Mock(return_value=response)
        )

        request = self._request(
            "/api/user/v2/account/login_session/",
            "LOGIN",
        )

        result = middleware(request)

        self.assertEqual(result.status_code, 200)

        mock_assessment.assert_called_once()

        self.assertEqual(
            mock_assessment.call_args.kwargs["expected_action"],
            "LOGIN",
        )

    @patch(
        "cba_production.recaptcha.middleware.create_assessment"
    )
    def test_password_reset_uses_password_reset_action(
        self,
        mock_assessment,
    ):
        response = JsonResponse({"ok": True})
        middleware = RecaptchaEnterpriseMiddleware(
            Mock(return_value=response)
        )

        request = self._request(
            "/account/password",
            "PASSWORD_RESET_REQUEST",
        )

        result = middleware(request)

        self.assertEqual(result.status_code, 200)

        mock_assessment.assert_called_once()

        self.assertEqual(
            mock_assessment.call_args.kwargs["expected_action"],
            "PASSWORD_RESET_REQUEST",
        )

    @patch(
        "cba_production.recaptcha.middleware.create_assessment"
    )
    def test_password_reset_rejects_login_action(
        self,
        mock_assessment,
    ):
        middleware = RecaptchaEnterpriseMiddleware(
            Mock(return_value=JsonResponse({"ok": True}))
        )

        request = self._request(
            "/account/password",
            "LOGIN",
        )

        result = middleware(request)

        self.assertEqual(result.status_code, 400)
        mock_assessment.assert_not_called()

        payload = json.loads(result.content)

        self.assertEqual(
            payload["error_code"],
            "recaptcha-action-invalid",
        )


class AuthenticationSecurityPolicyTest(SimpleTestCase):
    """Regression contract for CBA authentication security settings."""

    def test_login_security_policy_source_contract(self):
        from pathlib import Path

        plugin_path = (
            Path(__file__).resolve().parents[1]
            / "plugin.py"
        )

        source = plugin_path.read_text(encoding="utf-8")

        required_settings = (
            "ENABLE_MAX_FAILED_LOGIN_ATTEMPTS = True",
            "MAX_FAILED_LOGIN_ATTEMPTS_ALLOWED = 10",
            "MAX_FAILED_LOGIN_ATTEMPTS_LOCKOUT_PERIOD_SECS = 1800",
            'LOGISTRATION_PER_EMAIL_RATELIMIT_RATE = "10/5m"',
            'LOGISTRATION_RATELIMIT_RATE = "50/5m"',
            "PASSWORD_RESET_TIMEOUT = 900",
            "ENABLE_PASSWORD_RESET_FAILURE_EMAIL = False",
            "ENABLE_AUTHN_REGISTER_HIBP_POLICY = True",
            "ENABLE_AUTHN_RESET_PASSWORD_HIBP_POLICY = True",
            "ENABLE_AUTHN_LOGIN_NUDGE_HIBP_POLICY = True",
            "ENABLE_AUTHN_LOGIN_BLOCK_HIBP_POLICY = True",
        )

        for setting in required_settings:
            with self.subTest(setting=setting):
                self.assertIn(setting, source)

    def test_hibp_settings_are_top_level(self):
        from pathlib import Path

        plugin_path = (
            Path(__file__).resolve().parents[1]
            / "plugin.py"
        )

        source = plugin_path.read_text(encoding="utf-8")

        obsolete_assignments = (
            'FEATURES["ENABLE_AUTHN_REGISTER_HIBP_POLICY"]',
            'FEATURES["ENABLE_AUTHN_RESET_PASSWORD_HIBP_POLICY"]',
            'FEATURES["ENABLE_AUTHN_LOGIN_NUDGE_HIBP_POLICY"]',
            'FEATURES["ENABLE_AUTHN_LOGIN_BLOCK_HIBP_POLICY"]',
        )

        for assignment in obsolete_assignments:
            with self.subTest(assignment=assignment):
                self.assertNotIn(assignment, source)
