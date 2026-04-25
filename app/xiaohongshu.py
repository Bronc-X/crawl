from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .schemas import (
    MediaAsset,
    XiaohongshuAccountType,
    XiaohongshuScrapeDraft,
    XiaohongshuScrapeRequest,
)


class XiaohongshuScrapeError(ValueError):
    pass


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.images: list[str] = []
        self.json_ld_blocks: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._in_title = True
            return

        if normalized_tag == "meta":
            key = attrs_map.get("property") or attrs_map.get("name")
            content = attrs_map.get("content")
            if key and content:
                self.meta[key.lower()] = content.strip()
            return

        if normalized_tag == "img":
            src = attrs_map.get("src") or attrs_map.get("data-src")
            if src:
                self.images.append(src.strip())
            return

        if normalized_tag == "script":
            script_type = attrs_map.get("type", "").lower()
            if script_type == "application/ld+json":
                self._in_json_ld = True
                self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._in_title = False
            return

        if normalized_tag == "script" and self._in_json_ld:
            block = "".join(self._json_ld_parts).strip()
            if block:
                self.json_ld_blocks.append(block)
            self._in_json_ld = False
            self._json_ld_parts = []

    @property
    def document_title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip())


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _iter_json_nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        nodes = [value]
        graph = value.get("@graph")
        if isinstance(graph, list):
            nodes.extend(item for item in graph if isinstance(item, dict))
        return nodes
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _parse_json_ld(blocks: list[str]) -> dict[str, Any]:
    for block in blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue

        for node in _iter_json_nodes(parsed):
            node_type = node.get("@type")
            if node_type == "Product" or (
                isinstance(node_type, list) and "Product" in node_type
            ):
                return node

        nodes = _iter_json_nodes(parsed)
        if nodes:
            return nodes[0]

    return {}


def _normalize_images(source_url: str, values: list[Any]) -> list[MediaAsset]:
    urls: list[str] = []
    for value in values:
        if isinstance(value, list):
            urls.extend(item for item in value if isinstance(item, str))
        elif isinstance(value, str):
            urls.append(value)

    seen: set[str] = set()
    media: list[MediaAsset] = []
    for url in urls:
        normalized = urljoin(source_url, url.strip())
        scheme = urlparse(normalized).scheme.lower()
        if not normalized or scheme not in ("http", "https") or normalized in seen:
            continue
        seen.add(normalized)
        media.append(MediaAsset(url=normalized))
        if len(media) >= 9:
            break
    return media


def _extract_note_id(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    match = re.search(r"/(?:explore|discovery/item)/([^/?#]+)", parsed.path)
    if match:
        return match.group(1)

    tail = parsed.path.rstrip("/").split("/")[-1]
    if tail:
        return tail
    return None


def _extract_price(product_json: dict[str, Any]) -> float | None:
    offers = product_json.get("offers")
    candidates: list[Any] = []
    if isinstance(offers, dict):
        candidates.append(offers.get("price"))
    candidates.append(product_json.get("price"))

    for candidate in candidates:
        if candidate in (None, ""):
            continue
        try:
            price = float(candidate)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _extract_currency(product_json: dict[str, Any]) -> str | None:
    offers = product_json.get("offers")
    if isinstance(offers, dict):
        currency = offers.get("priceCurrency")
        if isinstance(currency, str) and currency.strip():
            return currency.strip()
    return None


class XiaohongshuScraper:
    def fetch_html(self, source_url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 compatible listing-importer/0.1",
            "Accept": "text/html,application/xhtml+xml",
        }
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(source_url, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise XiaohongshuScrapeError(f"Could not fetch source URL: {exc}") from exc
        return response.text

    def scrape(self, payload: XiaohongshuScrapeRequest) -> XiaohongshuScrapeDraft:
        html = payload.html_snapshot or self.fetch_html(payload.source_url)
        parser = _MetadataParser()
        parser.feed(html)
        product_json = _parse_json_ld(parser.json_ld_blocks)

        title = _first_text(
            product_json.get("name"),
            parser.meta.get("og:title"),
            parser.meta.get("title"),
            parser.document_title,
            _extract_note_id(payload.source_url),
        )
        if title is None:
            raise XiaohongshuScrapeError("Could not extract a title from source.")

        description = _first_text(
            product_json.get("description"),
            parser.meta.get("og:description"),
            parser.meta.get("description"),
            title,
        )
        media = _normalize_images(
            payload.source_url,
            [
                product_json.get("image"),
                parser.meta.get("og:image"),
                *parser.images,
            ],
        )
        note_id = _extract_note_id(payload.source_url)
        attributes: dict[str, Any] = {
            "source_platform": "xiaohongshu",
            "source_url": payload.source_url,
            "xiaohongshu_account_type": payload.account_type.value,
            "publish_surface": (
                "note"
                if payload.account_type == XiaohongshuAccountType.personal
                else "merchant_listing"
            ),
        }
        if note_id:
            attributes["source_note_id"] = note_id
        if payload.account_type == XiaohongshuAccountType.personal:
            attributes["safety_mode"] = "human_confirm_required"
            attributes["confirm_required"] = payload.confirm_required
            attributes["topics"] = payload.topics

        title_override = (payload.title_override or "").strip()
        description_override = (payload.description_override or "").strip()
        if title_override:
            title = title_override
            attributes["creative_source"] = "llm_rewrite"
        if description_override:
            description = description_override
            attributes["creative_source"] = "llm_rewrite"
        if payload.topics:
            if payload.account_type == XiaohongshuAccountType.personal:
                attributes["topics"] = payload.topics
            else:
                attributes["creative_topics"] = payload.topics

        return XiaohongshuScrapeDraft(
            source_url=payload.source_url,
            title=title,
            description=description or "",
            category=payload.category or "xiaohongshu_import",
            price=payload.price or _extract_price(product_json),
            currency=payload.currency or _extract_currency(product_json) or "CNY",
            attributes=attributes,
            media=media,
        )
