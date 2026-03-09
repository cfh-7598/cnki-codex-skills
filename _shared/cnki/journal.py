"""Journal-related CNKI workflows."""

from __future__ import annotations

from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import ChromeSession, CnkiError, ok  # type: ignore
    from cnki_selectors import JOURNAL_HOME_URL, KNOWN_JOURNAL_TAGS  # type: ignore
else:
    from .browser import ChromeSession, CnkiError, ok
    from .cnki_selectors import JOURNAL_HOME_URL, KNOWN_JOURNAL_TAGS


JOURNAL_SEARCH_JS = """async (query) => {
  const select = document.querySelector('select');
  if (select) {
    if (/^\\d{4}-\\d{3}[\\dXx]$/.test(query)) select.value = 'ISSN';
    else if (/^\\d{2}-\\d{4}/.test(query)) select.value = 'CN';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const input = document.querySelector('input[placeholder*="检索词"]');
  if (input) {
    input.value = query;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  document.querySelector('input.researchbtn')?.click();
}"""


JOURNAL_RESULTS_JS = """() => {
  const titleLinks = document.querySelectorAll('a[href*="knavi/detail"]');
  const results = [];
  titleLinks.forEach(link => {
    const text = link.innerText?.trim();
    if (!text || text.length < 2) return;
    const parent = link.closest('li, .list-item') || link.parentElement?.parentElement;
    const pt = parent?.innerText || '';
    results.push({
      name: text.split('\\n')[0]?.trim(),
      url: link.href,
      issn: (pt.match(/ISSN[：:]\\s*(\\S+)/) || [])[1] || '',
      cn: (pt.match(/CN[：:]\\s*(\\S+)/) || [])[1] || '',
      cif: (pt.match(/复合影响因子[：:]\\s*([\\d.]+)/) || [])[1] || '',
      aif: (pt.match(/综合影响因子[：:]\\s*([\\d.]+)/) || [])[1] || '',
      citations: (pt.match(/被引次数[：:]\\s*([\\d,]+)/) || [])[1] || '',
      downloads: (pt.match(/下载次数[：:]\\s*([\\d,]+)/) || [])[1] || '',
      sponsor: (pt.match(/主办单位[：:]\\s*(.+?)(?=\\n|ISSN)/) || [])[1]?.trim() || ''
    });
  });
  const body = document.body.innerText;
  const countMatch = body.match(/共\\s*(\\d+)\\s*条结果/) || body.match(/找到\\s*(\\d+)\\s*条结果/);
  return { count: countMatch ? parseInt(countMatch[1], 10) : results.length, items: results };
}"""


async def _search_journal_page(session: ChromeSession, page, query: str) -> dict[str, Any]:
    await session.goto(page, JOURNAL_HOME_URL)
    await session.ensure_selector(page, "input.researchbtn")
    await session.require_no_captcha(page)
    await page.evaluate(JOURNAL_SEARCH_JS, query)
    await session.ensure_text(page, "条结果")
    if await page.get_by_text("期刊").count():
        await page.get_by_text("期刊").first.click()
        await page.wait_for_timeout(1500)
    await session.require_no_captcha(page)
    results = await page.evaluate(JOURNAL_RESULTS_JS)
    if not results["items"]:
        raise CnkiError("not_found", f'No CNKI journal results matched "{query}".', page_url=page.url)
    return results


