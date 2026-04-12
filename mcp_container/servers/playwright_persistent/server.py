"""Playwright-persistent MCP server — browser automation with a persistent context."""

from __future__ import annotations

import base64
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent_power_pack.logging import get_logger

log = get_logger("servers.playwright_persistent")

# Lazy-initialized browser state
_browser = None
_context = None
_page = None


async def _ensure_browser():
    """Lazily initialize playwright browser, context, and page."""
    global _browser, _context, _page
    if _page is not None:
        return _page

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)
        _context = await _browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="agent-power-pack/0.0.1",
        )
        _page = await _context.new_page()
        log.info("browser_initialized")
        return _page
    except Exception as exc:
        log.error("browser_init_failed", error=str(exc))
        raise RuntimeError(
            f"Failed to initialize Playwright browser: {exc}. "
            "Ensure playwright browsers are installed (playwright install chromium)."
        ) from exc


def create_server() -> FastMCP:
    mcp = FastMCP("playwright-persistent")

    @mcp.tool()
    async def navigate(url: str) -> str:
        """Navigate to a URL and return the page title."""
        page = await _ensure_browser()
        response = await page.goto(url, wait_until="domcontentloaded")
        status = response.status if response else "unknown"
        title = await page.title()
        return f"Navigated to {url} (status={status}, title={title})"

    @mcp.tool()
    async def screenshot(selector: str | None = None) -> str:
        """Take a screenshot of the page or a specific element. Returns base64-encoded PNG."""
        page = await _ensure_browser()
        if selector:
            element = await page.query_selector(selector)
            if not element:
                return f"Element not found: {selector}"
            raw = await element.screenshot()
        else:
            raw = await page.screenshot(full_page=False)
        return base64.b64encode(raw).decode("ascii")

    @mcp.tool()
    async def click(selector: str) -> str:
        """Click an element matching the CSS selector."""
        page = await _ensure_browser()
        await page.click(selector)
        return f"Clicked: {selector}"

    @mcp.tool()
    async def fill(selector: str, value: str) -> str:
        """Fill an input element with a value."""
        page = await _ensure_browser()
        await page.fill(selector, value)
        return f"Filled {selector} with {len(value)} chars"

    @mcp.tool()
    async def get_text(selector: str | None = None) -> str:
        """Get text content of an element or the whole page."""
        page = await _ensure_browser()
        if selector:
            element = await page.query_selector(selector)
            if not element:
                return f"Element not found: {selector}"
            return await element.text_content() or ""
        return await page.text_content("body") or ""

    @mcp.tool()
    async def evaluate(script: str) -> Any:
        """Evaluate a JavaScript expression in the page context."""
        page = await _ensure_browser()
        result = await page.evaluate(script)
        return result

    @mcp.tool()
    async def wait_for(selector: str, state: str = "visible") -> str:
        """Wait for an element to reach a given state.

        Args:
            selector: CSS selector to wait for.
            state: One of 'attached', 'detached', 'visible', 'hidden'.
        """
        page = await _ensure_browser()
        await page.wait_for_selector(selector, state=state, timeout=30000)
        return f"Element {selector} is now {state}"

    return mcp
