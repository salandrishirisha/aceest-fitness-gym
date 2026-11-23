"""Payload validation helpers shared by the API blueprints."""


class ValidationError(ValueError):
    """Raised when a request payload contains an invalid value."""


def to_text(data, field):
    """Read an optional text field from a payload, stripped of whitespace."""
    value = data.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    return value.strip()


def to_number(data, field, cast=float, default=None, minimum=0):
    """Read an optional numeric field from a payload and validate it."""
    value = data.get(field, default)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number")
    try:
        number = cast(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be >= {minimum}")
    return number
