---
name: cnki-search-codex
description: Search CNKI papers from Codex through an existing Chrome CDP session. Use when Codex needs to find CNKI papers by keyword and return the current result page with structured titles, authors, journals, dates, citations, and download counts.
---

# CNKI Search (Codex)

Use this skill for first-pass CNKI literature search.

## Prerequisites

- Chrome must already be running with `--remote-debugging-port=9222`.
- CNKI captcha must be solved manually if it appears.

## Run

```bash
python3 _shared/cnki/cli.py search --query "人工智能"
```

The shared runtime forces the normal search entry back to `总库 + 中文` before submitting the query, so it does not drift into foreign-mode search.

## Return shape

Expect JSON with:

- `status`
- `message`
- `data.total`
- `data.page`
- `data.items`

## Follow-on

- Use `$cnki-parse-results-codex` if the user already has a result page open.
- Use `$cnki-paper-detail-codex` for a specific paper URL.
- Use `$cnki-collect-details-codex` when the user wants abstracts, keywords, fund info, or other detail-page fields returned in batch.
- Use `$cnki-navigate-pages-codex` to paginate or sort.
