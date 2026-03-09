---
name: cnki-advanced-search-codex
description: Run filtered CNKI searches from Codex through an existing Chrome CDP session. Use when Codex needs author, journal, date-range, field-type, or source-category filters such as SCI, EI, CSSCI, 北大核心, or CSCD.
---

# CNKI Advanced Search (Codex)

Use this skill when keyword search is too broad and CNKI filters matter.

## Run

```bash
python3 /Users/cfh/Nutstore\ Files/code/skill/codex-skills/_shared/cnki/cli.py advanced-search \
  --query "人工智能" \
  --source CSSCI \
  --start-year 2020 \
  --end-year 2025
```

## Useful flags

- `--field-type SU|TI|KY|TKA|AB`
- `--query2 "..."`
- `--row-logic AND|OR|NOT`
- `--author "..."`
- `--journal "..."`
- `--source SCI|EI|hx|CSSCI|CSCD`

## Notes

- This skill uses the old CNKI advanced search page because that page still exposes source-category checkboxes.
- Return data includes both the result list and the applied filters.

