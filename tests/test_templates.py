import pytest

from zenkit.errors import ZenkitError
from zenkit.templates import TEMPLATES, get_template, template_files


def test_three_kinds_are_registered() -> None:
    assert set(TEMPLATES) == {"cli", "lib", "web"}


def test_unknown_kind_lists_the_alternatives() -> None:
    with pytest.raises(ZenkitError, match="cli, lib, web"):
        get_template("desktop")


@pytest.mark.parametrize("kind", sorted(TEMPLATES))
def test_every_template_has_a_summary_and_short_default_description(kind: str) -> None:
    template = get_template(kind)
    assert template.summary
    assert 0 < len(template.default_description) <= 72


@pytest.mark.parametrize("kind", sorted(TEMPLATES))
def test_every_template_ships_tests_and_pyproject(kind: str) -> None:
    files = template_files(kind)
    assert "pyproject.toml" in files
    assert "tests/__init__.py" in files
    assert any(path.startswith("tests/test_") for path in files)


def test_license_and_ci_flags_control_optional_files() -> None:
    assert "LICENSE" in template_files("cli", license="mit")
    assert "LICENSE" not in template_files("cli", license="none")
    assert ".github/workflows/ci.yml" in template_files("cli", ci=True)
    assert ".github/workflows/ci.yml" not in template_files("cli", ci=False)
