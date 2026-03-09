---
name: cnki-download-codex
description: Trigger CNKI PDF or CAJ downloads from Codex through an existing Chrome CDP session. Use when Codex needs to click the download control on a CNKI paper page while preserving the user's existing login state and browser download behavior.
---

# CNKI Download (Codex)

Use this skill only when the user wants the actual CNKI file download.

## Run

```bash
python3 /Users/cfh/Nutstore\ Files/code/skill/codex-skills/_shared/cnki/cli.py download --url "https://..." --format pdf
```

## Notes

- The command fails with `not_logged_in` if the connected Chrome session is not authenticated for CNKI downloads.
- CNKI captcha still requires manual handling.

