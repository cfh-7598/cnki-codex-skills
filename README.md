# CNKI Codex Skills

Codex-native CNKI skills for literature search, paper metadata extraction, journal lookup, TOC browsing, download triggering, and citation export through an existing Chrome CDP session.

## What is included

- 10 focused Codex skills
- 1 thin routing skill: `cnki-codex`
- Shared Python implementation under `_shared/cnki/`
- Zotero export support through the local Connector API

## Skills

- `cnki-codex`
- `cnki-search-codex`
- `cnki-advanced-search-codex`
- `cnki-parse-results-codex`
- `cnki-paper-detail-codex`
- `cnki-navigate-pages-codex`
- `cnki-journal-search-codex`
- `cnki-journal-index-codex`
- `cnki-journal-toc-codex`
- `cnki-download-codex`
- `cnki-export-codex`

## Requirements

- Python 3.11+
- Playwright for Python
- Google Chrome started with remote debugging enabled
- Manual CNKI login in the connected Chrome session
- Zotero desktop app for `zotero` export mode

## Quick start

Start Chrome with remote debugging:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

Run the shared CLI directly:

```bash
python3 _shared/cnki/cli.py search --query "人工智能"
python3 _shared/cnki/cli.py journal-search --query "计算机学报"
```

Or invoke a specific skill from Codex after installing this repository under your Codex skills directory.

## Notes

- CNKI captcha is detected but not solved automatically.
- The automation reuses the current browser session and does not bypass CNKI login or download permissions.
- Batch export operates on the current search results page.

## Credits

The selectors and workflow mapping were adapted from the public Claude-oriented project [`cookjohn/cnki-skills`](https://github.com/cookjohn/cnki-skills), then rewritten for Codex and Playwright/CDP.

