from __future__ import annotations

from dataclasses import dataclass, field

from .models import ConversationState


class InvalidTransitionError(ValueError):
    """Raised when the state machine receives an invalid transition."""


ALLOWED_TRANSITIONS: dict[ConversationState, frozenset[ConversationState]] = {
    ConversationState.IDLE: frozenset(
        {
            ConversationState.NEW_MESSAGE_DETECTED,
            ConversationState.ABNORMAL_UI_STATE,
            ConversationState.OPERATOR_TAKEOVER,
        }
    ),
    ConversationState.NEW_MESSAGE_DETECTED: frozenset(
        {
            ConversationState.CONTEXT_EXTRACTED,
            ConversationState.CLASSIFIED_HANDOFF,
            ConversationState.ABNORMAL_UI_STATE,
        }
    ),
    ConversationState.CONTEXT_EXTRACTED: frozenset(
        {
            ConversationState.CLASSIFIED_SAFE,
            ConversationState.CLASSIFIED_HANDOFF,
            ConversationState.ABNORMAL_UI_STATE,
        }
    ),
    ConversationState.CLASSIFIED_SAFE: frozenset(
        {
            ConversationState.SENDING,
            ConversationState.OPERATOR_TAKEOVER,
        }
    ),
    ConversationState.CLASSIFIED_HANDOFF: frozenset(
        {
            ConversationState.HANDOFF_NOTIFIED,
            ConversationState.OPERATOR_TAKEOVER,
        }
    ),
    ConversationState.SENDING: frozenset(
        {
            ConversationState.SEND_VERIFIED,
            ConversationState.SEND_FAILED,
            ConversationState.ABNORMAL_UI_STATE,
        }
    ),
    ConversationState.SEND_VERIFIED: frozenset({ConversationState.IDLE}),
    ConversationState.SEND_FAILED: frozenset(
        {
            ConversationState.CLASSIFIED_HANDOFF,
            ConversationState.OPERATOR_TAKEOVER,
            ConversationState.IDLE,
        }
    ),
    ConversationState.HANDOFF_NOTIFIED: frozenset({ConversationState.IDLE}),
    ConversationState.OPERATOR_TAKEOVER: frozenset({ConversationState.IDLE}),
    ConversationState.ABNORMAL_UI_STATE: frozenset(
        {
            ConversationState.IDLE,
            ConversationState.OPERATOR_TAKEOVER,
        }
    ),
}


@dataclass
class ConversationStateMachine:
    state: ConversationState = ConversationState.IDLE
    history: list[ConversationState] = field(default_factory=lambda: [ConversationState.IDLE])

    def transition(self, next_state: ConversationState) -> ConversationState:
        if next_state not in ALLOWED_TRANSITIONS[self.state]:
            raise InvalidTransitionError(f"{self.state.value} -> {next_state.value} is not allowed")

        self.state = next_state
        self.history.append(next_state)
        return self.state

    def reset(self) -> None:
        if self.state != ConversationState.IDLE:
            self.transition(ConversationState.IDLE)

    def snapshot(self) -> tuple[ConversationState, ...]:
        return tuple(self.history)
