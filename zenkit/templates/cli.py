"""The ``cli`` template: an argparse command line tool with a console script."""

from __future__ import annotations

from .common import TOOL_CONFIG

SUMMARY = "Command line tool: argparse entry point, console script, `python -m` support."
DEFAULT_DESCRIPTION = "A small Python command-line tool."

PYPROJECT = (
    '''\
[project]
name = "@@name@@"
version = "0.1.0"
description = "@@description_toml@@"
readme = "README.md"
requires-python = ">=@@python_min@@"
@@license_line@@
@@authors_line@@
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
]

[project.scripts]
@@name@@ = "@@package@@.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["@@package@@*"]

'''
    + TOOL_CONFIG
)

INIT = '''\
"""@@description_py@@"""

__version__ = "0.1.0"
'''

MAIN = '''\
"""Allow ``python -m @@package@@``."""

from .cli import main

raise SystemExit(main())
'''

CLI = '''\
"""Command line interface for @@name@@."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__


def greet(who: str, *, shout: bool = False) -> str:
    """Build the greeting. Replace this with the real work of your tool."""
    message = f"Hello, {who}!"
    return message.upper() if shout else message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="@@name@@",
        description="@@description_py@@",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("who", nargs="?", default="world", help="who to greet (default: world)")
    parser.add_argument("--shout", action="store_true", help="upper-case the greeting")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code (0 on success, 2 on bad usage)."""
    args = build_parser().parse_args(argv)
    print(greet(args.who, shout=args.shout))
    return 0
'''

TEST_CLI = '''\
import subprocess
import sys

import pytest

from @@package@@ import __version__
from @@package@@.cli import build_parser, greet, main


def test_greet_defaults() -> None:
    assert greet("world") == "Hello, world!"


def test_greet_shout() -> None:
    assert greet("ada", shout=True) == "HELLO, ADA!"


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["Ada"]) == 0
    assert capsys.readouterr().out == "Hello, Ada!\\n"


def test_main_defaults_to_world(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "world" in capsys.readouterr().out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_flag_exits_with_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--nope"])
    assert exc.value.code == 2


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "@@package@@", "--shout", "Ada"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "HELLO, ADA!"
'''

README = '''\
# @@name@@

**@@description@@**

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
@@name@@ --help
@@name@@ Ada --shout
python -m @@package@@ --version
```

## Development

```bash
pytest -q
ruff check .
```

@@license_section@@
'''

FILES: dict[str, str] = {
    "pyproject.toml": PYPROJECT,
    "README.md": README,
    "@@package@@/__init__.py": INIT,
    "@@package@@/__main__.py": MAIN,
    "@@package@@/cli.py": CLI,
    "tests/__init__.py": "",
    "tests/test_cli.py": TEST_CLI,
}
