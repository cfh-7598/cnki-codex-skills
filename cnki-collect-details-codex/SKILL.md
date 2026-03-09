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

Force serial detail collection:

```bash
python3 _shared/cnki/cli.py collect-details \
  --query "干细胞治疗关节炎" \
  --count 10 \
  --concurrency-mode serial
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
- Adaptive detail collection is the default. It starts conservatively, increases concurrency only after repeated healthy detail fetches, and falls back to single-page mode when CNKI shows risk signals.
- Optional tuning flags are `--concurrency-mode`, `--max-concurrency`, `--min-delay-ms`, and `--max-delay-ms`.
- Each returned item keeps the result-row fields and adds `abstract`, `keywords`, `fund`, `classification`, `affiliations`, `detailAuthors`, `pubInfo`, and nested `detail`.
- If a specific detail page fails while batch collection continues, the item includes `detailError`.
