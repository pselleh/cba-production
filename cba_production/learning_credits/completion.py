"""Read LMS block completion; additional award requirements apply."""


def missing_required_blocks(*, learner, plan):
    """Return required block keys without a recorded completion of 1.0."""
    from django.apps import apps

    required = plan.required_block_keys
    if not isinstance(required, list) or not required:
        raise ValueError("The credit plan must specify required blocks.")
    if any(not isinstance(key, str) or not key.strip() for key in required):
        raise ValueError("Required block keys must be nonempty strings.")
    if len(required) != len(set(required)):
        raise ValueError("Required block keys must be unique.")

    completion_model = apps.get_model("completion", "BlockCompletion")
    values = completion_model.get_learning_context_completions(
        learner, plan.course_key
    )
    completed = {
        str(key)
        for key, value in values.items()
        if value == 1.0
    }
    return [key for key in required if key not in completed]
