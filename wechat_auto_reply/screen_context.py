from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .models import IncomingMessage


_TIME_ONLY_PATTERNS = (
    re.compile(r"^\d{1,2}:\d{2}$"),
    re.compile(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$"),
    re.compile(r"^(?:今天|昨天|前天|星期[一二三四五六日天]|周[一二三四五六日天])\s*\d{1,2}:\d{2}$"),
    re.compile(r"^(今天|昨天|前天|刚刚)$"),
)
_FILE_SIZE_PATTERN = re.compile(r"^\d+(?:\.\d+)?\s?(?:B|KB|MB|GB|TB|K|M|G)$", re.IGNORECASE)
_FILE_NAME_PATTERN = re.compile(r".+\.(?:zip|rar|7z|pdf|doc|docx|xls|xlsx|ppt|pptx|txt|csv)$", re.IGNORECASE)
_NEW_MESSAGE_PATTERN = re.compile(r"^\d+条新消息$")
_GENERIC_UI_NOISE = frozenset(
    {
        "已读",
        "未读",
        "查看更多消息",
        "查看更多",
        "微信",
        "WeChat",
        "微信电脑版",
        "·微信电脑版",
    }
)
_COMPOSER_PLACEHOLDERS = frozenset(
    {
        "发消息",
        "输入",
        "输入消息",
        "请输入",
        "请输入消息",
        "发送",
    }
)


def _collapse_line(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split()).strip()


def _normalize_lines(text: str) -> list[str]:
    return [_collapse_line(line) for line in text.splitlines() if _collapse_line(line)]


def _looks_like_time_only(line: str) -> bool:
    for pattern in _TIME_ONLY_PATTERNS:
        if pattern.fullmatch(line):
            return True
    return False


def _looks_like_attachment_noise(line: str) -> bool:
    if _FILE_SIZE_PATTERN.fullmatch(line):
        return True
    if _FILE_NAME_PATTERN.fullmatch(line):
        return True
    if _NEW_MESSAGE_PATTERN.fullmatch(line):
        return True
    if line.startswith("[") and line.endswith("]"):
        return True
    return False


def _keep_message_line(line: str) -> bool:
    if not line:
        return False
    if line in _GENERIC_UI_NOISE:
        return False
    if _looks_like_time_only(line):
        return False
    if _looks_like_attachment_noise(line):
        return False
    return True


def _pick_contact_name(lines: list[str], fallback_contact_name: str | None) -> str | None:
    for line in lines:
        if _keep_message_line(line):
            return line
    fallback = _collapse_line(fallback_contact_name or "")
    return fallback or None


def _normalize_line_items(raw_items: object) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    if not isinstance(raw_items, list):
        return normalized

    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        text = _collapse_line(str(item.get("text") or ""))
        if not text:
            continue
        normalized.append(
            {
                "text": text,
                "left": int(item.get("left") or 0),
                "top": int(item.get("top") or 0),
                "right": int(item.get("right") or 0),
                "bottom": int(item.get("bottom") or 0),
                "confidence": item.get("confidence"),
            }
        )
    normalized.sort(key=lambda item: (int(item["top"]), int(item["left"])))
    return normalized


def _pick_message_text(lines: list[str]) -> str | None:
    filtered = [line for line in lines if _keep_message_line(line)]
    if not filtered:
        return None
    return "\n".join(filtered)


def _pick_composer_text(lines: list[str]) -> str | None:
    filtered = [
        line
        for line in lines
        if _keep_message_line(line) and line not in _COMPOSER_PLACEHOLDERS
    ]
    if not filtered:
        return None
    return "\n".join(filtered)


def _pick_latest_from_message_pane(
    region: Mapping[str, object],
    latest_lines: list[str],
    include_outgoing_messages: bool = False,
) -> str | None:
    line_items = _normalize_line_items(region.get("line_items"))
    if line_items:
        right_boundary = max(int(item["right"]) for item in line_items)
        incoming_threshold = max(80, int(right_boundary * 0.55))
        candidate_items = [
            item
            for item in line_items
            if _keep_message_line(str(item["text"]))
            and (include_outgoing_messages or int(item["left"]) <= incoming_threshold)
        ]
        if candidate_items:
            candidate_items.sort(key=lambda item: (int(item["bottom"]), int(item["left"])))
            return str(candidate_items[-1]["text"])

    return _pick_message_text(latest_lines)


def _build_region_map(ocr_payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {
        str(region.get("name")): region
        for region in ocr_payload.get("regions", [])
        if isinstance(region, Mapping) and region.get("name")
    }


def write_context_failure(
    output_dir: Path,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "supported": False,
        "reason": reason,
        "metadata": metadata or {},
    }
    artifact_path = output_dir / "context-probe.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["artifact_path"] = str(artifact_path)
    return payload


def build_context_from_ocr_payload(
    ocr_payload: Mapping[str, object],
    output_dir: Path,
    fallback_contact_name: str | None = None,
    metadata: dict[str, object] | None = None,
) -> tuple[dict[str, object], IncomingMessage | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = metadata or {}

    if not ocr_payload.get("supported"):
        reason = str(ocr_payload.get("reason") or "ocr probe is not available")
        return write_context_failure(output_dir, reason, metadata=metadata), None

    region_map = _build_region_map(ocr_payload)
    header_region = region_map.get("chat_header", {})
    latest_region = region_map.get("latest_message_band", {})
    message_pane_region = region_map.get("message_pane", {})
    composer_region = region_map.get("composer_input", {})
    selected_conversation_region = region_map.get("selected_conversation", {})

    header_lines = _normalize_lines(str(header_region.get("text") or ""))
    selected_conversation_lines = _normalize_lines(str(selected_conversation_region.get("text") or ""))
    latest_lines = _normalize_lines(str(latest_region.get("text") or ""))
    message_pane_lines = _normalize_lines(str(message_pane_region.get("text") or ""))
    composer_lines = _normalize_lines(str(composer_region.get("text") or ""))

    contact_name = _pick_contact_name(header_lines, None)
    if not contact_name:
        contact_name = _pick_contact_name(selected_conversation_lines, fallback_contact_name)
    else:
        contact_name = _pick_contact_name(header_lines, fallback_contact_name)

    include_outgoing_messages = bool(metadata.get("include_outgoing_messages"))
    latest_message_text = _pick_latest_from_message_pane(
        message_pane_region,
        message_pane_lines,
        include_outgoing_messages=include_outgoing_messages,
    )
    if not latest_message_text:
        latest_message_text = _pick_message_text(latest_lines)
    composer_text = _pick_composer_text(composer_lines)

    regions = []
    for region_name in ("selected_conversation", "chat_header", "message_pane", "latest_message_band", "composer_input"):
        region = region_map.get(region_name, {})
        region_lines = _normalize_lines(str(region.get("text") or ""))
        regions.append(
            {
                "name": region_name,
                "success": bool(region.get("success")),
                "raw_text": str(region.get("text") or ""),
                "normalized_lines": region_lines,
                "mean_confidence": region.get("mean_confidence"),
                "line_count": region.get("line_count"),
            }
        )

    incoming_message = None
    if latest_message_text:
        message_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        resolved_contact = contact_name or "unknown-contact"
        incoming_message = IncomingMessage(
            message_id=f"screen-probe:{message_stamp}",
            conversation_id=resolved_contact,
            contact_name=resolved_contact,
            text=latest_message_text,
            raw_context=tuple(item for item in (composer_text,) if item),
            metadata={
                "source": "ocr_probe",
                "chat_header_confidence": str(header_region.get("mean_confidence") or ""),
                "latest_message_confidence": str(latest_region.get("mean_confidence") or ""),
                "composer_confidence": str(composer_region.get("mean_confidence") or ""),
            },
        )

    payload = {
        "supported": True,
        "contact_name": contact_name,
        "latest_message_text": latest_message_text,
        "composer_text": composer_text,
        "regions": regions,
        "incoming_message": (
            {
                "message_id": incoming_message.message_id,
                "conversation_id": incoming_message.conversation_id,
                "contact_name": incoming_message.contact_name,
                "text": incoming_message.text,
                "raw_context": list(incoming_message.raw_context),
                "metadata": incoming_message.metadata,
            }
            if incoming_message
            else None
        ),
        "metadata": metadata,
    }
    artifact_path = output_dir / "context-probe.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["artifact_path"] = str(artifact_path)
    return payload, incoming_message
