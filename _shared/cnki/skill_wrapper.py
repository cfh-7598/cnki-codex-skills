"""Helpers for portable per-skill wrapper scripts."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys

GLOBAL_FLAGS_WITH_VALUE = {"--cdp-url"}
GLOBAL_FLAGS_NO_VALUE = {"--text"}


def run_skill(command: str) -> None:
    """Invoke the shared CLI while allowing global flags anywhere in argv."""

    root = Path(__file__).resolve().parents[2]
    cli = root / "_shared" / "cnki" / "cli.py"

    global_args: list[str] = []
    rest: list[str] = []
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        token = args[index]
        if token in GLOBAL_FLAGS_WITH_VALUE:
            if index + 1 >= len(args):
                rest.append(token)
            else:
                global_args.extend([token, args[index + 1]])
                index += 1
        elif any(token.startswith(flag + "=") for flag in GLOBAL_FLAGS_WITH_VALUE):
            global_args.append(token)
        elif token in GLOBAL_FLAGS_NO_VALUE:
            global_args.append(token)
        else:
            rest.append(token)
        index += 1

    sys.argv = [str(cli), *global_args, command, *rest]
    runpy.run_path(str(cli), run_name="__main__")

