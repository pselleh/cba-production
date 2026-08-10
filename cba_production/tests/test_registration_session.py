from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.test import SimpleTestCase, override_settings

from cba_production.recaptcha.middleware import (
    RecaptchaEnterpriseMiddleware,
)


@override_settings(
    SHOW_ACTIVATE_CTA_POPUP_COOKIE_NAME="show-account-activation-popup",
    SESSION_COOKIE_DOMAIN=".centerforbusinessacceleration.com",
)
class RegistrationVerificationBoundaryTest(SimpleTestCase):
    def _request(
        self,
        *,
        path="/api/user/v1/account/registration/",
        method="POST",
        authenticated=True,
        active=False,
    ):
        return SimpleNamespace(
            path=path,
            method=method,
            user=SimpleNamespace(
                id=123,
                is_authenticated=authenticated,
                is_active=active,
            ),
        )

    @patch(
        "cba_production.recaptcha.middleware."
        "mark_user_change_as_expected"
    )
    @patch(
        "cba_production.recaptcha.middleware.delete_logged_in_cookies"
    )
    @patch("cba_production.recaptcha.middleware.logout")
    def test_successful_inactive_registration_is_logged_out(
        self,
        mock_logout,
        mock_delete_logged_in_cookies,
        mock_mark_expected,
    ):
        request = self._request()
        response = JsonResponse(
            {"authenticated_user": {"user_id": 123}},
            status=200,
        )
        response.set_cookie(
            "show-account-activation-popup",
            True,
            domain=".centerforbusinessacceleration.com",
            path="/",
        )

        result = (
            RecaptchaEnterpriseMiddleware
            ._enforce_registration_verification_boundary(
                request,
                response,
            )
        )

        self.assertIs(result, response)
        mock_logout.assert_called_once_with(request)
        mock_delete_logged_in_cookies.assert_called_once_with(response)
        mock_mark_expected.assert_called_once_with(None)

        activation_cookie = response.cookies[
            "show-account-activation-popup"
        ]
        self.assertEqual(activation_cookie["max-age"], 0)

    @patch("cba_production.recaptcha.middleware.logout")
    def test_active_registration_user_is_not_logged_out(
        self,
        mock_logout,
    ):
        request = self._request(active=True)
        response = JsonResponse({}, status=200)

        RecaptchaEnterpriseMiddleware \
            ._enforce_registration_verification_boundary(
                request,
                response,
            )

        mock_logout.assert_not_called()

    @patch("cba_production.recaptcha.middleware.logout")
    def test_failed_registration_is_not_logged_out(
        self,
        mock_logout,
    ):
        request = self._request()
        response = JsonResponse({}, status=400)

        RecaptchaEnterpriseMiddleware \
            ._enforce_registration_verification_boundary(
                request,
                response,
            )

        mock_logout.assert_not_called()

    @patch("cba_production.recaptcha.middleware.logout")
    def test_non_registration_request_is_not_logged_out(
        self,
        mock_logout,
    ):
        request = self._request(path="/api/user/v2/account/login_session/")
        response = JsonResponse({}, status=200)

        RecaptchaEnterpriseMiddleware \
            ._enforce_registration_verification_boundary(
                request,
                response,
            )

        mock_logout.assert_not_called()

    @patch("cba_production.recaptcha.middleware.logout")
    def test_get_registration_request_is_not_logged_out(
        self,
        mock_logout,
    ):
        request = self._request(method="GET")
        response = JsonResponse({}, status=200)

        RecaptchaEnterpriseMiddleware \
            ._enforce_registration_verification_boundary(
                request,
                response,
            )

        mock_logout.assert_not_called()


@override_settings(
    CBA_RECAPTCHA_ENABLED=True,
    CBA_RECAPTCHA_PROTECTED_PATHS=(
        "/login_ajax",
        "/login_ajax/",
        "/api/user/v1/account/login",
        "/api/user/v1/account/login/",
        "/api/user/v2/account/login_session",
        "/api/user/v2/account/login_session/",
    ),
    SHOW_ACTIVATE_CTA_POPUP_COOKIE_NAME="show-account-activation-popup",
    SESSION_COOKIE_DOMAIN=".centerforbusinessacceleration.com",
)
class RegistrationVerificationMiddlewareFlowTest(SimpleTestCase):
    @patch(
        "cba_production.recaptcha.middleware."
        "mark_user_change_as_expected"
    )
    @patch(
        "cba_production.recaptcha.middleware.delete_logged_in_cookies"
    )
    @patch("cba_production.recaptcha.middleware.logout")
    def test_registration_reaches_boundary_when_not_recaptcha_protected(
        self,
        mock_logout,
        mock_delete_logged_in_cookies,
        mock_mark_expected,
    ):
        request = SimpleNamespace(
            path="/api/user/v1/account/registration/",
            method="POST",
            content_type="application/json",
            user=SimpleNamespace(
                id=123,
                is_authenticated=True,
                is_active=False,
            ),
        )

        response = JsonResponse(
            {"authenticated_user": {"user_id": 123}},
            status=200,
        )

        get_response = Mock(return_value=response)
        middleware = RecaptchaEnterpriseMiddleware(get_response)

        result = middleware(request)

        self.assertIs(result, response)
        get_response.assert_called_once_with(request)
        mock_logout.assert_called_once_with(request)
        mock_delete_logged_in_cookies.assert_called_once_with(response)
        mock_mark_expected.assert_called_once_with(None)
