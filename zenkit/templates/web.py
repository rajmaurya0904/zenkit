"""The ``web`` template: a dependency-free WSGI service with JSON routes and a dev server."""

from __future__ import annotations

from .common import TOOL_CONFIG

SUMMARY = "Web service: standard-library WSGI app, JSON routes, /health, `python -m` dev server."
DEFAULT_DESCRIPTION = "A small WSGI web service."

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
@@name@@ = "@@package@@.server:main"

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

APP = '''\
"""The WSGI application for @@name@@."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from . import __version__

StartResponse = Callable[..., Any]
Handler = Callable[[], tuple[int, dict[str, Any]]]

_STATUS_TEXT = {200: "200 OK", 404: "404 Not Found", 405: "405 Method Not Allowed"}


def index() -> tuple[int, dict[str, Any]]:
    return 200, {"app": "@@name@@", "version": __version__}


def health() -> tuple[int, dict[str, Any]]:
    return 200, {"status": "ok"}


# path -> handler. Only GET (and HEAD) are routed; add methods as your service grows.
ROUTES: dict[str, Handler] = {
    "/": index,
    "/health": health,
}


def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
    """WSGI entry point: dispatch on the request path, always answer with JSON."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/") or "/"
    extra_headers: list[tuple[str, str]] = []

    handler = ROUTES.get(path)
    if handler is None:
        code, payload = 404, {"error": f"no route for {path}"}
    elif method not in ("GET", "HEAD"):
        code, payload = 405, {"error": f"{method} is not allowed on {path}"}
        extra_headers.append(("Allow", "GET, HEAD"))
    else:
        code, payload = handler()

    body = json.dumps(payload).encode("utf-8")
    start_response(
        _STATUS_TEXT[code],
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            *extra_headers,
        ],
    )
    return [] if method == "HEAD" else [body]
'''

SERVER = '''\
"""Development server: ``@@name@@`` or ``python -m @@package@@``."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from wsgiref.simple_server import make_server

from . import __version__
from .app import app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="@@name@@", description="@@description_py@@")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Serve the app with wsgiref until interrupted. For development only."""
    args = build_parser().parse_args(argv)
    with make_server(args.host, args.port, app) as server:
        print(f"serving on http://{args.host}:{args.port}/ (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopped")
    return 0
'''

MAIN = '''\
"""Allow ``python -m @@package@@``."""

from .server import main

raise SystemExit(main())
'''

TEST_APP = '''\
import json
from typing import Any
from wsgiref.util import setup_testing_defaults

from @@package@@ import __version__
from @@package@@.app import app


def call(path: str, method: str = "GET") -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, Any] = {"REQUEST_METHOD": method, "PATH_INFO": path}
    setup_testing_defaults(environ)
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


def test_index_reports_name_and_version() -> None:
    status, headers, body = call("/")
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body) == {"app": "@@name@@", "version": __version__}


def test_health_endpoint() -> None:
    status, _, body = call("/health")
    assert status == "200 OK"
    assert json.loads(body) == {"status": "ok"}


def test_unknown_path_is_a_json_404() -> None:
    status, _, body = call("/missing")
    assert status == "404 Not Found"
    assert "/missing" in json.loads(body)["error"]


def test_post_is_rejected_with_allow_header() -> None:
    status, headers, _ = call("/health", method="POST")
    assert status == "405 Method Not Allowed"
    assert headers["Allow"] == "GET, HEAD"


def test_head_has_length_but_no_body() -> None:
    status, headers, body = call("/health", method="HEAD")
    assert status == "200 OK"
    assert int(headers["Content-Length"]) > 0
    assert body == b""
'''

TEST_SERVER = '''\
import pytest

from @@package@@.server import build_parser


def test_defaults() -> None:
    args = build_parser().parse_args([])
    assert (args.host, args.port) == ("127.0.0.1", 8000)


def test_port_must_be_an_integer() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--port", "abc"])
    assert exc.value.code == 2
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
@@name@@ --port 8000        # or: python -m @@package@@
curl http://127.0.0.1:8000/health
```

The app is a plain WSGI callable, `@@package@@.app:app`, so it also runs under gunicorn or
any other WSGI server.

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
    "@@package@@/app.py": APP,
    "@@package@@/server.py": SERVER,
    "tests/__init__.py": "",
    "tests/test_app.py": TEST_APP,
    "tests/test_server.py": TEST_SERVER,
}
