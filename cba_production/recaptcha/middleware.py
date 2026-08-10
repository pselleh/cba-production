import json
import logging
from json import JSONDecodeError

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse

from openedx.core.djangoapps.safe_sessions.middleware import (
    mark_user_change_as_expected,
)
from openedx.core.djangoapps.user_authn.cookies import (
    delete_logged_in_cookies,
)

from .assessment import create_assessment
from .exceptions import (
    RecaptchaActionMismatch,
    RecaptchaConfigurationError,
    RecaptchaInvalidToken,
    RecaptchaLowScore,
    RecaptchaServiceError,
)

logger = logging.getLogger(__name__)


class RecaptchaEnterpriseMiddleware:
    """
    Validate reCAPTCHA Enterprise tokens before selected LMS views execute.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._should_protect(request):
            response = self.get_response(request)
            return self._enforce_registration_verification_boundary(
                request,
                response,
            )

        token, submitted_action = self._extract_recaptcha_fields(request)

        expected_action = str(
            getattr(settings, "CBA_RECAPTCHA_EXPECTED_ACTION", "LOGIN")
        )

        if not token:
            return self._error_response(
                status=400,
                error_code="recaptcha-token-missing",
                reason="TOKEN_MISSING",
            )

        if submitted_action and submitted_action != expected_action:
            return self._error_response(
                status=400,
                error_code="recaptcha-action-invalid",
                reason="ACTION_MISMATCH",
            )

        try:
            create_assessment(
                token=token,
                expected_action=expected_action,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                user_ip_address=self._get_client_ip(request),
                requested_uri=request.build_absolute_uri(),
            )
        except RecaptchaInvalidToken as exc:
            logger.warning(
                "reCAPTCHA rejected an invalid token: reason=%s",
                exc.invalid_reason,
            )
            return self._error_response(
                status=400,
                error_code="recaptcha-invalid",
                reason="INVALID_TOKEN",
            )
        except RecaptchaActionMismatch:
            logger.warning("reCAPTCHA token action did not match LOGIN")
            return self._error_response(
                status=400,
                error_code="recaptcha-action-invalid",
                reason="ACTION_MISMATCH",
            )
        except RecaptchaLowScore:
            # Deliberately do not expose the score to the browser.
            logger.warning("reCAPTCHA assessment score was below threshold")
            return self._error_response(
                status=403,
                error_code="recaptcha-challenge-required",
                reason="LOW_SCORE",
                challenge_required=True,
            )
        except RecaptchaConfigurationError:
            logger.exception("reCAPTCHA configuration error")
            return self._service_failure_response()
        except RecaptchaServiceError:
            logger.exception("reCAPTCHA assessment service error")
            return self._service_failure_response()

        # Assessment passed. Continue to the unmodified Open edX login view.
        response = self.get_response(request)
        return self._enforce_registration_verification_boundary(
            request,
            response,
        )

    @staticmethod
    def _enforce_registration_verification_boundary(request, response):
        """
        Do not leave a newly registered inactive learner authenticated.

        Open edX intentionally authenticates a newly created inactive user
        during registration and sets its login/JWT cookies. CBA requires
        email verification before authenticated access, so terminate that
        registration-created session after a successful registration.

        This is deliberately limited to successful POST requests to the
        registration endpoints. Normal login and other inactive-user flows
        are not changed.
        """
        registration_paths = {
            "/create_account",
            "/api/user/v1/account/registration/",
            "/api/user/v2/account/registration/",
            "/user_api/v1/account/registration/",
            "/user_api/v2/account/registration/",
        }

        if request.method.upper() != "POST":
            return response

        if request.path not in registration_paths:
            return response

        if response.status_code != 200:
            return response

        user = getattr(request, "user", None)
        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or getattr(user, "is_active", True)
        ):
            return response

        user_id = getattr(user, "id", None)

        logger.info(
            "CBA registration verification boundary: "
            "terminating registration-created session for user_id=%s",
            user_id,
        )

        logout(request)
        delete_logged_in_cookies(response)

        # RegistrationView sets this cookie for Open edX's normal
        # post-registration activation reminder. CBA does not permit the
        # inactive learner to remain authenticated, so remove it as well.
        response.delete_cookie(
            settings.SHOW_ACTIVATE_CTA_POPUP_COOKIE_NAME,
            path="/",
            domain=settings.SESSION_COOKIE_DOMAIN,
        )

        mark_user_change_as_expected(None)

        return response

    @staticmethod
    def _should_protect(request):
        if not bool(
            getattr(settings, "CBA_RECAPTCHA_ENABLED", False)
        ):
            return False

        if request.method.upper() != "POST":
            return False

        configured_paths = getattr(
            settings,
            "CBA_RECAPTCHA_PROTECTED_PATHS",
            (
                "/login_ajax",
                "/login_ajax/",
                "/api/user/v1/account/login",
                "/api/user/v1/account/login/",
            ),
        )

        return request.path in set(configured_paths)

    @staticmethod
    def _extract_recaptcha_fields(request):
        token = ""
        action = ""

        content_type = request.content_type or ""

        if "application/json" in content_type:
            try:
                payload = json.loads(
                    request.body.decode(request.encoding or "utf-8")
                )
            except (
                JSONDecodeError,
                UnicodeDecodeError,
                AttributeError,
            ):
                payload = {}

            if isinstance(payload, dict):
                token = payload.get("recaptcha_token", "")
                action = payload.get("recaptcha_action", "")
        else:
            token = request.POST.get("recaptcha_token", "")
            action = request.POST.get("recaptcha_action", "")

        return str(token).strip(), str(action).strip()

    @staticmethod
    def _get_client_ip(request):
        """
        Prefer REMOTE_ADDR so an arbitrary client cannot spoof its address
        through an untrusted X-Forwarded-For value.
        """
        return str(request.META.get("REMOTE_ADDR", ""))

    @staticmethod
    def _error_response(
        *,
        status,
        error_code,
        reason,
        challenge_required=False,
    ):
        return JsonResponse(
            {
                "success": False,
                "error_code": error_code,
                "challenge_required": challenge_required,
                "recaptcha": {
                    "valid": False,
                    "reason": reason,
                },
            },
            status=status,
        )

    @staticmethod
    def _service_failure_response():
        fail_closed = bool(
            getattr(settings, "CBA_RECAPTCHA_FAIL_CLOSED", True)
        )

        if not fail_closed:
            # This branch is intentionally unavailable from this static
            # method. Production should remain fail-closed.
            logger.error(
                "CBA_RECAPTCHA_FAIL_CLOSED=False is not supported "
                "for authentication requests"
            )

        return JsonResponse(
            {
                "success": False,
                "error_code": "recaptcha-service-unavailable",
                "challenge_required": False,
                "recaptcha": {
                    "valid": False,
                    "reason": "SERVICE_UNAVAILABLE",
                },
            },
            status=503,
        )
