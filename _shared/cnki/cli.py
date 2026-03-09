"""Unified CLI entry point for Codex CNKI skills."""

from __future__ import annotations

import argparse
import json
from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import fail, ok, run_async  # type: ignore
    from journal import journal_index, journal_search, journal_toc  # type: ignore
    from paper import download, export, paper_detail  # type: ignore
    from search import advanced_search, collect_details, navigate_pages, parse_results, search, thesis_search  # type: ignore
    from zotero import ZoteroError  # type: ignore
else:
    from .browser import fail, ok, run_async
    from .journal import journal_index, journal_search, journal_toc
    from .paper import download, export, paper_detail
    from .search import advanced_search, collect_details, navigate_pages, parse_results, search, thesis_search
    from .zotero import ZoteroError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex CNKI automation CLI")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="Chrome CDP endpoint to connect to.")
    parser.add_argument("--text", action="store_true", help="Emit a compact text summary instead of JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search CNKI by keyword.")
    search_parser.add_argument("--query", required=True)

    thesis_parser = subparsers.add_parser(
        "thesis-search",
        help="Search CNKI theses and filter by doctoral/master degree.",
    )
    thesis_parser.add_argument("--query", required=True)
    thesis_parser.add_argument(
        "--degree",
        choices=["both", "doctoral", "master"],
        default="both",
        help="Degree scope: doctoral (CDFD), master (CMFD), or both.",
    )
    thesis_parser.add_argument("--count", type=int, default=20, help="Number of thesis records to collect.")
    thesis_parser.add_argument("--max-pages", type=int, default=20, help="Maximum results pages to scan.")

    collect_parser = subparsers.add_parser(
        "collect-details",
        help="Search CNKI and enrich results with abstract, keywords, fund, and detail metadata.",
    )
    collect_parser.add_argument("--query", required=True)
    collect_parser.add_argument("--count", type=int, default=10, help="Number of enriched records to collect.")
    collect_parser.add_argument("--max-pages", type=int, default=20, help="Maximum results pages to scan.")
    collect_parser.add_argument("--scope", choices=["papers", "theses"], default="papers")
    collect_parser.add_argument(
        "--degree",
        choices=["both", "doctoral", "master"],
        default="both",
        help="Degree scope when --scope theses is used.",
    )
    collect_parser.add_argument(
        "--concurrency-mode",
        choices=["serial", "adaptive"],
        default="adaptive",
        help="Detail-page collection mode. Adaptive is the default safer batch mode.",
    )
    collect_parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="Maximum detail-page worker count when adaptive mode is used.",
    )
    collect_parser.add_argument(
        "--min-delay-ms",
        type=int,
        default=300,
        help="Minimum randomized delay before each detail-page request.",
    )
    collect_parser.add_argument(
        "--max-delay-ms",
        type=int,
        default=1200,
        help="Maximum randomized delay before each detail-page request.",
    )

    advanced_parser = subparsers.add_parser("advanced-search", help="Run an advanced CNKI search.")
    advanced_parser.add_argument("--query", required=True)
    advanced_parser.add_argument("--field-type", default="SU", choices=["SU", "TI", "KY", "TKA", "AB"])
    advanced_parser.add_argument("--query2")
    advanced_parser.add_argument("--field-type2", default="KY", choices=["SU", "TI", "KY", "TKA", "AB"])
    advanced_parser.add_argument("--row-logic", default="AND", choices=["AND", "OR", "NOT"])
    advanced_parser.add_argument("--source", action="append", choices=["SCI", "EI", "hx", "CSSCI", "CSCD"])
    advanced_parser.add_argument("--start-year")
    advanced_parser.add_argument("--end-year")
    advanced_parser.add_argument("--author")
    advanced_parser.add_argument("--journal")

    subparsers.add_parser("parse-results", help="Parse the current CNKI results page.")

    detail_parser = subparsers.add_parser("paper-detail", help="Extract CNKI paper details.")
    detail_parser.add_argument("--url")

    nav_parser = subparsers.add_parser("navigate-pages", help="Navigate or sort CNKI result pages.")
    nav_parser.add_argument("--action", choices=["next", "previous"])
    nav_parser.add_argument("--page", type=int)
    nav_parser.add_argument("--sort-by", choices=["relevance", "date", "citations", "downloads", "comprehensive"])

    journal_search_parser = subparsers.add_parser("journal-search", help="Search CNKI journals.")
    journal_search_parser.add_argument("--query", required=True)

    journal_index_parser = subparsers.add_parser("journal-index", help="Extract CNKI journal indexing details.")
    journal_index_parser.add_argument("--query")
    journal_index_parser.add_argument("--url")

    journal_toc_parser = subparsers.add_parser("journal-toc", help="Browse CNKI journal issues and TOCs.")
    journal_toc_parser.add_argument("--query")
    journal_toc_parser.add_argument("--url")
    journal_toc_parser.add_argument("--year")
    journal_toc_parser.add_argument("--issue")
    journal_toc_parser.add_argument("--download", action="store_true")

    download_parser = subparsers.add_parser("download", help="Trigger a CNKI PDF or CAJ download.")
    download_parser.add_argument("--url")
    download_parser.add_argument("--format", choices=["pdf", "caj"], default="pdf")

    export_parser = subparsers.add_parser("export", help="Export CNKI citations or send them to Zotero.")
    export_parser.add_argument("--url")
    export_parser.add_argument("--mode", choices=["zotero", "ris", "gb"], default="zotero")
    export_parser.add_argument("--all-current-page", action="store_true")
    export_parser.add_argument("--index", type=int, action="append", help="1-based result index on the current results page.")

    return parser


def summarize(result: dict[str, Any]) -> str:
    if result["status"] == "error":
        return f'{result["error"]}: {result["message"]}'
    if result["status"] == "blocked":
        return result["message"]
    if result["status"] == "partial":
        return result["message"]
    data = result.get("data")
    if isinstance(data, dict):
        if "items" in data:
            return f'{result["message"]} {len(data["items"])} item(s).'
        if "title" in data:
            return f'{result["message"]} {data["title"]}'
        if "nameCN" in data:
            return f'{result["message"]} {data["nameCN"]}'
        if "paperCount" in data:
            return f'{result["message"]} {data["paperCount"]} paper(s).'
    if isinstance(data, list):
        return f'{result["message"]} {len(data)} record(s).'
    return result["message"]


def dispatch(args) -> dict[str, Any]:
    try:
        if args.command == "search":
            return run_async(search, args)
        if args.command == "thesis-search":
            return run_async(thesis_search, args)
        if args.command == "collect-details":
            return run_async(collect_details, args)
        if args.command == "advanced-search":
            return run_async(advanced_search, args)
        if args.command == "parse-results":
            return run_async(parse_results, args)
        if args.command == "paper-detail":
            return run_async(paper_detail, args)
        if args.command == "navigate-pages":
            return run_async(navigate_pages, args)
        if args.command == "journal-search":
            return run_async(journal_search, args)
        if args.command == "journal-index":
            if not args.query and not args.url:
                return fail("not_found", "Provide --query or --url for journal-index.")
            return run_async(journal_index, args)
        if args.command == "journal-toc":
            if not args.query and not args.url:
                return fail("not_found", "Provide --query or --url for journal-toc.")
            return run_async(journal_toc, args)
        if args.command == "download":
            return run_async(download, args)
        if args.command == "export":
            return run_async(export, args)
        return fail("not_found", f"Unsupported command: {args.command}")
    except ZoteroError as exc:
        return fail(exc.code, exc.message)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = dispatch(args)
    if args.text:
        print(summarize(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
