from pathlib import Path

import pytest

from zenkit.errors import ZenkitError
from zenkit.generate import plan_writes, render_project, write_files
from zenkit.render import Context


def ctx(kind: str = "cli", **overrides: object) -> Context:
    base: dict[str, object] = {
        "kind": kind,
        "name": "demo-tool",
        "description": "Does a thing.",
        "author": "Ada Lovelace",
        "email": "ada@example.com",
        "year": 2030,
    }
    base.update(overrides)
    return Context(**base)  # type: ignore[arg-type]


def test_cli_project_has_expected_files() -> None:
    files = render_project(ctx("cli"))
    assert set(files) == {
        ".editorconfig",
        ".github/workflows/ci.yml",
        ".gitignore",
        "LICENSE",
        "README.md",
        "demo_tool/__init__.py",
        "demo_tool/__main__.py",
        "demo_tool/cli.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_cli.py",
    }


def test_lib_project_ships_the_typing_marker() -> None:
    files = render_project(ctx("lib"))
    assert "demo_tool/py.typed" in files
    assert 'demo_tool = ["py.typed"]' in files["pyproject.toml"]


def test_web_project_exposes_a_console_script() -> None:
    files = render_project(ctx("web"))
    assert 'demo-tool = "demo_tool.server:main"' in files["pyproject.toml"]
    assert "demo_tool/app.py" in files


def test_cli_console_script_points_at_main() -> None:
    assert 'demo-tool = "demo_tool.cli:main"' in render_project(ctx("cli"))["pyproject.toml"]


def test_no_placeholders_survive_in_any_kind() -> None:
    for kind in ("cli", "lib", "web"):
        for path, body in render_project(ctx(kind)).items():
            assert "@@" not in body, f"{kind}:{path}"
            assert "@@" not in path


def test_files_are_sorted_and_use_posix_separators() -> None:
    files = list(render_project(ctx("web")))
    assert files == sorted(files)
    assert all("\\" not in path for path in files)


def test_no_ci_drops_the_workflow() -> None:
    assert ".github/workflows/ci.yml" not in render_project(ctx(ci=False))


def test_license_none_drops_license_file_and_readme_section() -> None:
    files = render_project(ctx(license="none"))
    assert "LICENSE" not in files
    assert "Licence" not in files["README.md"]
    assert "license =" not in files["pyproject.toml"]


def test_licence_text_carries_year_and_holder() -> None:
    mit = render_project(ctx(license="mit"))["LICENSE"]
    assert "Copyright (c) 2030 Ada Lovelace" in mit
    bsd = render_project(ctx(license="bsd-3-clause"))["LICENSE"]
    assert "Copyright (c) 2030, Ada Lovelace" in bsd
    assert 'license = { text = "BSD-3-Clause" }' in render_project(ctx(license="bsd-3-clause"))[
        "pyproject.toml"
    ]


def test_ci_matrix_follows_the_minimum_python() -> None:
    ci = render_project(ctx(python_min="3.12"))[".github/workflows/ci.yml"]
    assert 'python-version: ["3.12", "3.13"]' in ci
    assert "${{ matrix.python-version }}" in ci
    assert 'requires-python = ">=3.12"' in render_project(ctx(python_min="3.12"))["pyproject.toml"]
    assert 'target-version = "py312"' in render_project(ctx(python_min="3.12"))["pyproject.toml"]


def test_author_is_optional() -> None:
    files = render_project(ctx(author="", email=""))
    assert "authors" not in files["pyproject.toml"]
    assert "Copyright (c) 2030 demo-tool" in files["LICENSE"]


def test_plan_marks_new_identical_and_conflicting_files(tmp_path: Path) -> None:
    files = render_project(ctx())
    first = plan_writes(tmp_path, files)
    assert {p.status for p in first} == {"new"}

    write_files(tmp_path, first)
    assert {p.status for p in plan_writes(tmp_path, files)} == {"identical"}

    (tmp_path / "README.md").write_text("mine\n", encoding="utf-8")
    statuses = {p.path: p.status for p in plan_writes(tmp_path, files)}
    assert statuses["README.md"] == "conflict"
    assert statuses["pyproject.toml"] == "identical"


def test_write_files_creates_nested_directories(tmp_path: Path) -> None:
    root = tmp_path / "deep" / "er"
    written = write_files(root, plan_writes(root, render_project(ctx())))
    assert (root / ".github" / "workflows" / "ci.yml").is_file()
    assert len(written) == len(render_project(ctx()))


def test_write_files_refuses_conflicts_and_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("mine\n", encoding="utf-8")
    planned = plan_writes(tmp_path, render_project(ctx()))
    with pytest.raises(ZenkitError, match="README.md"):
        write_files(tmp_path, planned)
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "mine\n"
    assert not (tmp_path / "pyproject.toml").exists()


def test_write_files_force_replaces_conflicts(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("mine\n", encoding="utf-8")
    planned = plan_writes(tmp_path, render_project(ctx()))
    write_files(tmp_path, planned, force=True)
    assert "demo-tool" in (tmp_path / "README.md").read_text(encoding="utf-8")


def test_written_files_use_lf_line_endings(tmp_path: Path) -> None:
    write_files(tmp_path, plan_writes(tmp_path, render_project(ctx())))
    assert b"\r" not in (tmp_path / "pyproject.toml").read_bytes()


def test_directory_in_the_way_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").mkdir()
    with pytest.raises(ZenkitError, match="directory"):
        plan_writes(tmp_path, render_project(ctx()))


def test_quotes_in_description_keep_generated_python_valid() -> None:
    files = render_project(ctx(description=r'Say "hi" to \ everyone'))
    for path, body in files.items():
        if path.endswith(".py"):
            compile(body, path, "exec")
