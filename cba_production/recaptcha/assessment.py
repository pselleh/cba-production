from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings

from .exceptions import (
    RecaptchaActionMismatch,
    RecaptchaConfigurationError,
    RecaptchaInvalidToken,
    RecaptchaLowScore,
    RecaptchaServiceError,
)


@dataclass(frozen=True)
class AssessmentResult:
    valid: bool
    action: str
    score: float
    assessment_name: str
    reasons: tuple[str, ...]


def _required_setting(name: str) -> Any:
    value = getattr(settings, name, None)

    if value in (None, ""):
        raise RecaptchaConfigurationError(
            f"Required Django setting {name} is not configured"
        )

    return value


def create_assessment(
    *,
    token: str,
    expected_action: str,
    user_agent: str = "",
    user_ip_address: str = "",
    requested_uri: str = "",
) -> AssessmentResult:
    """
    Submit a browser token to Google reCAPTCHA Enterprise.

    Raises a RecaptchaError subclass when the assessment cannot be accepted.
    """
    project_id = str(_required_setting("RECAPTCHA_PROJECT_ID"))
    api_key = str(_required_setting("RECAPTCHA_PRIVATE_KEY"))

    site_keys = _required_setting("RECAPTCHA_SITE_KEYS")
    site_key = site_keys.get("web") if isinstance(site_keys, dict) else None

    if not site_key:
        raise RecaptchaConfigurationError(
            "RECAPTCHA_SITE_KEYS['web'] is not configured"
        )

    threshold = float(
        getattr(settings, "CBA_RECAPTCHA_SCORE_THRESHOLD", 0.5)
    )
    timeout = float(
        getattr(settings, "CBA_RECAPTCHA_HTTP_TIMEOUT", 5.0)
    )

    encoded_project_id = quote(project_id, safe="")
    endpoint = (
        "https://recaptchaenterprise.googleapis.com/"
        f"v1/projects/{encoded_project_id}/assessments"
    )

    event = {
        "token": token,
        "siteKey": site_key,
        "expectedAction": expected_action,
    }

    if user_agent:
        event["userAgent"] = user_agent[:1024]

    if user_ip_address:
        event["userIpAddress"] = user_ip_address

    if requested_uri:
        event["requestedUri"] = requested_uri[:2048]

    payload = {
        "event": event,
    }

    try:
        response = requests.post(
            endpoint,
            params={"key": api_key},
            json=payload,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        response.raise_for_status()
        assessment = response.json()
    except requests.RequestException as exc:
        raise RecaptchaServiceError(
            "Google reCAPTCHA Enterprise request failed"
        ) from exc
    except ValueError as exc:
        raise RecaptchaServiceError(
            "Google reCAPTCHA Enterprise returned invalid JSON"
        ) from exc

    token_properties = assessment.get("tokenProperties") or {}
    risk_analysis = assessment.get("riskAnalysis") or {}

    valid = bool(token_properties.get("valid", False))
    invalid_reason = token_properties.get(
        "invalidReason",
        "UNKNOWN_INVALID_REASON",
    )

    if not valid:
        raise RecaptchaInvalidToken(invalid_reason)

    actual_action = str(token_properties.get("action") or "")

    if actual_action != expected_action:
        raise RecaptchaActionMismatch(
            actual_action=actual_action,
            expected_action=expected_action,
        )

    try:
        score = float(risk_analysis.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0

    if score < threshold:
        raise RecaptchaLowScore(
            score=score,
            threshold=threshold,
        )

    reasons = tuple(
        str(reason)
        for reason in risk_analysis.get("reasons", [])
    )

    return AssessmentResult(
        valid=True,
        action=actual_action,
        score=score,
        assessment_name=str(assessment.get("name") or ""),
        reasons=reasons,
    )
