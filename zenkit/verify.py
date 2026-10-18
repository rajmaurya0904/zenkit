"""Generate a template into a scratch directory and prove it lints, tests and runs."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .generate import plan_writes, render_project, write_files
from .render import PLACEHOLDER, Context

STEP_TIMEOUT_SECONDS = 300


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class VerifyReport:
    kind: str
    project_dir: Path
    scratch: Path | None = None  # temp directory owned by this report, if verify created one
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def cleanup(self) -> None:
        """Delete the scratch directory verify created (a caller-supplied workdir is kept)."""
        if self.scratch is not None:
            shutil.rmtree(self.scratch, ignore_errors=True)


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STEP_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {STEP_TIMEOUT_SECONDS}s"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.splitlines()[-lines:])


def _module_step(name: str, module: str, args: list[str], cwd: Path) -> StepResult:
    if importlib.util.find_spec(module) is None:
        return StepResult(
            name, False, f"{module} is not installed in this interpreter (pip install {module})"
        )
    code, output = _run([sys.executable, "-m", module, *args], cwd)
    return StepResult(name, code == 0, _tail(output))


def check_files(root: Path) -> StepResult:
    """Static checks: pyproject parses and no placeholder survived rendering."""
    try:
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return StepResult("pyproject.toml parses", False, str(exc))
    for path in sorted(root.rglob("*")):
        if path.is_file():
            match = PLACEHOLDER.search(path.read_text(encoding="utf-8", errors="replace"))
            if match:
                rel = path.relative_to(root).as_posix()
                return StepResult("no leftover placeholders", False, f"{rel}: {match.group(0)}")
    return StepResult("static checks", True, "pyproject.toml parses, no leftover placeholders")


def verify(
    ctx: Context,
    *,
    workdir: Path | None = None,
    on_step: Callable[[StepResult], None] | None = None,
) -> VerifyReport:
    """Generate ``ctx`` under ``workdir`` (a temp dir by default) and run every check."""
    scratch = Path(tempfile.mkdtemp(prefix="zenkit-verify-")) if workdir is None else None
    base = scratch if scratch is not None else workdir
    root = base / ctx.name
    write_files(root, plan_writes(root, render_project(ctx)))
    report = VerifyReport(ctx.kind, root, scratch)

    def record(step: StepResult) -> None:
        report.steps.append(step)
        if on_step:
            on_step(step)

    record(check_files(root))
    record(_module_step("ruff check", "ruff", ["check", "."], root))
    record(_module_step("pytest", "pytest", ["-q"], root))
    if ctx.kind == "lib":
        code, output = _run(
            [sys.executable, "-c", f"import {ctx.package}; print({ctx.package}.__version__)"], root
        )
        record(StepResult("import package", code == 0, _tail(output)))
    else:
        code, output = _run([sys.executable, "-m", ctx.package, "--help"], root)
        record(StepResult(f"python -m {ctx.package} --help", code == 0, _tail(output)))
    return report
