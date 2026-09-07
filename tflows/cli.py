"""Command-line interface for tflows.

Usage::

    tflows check bot.flow
    tflows check scripts/
    tflows --version
"""

from __future__ import annotations

import argparse
import os
import sys

from .diagnostics import check_file, check_source, format_diagnostics
from .version import __version__


def _iter_scripts(paths: list[str]) -> list[str]:
    found = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for name in files:
                    if name.endswith((".flow", ".tflow")):
                        found.append(os.path.join(root, name))
        else:
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tflows", description="tflows scripting tools")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    check_p = sub.add_parser("check", help="validate .flow scripts without running the bot")
    check_p.add_argument("paths", nargs="+", help="script files or directories")

    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.command == "check":
        return _cmd_check(args.paths)
    parser.print_help()
    return 0


def _cmd_check(paths: list[str]) -> int:
    any_error = False
    files = _iter_scripts(paths)
    if not files:
        print("No script files found.")
        return 1
    for path in files:
        diagnostics = check_file(path)
        errors = [d for d in diagnostics if d.severity == "error"]
        if diagnostics:
            print(format_diagnostics(diagnostics))
            print()
        else:
            print(f"{path}: ok")
        if errors:
            any_error = True
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
