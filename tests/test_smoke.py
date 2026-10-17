"""Smoke test: package imports cleanly. Replace/extend as modules land."""

import zenkit


def test_version_is_set() -> None:
    assert zenkit.__version__
