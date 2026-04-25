from __future__ import annotations

from dataclasses import dataclass

from .models import ActionResult, Decision, IncomingMessage
from .platform.base import PlatformExecutor


@dataclass
class HandoffNotifier:
    human_contact: str
    disabled: bool = False

    def build_message(self, incoming: IncomingMessage, decision: Decision) -> str:
        excerpt = incoming.text.strip().replace("\n", " ")
        if len(excerpt) > 120:
            excerpt = excerpt[:117] + "..."

        return (
            f"[转人工通知]\n"
            f"客户: {incoming.contact_name}\n"
            f"会话: {incoming.conversation_id}\n"
            f"原因: {decision.reason}\n"
            f"原消息: {excerpt}"
        )

    def notify(
        self,
        executor: PlatformExecutor,
        incoming: IncomingMessage,
        decision: Decision,
    ) -> ActionResult:
        if self.disabled:
            return ActionResult(False, "handoff notifications disabled by configuration")
        body = self.build_message(incoming, decision)
        return executor.send_handoff_notification(self.human_contact, body)
