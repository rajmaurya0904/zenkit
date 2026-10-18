import pytest

from zenkit.errors import TemplateError, ZenkitError
from zenkit.render import Context, render_text, substitute


def make(**overrides: object) -> Context:
    base: dict[str, object] = {"kind": "cli", "name": "demo-tool", "description": "Does a thing."}
    base.update(overrides)
    return Context(**base)  # type: ignore[arg-type]


def test_substitute_replaces_all_occurrences() -> None:
    assert substitute("@@a@@-@@b@@-@@a@@", {"a": "1", "b": "2"}) == "1-2-1"


def test_substitute_unknown_placeholder_is_a_template_error() -> None:
    with pytest.raises(TemplateError, match="@@nope@@"):
        substitute("x @@nope@@", {})


def test_substitute_leaves_github_expressions_alone() -> None:
    text = "python-version: ${{ matrix.python-version }}"
    assert substitute(text, {}) == text


def test_empty_whole_line_placeholder_drops_the_line() -> None:
    text = "one\n@@maybe@@\ntwo\n"
    assert render_text(text, {"maybe": ""}) == "one\ntwo\n"
    assert render_text(text, {"maybe": "mid"}) == "one\nmid\ntwo\n"


def test_empty_placeholder_inside_a_line_is_kept_as_empty() -> None:
    assert render_text("a=@@x@@;\n", {"x": ""}) == "a=;\n"


def test_variables_derive_package_and_tags() -> None:
    v = make(python_min="3.12").variables()
    assert v["package"] == "demo_tool"
    assert v["py_tag"] == "py312"
    assert v["ci_matrix"] == '["3.12", "3.13"]'


def test_ci_matrix_spans_from_minimum_to_latest() -> None:
    assert make(python_min="3.10").variables()["ci_matrix"] == '["3.10", "3.11", "3.12", "3.13"]'


def test_author_and_email_lines() -> None:
    assert make().variables()["authors_line"] == ""
    assert make(author="Ada").variables()["authors_line"] == 'authors = [{ name = "Ada" }]'
    both = make(author="Ada", email="ada@example.com").variables()["authors_line"]
    assert both == 'authors = [{ name = "Ada", email = "ada@example.com" }]'


def test_toml_and_python_escaping_of_quotes_and_backslashes() -> None:
    v = make(description='Say "hi" \\ bye').variables()
    assert v["description_toml"] == 'Say \\"hi\\" \\\\ bye'
    assert v["description_py"] == 'Say \\"hi\\" \\\\ bye'


def test_license_variables() -> None:
    assert make(license="mit").variables()["license_line"] == 'license = { text = "MIT" }'
    none = make(license="none").variables()
    assert none["license_line"] == "" and none["license_section"] == ""


def test_holder_falls_back_to_project_name() -> None:
    assert make().variables()["holder"] == "demo-tool"
    assert make(author="Ada").variables()["holder"] == "Ada"


@pytest.mark.parametrize(
    "overrides",
    [
        {"license": "gpl"},
        {"python_min": "3.8"},
        {"description": ""},
        {"description": "two\nlines"},
        {"author": "a\nb"},
        {"name": "Bad Name"},
    ],
)
def test_context_rejects_bad_input(overrides: dict[str, object]) -> None:
    with pytest.raises(ZenkitError):
        make(**overrides)
