class RecaptchaError(Exception):
    """Base exception for the CBA reCAPTCHA integration."""


class RecaptchaConfigurationError(RecaptchaError):
    """Required reCAPTCHA configuration is missing."""


class RecaptchaServiceError(RecaptchaError):
    """Google could not create an assessment."""


class RecaptchaInvalidToken(RecaptchaError):
    """Google reported that the token was invalid."""

    def __init__(self, invalid_reason="UNKNOWN_INVALID_REASON"):
        self.invalid_reason = invalid_reason
        super().__init__(f"Invalid reCAPTCHA token: {invalid_reason}")


class RecaptchaActionMismatch(RecaptchaError):
    """The token action does not match the expected action."""

    def __init__(self, actual_action, expected_action):
        self.actual_action = actual_action
        self.expected_action = expected_action
        super().__init__("reCAPTCHA action mismatch")


class RecaptchaLowScore(RecaptchaError):
    """The assessment score is below the configured threshold."""

    def __init__(self, score, threshold):
        self.score = score
        self.threshold = threshold
        super().__init__("reCAPTCHA score below threshold")
