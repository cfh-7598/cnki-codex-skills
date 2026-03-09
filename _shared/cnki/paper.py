"""Paper detail, download, and export helpers for CNKI."""

from __future__ import annotations

from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import ChromeSession, CnkiError, ok  # type: ignore
    from cnki_selectors import EXPORT_API_URL, PAPER_SECTION_SELECTOR, PAPER_TITLE_SELECTOR, SEARCH_URL  # type: ignore
    from zotero import save_export_payload_to_zotero  # type: ignore
else:
    from .browser import ChromeSession, CnkiError, ok
    from .cnki_selectors import EXPORT_API_URL, PAPER_SECTION_SELECTOR, PAPER_TITLE_SELECTOR, SEARCH_URL
    from .zotero import save_export_payload_to_zotero


DETAIL_JS = """() => {
  const brief = document.querySelector('.brief');
  if (!brief) return null;

  const title = brief.querySelector('h1')?.innerText?.trim()
    ?.replace(/\\s*附视频\\s*$/, '')
    ?.replace(/\\s*网络首发\\s*$/, '');
  const authorH3s = brief.querySelectorAll('h3.author');
  const authors = [];
  if (authorH3s[0]) {
    authorH3s[0].querySelectorAll('a').forEach(a => {
      const raw = a.innerText || '';
      authors.push({
        name: raw.replace(/\\d+$/, '').trim(),
        affiliationNum: (raw.match(/(\\d+)$/) || [])[1] || ''
      });
    });
  }
  const affiliations = authorH3s[1]
    ? Array.from(authorH3s[1].querySelectorAll('a')).map(a => a.innerText?.trim())
    : [];
  const abstract = document.querySelector('.abstract-text')?.innerText?.trim() || '';
  const keywords = Array.from(document.querySelectorAll('p.keywords a')).map(a => a.innerText?.replace(/;$/, '').trim());
  const fund = document.querySelector('p.funds')?.innerText?.trim() || '';
  const classification = document.querySelector('.clc-code')?.innerText?.trim() || '';
  const journal = document.querySelector('.doc-top a')?.innerText?.trim() || '';
  const pubInfo = document.querySelector('.head-time')?.innerText?.trim() || '';
  return {
    title,
    authors,
    affiliations,
    abstract,
    keywords,
    fund,
    classification,
    journal,
    pubInfo,
    isOnlineFirst: !!brief.querySelector('.icon-shoufa'),
  };
}"""


async def ensure_detail_page(session: ChromeSession, page, url: str | None) -> None:
    if url:
        await session.goto(page, url)
    await session.ensure_selector(page, PAPER_SECTION_SELECTOR)
    await session.require_no_captcha(page)


