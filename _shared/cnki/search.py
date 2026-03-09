"""Search-related CNKI workflows."""

from __future__ import annotations

from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import ChromeSession, CnkiError, ok  # type: ignore
    from cnki_selectors import ADVANCED_SEARCH_URL, SEARCH_URL  # type: ignore
else:
    from .browser import ChromeSession, CnkiError, ok
    from .cnki_selectors import ADVANCED_SEARCH_URL, SEARCH_URL


PARSE_RESULTS_JS = """() => {
  const rows = document.querySelectorAll('.result-table-list tbody tr');
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const results = Array.from(rows).map((row, index) => {
    const nameCell = row.querySelector('td.name');
    const titleLink = nameCell?.querySelector('a.fz14');
    const authorCell = row.querySelector('td.author');
    const sourceCell = row.querySelector('td.source');
    const dateCell = row.querySelector('td.date');
    const dataCell = row.querySelector('td.data');
    const quoteCell = row.querySelector('td.quote');
    const downloadCell = row.querySelector('td.download');
    const isOnlineFirst = !!nameCell?.querySelector('.marktip');

    return {
      number: index + 1,
      title: titleLink?.innerText?.trim() || '',
      url: titleLink?.href || '',
      exportId: checkboxes[index]?.value || '',
      authors: Array.from(authorCell?.querySelectorAll('a.KnowledgeNetLink') || []).map(a => a.innerText?.trim()),
      journal: sourceCell?.querySelector('a')?.innerText?.trim() || '',
      date: dateCell?.innerText?.trim() || '',
      database: dataCell?.innerText?.trim() || '',
      citations: quoteCell?.innerText?.trim() || '',
      downloads: downloadCell?.innerText?.trim() || '',
      isOnlineFirst
    };
  });

  const totalText = document.querySelector('.pagerTitleCell')?.innerText || '';
  const totalMatch = totalText.match(/([\\d,]+)/);
  const pageInfo = document.querySelector('.countPageMark')?.innerText || '';

  return {
    total: totalMatch ? totalMatch[1] : '0',
    page: pageInfo || '1/1',
    items: results
  };
}"""


async def parse_results_from_page(page) -> dict[str, Any]:
    parsed = await page.evaluate(PARSE_RESULTS_JS)
    if not parsed["items"] and "条结果" not in await page.text_content("body"):
        raise CnkiError("page_not_supported", "The current page is not a CNKI results page.", page_url=page.url)
    return parsed


async def search(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.goto(page, SEARCH_URL)
        await session.ensure_selector(page, "input.search-input")
        await session.require_no_captcha(page)
        await page.fill("input.search-input", args.query)
        await page.click("input.search-btn")
        await session.ensure_text(page, "条结果")
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        return ok(f'Searched CNKI for "{args.query}".', parsed, page_url=page.url)


async def advanced_search(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(ADVANCED_SEARCH_URL)
        await session.goto(page, ADVANCED_SEARCH_URL)
        await session.ensure_selector(page, "#txt_1_value1")
        await session.require_no_captcha(page)

        payload = {
            "query": args.query,
            "fieldType": args.field_type,
            "query2": args.query2 or "",
            "fieldType2": args.field_type2,
            "rowLogic": args.row_logic,
            "sourceTypes": args.source or [],
            "startYear": args.start_year or "",
            "endYear": args.end_year or "",
            "author": args.author or "",
            "journal": args.journal or "",
        }
        result = await page.evaluate(
            """async (config) => {
              const selects = Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null);
              const setValue = (el, value, eventName='change') => {
                if (!el) return;
                el.value = value;
                el.dispatchEvent(new Event(eventName, { bubbles: true }));
              };

              if (config.sourceTypes.length > 0) {
                const all = document.querySelector('#gjAll');
                if (all && all.checked) all.click();
                for (const key of config.sourceTypes) {
                  const box = document.querySelector('#' + key);
                  if (box && !box.checked) box.click();
                }
              }

              setValue(selects[0], config.fieldType);
              const input1 = document.querySelector('#txt_1_value1');
              if (input1) {
                input1.value = config.query;
                input1.dispatchEvent(new Event('input', { bubbles: true }));
              }

              if (config.query2) {
                setValue(selects[5], config.rowLogic);
                setValue(selects[6], config.fieldType2);
                const input2 = document.querySelector('#txt_2_value1');
                if (input2) {
                  input2.value = config.query2;
                  input2.dispatchEvent(new Event('input', { bubbles: true }));
                }
              }

              const author = document.querySelector('#au_1_value1');
              if (author && config.author) {
                author.value = config.author;
                author.dispatchEvent(new Event('input', { bubbles: true }));
              }

              const journal = document.querySelector('#magazine_value1');
              if (journal && config.journal) {
                journal.value = config.journal;
                journal.dispatchEvent(new Event('input', { bubbles: true }));
              }

              if (config.startYear) setValue(document.querySelector('#startYear'), config.startYear);
              if (config.endYear) setValue(document.querySelector('#endYear'), config.endYear);

              document.querySelector('div.search')?.click();
            }""",
            payload,
        )
        _ = result
        await session.ensure_text(page, "条结果")
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        parsed["filters"] = payload
        return ok(f'Ran advanced CNKI search for "{args.query}".', parsed, page_url=page.url)


async def parse_results(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        return ok("Parsed the current CNKI results page.", parsed, page_url=page.url)


async def navigate_pages(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.require_no_captcha(page)
        previous_mark = await page.locator(".countPageMark").text_content()

        if args.sort_by:
            id_map = {
                "relevance": "FFD",
                "date": "PT",
                "citations": "CF",
                "downloads": "DFR",
                "comprehensive": "ZH",
            }
            sort_id = id_map[args.sort_by]
            await page.click(f"#orderList li#{sort_id}")
        elif args.action == "next":
            await page.get_by_text("下一页").first.click()
        elif args.action == "previous":
            await page.get_by_text("上一页").first.click()
        elif args.page:
            await page.get_by_text(str(args.page), exact=True).first.click()
        else:
            raise CnkiError("not_found", "Provide --sort-by, --action, or --page.", page_url=page.url)

        await page.wait_for_function(
            """(prev) => {
                const mark = document.querySelector('.countPageMark')?.innerText || '';
                return Boolean(mark) && mark !== prev;
            }""",
            previous_mark or "",
            timeout=15000,
        )
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        message = "Updated CNKI page ordering." if args.sort_by else "Navigated the CNKI results page."
        return ok(message, parsed, page_url=page.url)
