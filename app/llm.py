from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .schemas import XiaohongshuRewriteRequest, XiaohongshuRewriteResponse


class XiaohongshuRewriteService:
    def __init__(
        self,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_env(cls) -> "XiaohongshuRewriteService":
        return cls(
            endpoint_url=os.getenv("LISTING_LLM_API_URL"),
            api_key=os.getenv("LISTING_LLM_API_KEY"),
            model=os.getenv("LISTING_LLM_MODEL"),
        )

    def rewrite(
        self, payload: XiaohongshuRewriteRequest
    ) -> XiaohongshuRewriteResponse:
        if not self.endpoint_url or not self.model:
            return self._local_fallback(payload)

        outbound = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rewrite Xiaohongshu source material into a clean product "
                        "listing. Return JSON with title, description, and topics."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "draft": payload.draft.model_dump(mode="json"),
                            "account_type": payload.account_type.value,
                            "style": payload.style,
                        }
                    ),
                },
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        raw_response = self._post_to_llm(outbound, headers)
        rewritten = self._parse_llm_response(raw_response)

        return XiaohongshuRewriteResponse(
            title=rewritten.get("title") or self._clean_title(payload.draft.title),
            description=(
                rewritten.get("description")
                or self._fallback_description(payload.draft.description, payload.draft.title)
            ),
            topics=self._normalize_topics(
                rewritten.get("topics"), payload.draft.category
            ),
            attributes={"creative_source": "llm_rewrite"},
            provider="llm_bridge",
            warnings=[],
        )

    def _post_to_llm(
        self, outbound: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(self.endpoint_url, json=outbound, headers=headers)
            response.raise_for_status()
            return response.json()

    def _local_fallback(
        self, payload: XiaohongshuRewriteRequest
    ) -> XiaohongshuRewriteResponse:
        title = self._clean_title(payload.draft.title)
        description = self._fallback_description(
            payload.draft.description, payload.draft.title
        )
        return XiaohongshuRewriteResponse(
            title=title,
            description=description,
            topics=self._normalize_topics(None, payload.draft.category),
            attributes={"creative_source": "local_rewrite"},
            provider="local_fallback",
            warnings=[
                "Using local fallback because LLM bridge configuration is incomplete."
            ],
        )

    @staticmethod
    def _parse_llm_response(raw_response: dict[str, Any]) -> dict[str, Any]:
        content = raw_response
        choices = raw_response.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = message.get("content", {})

        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}

        return content if isinstance(content, dict) else {}

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = title.strip()
        if " - " in cleaned:
            cleaned = cleaned.rsplit(" - ", 1)[0].strip()
        return cleaned or "Untitled Xiaohongshu Listing"

    @staticmethod
    def _fallback_description(description: str, title: str) -> str:
        source_text = (description or title).strip()
        if len(source_text) >= 20:
            return source_text
        return (
            f"{source_text} curated for a product listing with clear benefits, "
            "media review, and publishing readiness."
        )

    @staticmethod
    def _normalize_topics(value: Any, category: str) -> list[str]:
        topics: list[str] = []
        if isinstance(value, list):
            topics.extend(item.strip() for item in value if isinstance(item, str))
        if topics:
            return topics
        if category:
            topics.append(category)
        topics.append("xiaohongshu")
        return topics
