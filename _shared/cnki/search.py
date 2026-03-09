"""Search-related CNKI workflows."""

from __future__ import annotations

import asyncio
from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import ChromeSession, CnkiError, ok  # type: ignore
    from cnki_selectors import ADVANCED_SEARCH_URL, SEARCH_URL  # type: ignore
    from paper import ensure_detail_page, extract_detail_from_page  # type: ignore
else:
    from .browser import ChromeSession, CnkiError, ok
    from .cnki_selectors import ADVANCED_SEARCH_URL, SEARCH_URL
    from .paper import ensure_detail_page, extract_detail_from_page


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

THESIS_SCOPE_SELECTOR = "a[name='classify'][resource='DISSERTATION'][data-chs='CDFD,CMFD']"
TOTAL_SCOPE_SELECTOR = "a[name='classify'][resource='CROSSDB'][classid='WD0FTY92']"
CHINESE_SWITCH_SELECTOR = ".switch-ChEn a.ch[data-val='Chinese'], .switch-ChEn a.ch"
THESIS_ALLOWED_DEGREES = {
    "both": {"博士", "硕士"},
    "doctoral": {"博士"},
    "master": {"硕士"},
}


async def parse_results_from_page(page) -> dict[str, Any]:
    parsed = await page.evaluate(PARSE_RESULTS_JS)
    if not parsed["items"] and "条结果" not in await page.text_content("body"):
        raise CnkiError("page_not_supported", "The current page is not a CNKI results page.", page_url=page.url)
    return parsed


async def _apply_default_total_chinese(page) -> None:
    # CNKI remembers previous language mode (Chinese/Foreign). For predictable
    # default search behavior, force CROSSDB + Chinese before entering queries.
    await page.evaluate(
        """(config) => {
            const pickVisible = (nodes) => {
              const isVisible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return !!el.offsetParent
                  && rect.width > 0
                  && rect.height > 0
                  && style.display !== 'none'
                  && style.visibility !== 'hidden';
              };
              return nodes.find(isVisible) || nodes[0] || null;
            };

            const total = pickVisible(Array.from(document.querySelectorAll(config.totalSelector)));
            if (total) total.click();

            const chinese = pickVisible(Array.from(document.querySelectorAll(config.chineseSelector)));
            if (chinese) chinese.click();

            const rlang = document.querySelector('#rlang');
            if (rlang) rlang.value = 'CHINESE';
        }""",
        {"totalSelector": TOTAL_SCOPE_SELECTOR, "chineseSelector": CHINESE_SWITCH_SELECTOR},
    )
    await page.wait_for_timeout(300)


async def _set_visible_search_input(page, query: str) -> None:
    input_box = page.locator("input.search-input:visible").first
    await input_box.fill("")
    await input_box.fill(query)
    current = (await input_box.input_value()).strip()
    if current != query.strip():
        # Some CNKI states delay input binding. Retry with keyboard overwrite.
        await input_box.click()
        await page.keyboard.press("Meta+A")
        await page.keyboard.type(query)
        current = (await input_box.input_value()).strip()
        if current != query.strip():
            raise CnkiError("not_found", "Unable to set the CNKI search input value.", page_url=page.url)

    # CNKI sometimes checks a parallel attribute instead of the live input value.
    await page.evaluate(
        """(q) => {
            const el = document.querySelector('input.search-input');
            if (!el) return;
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
            setter?.call(el, q);
            el.setAttribute('value', q);
            el.setAttribute('searchword', q);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Enter' }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        }""",
        query,
    )
    await page.wait_for_timeout(100)


