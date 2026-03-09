---
name: cnki-journal-index-codex
description: Extract CNKI journal indexing and evaluation data from Codex through an existing Chrome CDP session. Use when Codex needs to check whether a journal is listed in 北大核心, CSSCI, CSCD, SCI, EI, or related databases, and capture impact factors and core metadata.
---

# CNKI Journal Index (Codex)

Use this skill for journal-level quality and indexing checks.

## Run

Search by journal name:

```bash
python3 scripts/run.py --query "计算机学报"
```

Or open a known CNKI journal URL:

```bash
python3 scripts/run.py --url "https://..."
```

## Return shape

Expect Chinese and English journal names, indexing tags, ISSN, CN, sponsor, frequency, and impact metrics.
