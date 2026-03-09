"""Search-related CNKI workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import random
from typing import Any

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from browser import ChromeSession, CnkiError, blocked, ok, partial  # type: ignore
    from cnki_selectors import ADVANCED_SEARCH_URL, SEARCH_URL  # type: ignore
    from paper import ensure_detail_page, extract_detail_from_page  # type: ignore
else:
    from .browser import ChromeSession, CnkiError, blocked, ok, partial
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
DETAIL_RETRYABLE_ERROR_CODES = {"overlay", "page_error", "page_not_supported", "timeout", "browser_error", "unexpected_error"}


@dataclass(slots=True)
class DetailConcurrencyConfig:
    mode: str
    initial_concurrency: int
    max_concurrency: int
    min_delay_ms: int
    max_delay_ms: int
    success_to_three: int = 5
    success_to_four: int = 13
    max_retries: int = 2
    max_recoveries: int = 2
    cooldown_min_ms: int = 20000
    cooldown_max_ms: int = 45000


@dataclass(slots=True)
class DetailJob:
    index: int
    item: dict[str, Any]
    attempts: int = 0


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
        dialog_task = asyncio.create_task(page.wait_for_event("dialog"))
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

            # No dialog appeared and the first result row became available.
            finished.result()

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


def _build_detail_config(args) -> DetailConcurrencyConfig:
    mode = getattr(args, "concurrency_mode", "adaptive") or "adaptive"
    min_delay_ms = max(0, int(getattr(args, "min_delay_ms", 300) or 0))
    max_delay_ms = max(min_delay_ms, int(getattr(args, "max_delay_ms", 1200) or min_delay_ms))
    if mode == "serial":
        return DetailConcurrencyConfig(
            mode="serial",
            initial_concurrency=1,
            max_concurrency=1,
            min_delay_ms=min_delay_ms,
            max_delay_ms=max_delay_ms,
        )

    max_concurrency = max(1, min(4, int(getattr(args, "max_concurrency", 4) or 4)))
    return DetailConcurrencyConfig(
        mode="adaptive",
        initial_concurrency=min(2, max_concurrency),
        max_concurrency=max_concurrency,
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
    )


def _make_detail_error(code: str, message: str, *, page_url: str | None = None, detail: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if page_url:
        payload["page_url"] = page_url
    if detail is not None:
        payload["detail"] = detail
    return payload


def _merge_detail_into_record(record: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    merged = dict(record)
    merged["abstract"] = detail.get("abstract", "")
    merged["keywords"] = detail.get("keywords", [])
    merged["fund"] = detail.get("fund", "")
    merged["classification"] = detail.get("classification", "")
    merged["affiliations"] = detail.get("affiliations", [])
    merged["detailAuthors"] = detail.get("authors", [])
    merged["journalDetail"] = detail.get("journal", "")
    merged["pubInfo"] = detail.get("pubInfo", "")
    merged["detail"] = detail
    return merged


async def _sleep_with_jitter(config: DetailConcurrencyConfig) -> None:
    if config.max_delay_ms <= 0:
        return
    delay_ms = random.randint(config.min_delay_ms, config.max_delay_ms)
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)


async def _collect_single_detail(
    session: ChromeSession,
    detail_page,
    job: DetailJob,
    config: DetailConcurrencyConfig,
) -> dict[str, Any]:
    record = dict(job.item)
    detail_url = (record.get("url") or "").strip()
    if not detail_url:
        error = _make_detail_error("not_found", "Result item has no detail URL.")
        return {"kind": "error", "job": job, "record": record, "error": error, "retryable": False}

    await _sleep_with_jitter(config)
    await session.dismiss_known_overlays(detail_page)

    try:
        await ensure_detail_page(session, detail_page, detail_url)
        await session.dismiss_known_overlays(detail_page)
        risk = await session.detect_risk(detail_page)
        if risk:
            if risk["code"] == "captcha":
                return {"kind": "captcha", "job": job, "record": record, "risk": risk}
            return {"kind": "risk", "job": job, "record": record, "risk": risk}
        detail = await extract_detail_from_page(detail_page)
        return {"kind": "success", "job": job, "record": _merge_detail_into_record(record, detail)}
    except CnkiError as exc:
        risk = await session.detect_risk(detail_page)
        if risk:
            if risk["code"] == "captcha":
                return {"kind": "captcha", "job": job, "record": record, "risk": risk}
            return {"kind": "risk", "job": job, "record": record, "risk": risk}
        error = _make_detail_error(exc.code, exc.message, page_url=exc.page_url)
        return {
            "kind": "error",
            "job": job,
            "record": record,
            "error": error,
            "retryable": exc.code in DETAIL_RETRYABLE_ERROR_CODES,
        }
    except Exception as exc:  # noqa: BLE001
        risk = await session.detect_risk(detail_page)
        if risk:
            if risk["code"] == "captcha":
                return {"kind": "captcha", "job": job, "record": record, "risk": risk}
            return {"kind": "risk", "job": job, "record": record, "risk": risk}
        error = _make_detail_error("unexpected_error", str(exc), page_url=detail_page.url)
        return {"kind": "error", "job": job, "record": record, "error": error, "retryable": True}


async def _enrich_items_with_detail(
    session: ChromeSession,
    items: list[dict[str, Any]],
    args,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config = _build_detail_config(args)
    assert session.context is not None

    detail_pages = [await session.context.new_page() for _ in range(config.max_concurrency)]
    records = [dict(item) for item in items]
    errors: list[dict[str, Any]] = []
    stats = {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "retried": 0,
        "captchaHits": 0,
        "cooldowns": 0,
    }
    risk_events: list[dict[str, Any]] = []
    pending = [DetailJob(index=index, item=dict(item)) for index, item in enumerate(items)]
    current_concurrency = config.initial_concurrency
    consecutive_successes = 0
    recoveries = 0
    blocked_state: dict[str, Any] | None = None
    stopped_early = False

    try:
        while pending:
            batch_size = 1 if config.mode == "serial" else min(current_concurrency, len(pending))
            batch_jobs = [pending.pop(0) for _ in range(batch_size)]
            outcomes = await asyncio.gather(
                *[
                    _collect_single_detail(session, detail_pages[index], job, config)
                    for index, job in enumerate(batch_jobs)
                ]
            )

            risk_in_batch = False
            for outcome in outcomes:
                stats["attempted"] += 1
                job = outcome["job"]
                title = job.item.get("title", "")
                url = job.item.get("url", "")

                if outcome["kind"] == "success":
                    records[job.index] = outcome["record"]
                    stats["succeeded"] += 1
                    consecutive_successes += 1
                    continue

                consecutive_successes = 0

                if outcome["kind"] == "captcha":
                    stats["captchaHits"] += 1
                    blocked_state = {
                        "message": "CNKI showed a slider captcha during batch detail collection. Solve it in Chrome, then rerun the command.",
                        "code": "captcha",
                    }
                    error = _make_detail_error(
                        "captcha",
                        "CNKI showed a slider captcha during batch detail collection.",
                        page_url=outcome["risk"].get("page_url"),
                        detail=outcome["risk"].get("detail"),
                    )
                    records[job.index]["detailError"] = error
                    errors.append({"title": title, "url": url, **error})
                    risk_events.append(
                        {
                            "type": "blocked",
                            "code": "captcha",
                            "title": title,
                            "attempt": job.attempts + 1,
                        }
                    )
                    break

                if outcome["kind"] == "risk":
                    risk_in_batch = True
                    risk = outcome["risk"]
                    risk_events.append(
                        {
                            "type": "risk",
                            "code": risk["code"],
                            "title": title,
                            "attempt": job.attempts + 1,
                        }
                    )
                    if job.attempts < config.max_retries:
                        stats["retried"] += 1
                        pending.append(DetailJob(index=job.index, item=job.item, attempts=job.attempts + 1))
                    else:
                        error = _make_detail_error(
                            risk["code"],
                            risk["message"],
                            page_url=risk.get("page_url"),
                            detail=risk.get("detail"),
                        )
                        records[job.index]["detailError"] = error
                        errors.append({"title": title, "url": url, **error})
                        stats["failed"] += 1
                    continue

                error = outcome["error"]
                if outcome["retryable"] and job.attempts < config.max_retries:
                    stats["retried"] += 1
                    pending.append(DetailJob(index=job.index, item=job.item, attempts=job.attempts + 1))
                    if error["code"] in DETAIL_RETRYABLE_ERROR_CODES:
                        risk_in_batch = True
                        risk_events.append(
                            {
                                "type": "retry",
                                "code": error["code"],
                                "title": title,
                                "attempt": job.attempts + 1,
                            }
                        )
                else:
                    records[job.index]["detailError"] = error
                    errors.append({"title": title, "url": url, **error})
                    stats["failed"] += 1

            if blocked_state:
                stopped_early = True
                break

            if config.mode == "adaptive":
                target_concurrency = current_concurrency
                if risk_in_batch:
                    if current_concurrency != 1:
                        risk_events.append(
                            {
                                "type": "downgrade",
                                "from": current_concurrency,
                                "to": 1,
                            }
                        )
                    target_concurrency = 1
                    if pending:
                        if recoveries < config.max_recoveries:
                            cooldown_ms = random.randint(config.cooldown_min_ms, config.cooldown_max_ms)
                            stats["cooldowns"] += 1
                            recoveries += 1
                            risk_events.append(
                                {
                                    "type": "cooldown",
                                    "milliseconds": cooldown_ms,
                                    "recovery": recoveries,
                                }
                            )
                            current_concurrency = target_concurrency
                            await asyncio.sleep(cooldown_ms / 1000)
                        else:
                            stopped_early = True
                            risk_events.append({"type": "stop", "reason": "max_recoveries_exceeded"})
                            current_concurrency = target_concurrency
                            break
                else:
                    if consecutive_successes >= config.success_to_four:
                        target_concurrency = min(4, config.max_concurrency)
                    elif consecutive_successes >= config.success_to_three:
                        target_concurrency = min(3, config.max_concurrency)
                    if target_concurrency > current_concurrency:
                        risk_events.append(
                            {
                                "type": "scale_up",
                                "from": current_concurrency,
                                "to": target_concurrency,
                            }
                        )
                    current_concurrency = target_concurrency

        meta = {
            "concurrencyMode": config.mode,
            "initialConcurrency": config.initial_concurrency,
            "maxConcurrency": config.max_concurrency,
            "finalConcurrency": current_concurrency,
            "detailStats": stats,
            "riskEvents": risk_events,
            "blocked": blocked_state is not None,
            "blockedMessage": blocked_state["message"] if blocked_state else "",
            "stoppedEarly": stopped_early and blocked_state is None,
        }
        return records, errors, meta
    finally:
        for detail_page in detail_pages:
            await detail_page.close()


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
        enriched_items, detail_errors, detail_meta = await _enrich_items_with_detail(session, source_items, args)
        data = {
            "query": args.query,
            "scope": scope,
            "degree": degree_mode if scope == "theses" else None,
            "requested": requested,
            "collected": len(enriched_items),
            "pagesScanned": current_page,
            "detailErrors": detail_errors,
            "concurrencyMode": detail_meta["concurrencyMode"],
            "initialConcurrency": detail_meta["initialConcurrency"],
            "maxConcurrency": detail_meta["maxConcurrency"],
            "finalConcurrency": detail_meta["finalConcurrency"],
            "detailStats": detail_meta["detailStats"],
            "riskEvents": detail_meta["riskEvents"],
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
        if detail_meta["blocked"]:
            return blocked(detail_meta["blockedMessage"], data, page_url=page.url)
        if detail_meta["stoppedEarly"]:
            return partial(
                f'{message} CNKI throttling forced an early stop before every queued detail page could be collected.',
                data,
                page_url=page.url,
            )
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
