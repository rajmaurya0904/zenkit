"""The ``lib`` template: an importable, typed library with no runtime dependencies."""

from __future__ import annotations

from .common import TOOL_CONFIG

SUMMARY = "Library: typed package (py.typed), public API in __init__, no runtime dependencies."
DEFAULT_DESCRIPTION = "A small typed Python library."

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
classifiers = [
    "Typing :: Typed",
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["@@package@@*"]

[tool.setuptools.package-data]
@@package@@ = ["py.typed"]

'''
    + TOOL_CONFIG
)

INIT = '''\
"""@@description_py@@"""

from .core import clamp

__all__ = ["__version__", "clamp"]

__version__ = "0.1.0"
'''

CORE = '''\
"""Core functionality of @@name@@."""

from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` limited to the inclusive range [low, high].

    Replace this with the real API of your library.

    Raises:
        ValueError: if ``low`` is greater than ``high``.
    """
    if low > high:
        raise ValueError(f"low ({low}) must not be greater than high ({high})")
    return max(low, min(value, high))
'''

TEST_CORE = '''\
import pytest

import @@package@@
from @@package@@ import clamp


def test_value_inside_range_is_unchanged() -> None:
    assert clamp(5, 0, 10) == 5


def test_value_is_limited_to_the_bounds() -> None:
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10


def test_bounds_are_inclusive() -> None:
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


def test_inverted_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be greater"):
        clamp(1, 10, 0)


def test_public_api_is_exported() -> None:
    assert "clamp" in @@package@@.__all__
    assert @@package@@.__version__
'''

README = '''\
# @@name@@

**@@description@@**

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```python
from @@package@@ import clamp

clamp(15, 0, 10)  # 10
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
    "@@package@@/core.py": CORE,
    "@@package@@/py.typed": "",
    "tests/__init__.py": "",
    "tests/test_core.py": TEST_CORE,
}
