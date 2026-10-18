import pytest

from zenkit.errors import ZenkitError
from zenkit.names import MAX_NAME_LENGTH, package_name, validate_name


@pytest.mark.parametrize("name", ["tool", "my-tool", "my_tool", "a1", "web-app-2", "x"])
def test_valid_names_are_accepted(name: str) -> None:
    assert validate_name(name) == name


@pytest.mark.parametrize(
    "name",
    ["", "Tool", "1tool", "-tool", "tool-", "my--tool", "my__tool", "my tool", "my.tool", "é"],
)
def test_invalid_names_are_rejected(name: str) -> None:
    with pytest.raises(ZenkitError):
        validate_name(name)


def test_overlong_name_is_rejected() -> None:
    with pytest.raises(ZenkitError, match="limit"):
        validate_name("a" * (MAX_NAME_LENGTH + 1))
    assert validate_name("a" * MAX_NAME_LENGTH)


def test_package_name_replaces_hyphens() -> None:
    assert package_name("my-cool-tool") == "my_cool_tool"
    assert package_name("plain") == "plain"


@pytest.mark.parametrize("name", ["json", "os", "test", "tests", "zenkit", "src"])
def test_package_name_rejects_clashing_names(name: str) -> None:
    with pytest.raises(ZenkitError):
        package_name(name)


def test_package_name_rejects_keywords() -> None:
    with pytest.raises(ZenkitError, match="keyword"):
        package_name("class")
