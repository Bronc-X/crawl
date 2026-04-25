from __future__ import annotations

from dataclasses import dataclass

from .audit_store import AuditStore
from .context_extractor import ContextExtractor
from .decision_engine import DecisionEngine
from .handoff_notifier import HandoffNotifier
from .material_service import MaterialNotFoundError, MaterialService
from .models import (
    ActionResult,
    ConversationState,
    Decision,
    DecisionKind,
    IncomingMessage,
    OrchestrationResult,
)
from .platform.base import PlatformExecutor
from .state_machine import ConversationStateMachine


@dataclass
class Orchestrator:
    executor: PlatformExecutor
    decision_engine: DecisionEngine
    material_service: MaterialService
    audit_store: AuditStore
    handoff_notifier: HandoffNotifier
    context_extractor: ContextExtractor
    state_machine: ConversationStateMachine

    def handle_message(self, raw_message: IncomingMessage | dict[str, object]) -> OrchestrationResult:
        self.state_machine = ConversationStateMachine()
        self.state_machine.transition(ConversationState.NEW_MESSAGE_DETECTED)

        message = self.context_extractor.extract(raw_message)
        self.audit_store.log_event("new_message_detected", {"message": message})

        self.state_machine.transition(ConversationState.CONTEXT_EXTRACTED)
        decision = self.decision_engine.classify(message)
        self.audit_store.log_event("decision_made", {"message": message, "decision": decision})

        if decision.kind in {DecisionKind.SAFE_REPLY, DecisionKind.SAFE_MATERIAL}:
            return self._handle_safe_path(message, decision)
        return self._handle_handoff_path(message, decision, send_result=None)

    def run_once(self, raw_message: IncomingMessage | dict[str, object] | None = None) -> OrchestrationResult | None:
        if raw_message is None:
            raw_message = self.executor.poll_message()
        if raw_message is None:
            return None
        return self.handle_message(raw_message)

    def _handle_safe_path(self, message: IncomingMessage, decision: Decision) -> OrchestrationResult:
        self.state_machine.transition(ConversationState.CLASSIFIED_SAFE)
        self.state_machine.transition(ConversationState.SENDING)

        if decision.kind is DecisionKind.SAFE_REPLY:
            send_result = self.executor.send_text(message.conversation_id, decision.reply_text or "")
        else:
            send_result = self._send_material(message, decision)

        self.audit_store.log_event(
            "send_attempted",
            {"message": message, "decision": decision, "result": send_result},
        )

        if send_result.success:
            self.state_machine.transition(ConversationState.SEND_VERIFIED)
            self.audit_store.log_event("send_verified", {"message": message, "result": send_result})
            self.state_machine.transition(ConversationState.IDLE)
            return OrchestrationResult(
                final_state=self.state_machine.state,
                decision=decision,
                send_result=send_result,
                handoff_result=None,
                state_history=self.state_machine.snapshot(),
            )

        self.state_machine.transition(ConversationState.SEND_FAILED)
        self.audit_store.log_event("send_failed", {"message": message, "result": send_result})
        return self._handle_handoff_path(message, decision, send_result=send_result)

    def _send_material(self, message: IncomingMessage, decision: Decision) -> ActionResult:
        try:
            material_path = self.material_service.resolve(decision.material_id or "")
        except MaterialNotFoundError as exc:
            return ActionResult(success=False, message=str(exc))

        return self.executor.send_material(
            message.conversation_id,
            material_path,
            caption=decision.reply_text,
        )

    def _handle_handoff_path(
        self,
        message: IncomingMessage,
        decision: Decision,
        send_result: ActionResult | None,
    ) -> OrchestrationResult:
        if self.state_machine.state == ConversationState.SEND_FAILED:
            self.state_machine.transition(ConversationState.CLASSIFIED_HANDOFF)
        elif self.state_machine.state != ConversationState.CLASSIFIED_HANDOFF:
            self.state_machine.transition(ConversationState.CLASSIFIED_HANDOFF)

        handoff_result = self.handoff_notifier.notify(self.executor, message, decision)
        self.audit_store.log_event(
            "handoff_attempted",
            {"message": message, "decision": decision, "result": handoff_result},
        )

        if handoff_result.success:
            self.state_machine.transition(ConversationState.HANDOFF_NOTIFIED)
            self.state_machine.transition(ConversationState.IDLE)
        else:
            self.state_machine.transition(ConversationState.OPERATOR_TAKEOVER)
            self.state_machine.transition(ConversationState.IDLE)

        return OrchestrationResult(
            final_state=self.state_machine.state,
            decision=decision,
            send_result=send_result,
            handoff_result=handoff_result,
            state_history=self.state_machine.snapshot(),
        )
