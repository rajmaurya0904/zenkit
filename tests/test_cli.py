import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from zenkit import __version__, cli
from zenkit.cli import main


@pytest.fixture(autouse=True)
def no_git_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never depend on the machine's git config."""
    monkeypatch.setattr(cli, "_git_config", lambda key: "")


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_missing_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_unknown_kind_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["new", "desktop", "thing"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_list_names_every_template(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines] == ["cli", "lib", "web"]


def test_show_lists_files_with_line_counts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["show", "lib"]) == 0
    out = capsys.readouterr().out
    assert "my_project/core.py" in out
    assert "lines" in out


def test_show_file_prints_rendered_content(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["show", "cli", "--file", "pyproject.toml"]) == 0
    out = capsys.readouterr().out
    assert 'name = "my-project"' in out
    assert "@@" not in out


def test_show_unknown_file_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["show", "cli", "--file", "nope.txt"]) == 1
    assert "not generated" in capsys.readouterr().err


def test_new_creates_the_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["new", "cli", "demo-tool", "--dir", str(tmp_path), "--author", "Ada"])
    assert code == 0
    root = tmp_path / "demo-tool"
    assert (root / "demo_tool" / "cli.py").is_file()
    assert "Ada" in (root / "LICENSE").read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "+ pyproject.toml" in out
    assert "11 file(s) written" in out
    assert 'pip install -e ".[dev]"' in out


def test_new_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "web", "demo-web", "--dir", str(tmp_path), "--dry-run"]) == 0
    assert not (tmp_path / "demo-web").exists()
    assert "Would create" in capsys.readouterr().out


def test_new_refuses_to_overwrite_then_force_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "demo-lib"
    root.mkdir()
    (root / "README.md").write_text("mine\n", encoding="utf-8")
    argv = ["new", "lib", "demo-lib", "--dir", str(tmp_path)]
    assert main(argv) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert (root / "README.md").read_text(encoding="utf-8") == "mine\n"

    assert main([*argv, "--force"]) == 0
    assert "demo-lib" in (root / "README.md").read_text(encoding="utf-8")


def test_new_rerun_is_idempotent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["new", "lib", "demo-lib", "--dir", str(tmp_path)]
    assert main(argv) == 0
    capsys.readouterr()
    assert main(argv) == 0
    assert "0 file(s) written" in capsys.readouterr().out


def test_new_rejects_bad_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "cli", "Bad Name", "--dir", str(tmp_path)]) == 1
    assert "invalid project name" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_new_rejects_name_that_shadows_the_stdlib(tmp_path: Path) -> None:
    assert main(["new", "lib", "json", "--dir", str(tmp_path)]) == 1


def test_new_rejects_overlong_description(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["new", "cli", "demo", "--dir", str(tmp_path), "--description", "x" * 80]
    assert main(argv) == 1
    assert "limit" in capsys.readouterr().err


def test_new_fails_when_target_is_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "demo").write_text("a file", encoding="utf-8")
    assert main(["new", "cli", "demo", "--dir", str(tmp_path)]) == 1
    assert "not a directory" in capsys.readouterr().err


def test_new_options_reach_the_output(tmp_path: Path) -> None:
    argv = [
        "new", "cli", "opts", "--dir", str(tmp_path),
        "--license", "none", "--no-ci", "--python", "3.12",
        "--description", "Tiny thing", "--author", "Ada", "--email", "ada@example.com",
    ]  # fmt: skip
    assert main(argv) == 0
    root = tmp_path / "opts"
    assert not (root / "LICENSE").exists()
    assert not (root / ".github").exists()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.12"' in pyproject
    assert 'description = "Tiny thing"' in pyproject
    assert 'authors = [{ name = "Ada", email = "ada@example.com" }]' in pyproject


def test_author_defaults_to_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"user.name": "Grace Hopper", "user.email": "grace@example.com"}
    monkeypatch.setattr(cli, "_git_config", lambda key: values[key])
    main(["new", "cli", "gitdefaults", "--dir", str(tmp_path)])
    text = (tmp_path / "gitdefaults" / "pyproject.toml").read_text(encoding="utf-8")
    assert "Grace Hopper" in text and "grace@example.com" in text


def test_explicit_empty_author_beats_git_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_git_config", lambda key: "Someone")
    main(["new", "cli", "anon", "--dir", str(tmp_path), "--author", "", "--email", ""])
    assert "authors" not in (tmp_path / "anon" / "pyproject.toml").read_text(encoding="utf-8")


def test_init_uses_the_directory_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "My Cool.Tool"
    target.mkdir()
    monkeypatch.chdir(target)
    assert main(["init", "lib"]) == 0
    assert (target / "my_cool_tool" / "core.py").is_file()
    assert "cd " not in capsys.readouterr().out


def test_init_with_explicit_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "web", "--name", "svc"]) == 0
    assert (tmp_path / "svc" / "app.py").is_file()


def test_init_reports_a_bad_directory_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "123"
    target.mkdir()
    monkeypatch.chdir(target)
    assert main(["init", "cli"]) == 1
    assert "invalid project name" in capsys.readouterr().err


def test_git_flag_initialises_a_repository(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    assert main(["new", "lib", "withgit", "--dir", str(tmp_path), "--git"]) == 0
    assert (tmp_path / "withgit" / ".git").exists()


def test_git_flag_leaves_an_existing_repository_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    assert main(["new", "lib", "repo", "--dir", str(tmp_path), "--git"]) == 0
    assert "already exists" in capsys.readouterr().out


def test_module_entry_point_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "zenkit", "list"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "web" in result.stdout


@pytest.mark.skipif(
    importlib.util.find_spec("ruff") is None, reason="ruff is needed to verify templates"
)
def test_verify_passes_for_a_template(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify", "lib"]) == 0
    out = capsys.readouterr().out
    assert "ok    ruff check" in out
    assert "FAIL" not in out


def test_verify_unknown_kind_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["verify", "desktop"]) == 1
    assert "unknown template" in capsys.readouterr().err
