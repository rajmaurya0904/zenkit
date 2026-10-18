"""Command line interface: ``zenkit list | show | new | init | verify``."""

from __future__ import annotations

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .errors import ZenkitError
from .generate import PlannedFile, plan_writes, render_project, write_files
from .render import DEFAULT_PYTHON, LICENSE_CHOICES, PYTHON_VERSIONS, Context
from .templates import TEMPLATES, get_template
from .verify import StepResult, verify

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2  # argparse's own exit code for bad usage
EXIT_VERIFY_FAILED = 3

SHOW_DEMO_NAME = "my-project"


def _git_config(key: str) -> str:
    """Return a value from the user's git config, or '' if git or the key is missing."""
    if shutil.which("git") is None:
        return ""
    try:
        proc = subprocess.run(
            ["git", "config", "--get", key],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _add_project_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--description", help="one-line description (default depends on kind)")
    parser.add_argument("--author", help="author name (default: git config user.name)")
    parser.add_argument("--email", help="author email (default: git config user.email)")
    parser.add_argument(
        "--license", choices=LICENSE_CHOICES, default="mit", help="licence to generate"
    )
    parser.add_argument(
        "--python",
        choices=PYTHON_VERSIONS,
        default=DEFAULT_PYTHON,
        help=f"oldest supported Python (default: {DEFAULT_PYTHON})",
    )
    parser.add_argument("--no-ci", action="store_true", help="skip the GitHub Actions workflow")
    parser.add_argument("--git", action="store_true", help="run `git init -b main` afterwards")
    parser.add_argument(
        "--force", action="store_true", help="overwrite existing files whose content differs"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would be written, write nothing"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zenkit",
        description="Generate minimal Python projects with lint, test and CI already wired up.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    sub.add_parser("list", help="list the available templates")

    show = sub.add_parser("show", help="show the files a template generates")
    show.add_argument("kind", choices=sorted(TEMPLATES))
    show.add_argument("--file", help="print one generated file instead of the file list")

    new = sub.add_parser("new", help="create a new project directory")
    new.add_argument("kind", choices=sorted(TEMPLATES))
    new.add_argument("name", help="project name, e.g. my-tool")
    new.add_argument("--dir", default=".", help="parent directory (default: current directory)")
    _add_project_options(new)

    init = sub.add_parser("init", help="generate into the current directory")
    init.add_argument("kind", choices=sorted(TEMPLATES))
    init.add_argument("--name", help="project name (default: derived from the directory name)")
    _add_project_options(init)

    check = sub.add_parser(
        "verify", help="generate templates in a temp dir and run their lint, tests and entry point"
    )
    check.add_argument("kinds", nargs="*", metavar="kind", help="templates to check (default: all)")
    check.add_argument("--keep", action="store_true", help="keep the generated projects")
    return parser


def _name_from_directory(path: Path) -> str:
    raw = path.resolve().name.lower()
    return re.sub(r"[\s.]+", "-", raw).strip("-_")


def _context_from_args(args: argparse.Namespace, name: str) -> Context:
    template = get_template(args.kind)
    author = args.author if args.author is not None else _git_config("user.name")
    email = args.email if args.email is not None else _git_config("user.email")
    return Context(
        kind=args.kind,
        name=name,
        description=args.description or template.default_description,
        author=author,
        email=email,
        license=args.license,
        python_min=args.python,
        year=datetime.date.today().year,
        ci=not args.no_ci,
    )


def _print_plan(planned: list[PlannedFile], *, dry_run: bool, force: bool) -> None:
    for item in planned:
        if item.status == "new":
            marker = "+"
        elif item.status == "identical":
            marker = "="
        else:
            marker = "!" if force or dry_run else "x"
        suffix = ""
        if item.status == "identical":
            suffix = "  (unchanged)"
        elif item.status == "conflict":
            suffix = "  (exists, differs)"
        print(f"  {marker} {item.path}{suffix}")


def _git_init(root: Path) -> None:
    if (root / ".git").exists():
        print("git: repository already exists, left alone")
        return
    if shutil.which("git") is None:
        print("warning: git is not installed, skipped `git init`", file=sys.stderr)
        return
    proc = subprocess.run(
        ["git", "init", "-b", "main"], cwd=root, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        print(f"warning: git init failed: {proc.stderr.strip()}", file=sys.stderr)
    else:
        print("git: initialised repository on branch main")


def _generate(args: argparse.Namespace, root: Path, name: str) -> int:
    ctx = _context_from_args(args, name)
    planned = plan_writes(root, render_project(ctx))
    verb = "Would create" if args.dry_run else "Creating"
    print(f"{verb} {ctx.kind} project {ctx.name!r} in {root}")
    _print_plan(planned, dry_run=args.dry_run, force=args.force)
    if args.dry_run:
        return EXIT_OK
    written = write_files(root, planned, force=args.force)
    print(f"{len(written)} file(s) written, {len(planned) - len(written)} unchanged.")
    if args.git:
        _git_init(root)
    here = root.resolve() == Path.cwd().resolve()
    print("Next:")
    if not here:
        print(f"  cd {root}")
    print('  pip install -e ".[dev]"')
    print("  pytest -q && ruff check .")
    return EXIT_OK


def cmd_list(_: argparse.Namespace) -> int:
    width = max(len(kind) for kind in TEMPLATES)
    for kind, template in sorted(TEMPLATES.items()):
        print(f"{kind:<{width}}  {template.summary}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    template = get_template(args.kind)
    ctx = Context(
        kind=args.kind,
        name=SHOW_DEMO_NAME,
        description=template.default_description,
        author="Your Name",
    )
    files = render_project(ctx)
    if args.file:
        if args.file not in files:
            known = ", ".join(files)
            raise ZenkitError(f"{args.file!r} is not generated by {args.kind}; files: {known}")
        sys.stdout.write(files[args.file])
        return EXIT_OK
    print(f"{args.kind}: {template.summary}")
    width = max(len(path) for path in files)
    for path, body in files.items():
        lines = len(body.splitlines())
        print(f"  {path:<{width}}  {lines:>4} lines")
    return EXIT_OK


def cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.dir) / args.name
    if root.exists() and not root.is_dir():
        raise ZenkitError(f"{root} exists and is not a directory")
    return _generate(args, root, args.name)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    name = args.name or _name_from_directory(root)
    return _generate(args, root, name)


def cmd_verify(args: argparse.Namespace) -> int:
    kinds = args.kinds or sorted(TEMPLATES)
    failed = False
    for kind in kinds:
        template = get_template(kind)
        ctx = Context(kind=kind, name=f"verify-{kind}", description=template.default_description)
        print(f"verify {kind}")

        def show_step(step: StepResult) -> None:
            print(f"  {'ok  ' if step.ok else 'FAIL'}  {step.name}")
            if not step.ok and step.detail:
                for line in step.detail.splitlines():
                    print(f"        {line}")

        report = verify(ctx, on_step=show_step)
        if not report.ok:
            failed = True
        if args.keep:
            print(f"  kept at {report.project_dir}")
        else:
            report.cleanup()
    return EXIT_VERIFY_FAILED if failed else EXIT_OK


COMMANDS = {
    "list": cmd_list,
    "show": cmd_show,
    "new": cmd_new,
    "init": cmd_init,
    "verify": cmd_verify,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on a reported error, 2 on bad usage, 3 if a
    template fails ``verify``."""
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except ZenkitError as exc:
        print(f"zenkit: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except OSError as exc:
        print(f"zenkit: error: {exc}", file=sys.stderr)
        return EXIT_ERROR
