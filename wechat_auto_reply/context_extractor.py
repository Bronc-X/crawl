from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping

from .models import IncomingMessage


class ContextExtractor:
    def extract(self, raw_message: IncomingMessage | Mapping[str, object]) -> IncomingMessage:
        if isinstance(raw_message, IncomingMessage):
            return raw_message

        return IncomingMessage(
            message_id=str(raw_message["message_id"]),
            conversation_id=str(raw_message["conversation_id"]),
            contact_name=str(raw_message["contact_name"]),
            text=str(raw_message["text"]),
            received_at=raw_message.get("received_at") or datetime.now(UTC),
            raw_context=tuple(str(item) for item in raw_message.get("raw_context", ())),
            metadata={str(key): str(value) for key, value in raw_message.get("metadata", {}).items()},
        )
