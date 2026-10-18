import importlib.util
from pathlib import Path

import pytest

from zenkit import verify as verify_module
from zenkit.generate import plan_writes, render_project, write_files
from zenkit.names import MAX_NAME_LENGTH
from zenkit.render import MAX_DESCRIPTION_LENGTH, Context
from zenkit.verify import check_files, verify

needs_dev_tools = pytest.mark.skipif(
    importlib.util.find_spec("ruff") is None or importlib.util.find_spec("pytest") is None,
    reason="ruff and pytest must be installed to verify generated projects",
)


def project(tmp_path: Path, kind: str = "lib") -> Path:
    ctx = Context(kind=kind, name="demo", description="Demo.")
    write_files(tmp_path, plan_writes(tmp_path, render_project(ctx)))
    return tmp_path


def test_check_files_accepts_a_fresh_project(tmp_path: Path) -> None:
    assert check_files(project(tmp_path)).ok


def test_check_files_flags_a_broken_pyproject(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "pyproject.toml").write_text("[project\nname =", encoding="utf-8")
    step = check_files(root)
    assert not step.ok
    assert "pyproject" in step.name


def test_check_files_flags_leftover_placeholders(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "README.md").write_text("hello @@oops@@\n", encoding="utf-8")
    step = check_files(root)
    assert not step.ok
    assert "README.md" in step.detail and "@@oops@@" in step.detail


@needs_dev_tools
@pytest.mark.parametrize("kind", ["cli", "lib", "web"])
def test_templates_pass_at_the_name_and_description_limits(kind: str) -> None:
    ctx = Context(
        kind=kind,
        name="a" * (MAX_NAME_LENGTH - 1) + "b",
        description="d" * MAX_DESCRIPTION_LENGTH,
        author="x" * 80,
        python_min="3.10",
    )
    report = verify(ctx)
    try:
        failures = [(s.name, s.detail) for s in report.steps if not s.ok]
        assert report.ok, failures
    finally:
        report.cleanup()


@needs_dev_tools
def test_verify_reports_each_step_in_order() -> None:
    seen: list[str] = []
    report = verify(
        Context(kind="cli", name="stepper", description="Steps."),
        on_step=lambda step: seen.append(step.name),
    )
    report.cleanup()
    assert seen == [
        "static checks",
        "ruff check",
        "pytest",
        "python -m stepper --help",
    ]


@needs_dev_tools
def test_verify_in_a_given_workdir_keeps_the_project(tmp_path: Path) -> None:
    report = verify(Context(kind="lib", name="kept", description="Kept."), workdir=tmp_path)
    report.cleanup()  # a caller-supplied directory is never deleted
    assert report.ok
    assert (tmp_path / "kept" / "pyproject.toml").is_file()


@needs_dev_tools
def test_verify_catches_a_failing_generated_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = Context(kind="lib", name="broken", description="B.")
    broken = {
        path: body.replace("assert clamp(5, 0, 10) == 5", "assert clamp(5, 0, 10) == 6")
        for path, body in render_project(ctx).items()
    }
    monkeypatch.setattr(verify_module, "render_project", lambda ctx: broken)
    report = verify(ctx, workdir=tmp_path)
    failed = [s.name for s in report.steps if not s.ok]
    assert failed == ["pytest"]
    assert "assert" in report.steps[2].detail


def test_missing_tool_is_reported_not_crashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verify_module.importlib.util, "find_spec", lambda name: None)
    report = verify(Context(kind="lib", name="notools", description="N."), workdir=tmp_path)
    missing = [s for s in report.steps if not s.ok and "not installed" in s.detail]
    assert [s.name for s in missing] == ["ruff check", "pytest"]
