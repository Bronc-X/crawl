from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.xiaohongshu_browser import (
    XiaohongshuBrowserBlockerError,
    build_xiaohongshu_search_url,
    detect_xiaohongshu_access_blocker,
    extract_browser_note_payload,
)


async def _human_delay(min_seconds: float, max_seconds: float) -> None:
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def _capture_login_state(args: argparse.Namespace) -> int:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError:
        print("PLAYWRIGHT_MISSING install playwright before browser capture")
        return 2

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel=args.browser)
        context = await browser.new_context(viewport={"width": 1440, "height": 1600})
        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com/", wait_until="domcontentloaded")
        print("XHS_LOGIN_REQUIRED complete login manually, then press Enter here")
        await asyncio.to_thread(input)
        Path(args.storage_state).parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=args.storage_state)
        await browser.close()
    print(f"XHS_LOGIN_STATE_SAVED {args.storage_state}")
    return 0


async def _scrape_search(args: argparse.Namespace) -> int:
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError:
        print("PLAYWRIGHT_MISSING install playwright before browser scraping")
        return 2

    storage_state = Path(args.storage_state)
    if not args.cdp_url and not storage_state.exists():
        print(f"XHS_LOGIN_STATE_MISSING {storage_state}")
        return 2

    results: list[dict[str, Any]] = []
    search_url = build_xiaohongshu_search_url(args.keyword)

    async with async_playwright() as p:
        if args.cdp_url:
            browser = await p.chromium.connect_over_cdp(args.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
        else:
            browser = await p.chromium.launch(headless=args.headless, channel=args.browser)
            context = await browser.new_context(
                storage_state=str(storage_state),
                viewport={"width": 1440, "height": 1600},
            )
        page = await context.new_page()
        try:
            await _human_delay(args.min_delay, args.max_delay)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await _human_delay(args.min_delay, args.max_delay)
            body = await page.locator("body").inner_text(timeout=5000)
            blocker = detect_xiaohongshu_access_blocker(
                title=await page.title(), body=body, final_url=page.url
            )
            if blocker:
                print(f"XHS_BLOCKED {blocker}")
                return 3

            cards = page.locator(".note-item:visible")
            count = await cards.count()
            indexes = list(range(count))
            random.shuffle(indexes)

            for index in indexes[: args.limit]:
                card = cards.nth(index)
                href = await card.locator('a[href*="/explore/"]').first.get_attribute("href")
                if not href:
                    continue
                source_url = urljoin("https://www.xiaohongshu.com", href)
                await card.scroll_into_view_if_needed(timeout=5000)
                await _human_delay(args.min_delay, args.max_delay)
                await card.click(timeout=10000)
                await _human_delay(args.detail_delay, args.detail_delay + 4)
                html = await page.content()
                try:
                    payload = extract_browser_note_payload(
                        source_url=source_url,
                        final_url=page.url,
                        html=html,
                    )
                except XiaohongshuBrowserBlockerError as exc:
                    print(f"XHS_BLOCKED {exc.reason}")
                    return 3
                results.append(
                    {
                        "source_url": payload.source_url,
                        "final_url": payload.final_url,
                        "html": html,
                        "title": payload.title,
                        "note_id": payload.note_id,
                    }
                )
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
                await _human_delay(args.min_delay, args.max_delay)
        finally:
            await browser.close()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"keyword": args.keyword, "search_url": search_url, "items": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"XHS_BROWSER_WORKER_DONE {output_path} items={len(results)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Low-frequency XHS browser worker with human login and blocker stop.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("capture-login")
    login.add_argument("--storage-state", default=".auth/xhs-storage.json")
    login.add_argument("--browser", default="msedge")

    scrape = subparsers.add_parser("scrape-search")
    scrape.add_argument("--keyword", required=True)
    scrape.add_argument("--limit", type=int, default=3)
    scrape.add_argument("--storage-state", default=".auth/xhs-storage.json")
    scrape.add_argument(
        "--cdp-url",
        default=None,
        help="Connect to an already logged-in local Chrome/Edge CDP endpoint, for example http://127.0.0.1:9222.",
    )
    scrape.add_argument("--output", default="data/xhs-browser/latest.json")
    scrape.add_argument("--browser", default="msedge")
    scrape.add_argument("--headless", action="store_true")
    scrape.add_argument("--min-delay", type=float, default=8.0)
    scrape.add_argument("--max-delay", type=float, default=18.0)
    scrape.add_argument("--detail-delay", type=float, default=8.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "capture-login":
        return asyncio.run(_capture_login_state(args))
    if args.command == "scrape-search":
        return asyncio.run(_scrape_search(args))
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
