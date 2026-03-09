# CNKI Codex Selector Notes

These selectors and text hooks were migrated from the Claude-oriented `cookjohn/cnki-skills` project and adapted for Playwright.

## Search results

- Search input: `input.search-input`
- Search button: `input.search-btn`
- Result rows: `.result-table-list tbody tr`
- Result title: `td.name a.fz14`
- Result authors: `td.author a.KnowledgeNetLink`
- Result journal: `td.source a`
- Result count: `.pagerTitleCell`
- Page indicator: `.countPageMark`
- Dissertation filter (mixed): `a[name="classify"][resource="DISSERTATION"][data-chs="CDFD,CMFD"]`
- Dissertation filter (doctoral): `a[name="classify"][resource="DISSERTATION"][data-chs="CDFD"]`
- Dissertation filter (master): `a[name="classify"][resource="DISSERTATION"][data-chs="CMFD"]`

## Paper detail

- Main paper container: `.brief`
- Title: `.brief h1`
- Abstract: `.abstract-text`
- Keywords: `p.keywords a`
- Fund info: `p.funds`
- Classification: `.clc-code`
- Journal/source: `.doc-top a`
- Download links: `#pdfDown`, `#cajDown`, `.btn-dlpdf a`, `.btn-dlcaj a`
- Export fields: `#export-url`, `#export-id`, `#paramdbcode`, `#paramdbname`, `#paramfilename`

## Journals

- Journal search button: `input.researchbtn`
- Journal detail links: `a[href*="knavi/detail"]`
- Journal issue groups: `#yearissue0 dl.s-dataList`
- Issue links: `dl.s-dataList dd a`
- TOC rows: `#CataLogContent dd.row`
- Original TOC reader link: `a.btn-preview:not(.btn-back)`

## Captcha

CNKI embeds the Tencent captcha SDK even when idle. Treat it as active only when `#tcaptcha_transform_dy` is visible on screen, not when it is parked off-screen.
