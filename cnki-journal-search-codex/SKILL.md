---
name: cnki-journal-search-codex
description: Search CNKI journals from Codex through an existing Chrome CDP session. Use when Codex needs to find journals by name, ISSN, CN number, or sponsor and return journal result cards with links and summary metrics.
---

# CNKI Journal Search (Codex)

Use this skill for journal discovery before deeper indexing or TOC work.

## Run

```bash
python3 scripts/run.py --query "计算机学报"
```

## Notes

- The command auto-detects ISSN and CN-number style queries.
- Use `$cnki-journal-index-codex` for indexing status.
- Use `$cnki-journal-toc-codex` for issue browsing.
