def to_integer(**kwargs):
    value = kwargs.get("value")
    maximum = kwargs.get("maximum")
    """Convert a value to integer, optionally rejecting values above a limit."""
    if value is None or value == "":
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    if maximum is not None and number > maximum:
        return None
    return number