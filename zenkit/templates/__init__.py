"""Registry of project templates, keyed by kind."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ZenkitError
from . import cli, lib, web
from .common import CI_YML, EDITORCONFIG, GITIGNORE, LICENSES


@dataclass(frozen=True)
class Template:
    """One project kind: its files (path -> body, both may hold placeholders)."""

    kind: str
    summary: str
    default_description: str
    files: dict[str, str]


TEMPLATES: dict[str, Template] = {
    "cli": Template("cli", cli.SUMMARY, cli.DEFAULT_DESCRIPTION, cli.FILES),
    "lib": Template("lib", lib.SUMMARY, lib.DEFAULT_DESCRIPTION, lib.FILES),
    "web": Template("web", web.SUMMARY, web.DEFAULT_DESCRIPTION, web.FILES),
}

# Files shared by every kind. LICENSE is added separately because its body depends on a choice.
COMMON_FILES: dict[str, str] = {
    ".gitignore": GITIGNORE,
    ".editorconfig": EDITORCONFIG,
}
CI_FILES: dict[str, str] = {".github/workflows/ci.yml": CI_YML}


def get_template(kind: str) -> Template:
    try:
        return TEMPLATES[kind]
    except KeyError:
        known = ", ".join(sorted(TEMPLATES))
        raise ZenkitError(f"unknown template {kind!r}; available: {known}") from None


def template_files(kind: str, *, license: str = "mit", ci: bool = True) -> dict[str, str]:
    """All raw (unrendered) files for ``kind``, in a stable order."""
    files: dict[str, str] = {}
    files.update(get_template(kind).files)
    files.update(COMMON_FILES)
    if ci:
        files.update(CI_FILES)
    if license != "none":
        files["LICENSE"] = LICENSES[license]
    return files
