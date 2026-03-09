---
name: cnki-master-search-codex
description: Use when Codex needs CNKI master thesis retrieval only through an existing Chrome CDP session, excluding doctoral dissertations.
---

# CNKI Master Thesis Search (Codex)

Use this skill when the user needs master dissertations only.

## Run

```bash
python3 _shared/cnki/cli.py thesis-search \
  --query "干细胞治疗关节炎" \
  --degree master \
  --count 10
```

## Notes

- The command uses CNKI dissertation scope and keeps only master (`硕士`) rows.
- If CNKI has fewer master hits than requested, it returns the available subset.
