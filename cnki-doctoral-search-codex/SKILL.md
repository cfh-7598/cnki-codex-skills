---
name: cnki-doctoral-search-codex
description: Use when Codex needs CNKI doctoral thesis retrieval only through an existing Chrome CDP session, excluding master dissertations.
---

# CNKI Doctoral Thesis Search (Codex)

Use this skill when the user needs doctoral dissertations only.

## Run

```bash
python3 _shared/cnki/cli.py thesis-search \
  --query "干细胞治疗关节炎" \
  --degree doctoral \
  --count 10
```

## Notes

- The command uses CNKI dissertation scope and keeps only doctoral (`博士`) rows.
- If CNKI has fewer doctoral hits than requested, it returns the available subset.
