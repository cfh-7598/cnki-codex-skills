#!/usr/bin/env python3
"""Portable wrapper for the cnki-journal-search-codex skill."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "_shared" / "cnki"))

from skill_wrapper import run_skill  # type: ignore  # noqa: E402

run_skill("journal-search")
