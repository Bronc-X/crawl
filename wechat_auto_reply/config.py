from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .models import FAQRule


DEFAULT_REDLINE_KEYWORDS = (
    "价格",
    "报价",
    "折扣",
    "退款",
    "投诉",
    "法律",
    "合同",
)

DEFAULT_FAQ_RULES = (
    FAQRule(
        rule_id="greeting",
        name="Greeting",
        keywords=("你好", "您好", "hello", "在吗"),
        reply_text="您好，已收到您的消息，我先帮您处理。",
    ),
    FAQRule(
        rule_id="brochure",
        name="Brochure Request",
        keywords=("资料", "介绍", "案例", "pdf", "brochure"),
        reply_text="好的，我先把资料发给您，请稍等。",
        material_id="default-brochure",
    ),
)

DEFAULT_MATERIAL_MAP = {
    "default-brochure": "default-brochure.pdf",
}


def _default_platform() -> str:
    if sys.platform.startswith("win"):
        return "windows-pywinauto"
    if sys.platform == "darwin":
        return "macos-accessibility"
    return "windows-pywinauto"


def _split_csv(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ()
    return tuple(part.strip() for part in raw_value.split(",") if part.strip())


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AutoReplyConfig:
    platform: str
    dry_run: bool
    listen_chats: tuple[str, ...]
    runtime_dir: Path
    screenshots_dir: Path
    materials_dir: Path
    human_contact: str
    faq_rules: tuple[FAQRule, ...]
    redline_keywords: tuple[str, ...]
    material_map: dict[str, str]
    manual_only_contacts: frozenset[str]
    allowed_contacts: frozenset[str]
    include_outgoing_messages: bool
    disable_handoff_notifications: bool

    @classmethod
    def from_env(cls) -> "AutoReplyConfig":
        runtime_dir = Path(
            os.getenv("WECHAT_AUTO_REPLY_RUNTIME_DIR", "data/wechat_auto_reply/runtime")
        )
        materials_dir = Path(
            os.getenv("WECHAT_AUTO_REPLY_MATERIALS_DIR", "data/wechat_auto_reply/materials")
        )
        human_contact = os.getenv("WECHAT_AUTO_REPLY_HUMAN_CONTACT", "manual-owner")
        dry_run = os.getenv("WECHAT_AUTO_REPLY_DRY_RUN", "true").lower() not in {"0", "false", "no"}
        redline_keywords = _split_csv(os.getenv("WECHAT_AUTO_REPLY_REDLINE_KEYWORDS")) or DEFAULT_REDLINE_KEYWORDS
        manual_only_contacts = frozenset(_split_csv(os.getenv("WECHAT_AUTO_REPLY_MANUAL_ONLY_CONTACTS")))
        allowed_contacts = frozenset(_split_csv(os.getenv("WECHAT_AUTO_REPLY_ALLOWED_CONTACTS")))
        include_outgoing_messages = _env_flag("WECHAT_AUTO_REPLY_INCLUDE_OUTGOING_MESSAGES")
        disable_handoff_notifications = _env_flag("WECHAT_AUTO_REPLY_DISABLE_HANDOFF")

        return cls(
            platform=os.getenv("WECHAT_AUTO_REPLY_PLATFORM", _default_platform()),
            dry_run=dry_run,
            listen_chats=_split_csv(os.getenv("WECHAT_AUTO_REPLY_LISTEN_CHATS")),
            runtime_dir=runtime_dir,
            screenshots_dir=runtime_dir / "screenshots",
            materials_dir=materials_dir,
            human_contact=human_contact,
            faq_rules=DEFAULT_FAQ_RULES,
            redline_keywords=redline_keywords,
            material_map=dict(DEFAULT_MATERIAL_MAP),
            manual_only_contacts=manual_only_contacts,
            allowed_contacts=allowed_contacts,
            include_outgoing_messages=include_outgoing_messages,
            disable_handoff_notifications=disable_handoff_notifications,
        )
