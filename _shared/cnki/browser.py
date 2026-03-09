"""Playwright helpers for connecting Codex CNKI skills to an existing Chrome."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

if __package__ in (None, ""):
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from cnki_selectors import CAPTCHA_SELECTOR  # type: ignore
else:
    from .cnki_selectors import CAPTCHA_SELECTOR


class CnkiError(RuntimeError):
    """Structured runtime error for CLI responses."""

    def __init__(self, code: str, message: str, *, page_url: str | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.page_url = page_url
        self.data = data


def ok(message: str, data: Any = None, *, page_url: str | None = None) -> dict[str, Any]:
    payload = {"status": "ok", "message": message, "data": data}
    if page_url:
        payload["page_url"] = page_url
    return payload


def blocked(message: str, *, page_url: str | None = None) -> dict[str, Any]:
    payload = {"status": "blocked", "message": message, "error": "captcha", "data": None}
    if page_url:
        payload["page_url"] = page_url
    return payload


def fail(code: str, message: str, *, page_url: str | None = None, data: Any = None) -> dict[str, Any]:
    payload = {"status": "error", "message": message, "error": code, "data": data}
    if page_url:
        payload["page_url"] = page_url
    return payload


@dataclass
class ChromeSession:
    """Manage a CDP-backed Chrome session and provide CNKI page helpers."""

    cdp_url: str = "http://127.0.0.1:9222"
    _playwright: Any = None
    browser: Browser | None = None
    context: BrowserContext | None = None

    async def __aenter__(self) -> "ChromeSession":
        try:
            self._playwright = await async_playwright().start()
            self.browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
        except Exception as exc:  # noqa: BLE001
            raise CnkiError(
                "connection_failed",
                "Unable to connect to Chrome CDP. Start Chrome with --remote-debugging-port=9222.",
                data={"cdp_url": self.cdp_url, "detail": str(exc)},
            ) from exc

        if self.browser.contexts:
            self.context = self.browser.contexts[0]
        else:
            self.context = await self.browser.new_context()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._playwright is not None:
            await self._playwright.stop()

    async def get_or_open_page(self, target_url: str, *, reuse_keyword: str = "cnki.net") -> Page:
        assert self.context is not None
        for page in self.context.pages:
            if reuse_keyword in (page.url or ""):
                return page

        page = await self.context.new_page()
        await page.goto(target_url, wait_until="domcontentloaded")
        return page

    async def goto(self, page: Page, url: str) -> None:
        await page.goto(url, wait_until="domcontentloaded")

    async def ensure_selector(self, page: Page, selector: str, *, timeout: int = 15000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
        except PlaywrightTimeoutError as exc:
            raise CnkiError(
                "not_found",
                f"Timed out waiting for selector: {selector}",
                page_url=page.url,
            ) from exc

    async def ensure_text(self, page: Page, text: str, *, timeout: int = 15000) -> None:
        try:
            await page.get_by_text(text).first.wait_for(timeout=timeout)
        except PlaywrightTimeoutError as exc:
            raise CnkiError(
                "not_found",
                f"Timed out waiting for text: {text}",
                page_url=page.url,
            ) from exc

    async def detect_captcha(self, page: Page) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """(selector) => {
                        const el = document.querySelector(selector);
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.top >= 0 && style.display !== 'none' && style.visibility !== 'hidden';
                    }""",
                    CAPTCHA_SELECTOR,
                )
            )
        except PlaywrightError:
            return False

    async def require_no_captcha(self, page: Page) -> None:
        if await self.detect_captcha(page):
            raise CnkiError(
                "captcha",
                "CNKI is showing a slider captcha. Solve it in Chrome, then rerun the command.",
                page_url=page.url,
            )

    async def cookies_as_header(self, page: Page) -> str:
        assert self.context is not None
        cookies = await self.context.cookies(page.url or None)
        return "; ".join(f"{item['name']}={item['value']}" for item in cookies)


async def run_command(handler, args) -> dict[str, Any]:
    """Run a coroutine handler and normalize known errors."""

    try:
        return await handler(args)
    except CnkiError as exc:
        if exc.code == "captcha":
            return blocked(exc.message, page_url=exc.page_url)
        return fail(exc.code, exc.message, page_url=exc.page_url, data=exc.data)
    except PlaywrightTimeoutError as exc:
        return fail("timeout", "The CNKI page did not finish loading in time.", data={"detail": str(exc)})
    except PlaywrightError as exc:
        return fail("browser_error", "Playwright failed while automating CNKI.", data={"detail": str(exc)})
    except Exception as exc:  # noqa: BLE001
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return fail(getattr(exc, "code"), getattr(exc, "message"))
        return fail("unexpected_error", "Unexpected CNKI automation failure.", data={"detail": str(exc)})


def run_async(handler, args) -> dict[str, Any]:
    """Synchronous entry point for the CLI."""

    return asyncio.run(run_command(handler, args))
