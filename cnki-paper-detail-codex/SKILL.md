---
name: cnki-paper-detail-codex
description: Extract detailed CNKI paper metadata from Codex through an existing Chrome CDP session. Use when Codex needs a paper title, author list, affiliations, abstract, keywords, fund information, journal, or publication details from a CNKI paper page.
---

# CNKI Paper Detail (Codex)

Use this skill for paper-level metadata extraction.

## Run

On the current paper page:

```bash
python3 scripts/run.py
```

On a specific URL:

```bash
python3 scripts/run.py --url "https://..."
```

## Return shape

Expect title, authors, affiliations, abstract, keywords, fund, classification, journal, and publication info.
