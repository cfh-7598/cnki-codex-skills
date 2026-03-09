---
name: cnki-codex
description: Route CNKI work to the right Codex sub-skill. Use when Codex needs a CNKI entry point for literature search, paper metadata extraction, journal lookup, indexing checks, TOC browsing, downloads, or citation export in an existing Chrome session.
---

# CNKI (Codex)

Use this skill as the thin entry point for CNKI tasks. Do not load the whole workflow into context unless the task truly spans multiple CNKI capabilities.

## Prerequisites

- Start Chrome with remote debugging enabled:
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
  ```
- Log in to CNKI in that Chrome session if the task needs downloads or export data.
- Expect manual captcha handling. If CNKI shows the Tencent slider, stop and ask the user to solve it in Chrome.

## Route tasks

- Search papers: use `$cnki-search-codex`
- Filtered search: use `$cnki-advanced-search-codex`
- Parse the current result page: use `$cnki-parse-results-codex`
- Extract paper metadata: use `$cnki-paper-detail-codex`
- Paginate or sort results: use `$cnki-navigate-pages-codex`
- Search journals: use `$cnki-journal-search-codex`
- Check journal indexing: use `$cnki-journal-index-codex`
- Browse issue tables of contents: use `$cnki-journal-toc-codex`
- Trigger PDF or CAJ download: use `$cnki-download-codex`
- Export citations or push to Zotero: use `$cnki-export-codex`

## Shared implementation

All sub-skills call the same CLI:

```bash
python3 /Users/cfh/Nutstore\ Files/code/skill/codex-skills/_shared/cnki/cli.py --help
```

Read shared notes only when needed:

- `/Users/cfh/Nutstore Files/code/skill/codex-skills/_shared/cnki/references/usage.md`
- `/Users/cfh/Nutstore Files/code/skill/codex-skills/_shared/cnki/references/selectors.md`

