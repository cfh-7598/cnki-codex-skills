---
name: cnki-navigate-pages-codex
description: Move through CNKI result pages or change result sorting from Codex through an existing Chrome CDP session. Use when Codex needs the next page, a specific page, or a different sort order such as date, citations, downloads, relevance, or comprehensive ranking.
---

# CNKI Navigate Pages (Codex)

Use this skill only on an existing CNKI result page.

## Run

Go to the next page:

```bash
python3 scripts/run.py --action next
```

Go to page 3:

```bash
python3 scripts/run.py --page 3
```

Sort by date:

```bash
python3 scripts/run.py --sort-by date
```
