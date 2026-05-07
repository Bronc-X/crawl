from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from .schemas import MediaAsset
from .xiaohongshu import _extract_note_id


ACCESS_BLOCKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "access_blocked",
        re.compile(r"安全限制|安全验证|账号存在风险|IP存在风险|访问过于频繁|异常流量|当前账号存在风险"),
    ),
    (
        "login_required",
        re.compile(r"登录后查看搜索结果|扫码登录|手机号登录|马上登录即可|请登录"),
    ),
    (
        "captcha_required",
        re.compile(r"验证码|请完成验证|captcha", re.IGNORECASE),
    ),
)


@dataclass(slots=True)
class XiaohongshuBrowserNotePayload:
    note_id: str
    source_url: str
    final_url: str
    title: str
    description: str
    author_name: str = ""
    author_profile_url: str = ""
    publish_time: str = ""
    tags: list[str] = field(default_factory=list)
    media: list[MediaAsset] = field(default_factory=list)
    validated: bool = True
    blocker: str | None = None


class XiaohongshuBrowserBlockerError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"小红书访问被拦截: {reason}。请人工介入处理，工具不会绕过验证码或风控。")


class _BrowserNoteHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.images: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.text_by_id: dict[str, list[str]] = {}
        self.all_text: list[str] = []
        self._tag_stack: list[tuple[str, dict[str, str]]] = []
        self._in_title = False
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {name.lower(): value or "" for name, value in attrs}
        normalized_tag = tag.lower()
        self._tag_stack.append((normalized_tag, attrs_map))

        if normalized_tag == "title":
            self._in_title = True
            return

        if normalized_tag == "script":
            self._in_script = True
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

        if normalized_tag == "a":
            href = attrs_map.get("href")
            if href:
                self.links.append((href.strip(), ""))

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.scripts.append(data)
            return

        text = _normalize_text(data)
        if not text:
            return

        self.all_text.append(text)
        if self._in_title:
            self.title_parts.append(text)

        for _tag, attrs in reversed(self._tag_stack):
            node_id = attrs.get("id")
            if node_id:
                self.text_by_id.setdefault(node_id, []).append(text)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._in_title = False

        if normalized_tag == "script":
            self._in_script = False

        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index][0] == normalized_tag:
                del self._tag_stack[index:]
                return

    @property
    def document_title(self) -> str:
        return _normalize_text(" ".join(self.title_parts))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _first_text(*values: str | None) -> str:
    for value in values:
        normalized = _normalize_text(value or "")
        if normalized:
            return normalized
    return ""


def _search_text(query: str) -> str:
    return re.sub(r"^site:xiaohongshu\.com/explore\s+", "", query).strip()


def build_xiaohongshu_search_url(query: str) -> str:
    return f"https://www.xiaohongshu.com/search_result?keyword={quote(_search_text(query))}"


def detect_xiaohongshu_access_blocker(
    *, title: str | None = None, body: str | None = None, final_url: str | None = None
) -> str | None:
    final_url = final_url or ""
    combined = _normalize_text(f"{title or ''} {body or ''} {final_url}")

    if final_url and "xiaohongshu.com" not in final_url:
        return "redirected_offsite"

    if "captcha" in final_url.lower():
        return "captcha_required"

    for reason, pattern in ACCESS_BLOCKER_PATTERNS:
        if pattern.search(combined):
            return reason
    return None


def _absolute_media(source_url: str, urls: list[str]) -> list[MediaAsset]:
    seen: set[str] = set()
    media: list[MediaAsset] = []
    for raw_url in urls:
        raw_url = raw_url.strip()
        if not raw_url:
            continue
        url = urljoin(source_url, raw_url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if url in seen:
            continue
        seen.add(url)
        media.append(MediaAsset(url=url))
        if len(media) >= 9:
            break
    return media


def _extract_tags(text: str) -> list[str]:
    seen: set[str] = set()
    tags: list[str] = []
    for match in re.finditer(r"#[\w\u4e00-\u9fff-]+", text):
        tag = match.group(0)
        if tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) >= 24:
            break
    return tags


def _extract_author(parser: _BrowserNoteHtmlParser, source_url: str) -> tuple[str, str]:
    for href, _text in parser.links:
        if "/user/profile/" in href:
            return "", urljoin(source_url, href)
    return "", ""


def _extract_balanced_json(source: str, start: int) -> str | None:
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] not in "[{":
        return None

    stack: list[str] = []
    in_string = False
    quote_char = ""
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                in_string = False
            continue

        if char in ('"', "'"):
            in_string = True
            quote_char = char
            continue

        if char in "[{":
            stack.append("]" if char == "[" else "}")
            continue

        if char in "]}":
            if not stack or char != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return source[start : index + 1]
    return None


def _parse_initial_state_from_script(script: str) -> dict[str, Any] | None:
    normalized_script = unescape(script)
    assignment = re.search(
        r"(?:window\s*\.\s*)?(?:__INITIAL_STATE__|__INITIAL_DATA__|__INITIAL_STORE__|initialState)\s*=",
        normalized_script,
    )
    if not assignment:
        return None

    value_start = assignment.end()
    json_parse = re.match(r"\s*JSON\.parse\(\s*([\"'])(.*?)\1\s*\)", normalized_script[value_start:], re.DOTALL)
    if json_parse:
        try:
            decoded = json.loads(f'"{json_parse.group(2)}"')
            parsed = json.loads(decoded)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    json_text = _extract_balanced_json(normalized_script, value_start)
    if not json_text:
        return None

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _looks_like_note(value: dict[str, Any], note_id: str) -> bool:
    candidate_id = _first_text(
        _as_text(value.get("noteId")),
        _as_text(value.get("note_id")),
        _as_text(value.get("id")),
    )
    if note_id and candidate_id == note_id:
        return True
    return bool(
        _first_text(_as_text(value.get("title")), _as_text(value.get("displayTitle")))
        and _first_text(_as_text(value.get("desc")), _as_text(value.get("description")), _as_text(value.get("content")))
    )


