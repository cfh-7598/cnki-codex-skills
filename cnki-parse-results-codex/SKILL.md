---
name: cnki-parse-results-codex
description: Parse the current CNKI result page from Codex through an existing Chrome CDP session. Use when the user already has a CNKI results page open and Codex should extract structured paper data without rerunning the search.
---

# CNKI Parse Results (Codex)

Use this skill only when a CNKI result page is already open in the connected Chrome session.

## Run

```bash
python3 /Users/cfh/Nutstore\ Files/code/skill/codex-skills/_shared/cnki/cli.py parse-results
```

## Notes

- The command fails with `page_not_supported` if the current page is not a CNKI results page.
- Use `$cnki-search-codex` if no result page exists yet.

