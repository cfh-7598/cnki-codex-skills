---
name: cnki-collect-details-codex
description: Use when Codex needs CNKI search results enriched in batch with abstracts, keywords, fund information, or thesis detail metadata through an existing Chrome CDP session.
---

# CNKI Collect Details (Codex)

Use this skill when plain result rows are not enough and the user wants detail-page fields returned in batch.

## Run

Normal literature:

```bash
python3 _shared/cnki/cli.py collect-details \
  --query "干细胞治疗关节炎" \
  --count 10
```

Doctoral theses only:

```bash
python3 _shared/cnki/cli.py collect-details \
  --query "干细胞治疗关节炎" \
  --scope theses \
  --degree doctoral \
  --count 10
```

## Notes

- Normal literature mode always resets CNKI to `总库 + 中文` before searching.
- Thesis mode reuses dissertation search and supports `both`, `doctoral`, and `master`.
- Each returned item keeps the result-row fields and adds `abstract`, `keywords`, `fund`, `classification`, `affiliations`, `detailAuthors`, `pubInfo`, and nested `detail`.
- If a specific detail page fails while batch collection continues, the item includes `detailError`.
