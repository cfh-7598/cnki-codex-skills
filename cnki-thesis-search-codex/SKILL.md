---
name: cnki-thesis-search-codex
description: Use when Codex needs CNKI thesis-only retrieval through an existing Chrome CDP session, including mixed doctoral and master results with structured metadata.
---

# CNKI Thesis Search (Codex)

Use this skill for CNKI thesis retrieval in mixed mode (doctoral + master).

## Run

```bash
python3 _shared/cnki/cli.py thesis-search \
  --query "干细胞治疗关节炎" \
  --degree both \
  --count 10
```

## Notes

- This command first switches to CNKI dissertation scope (`CDFD+CMFD`) and then collects thesis rows.
- Each item includes `degree` (`博士` or `硕士`) and the original CNKI result metadata.