async def paper_detail(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(args.url or SEARCH_URL)
        await ensure_detail_page(session, page, args.url)
        detail = await page.evaluate(DETAIL_JS)
        if not detail:
            raise CnkiError("page_not_supported", "The current page is not a CNKI paper detail page.", page_url=page.url)
        return ok("Extracted CNKI paper details.", detail, page_url=page.url)


async def download(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(args.url or SEARCH_URL)
        await ensure_detail_page(session, page, args.url)
        result = await page.evaluate(
            """(format) => {
              const notLogged = document.querySelector('.downloadlink.icon-notlogged')
                || document.querySelector('[class*="notlogged"]');
              if (notLogged) return { error: 'not_logged_in' };

              const pdfLink = document.querySelector('#pdfDown') || document.querySelector('.btn-dlpdf a');
              const cajLink = document.querySelector('#cajDown') || document.querySelector('.btn-dlcaj a');
              const title = document.querySelector('.brief h1')?.innerText?.trim()?.replace(/\\s*网络首发\\s*$/, '') || '';

              if (format === 'pdf' && pdfLink) { pdfLink.click(); return { status: 'downloading', format: 'PDF', title }; }
              if (format === 'caj' && cajLink) { cajLink.click(); return { status: 'downloading', format: 'CAJ', title }; }
              if (pdfLink) { pdfLink.click(); return { status: 'downloading', format: 'PDF', title }; }
              if (cajLink) { cajLink.click(); return { status: 'downloading', format: 'CAJ', title }; }
              return { error: 'not_found' };
            }""",
            args.format,
        )
        if result.get("error") == "not_logged_in":
            raise CnkiError("not_logged_in", "CNKI download requires a logged-in browser session.", page_url=page.url)
        if result.get("error"):
            raise CnkiError("not_found", "No CNKI download link was found on the page.", page_url=page.url)
        return ok(f'Triggered CNKI {result["format"]} download.', result, page_url=page.url)


async def export(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(args.url or SEARCH_URL)
        if args.url:
            await session.goto(page, args.url)
        await session.require_no_captcha(page)
        export_payload = await _collect_export_payload(page, session, args)
        if args.mode == "zotero":
            saved = save_export_payload_to_zotero(export_payload)
            return ok("Sent CNKI export payload to Zotero.", saved, page_url=page.url)
        if args.mode == "gb":
            formatted = _format_export_mode(export_payload, "GBTREFER")
        else:
            formatted = _format_export_mode(export_payload, "ENDNOTE")
        return ok(f"Collected CNKI export data in {args.mode} mode.", formatted, page_url=page.url)


async def _collect_export_payload(page, session: ChromeSession, args) -> list[dict[str, Any]]:
    body = await page.text_content("body")
    if body and "条结果" in body and (args.all_current_page or args.index):
        payload = await page.evaluate(
            """async ({ apiUrl, indices }) => {
              const checkboxes = Array.from(document.querySelectorAll('.result-table-list tbody input.cbItem'));
              const rows = Array.from(document.querySelectorAll('.result-table-list tbody tr'));
              if (!checkboxes.length) return [];

              const wantsAll = !indices.length;
              const normalized = indices.map(n => n - 1);
              const items = [];
              for (let i = 0; i < checkboxes.length; i++) {
                if (!wantsAll && !normalized.includes(i)) continue;
                const exportId = checkboxes[i].value;
                const pageUrl = rows[i]?.querySelector('td.name a.fz14')?.href || '';
                const resp = await fetch(apiUrl, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                  body: new URLSearchParams({
                    filename: exportId,
                    displaymode: 'GBTREFER,elearning,EndNote',
                    uniplatform: 'NZKPT'
                  })
                });
                const data = await resp.json();
                if (data.code !== 1) continue;
                const record = { pageUrl, exportId };
                for (const item of data.data) {
                  record[item.mode] = item.value[0];
                }
                const issnMatch = record.ENDNOTE?.match(/%@\\s*([^\\s<]+)/);
                record.issn = issnMatch ? issnMatch[1] : '';
                items.push(record);
              }
              return items;
            }""",
            {"apiUrl": EXPORT_API_URL, "indices": args.index or []},
        )
        if not payload:
            raise CnkiError("not_found", "No exportable papers were found on the current results page.", page_url=page.url)
        return payload

    await ensure_detail_page(session, page, args.url)
    single = await page.evaluate(
        """async (apiUrl) => {
          const exportUrl = document.querySelector('#export-url')?.value || apiUrl;
          const exportId = document.querySelector('#export-id')?.value;
          const uniplatform = new URLSearchParams(window.location.search).get('uniplatform') || 'NZKPT';
          if (!exportId) return null;

          const resp = await fetch(exportUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
              filename: exportId,
              displaymode: 'GBTREFER,elearning,EndNote',
              uniplatform
            })
          });
          const data = await resp.json();
          if (data.code !== 1) return null;
          const record = { pageUrl: window.location.href, exportId };
          for (const item of data.data) {
            record[item.mode] = item.value[0];
          }
          record.dbcode = document.querySelector('#paramdbcode')?.value || '';
          record.dbname = document.querySelector('#paramdbname')?.value || '';
          record.filename = document.querySelector('#paramfilename')?.value || '';
          record.pdfUrl = document.querySelector('#pdfDown')?.href || '';
          return record;
        }""",
        EXPORT_API_URL,
    )
    if not single:
        raise CnkiError("not_found", "CNKI export controls were not found on the current page.", page_url=page.url)
    single["cookies"] = await session.cookies_as_header(page)
    return [single]


def _format_export_mode(payload: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    formatted = []
    for item in payload:
        formatted.append(
            {
                "title": _extract_title(item),
                "pageUrl": item.get("pageUrl", ""),
                "exportId": item.get("exportId", ""),
                "content": item.get(key, ""),
            }
        )
    return formatted


def _extract_title(item: dict[str, Any]) -> str:
    raw = item.get("ELEARNING", "")
    for line in raw.splitlines():
        if line.startswith("Title-题名:"):
            return line.split(":", 1)[1].strip()
    heading = item.get("GBTREFER", "") or item.get("ENDNOTE", "")
    return heading.splitlines()[0].strip() if heading else ""
