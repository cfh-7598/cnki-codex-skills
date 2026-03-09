#!/usr/bin/env python3
"""Portable wrapper for the cnki-parse-results-codex skill."""

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "_shared" / "cnki" / "cli.py"

sys.argv = [str(CLI), "parse-results", *sys.argv[1:]]
runpy.run_path(str(CLI), run_name="__main__")

