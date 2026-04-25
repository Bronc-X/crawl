from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .models import ExecutorHealth, IncomingMessage
from .platform.base import PlatformExecutor


def build_message_fingerprint(message: IncomingMessage) -> str:
    payload = {
        "contact_name": message.contact_name,
        "conversation_id": message.conversation_id,
        "text": message.text,
        "raw_context": list(message.raw_context),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


@dataclass
class MonitorStateStore:
    state_path: Path

    def load(self) -> dict[str, object]:
        if not self.state_path.exists():
            return {"last_processed_by_contact": {}}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, object]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_last_fingerprint(self, contact_name: str) -> str | None:
        payload = self.load()
        mapping = payload.get("last_processed_by_contact", {})
        if not isinstance(mapping, dict):
            return None
        value = mapping.get(contact_name)
        return str(value) if value else None

    def mark_processed(self, message: IncomingMessage) -> str:
        payload = self.load()
        mapping = payload.setdefault("last_processed_by_contact", {})
        if not isinstance(mapping, dict):
            mapping = {}
            payload["last_processed_by_contact"] = mapping
        fingerprint = build_message_fingerprint(message)
        mapping[message.contact_name] = fingerprint
        self.save(payload)
        return fingerprint


@dataclass
class EventMonitor:
    executor: PlatformExecutor

    def healthcheck(self) -> ExecutorHealth:
        return self.executor.healthcheck()

    def poll_once(self) -> IncomingMessage | None:
        return self.executor.poll_message()
