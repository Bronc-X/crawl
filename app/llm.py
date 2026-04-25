from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .schemas import (
    XiaohongshuAccountType,
    XiaohongshuRewriteRequest,
    XiaohongshuRewriteResponse,
)


def _clean_title(value: str) -> str:
    title = re.sub(r"\s*-\s*小红书\s*$", "", value.strip(), flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title)
    return title[:80].strip() or "小红书选品"


def _topic_candidates(title: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", title)
    seen: set[str] = set()
    topics: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        topics.append(normalized[:16])
        if len(topics) >= 5:
            break
    return topics or ["小红书选品", "上架文案"]


def _local_rewrite(
    payload: XiaohongshuRewriteRequest, warnings: list[str] | None = None
) -> XiaohongshuRewriteResponse:
    title = _clean_title(payload.draft.title)
    description = payload.draft.description.strip()
    if len(description) < 30:
        surface = (
            "个人号发布前人工确认"
            if payload.account_type == XiaohongshuAccountType.personal
            else "商品上架前校验"
        )
        description = (
            f"{title}。已根据来源内容整理为更完整的{surface}文案，"
            "包含核心卖点、使用场景和注意事项，方便继续补充素材后发布。"
        )

    return XiaohongshuRewriteResponse(
        title=title,
        description=description,
        topics=_topic_candidates(title),
        attributes={"creative_source": "local_fallback", "rewrite_style": payload.style},
        provider="local_fallback",
        warnings=warnings or ["未配置 LLM，已使用本地二创兜底。"],
    )


def _extract_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object.")
    return parsed


def _extract_llm_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    if {"title", "description"} <= response_payload.keys():
        return response_payload

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response is missing choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("LLM response choice is invalid.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM response message is invalid.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response content is empty.")
    return _extract_json_object(content)


def _topics_from_value(value: Any, fallback_title: str) -> list[str]:
    if isinstance(value, list):
        topics = [str(item).strip() for item in value if str(item).strip()]
        if topics:
            return topics[:8]
    return _topic_candidates(fallback_title)


class XiaohongshuRewriteService:
    def __init__(
        self,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.endpoint_url = self._normalize_endpoint_url(
            endpoint_url or os.getenv("LISTING_LLM_API_URL")
        )
        self.api_key = api_key or os.getenv("LISTING_LLM_API_KEY")
        self.model = model or os.getenv("LISTING_LLM_MODEL")

    @classmethod
    def from_env(cls) -> "XiaohongshuRewriteService":
        return cls()

    @staticmethod
    def _normalize_endpoint_url(endpoint_url: str | None) -> str | None:
        if not endpoint_url:
            return None
        normalized = endpoint_url.rstrip("/")
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return normalized

    def rewrite(
        self, payload: XiaohongshuRewriteRequest
    ) -> XiaohongshuRewriteResponse:
        missing = [
            name
            for name, value in (
                ("LISTING_LLM_API_URL", self.endpoint_url),
                ("LISTING_LLM_API_KEY", self.api_key),
                ("LISTING_LLM_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            return _local_rewrite(
                payload,
                warnings=[f"未配置 {', '.join(missing)}，已使用本地二创兜底。"],
            )

        outbound = self._build_outbound(payload)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response_payload = self._post_to_llm(outbound, headers)
            rewritten = _extract_llm_payload(response_payload)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError, KeyError) as exc:
            return _local_rewrite(
                payload,
                warnings=[f"LLM 二创失败，已使用本地兜底：{exc}"],
            )

        title = _clean_title(str(rewritten.get("title") or payload.draft.title))
        description = str(rewritten.get("description") or "").strip()
        if len(description) < 20:
            description = _local_rewrite(payload).description
        topics = _topics_from_value(rewritten.get("topics"), title)
        return XiaohongshuRewriteResponse(
            title=title,
            description=description,
            topics=topics,
            attributes={"creative_source": "llm_bridge", "rewrite_style": payload.style},
            provider="llm_bridge",
            warnings=[],
        )

    def _build_outbound(self, payload: XiaohongshuRewriteRequest) -> dict[str, Any]:
        draft = payload.draft.model_dump(mode="json")
        return {
            "model": self.model,
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是电商商品上架前的二创文案助手。"
                        "只输出 JSON，字段为 title、description、topics。"
                        "文案要真实克制，不能编造功效、库存、价格或承诺。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "account_type": payload.account_type.value,
                            "style": payload.style,
                            "draft": draft,
                            "requirements": [
                                "标题去掉来源平台后缀",
                                "描述至少 30 个中文字符或 60 个英文字符",
                                "保留可核验信息，不夸大功效",
                                "给出 3 到 6 个话题词",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

    def _post_to_llm(
        self, outbound: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(self.endpoint_url, json=outbound, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("LLM response must be a JSON object.")
            return data
