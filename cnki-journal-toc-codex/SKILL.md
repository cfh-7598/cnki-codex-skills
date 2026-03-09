---
name: cnki-journal-toc-codex
description: Browse CNKI journal issues and tables of contents from Codex through an existing Chrome CDP session. Use when Codex needs the paper list for a specific issue, or needs to open the original TOC reader for a journal issue.
---

# CNKI Journal TOC (Codex)

Use this skill for issue-level browsing.

## Run

```bash
python3 scripts/run.py \
  --query "计算机学报" \
  --year 2025 \
  --issue 01
```

Open the original TOC reader:

```bash
python3 scripts/run.py \
  --query "计算机学报" \
  --year 2025 \
  --issue 01 \
  --download
```

## Notes

- `--download` opens the reader page for the original TOC. CNKI login and browser download settings still control the final file download.
