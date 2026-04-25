from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ActionResult, ExecutorHealth, IncomingMessage


class PlatformExecutor(ABC):
    def __init__(
        self,
        dry_run: bool = True,
        runtime_dir: Path | None = None,
        listen_chats: tuple[str, ...] | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.runtime_dir = runtime_dir or Path("data/wechat_auto_reply/runtime")
        self.listen_chats = tuple(listen_chats or ())
        self.platform_runtime_dir = self.runtime_dir / "platform" / self.name
        self.platform_runtime_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> ExecutorHealth:
        raise NotImplementedError

    def poll_message(self) -> IncomingMessage | None:
        return None

    def prefers_message_polling(self) -> bool:
        return False

    def send_text(self, conversation_id: str, text: str) -> ActionResult:
        if self.dry_run:
            return ActionResult(True, f"[dry-run] send_text via {self.name} -> {conversation_id}")
        return ActionResult(False, f"{self.name} send_text is not implemented yet")

    def send_material(
        self,
        conversation_id: str,
        material_path: Path,
        caption: str | None = None,
    ) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] send_material via {self.name} -> {conversation_id}: {material_path.name}",
                metadata={"caption": caption or ""},
            )
        return ActionResult(False, f"{self.name} send_material is not implemented yet")

    def send_handoff_notification(self, human_contact: str, text: str) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] notify handoff via {self.name} -> {human_contact}",
                metadata={"text": text},
            )
        return ActionResult(False, f"{self.name} send_handoff_notification is not implemented yet")

    def focus_detected_window(self) -> ActionResult:
        if self.dry_run:
            return ActionResult(True, f"[dry-run] focus_detected_window via {self.name}")
        return ActionResult(False, f"{self.name} focus_detected_window is not implemented yet")

    def capture_detected_window(self, output_path: Path) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] capture_detected_window via {self.name}",
                screenshot_path=output_path,
            )
        return ActionResult(False, f"{self.name} capture_detected_window is not implemented yet")

    def inspect_ui_tree(
        self,
        max_depth: int = 2,
        max_nodes: int = 40,
        backend: str = "uia",
    ) -> dict[str, object]:
        return {
            "executor": self.name,
            "supported": False,
            "reason": f"{self.name} does not implement UI tree inspection yet",
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "backend": backend,
        }


def create_executor(
    name: str,
    dry_run: bool = True,
    runtime_dir: Path | None = None,
    listen_chats: tuple[str, ...] | None = None,
) -> PlatformExecutor:
    from .macos_accessibility import MacOSAccessibilityExecutor
    from .windows_astron import WindowsAstronExecutor
    from .windows_pywinauto import WindowsPywinautoExecutor
    from .windows_wxauto import WindowsWxautoExecutor

    registry = {
        "windows-astron": WindowsAstronExecutor,
        "windows-pywinauto": WindowsPywinautoExecutor,
        "windows-wxauto": WindowsWxautoExecutor,
        "macos-accessibility": MacOSAccessibilityExecutor,
    }
    try:
        executor_cls = registry[name]
    except KeyError as exc:
        available = ", ".join(sorted(registry))
        raise ValueError(f"unknown executor '{name}'. Available: {available}") from exc
    return executor_cls(dry_run=dry_run, runtime_dir=runtime_dir, listen_chats=listen_chats)


def get_available_executor_names() -> tuple[str, ...]:
    return (
        "windows-astron",
        "windows-pywinauto",
        "macos-accessibility",
    )