def _iter_note_candidates(value: Any, note_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _looks_like_note(value, note_id):
            candidates.append(value)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                candidates.extend(_iter_note_candidates(nested, note_id))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_iter_note_candidates(item, note_id))
    return candidates


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""


def _collect_url_values(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in {"url", "src", "imageurl", "originurl", "originalurl"}:
                url = _as_text(nested)
                if url:
                    urls.append(url)
            elif isinstance(nested, (dict, list)):
                urls.extend(_collect_url_values(nested))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_collect_url_values(item))
    return urls


def _extract_structured_note_payload(
    *,
    source_url: str,
    final_url: str,
    parser: _BrowserNoteHtmlParser,
    full_text: str,
) -> XiaohongshuBrowserNotePayload | None:
    note_id_from_url = _extract_note_id(final_url) or _extract_note_id(source_url) or ""
    for script in parser.scripts:
        state = _parse_initial_state_from_script(script)
        if not state:
            continue
        candidates = _iter_note_candidates(state, note_id_from_url)
        if not candidates:
            continue

        note = candidates[0]
        user = note.get("user") or note.get("author") or note.get("userInfo") or {}
        if not isinstance(user, dict):
            user = {}

        note_id = _first_text(
            _as_text(note.get("noteId")),
            _as_text(note.get("note_id")),
            _as_text(note.get("id")),
            note_id_from_url,
        )
        title = _first_text(
            _as_text(note.get("title")),
            _as_text(note.get("displayTitle")),
            " ".join(parser.text_by_id.get("detail-title", [])),
            parser.meta.get("og:title"),
            parser.document_title,
            note_id,
        )
        description = _first_text(
            _as_text(note.get("desc")),
            _as_text(note.get("description")),
            _as_text(note.get("content")),
            " ".join(parser.text_by_id.get("detail-desc", [])),
            parser.meta.get("og:description"),
            parser.meta.get("description"),
        )
        author_name = _first_text(
            _as_text(user.get("nickname")),
            _as_text(user.get("name")),
            _as_text(user.get("nickName")),
        )
        user_id = _first_text(
            _as_text(user.get("userId")),
            _as_text(user.get("user_id")),
            _as_text(user.get("id")),
        )
        author_profile_url = (
            urljoin(source_url, f"/user/profile/{user_id}") if user_id else ""
        )
        if not author_name:
            fallback_author_name, fallback_author_url = _extract_author(parser, source_url)
            author_name = fallback_author_name
            author_profile_url = fallback_author_url

        media_urls = []
        for key in ("imageList", "images", "image_list", "media", "mediaList"):
            if key in note:
                media_urls.extend(_collect_url_values(note[key]))
        if not media_urls:
            media_urls.extend([parser.meta.get("og:image") or "", *parser.images])

        tags = _extract_tags(_normalize_text(f"{title} {description} {full_text}"))

        return XiaohongshuBrowserNotePayload(
            note_id=note_id,
            source_url=source_url,
            final_url=final_url,
            title=title,
            description=description,
            author_name=author_name,
            author_profile_url=author_profile_url,
            publish_time=_first_text(
                _as_text(note.get("time")),
                _as_text(note.get("publishTime")),
                _as_text(note.get("lastUpdateTime")),
            ),
            tags=tags,
            media=_absolute_media(source_url, media_urls),
            validated=True,
            blocker=None,
        )

    return None


def extract_browser_note_payload(
    *, source_url: str, final_url: str, html: str
) -> XiaohongshuBrowserNotePayload:
    if not _normalize_text(html):
        raise ValueError("browser extract html is required")

    parser = _BrowserNoteHtmlParser()
    parser.feed(html)

    full_text = _normalize_text(" ".join(parser.all_text))
    blocker = detect_xiaohongshu_access_blocker(
        title=parser.document_title or parser.meta.get("og:title"),
        body=full_text,
        final_url=final_url,
    )
    if blocker:
        raise XiaohongshuBrowserBlockerError(blocker)

    structured_payload = _extract_structured_note_payload(
        source_url=source_url,
        final_url=final_url,
        parser=parser,
        full_text=full_text,
    )
    if structured_payload:
        return structured_payload

    title = _first_text(
        " ".join(parser.text_by_id.get("detail-title", [])),
        parser.meta.get("og:title"),
        parser.meta.get("title"),
        parser.document_title,
        _extract_note_id(source_url),
    )
    description = _first_text(
        " ".join(parser.text_by_id.get("detail-desc", [])),
        parser.meta.get("og:description"),
        parser.meta.get("description"),
    )
    author_name, author_profile_url = _extract_author(parser, source_url)
    if not author_name:
        author_name = next(
            (
                text
                for text in parser.all_text
                if text and len(text) <= 40 and text not in (title, description)
            ),
            "",
        )

    media = _absolute_media(
        source_url,
        [
            parser.meta.get("og:image") or "",
            *parser.images,
        ],
    )
    note_id = _extract_note_id(final_url) or _extract_note_id(source_url) or ""
    tags = _extract_tags(_normalize_text(f"{title} {description} {full_text}"))

    return XiaohongshuBrowserNotePayload(
        note_id=note_id,
        source_url=source_url,
        final_url=final_url,
        title=title,
        description=description,
        author_name=author_name,
        author_profile_url=author_profile_url,
        publish_time=_first_text(" ".join(parser.text_by_id.get("publish-time", []))),
        tags=tags,
        media=media,
        validated=True,
        blocker=None,
    )