async def journal_search(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(JOURNAL_HOME_URL)
        results = await _search_journal_page(session, page, args.query)
        return ok(f'Found CNKI journal results for "{args.query}".', results, page_url=page.url)


async def journal_index(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(JOURNAL_HOME_URL)
        target_url = args.url
        if not target_url:
            results = await _search_journal_page(session, page, args.query)
            target_url = results["items"][0]["url"]
        await session.goto(page, target_url)
        await page.wait_for_load_state("domcontentloaded")
        await session.require_no_captcha(page)
        detail = await page.evaluate(
            """(knownTags) => {
              const body = document.body.innerText;
              const titleEl = document.querySelector('h3.titbox, h3.titbox1');
              const titleText = titleEl?.innerText?.trim() || '';
              const titleParts = titleText.split('\\n').map(s => s.trim()).filter(Boolean);
              const indexedIn = knownTags.filter(tag => body.includes(tag));
              return {
                nameCN: titleParts[0] || '',
                nameEN: titleParts[1] || '',
                indexedIn,
                sponsor: (body.match(/主办单位[：:]\\s*(.+?)(?=\\n)/) || [])[1] || '',
                frequency: (body.match(/出版周期[：:]\\s*(\\S+)/) || [])[1] || '',
                issn: (body.match(/ISSN[：:]\\s*(\\S+)/) || [])[1] || '',
                cn: (body.match(/CN[：:]\\s*(\\S+)/) || [])[1] || '',
                collection: (body.match(/专辑名称[：:]\\s*(.+?)(?=\\n)/) || [])[1] || '',
                paperCount: (body.match(/出版文献量[：:]\\s*(.+?)(?=\\n)/) || [])[1] || '',
                impactComposite: (body.match(/复合影响因子[：:]\\s*([\\d.]+)/) || [])[1] || '',
                impactComprehensive: (body.match(/综合影响因子[：:]\\s*([\\d.]+)/) || [])[1] || ''
              };
            }""",
            KNOWN_JOURNAL_TAGS,
        )
        return ok("Extracted CNKI journal indexing data.", detail, page_url=page.url)


async def journal_toc(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(JOURNAL_HOME_URL)
        target_url = args.url
        if not target_url:
            results = await _search_journal_page(session, page, args.query)
            target_url = results["items"][0]["url"]
        await session.goto(page, target_url)
        await page.wait_for_load_state("domcontentloaded")
        await session.require_no_captcha(page)
        toc = await page.evaluate(
            """async ({ year, issue }) => {
              const groups = Array.from(document.querySelectorAll('#yearissue0 dl.s-dataList'));
              if (!groups.length) return null;

              let targetGroup = groups[0];
              if (year) {
                const match = groups.find(dl => dl.querySelector('dt')?.innerText?.trim() === year);
                if (match) targetGroup = match;
              }

              let targetIssue = targetGroup.querySelector('dd a');
              if (issue) {
                const expected = issue.startsWith('No.') ? issue : `No.${issue.padStart(2, '0')}`;
                const match = Array.from(targetGroup.querySelectorAll('dd a')).find(a => a.innerText.trim() === expected);
                if (match) targetIssue = match;
              }
              if (!targetIssue) return { error: 'issue_not_found' };

              targetIssue.click();
              await new Promise((resolve, reject) => {
                let tries = 0;
                const check = () => {
                  if (document.querySelectorAll('#CataLogContent dd.row').length > 0) return resolve();
                  if (++tries > 30) return reject(new Error('timeout'));
                  setTimeout(check, 500);
                };
                setTimeout(check, 1000);
              });

              const papers = Array.from(document.querySelectorAll('#CataLogContent dd.row')).map((dd, i) => ({
                no: i + 1,
                title: dd.querySelector('span.name a')?.innerText?.trim() || '',
                authors: dd.querySelector('span.author')?.innerText?.trim()?.replace(/;$/, '') || '',
                pages: dd.querySelector('span.company')?.innerText?.trim() || ''
              }));
              const tocLink = document.querySelector('a.btn-preview:not(.btn-back)');
              return {
                issueLabel: document.querySelector('span.date-list')?.innerText?.trim() || '',
                paperCount: papers.length,
                papers,
                tocUrl: tocLink?.href || null
              };
            }""",
            {"year": args.year or "", "issue": args.issue or ""},
        )
        if not toc:
            raise CnkiError("page_not_supported", "CNKI journal issue browsing is unavailable on this page.", page_url=page.url)
        if toc.get("error") == "issue_not_found":
            raise CnkiError("not_found", "The requested CNKI journal issue was not found.", page_url=page.url)
        if args.download and toc.get("tocUrl"):
            await session.goto(page, toc["tocUrl"])
            return ok("Opened the CNKI original TOC reader for download.", toc, page_url=page.url)
        return ok("Extracted the CNKI journal table of contents.", toc, page_url=page.url)
