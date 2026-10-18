"""Turn a Context into rendered files and write them to disk safely."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ZenkitError
from .render import Context, render_text
from .templates import template_files


def render_project(ctx: Context) -> dict[str, str]:
    """Render every file of the project; keys are POSIX-style relative paths."""
    variables = ctx.variables()
    rendered: dict[str, str] = {}
    for raw_path, body in template_files(ctx.kind, license=ctx.license, ci=ctx.ci).items():
        path = render_text(raw_path, variables)
        rendered[path] = render_text(body, variables)
    return dict(sorted(rendered.items()))


@dataclass(frozen=True)
class PlannedFile:
    """A file zenkit intends to write and what is currently at that path."""

    path: str
    content: str
    status: str  # "new", "identical" or "conflict"


def plan_writes(root: Path, files: dict[str, str]) -> list[PlannedFile]:
    """Compare rendered ``files`` against what already exists under ``root``."""
    planned: list[PlannedFile] = []
    for path, content in files.items():
        target = root / path
        if target.is_dir():
            raise ZenkitError(f"cannot write {path}: a directory is in the way")
        if not target.exists():
            status = "new"
        elif target.read_text(encoding="utf-8", errors="replace") == content:
            status = "identical"
        else:
            status = "conflict"
        planned.append(PlannedFile(path, content, status))
    return planned


def write_files(
    root: Path, planned: list[PlannedFile], *, force: bool = False
) -> list[PlannedFile]:
    """Write ``planned`` under ``root`` and return the files actually written.

    Existing files whose content differs are only replaced when ``force`` is true; identical
    files are left untouched. Nothing is written if a conflict would be refused, so a failed
    run never leaves a half-generated project behind.
    """
    conflicts = [p.path for p in planned if p.status == "conflict"]
    if conflicts and not force:
        listing = ", ".join(conflicts)
        raise ZenkitError(
            f"refusing to overwrite existing files: {listing} (use --force to replace them)"
        )
    written: list[PlannedFile] = []
    for item in planned:
        if item.status == "identical":
            continue
        target = root / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(item.content)
        written.append(item)
    return written
