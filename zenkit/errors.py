"""Exception types shared across zenkit."""


class ZenkitError(Exception):
    """A failure the user can act on. The message is printed as-is, without a traceback."""


class TemplateError(ZenkitError):
    """A template references a placeholder that has no value (a bug in the template)."""
