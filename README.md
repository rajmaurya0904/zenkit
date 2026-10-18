# zenkit

**Generates a small Python project (command line tool, library or web service) with lint, tests and CI already wired up and already passing.**

Every new project starts with the same twenty minutes: copy a pyproject.toml from the last
one, fix the names, remember how the console script entry point is spelled, paste a CI
workflow, find out the first test run fails on an import. zenkit does that in one command, and
a built-in `verify` command generates each template from scratch and runs its linter, its tests
and its entry point, so the templates cannot quietly rot.

```console
$ zenkit new cli greeter --description "Greets people" --author "Ada Lovelace"
Creating cli project 'greeter' in greeter
  + .editorconfig
  + .github/workflows/ci.yml
  + .gitignore
  + LICENSE
  + README.md
  + greeter/__init__.py
  + greeter/__main__.py
  + greeter/cli.py
  + pyproject.toml
  + tests/__init__.py
  + tests/test_cli.py
11 file(s) written, 0 unchanged.
Next:
  cd greeter
  pip install -e ".[dev]"
  pytest -q && ruff check .

$ cd greeter && pytest -q && ruff check .
.......                                                                  [100%]
7 passed in 0.38s
All checks passed!

$ zenkit verify
verify cli
  ok    static checks
  ok    ruff check
  ok    pytest
  ok    python -m verify_cli --help
verify lib
  ok    static checks
  ok    ruff check
  ok    pytest
  ok    import package
verify web
  ok    static checks
  ok    ruff check
  ok    pytest
  ok    python -m verify_web --help
```

Running `new` again over an existing project never clobbers anything:

```console
$ zenkit new cli greeter
zenkit: error: refusing to overwrite existing files: LICENSE, README.md, greeter/__init__.py, greeter/cli.py, pyproject.toml (use --force to replace them)
```

## Install

zenkit is not on PyPI. Install it from a clone (Python 3.11 or newer, no runtime dependencies):

```bash
git clone https://github.com/rajmaurya0904/zenkit && cd zenkit
pip install -e .
```

## Usage

```bash
zenkit list                                  # the available templates: cli, lib, web
zenkit show web --file pyproject.toml        # print one generated file (omit --file for the list)
zenkit new lib my-lib --license bsd-3-clause --python 3.12 --git   # new directory, optional git init
zenkit init cli                              # generate into the current directory, named after it
```

`new` and `init` also take `--description`, `--author` and `--email` (the last two default to
your git config), `--no-ci`, `--dry-run` and `--force`. Exit codes: 0 success, 1 error (bad name,
refused overwrite), 2 bad usage, 3 `verify` found a failing template.

## How it works

- Each template is a set of file bodies and paths with `@@placeholder@@` markers, stored as
  Python strings in `zenkit/templates/`. Rendering fails loudly on an unknown placeholder, and a
  line holding only an empty optional placeholder (licence, authors) is dropped.
- **cli**: argparse entry point with `--version`, a console script, `python -m` support and tests
  that run the module in a subprocess. **lib**: typed package with `py.typed` and a public API.
  **web**: a dependency-free WSGI app with JSON routes, a `/health` endpoint and a dev server;
  its tests make real HTTP requests against it.
- Every project gets a pyproject.toml (pytest and ruff configured, setuptools flat layout), a
  `.gitignore`, an `.editorconfig`, a licence (MIT or BSD-3-Clause) and a GitHub Actions
  workflow that lints and tests on every Python version from your minimum to 3.13.
- Names are validated up front: lowercase words, at most 30 characters, no standard library or
  keyword clashes. Descriptions are capped at 72 characters. The caps exist because `verify`
  showed that longer values push generated lines past the 100-column lint limit.
- `verify` generates a template into a temp directory, checks that pyproject.toml parses and no
  placeholder survived, then runs `ruff check`, `pytest -q` and either `python -m <pkg> --help`
  or an import of the package.

## Limitations

zenkit generates Python projects only, and only three kinds. There is no plugin system or user
templates directory; adding a template means editing the package. The generated code is a
starting point (a greeting function, a `clamp` helper, two routes), not scaffolding for your
domain, and the web template is stdlib WSGI, not Flask or FastAPI.

`verify` runs lint, tests and `python -m`, but does not `pip install` the generated project, so
the console script itself is not exercised by it. It needs ruff and pytest in the same
interpreter (`pip install -e ".[dev]"` provides them). The generated GitHub Actions workflow is
checked only for leftover placeholders, not run on GitHub. Supported Python versions are 3.10 to
3.13, the only licences are MIT and BSD-3-Clause, and `--git` runs `git init -b main` but makes
no commit and adds no remote. The test suite runs on Windows locally and on Linux in CI; macOS
is untested.

## Development

```bash
pip install -e ".[dev]"
pytest -q          # roughly 30 seconds: the verify tests generate and check real projects
ruff check .
```

## Licence

MIT -- see [LICENSE](LICENSE).
