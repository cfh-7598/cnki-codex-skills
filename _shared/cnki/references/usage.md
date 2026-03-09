# CNKI Codex Usage

## Chrome setup

Use an existing logged-in Chrome session. Start Chrome with remote debugging enabled:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

Then run the shared CLI:

```bash
python3 _shared/cnki/cli.py search --query "人工智能"
```

## Common workflows

- Search papers: `search --query "..."`
- Refine search: `advanced-search --query "..." --source CSSCI --start-year 2020 --end-year 2025`
- Parse current results page: `parse-results`
- Open paper detail metadata: `paper-detail --url "https://..."`
- Move through results: `navigate-pages --action next` or `navigate-pages --sort-by date`
- Search journals: `journal-search --query "计算机学报"`
- Check indexing data: `journal-index --query "计算机学报"`
- Browse issue tables of contents: `journal-toc --query "计算机学报" --year 2025 --issue 01`
- Trigger download: `download --url "https://..." --format pdf`
- Export current page to Zotero: `export --all-current-page --mode zotero`

## Limits

- The CLI only reuses the current browser session. It does not solve CNKI captchas or log in for the user.
- Batch export works on the current results page, not the entire result set.
- If CNKI changes its DOM or export endpoint shape, update the selectors or page scripts in the shared implementation.