async def _submit_search(page, query: str) -> None:
    async def _submit_once(*, use_enter: bool) -> str | None:
        dialog_task = asyncio.create_task(page.wait_for_event("dialog", timeout=2000))
        results_task = asyncio.create_task(page.locator(".result-table-list tbody tr").first.wait_for(timeout=6000))
        try:
            if use_enter:
                await page.locator("input.search-input:visible").first.press("Enter")
            else:
                await page.locator("input.search-btn:visible").first.click()

            done, pending = await asyncio.wait(
                {dialog_task, results_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

            finished = next(iter(done))
            if finished is dialog_task:
                dialog = finished.result()
                message = dialog.message
                await dialog.accept()
                return message

            await page.wait_for_timeout(150)
            return None
        finally:
            if not dialog_task.done():
                dialog_task.cancel()
            if not results_task.done():
                results_task.cancel()

    for use_enter in (True, False, False):
        await _set_visible_search_input(page, query)
        dialog_message = await _submit_once(use_enter=use_enter)
        if not dialog_message:
            return

    raise CnkiError(
        "not_found",
        "CNKI blocked search submission with dialog: 请输入检索词",
        page_url=page.url,
    )


async def search(args) -> dict[str, Any]:
    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.goto(page, SEARCH_URL)
        await session.ensure_selector(page, "input.search-input")
        await session.require_no_captcha(page)
        await _apply_default_total_chinese(page)
        await _submit_search(page, args.query)
        await session.ensure_text(page, "条结果")
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        return ok(f'Searched CNKI for "{args.query}".', parsed, page_url=page.url)


def _collect_result_items(
    parsed: dict[str, Any],
    seen_keys: set[str],
    collected: list[dict[str, Any]],
) -> None:
    for item in parsed.get("items", []):
        key = (item.get("url") or item.get("title") or "").strip()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        collected.append(dict(item))


def _normalize_degree(database: str) -> str | None:
    text = (database or "").strip()
    if "博士" in text or "CDFD" in text:
        return "博士"
    if "硕士" in text or "CMFD" in text:
        return "硕士"
    return None


def _collect_thesis_items(
    parsed: dict[str, Any],
    degree_mode: str,
    seen_keys: set[str],
    collected: list[dict[str, Any]],
) -> None:
    allowed = THESIS_ALLOWED_DEGREES[degree_mode]
    for item in parsed.get("items", []):
        degree = _normalize_degree(item.get("database", ""))
        if not degree or degree not in allowed:
            continue
        key = (item.get("url") or item.get("title") or "").strip()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        record = dict(item)
        record["degree"] = degree
        collected.append(record)


async def _apply_thesis_scope(page) -> None:
    # Prefer the visible dissertation scope item. Fallback to first matching node.
    clicked = await page.evaluate(
        """(selector) => {
            const nodes = Array.from(document.querySelectorAll(selector));
            if (!nodes.length) return false;
            const isVisible = (el) => {
              const rect = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return !!el.offsetParent
                && rect.width > 0
                && rect.height > 0
                && style.display !== 'none'
                && style.visibility !== 'hidden';
            };
            const target = nodes.find(isVisible) || nodes[0];
            target.click();
            return true;
        }""",
        THESIS_SCOPE_SELECTOR,
    )
    if not clicked:
        raise CnkiError("not_found", "CNKI dissertation filter was not found.", page_url=page.url)


async def _wait_for_results_page_change(page, previous_mark: str | None) -> None:
    try:
        await page.wait_for_function(
            """(prev) => {
                const mark = document.querySelector('.countPageMark')?.innerText || '';
                return Boolean(mark) && mark !== prev;
            }""",
            arg=previous_mark or "",
            timeout=15000,
        )
    except Exception:  # noqa: BLE001
        pass


async def _move_to_next_results_page(page, current_page: int) -> bool:
    previous_mark = await page.locator(".countPageMark").text_content()
    moved = False
    try:
        await page.get_by_text(str(current_page + 1), exact=True).first.click()
        moved = True
    except Exception:  # noqa: BLE001
        pass

    if not moved:
        try:
            await page.get_by_text("下一页").first.click()
            moved = True
        except Exception:  # noqa: BLE001
            moved = False

    if moved:
        await _wait_for_results_page_change(page, previous_mark)
    return moved


async def _enrich_items_with_detail(session: ChromeSession, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assert session.context is not None
    detail_page = await session.context.new_page()
    enriched: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        for item in items:
            record = dict(item)
            detail_url = (item.get("url") or "").strip()
            if not detail_url:
                error = {"code": "not_found", "message": "Result item has no detail URL."}
                record["detailError"] = error
                errors.append({"title": item.get("title", ""), "url": "", **error})
                enriched.append(record)
                continue

            try:
                await ensure_detail_page(session, detail_page, detail_url)
                detail = await extract_detail_from_page(detail_page)
            except CnkiError as exc:
                if exc.code == "captcha":
                    raise
                error = {"code": exc.code, "message": exc.message, "page_url": exc.page_url}
                record["detailError"] = error
                errors.append({"title": item.get("title", ""), "url": detail_url, **error})
                enriched.append(record)
                continue

            record["abstract"] = detail.get("abstract", "")
            record["keywords"] = detail.get("keywords", [])
            record["fund"] = detail.get("fund", "")
            record["classification"] = detail.get("classification", "")
            record["affiliations"] = detail.get("affiliations", [])
            record["detailAuthors"] = detail.get("authors", [])
            record["journalDetail"] = detail.get("journal", "")
            record["pubInfo"] = detail.get("pubInfo", "")
            record["detail"] = detail
            enriched.append(record)
    finally:
        await detail_page.close()
    return enriched, errors


async def thesis_search(args) -> dict[str, Any]:
    requested = max(1, int(args.count or 20))
    max_pages = max(1, int(args.max_pages or 20))
    degree_mode = args.degree or "both"

    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.goto(page, SEARCH_URL)
        await session.ensure_selector(page, "input.search-input")
        await session.require_no_captcha(page)
        await _apply_default_total_chinese(page)
        await _submit_search(page, args.query)
        await session.ensure_text(page, "条结果")
        await session.require_no_captcha(page)

        previous_mark = await page.locator(".countPageMark").text_content()
        await _apply_thesis_scope(page)
        await _wait_for_results_page_change(page, previous_mark)

        parsed = await parse_results_from_page(page)
        seen: set[str] = set()
        collected: list[dict[str, Any]] = []
        _collect_thesis_items(parsed, degree_mode, seen, collected)

        current_page = 1
        while len(collected) < requested and current_page < max_pages:
            if not await _move_to_next_results_page(page, current_page):
                break

            await session.require_no_captcha(page)
            parsed = await parse_results_from_page(page)
            _collect_thesis_items(parsed, degree_mode, seen, collected)
            current_page += 1

        items = collected[:requested]
        data = {
            "query": args.query,
            "degree": degree_mode,
            "requested": requested,
            "collected": len(items),
            "pagesScanned": current_page,
            "summary": {
                "doctoral": sum(1 for item in items if item.get("degree") == "博士"),
                "master": sum(1 for item in items if item.get("degree") == "硕士"),
            },
            "items": items,
        }
        return ok(
            f'Collected {len(items)} thesis record(s) for "{args.query}" in {degree_mode} mode.',
            data,
            page_url=page.url,
        )


async def collect_details(args) -> dict[str, Any]:
    requested = max(1, int(args.count or 10))
    max_pages = max(1, int(args.max_pages or 20))
    scope = args.scope or "papers"
    degree_mode = args.degree or "both"

    async with ChromeSession(args.cdp_url) as session:
        page = await session.get_or_open_page(SEARCH_URL)
        await session.goto(page, SEARCH_URL)
        await session.ensure_selector(page, "input.search-input")
        await session.require_no_captcha(page)
        await _apply_default_total_chinese(page)
        await _submit_search(page, args.query)
        await session.ensure_text(page, "条结果")
        await session.require_no_captcha(page)

        if scope == "theses":
            previous_mark = await page.locator(".countPageMark").text_content()
            await _apply_thesis_scope(page)
            await _wait_for_results_page_change(page, previous_mark)

        parsed = await parse_results_from_page(page)
        seen: set[str] = set()
        collected: list[dict[str, Any]] = []
        if scope == "theses":
            _collect_thesis_items(parsed, degree_mode, seen, collected)
        else:
            _collect_result_items(parsed, seen, collected)

        current_page = 1
        while len(collected) < requested and current_page < max_pages:
            if not await _move_to_next_results_page(page, current_page):
                break
            await session.require_no_captcha(page)
            parsed = await parse_results_from_page(page)
            if scope == "theses":
                _collect_thesis_items(parsed, degree_mode, seen, collected)
            else:
                _collect_result_items(parsed, seen, collected)
            current_page += 1

        source_items = collected[:requested]
        enriched_items, detail_errors = await _enrich_items_with_detail(session, source_items)
        data = {
            "query": args.query,
            "scope": scope,
            "degree": degree_mode if scope == "theses" else None,
            "requested": requested,
            "collected": len(enriched_items),
            "pagesScanned": current_page,
            "detailErrors": detail_errors,
            "items": enriched_items,
        }
        if scope == "theses":
            data["summary"] = {
                "doctoral": sum(1 for item in enriched_items if item.get("degree") == "博士"),
                "master": sum(1 for item in enriched_items if item.get("degree") == "硕士"),
            }
            message = f'Collected {len(enriched_items)} thesis detail record(s) for "{args.query}" in {degree_mode} mode.'
        else:
            message = f'Collected {len(enriched_items)} paper detail record(s) for "{args.query}".'
        return ok(message, data, page_url=page.url)


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

        try:
            await page.wait_for_function(
                """(prev) => {
                    const mark = document.querySelector('.countPageMark')?.innerText || '';
                    return Boolean(mark) && mark !== prev;
                }""",
                arg=previous_mark or "",
                timeout=15000,
            )
        except Exception:  # noqa: BLE001
            # CNKI occasionally updates list content without refreshing the page marker in time.
            # Continue and parse the page snapshot instead of failing hard.
            pass
        await session.require_no_captcha(page)
        parsed = await parse_results_from_page(page)
        message = "Updated CNKI page ordering." if args.sort_by else "Navigated the CNKI results page."
        return ok(message, parsed, page_url=page.url)
