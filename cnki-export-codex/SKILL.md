---
name: cnki-export-codex
description: Export CNKI citation data or send it to Zotero from Codex through an existing Chrome CDP session. Use when Codex needs GB/T or EndNote-style export content, or needs to push current-page or single-paper export data into a local Zotero Connector session.
---

# CNKI Export (Codex)

Use this skill for citation export and Zotero handoff.

## Run

Export a single paper to Zotero:

```bash
python3 scripts/run.py --url "https://..." --mode zotero
```

Export the current result page in batch:

```bash
python3 scripts/run.py --all-current-page --mode zotero
```

Return GB/T text payloads:

```bash
python3 scripts/run.py --url "https://..." --mode gb
```

## Notes

- `--mode ris` returns the EndNote-style export payload CNKI exposes through its export API.
- Zotero mode requires the local Zotero desktop app and Connector API to be available at `127.0.0.1:23119`.
