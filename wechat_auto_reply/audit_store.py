from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


class AuditStore:
    def __init__(self, runtime_dir: Path, screenshots_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.screenshots_dir = screenshots_dir
        self.artifacts_dir = runtime_dir / "artifacts"
        self.events_path = runtime_dir / "events.jsonl"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "event_type": event_type,
            "payload": _serialize(payload),
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def reserve_screenshot_path(self, prefix: str, suffix: str = ".bmp") -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return self.screenshots_dir / f"{prefix}-{stamp}{suffix}"

    def reserve_artifact_dir(self, prefix: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.artifacts_dir / f"{prefix}-{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_artifact(self, prefix: str, payload: dict[str, Any]) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.artifacts_dir / f"{prefix}-{stamp}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(_serialize(payload), handle, ensure_ascii=False, indent=2)
        return path
