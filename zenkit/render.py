"""Placeholder substitution and the per-project variable set."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import TemplateError, ZenkitError
from .names import package_name

PLACEHOLDER = re.compile(r"@@([a-z_]+)@@")

PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13")
DEFAULT_PYTHON = "3.11"

LICENSE_CHOICES = ("mit", "bsd-3-clause", "none")
_SPDX = {"mit": "MIT", "bsd-3-clause": "BSD-3-Clause"}


def _toml_escape(text: str) -> str:
    """Escape ``text`` for use inside a TOML basic (double-quoted) string."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _py_escape(text: str) -> str:
    """Escape ``text`` for use inside a double-quoted Python string or docstring."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _check_single_line(label: str, value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ZenkitError(f"{label} must be a single line")
    return value.strip()


@dataclass(frozen=True)
class Context:
    """Everything a template can refer to, validated once at construction."""

    kind: str
    name: str
    description: str
    author: str = ""
    email: str = ""
    license: str = "mit"
    python_min: str = DEFAULT_PYTHON
    year: int = 2026
    ci: bool = True

    def __post_init__(self) -> None:
        if self.license not in LICENSE_CHOICES:
            raise ZenkitError(
                f"unknown license {self.license!r}; choose one of: {', '.join(LICENSE_CHOICES)}"
            )
        if self.python_min not in PYTHON_VERSIONS:
            raise ZenkitError(
                f"unsupported Python version {self.python_min!r}; "
                f"choose one of: {', '.join(PYTHON_VERSIONS)}"
            )
        for label, value in (
            ("description", self.description),
            ("author", self.author),
            ("email", self.email),
        ):
            _check_single_line(label, value)
        if not self.description.strip():
            raise ZenkitError("description must not be empty")
        package_name(self.name)  # raises ZenkitError for bad names

    @property
    def package(self) -> str:
        return package_name(self.name)

    def variables(self) -> dict[str, str]:
        """The full placeholder table. Empty values make a whole-line placeholder vanish."""
        description = self.description.strip()
        author = self.author.strip()
        email = self.email.strip()
        spdx = _SPDX.get(self.license, "")

        fields = []
        if author:
            fields.append(f'name = "{_toml_escape(author)}"')
        if email:
            fields.append(f'email = "{_toml_escape(email)}"')
        authors_line = "authors = [{ " + ", ".join(fields) + " }]" if fields else ""

        minor = int(self.python_min.split(".")[1])
        supported = [f"3.{m}" for m in range(minor, 14)]
        matrix = "[" + ", ".join(f'"{v}"' for v in supported) + "]"

        license_section = (
            f"## Licence\n\n{spdx} -- see [LICENSE](LICENSE).\n" if self.license != "none" else ""
        )
        return {
            "kind": self.kind,
            "name": self.name,
            "package": self.package,
            "description": description,
            "description_toml": _toml_escape(description),
            "description_py": _py_escape(description),
            "authors_line": authors_line,
            "license_line": f'license = {{ text = "{spdx}" }}' if spdx else "",
            "license_section": license_section,
            "holder": author or self.name,
            "python_min": self.python_min,
            "py_tag": "py" + self.python_min.replace(".", ""),
            "ci_matrix": matrix,
            "year": str(self.year),
        }


def substitute(text: str, variables: dict[str, str]) -> str:
    """Replace every ``@@name@@`` in ``text``; unknown names are a template bug."""

    def lookup(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise TemplateError(f"template uses unknown placeholder @@{key}@@")
        return variables[key]

    return PLACEHOLDER.sub(lookup, text)


def render_text(text: str, variables: dict[str, str]) -> str:
    """Render a template body.

    A line that holds nothing but a placeholder whose value is empty is dropped entirely, so
    optional pieces (the license line, the authors line) leave no blank gaps behind.
    """
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        whole = PLACEHOLDER.fullmatch(line.strip())
        if whole and variables.get(whole.group(1)) == "":
            continue
        out.append(substitute(line, variables))
    return "".join(out)
