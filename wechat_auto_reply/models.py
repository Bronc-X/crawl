from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionKind(str, Enum):
    SAFE_REPLY = "safe_reply"
    SAFE_MATERIAL = "safe_material"
    HANDOFF = "handoff"


class ConversationState(str, Enum):
    IDLE = "idle"
    NEW_MESSAGE_DETECTED = "new_message_detected"
    CONTEXT_EXTRACTED = "context_extracted"
    CLASSIFIED_SAFE = "classified_safe"
    CLASSIFIED_HANDOFF = "classified_handoff"
    SENDING = "sending"
    SEND_VERIFIED = "send_verified"
    SEND_FAILED = "send_failed"
    HANDOFF_NOTIFIED = "handoff_notified"
    OPERATOR_TAKEOVER = "operator_takeover"
    ABNORMAL_UI_STATE = "abnormal_ui_state"


@dataclass(frozen=True)
class FAQRule:
    rule_id: str
    name: str
    keywords: tuple[str, ...]
    reply_text: str | None = None
    material_id: str | None = None


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    conversation_id: str
    contact_name: str
    text: str
    received_at: datetime = field(default_factory=utc_now)
    raw_context: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    reason: str
    rule_id: str | None = None
    reply_text: str | None = None
    material_id: str | None = None
    matched_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str
    screenshot_path: Path | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutorCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DetectedProcess:
    process_name: str
    pid: int
    executable_path: str | None = None
    window_title: str | None = None


@dataclass(frozen=True)
class DetectedWindow:
    title: str
    pid: int
    class_name: str | None = None
    hwnd: int | None = None


@dataclass(frozen=True)
class ExecutorHealth:
    executor_name: str
    supported: bool
    details: str
    checks: tuple[ExecutorCheck, ...] = ()
    detected_processes: tuple[DetectedProcess, ...] = ()
    detected_windows: tuple[DetectedWindow, ...] = ()


@dataclass(frozen=True)
class OrchestrationResult:
    final_state: ConversationState
    decision: Decision
    send_result: ActionResult | None
    handoff_result: ActionResult | None
    state_history: tuple[ConversationState, ...]
