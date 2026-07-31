MIDDLEWARE_PATH = "cba_production.recaptcha.middleware.RecaptchaEnterpriseMiddleware"


def plugin_settings(settings):
    """
    Add the reCAPTCHA middleware to the LMS without modifying edx-platform.

    The middleware is appended so Django's standard request, session, CSRF,
    and authentication middleware have already initialized the request.
    It still executes before the login view itself.
    """
    middleware = list(settings.MIDDLEWARE)

    if MIDDLEWARE_PATH not in middleware:
        middleware.append(MIDDLEWARE_PATH)

    settings.MIDDLEWARE = middleware
