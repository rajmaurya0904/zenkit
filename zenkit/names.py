"""Validation of project names and their derived Python package names."""

from __future__ import annotations

import keyword
import re
import sys

from .errors import ZenkitError

# Short enough that every generated line stays inside the 100-column lint limit.
MAX_NAME_LENGTH = 30

# Lowercase words joined by single '-' or '_' separators, starting with a letter.
_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")

# Names that would import fine but cause confusing clashes in a flat layout.
_RESERVED = frozenset({"tests", "test", "src", "zenkit", "setup", "build", "dist"})


def validate_name(name: str) -> str:
    """Return ``name`` unchanged if it is a usable project name, else raise ZenkitError."""
    if not name:
        raise ZenkitError("project name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ZenkitError(
            f"project name is {len(name)} characters long; the limit is {MAX_NAME_LENGTH}"
        )
    if not _NAME_RE.match(name):
        raise ZenkitError(
            f"invalid project name {name!r}: use lowercase letters, digits, '-' and '_', "
            "start with a letter, and do not end or double up separators"
        )
    return name


def package_name(name: str) -> str:
    """Derive the importable package name for a project name (``my-tool`` -> ``my_tool``)."""
    package = validate_name(name).replace("-", "_")
    if keyword.iskeyword(package):
        raise ZenkitError(f"{name!r} becomes the Python keyword {package!r}; pick another name")
    if package in sys.stdlib_module_names:
        raise ZenkitError(
            f"{name!r} would shadow the standard library module {package!r}; pick another name"
        )
    if package in _RESERVED:
        raise ZenkitError(f"{name!r} is reserved because it collides with common project paths")
    return package
