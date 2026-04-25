from __future__ import annotations

import os
import sys
import time
from collections import deque
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from ..layout_probe import probe_layout_from_screenshot
from ..models import ActionResult, ExecutorCheck, ExecutorHealth
from ..ocr_probe import probe_ocr_from_layout
from ..screen_context import build_context_from_ocr_payload
from .base import PlatformExecutor
from .windows_common import (
    capture_window,
    click_screen_point,
    focus_window,
    get_window_rect,
    has_python_module,
    list_wechat_processes,
    list_wechat_windows,
    probe_pywinauto_runtime,
    send_keys_sequence,
    set_clipboard_text,
)


ACTION_OCR_REGIONS = (
    "conversation_list",
    "chat_header",
    "message_pane",
    "latest_message_band",
    "composer_input",
    "send_button_candidate",
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


class WindowsPywinautoExecutor(PlatformExecutor):
    @property
    def name(self) -> str:
        return "windows-pywinauto"

    def healthcheck(self) -> ExecutorHealth:
        running_on_windows = sys.platform.startswith("win")
        dependency_installed = has_python_module("pywinauto")
        runtime_ready = False
        runtime_detail = "pywinauto is not installed"
        if dependency_installed and running_on_windows:
            runtime_ready, runtime_detail = probe_pywinauto_runtime()
        processes = list_wechat_processes() if running_on_windows else ()
        windows = list_wechat_windows() if running_on_windows else ()
        supported = running_on_windows and dependency_installed and runtime_ready

        if not running_on_windows:
            details = "pywinauto executor only applies to Windows hosts"
        elif not dependency_installed:
            details = "pywinauto is not installed yet; host WeChat detection is available"
        elif not runtime_ready:
            details = f"pywinauto is installed but not runtime-ready: {runtime_detail}"
        elif not processes:
            details = "pywinauto is available, but no WeChat process is running"
        elif not windows:
            details = "pywinauto is available and WeChat is running, but no visible WeChat window was found"
        else:
            details = "pywinauto is available and a visible WeChat window was detected"

        checks = (
            ExecutorCheck("running_on_windows", running_on_windows, "Windows host is required"),
            ExecutorCheck("pywinauto_installed", dependency_installed, "Install pywinauto to enable this executor"),
            ExecutorCheck("pywinauto_runtime_ready", runtime_ready, runtime_detail),
            ExecutorCheck("wechat_process_running", bool(processes), "Start and log into desktop WeChat"),
            ExecutorCheck("visible_wechat_window", bool(windows), "Bring a WeChat window to the foreground"),
        )
        return ExecutorHealth(
            self.name,
            supported,
            details,
            checks=checks,
            detected_processes=processes,
            detected_windows=windows,
        )

    def focus_detected_window(self) -> ActionResult:
        target = self._get_primary_window()
        if target is None or target.hwnd is None:
            return ActionResult(False, "No visible WeChat window is available for focus")
        if self.dry_run:
            return ActionResult(True, f"[dry-run] focus window hwnd={target.hwnd}")

        success, detail = focus_window(target.hwnd)
        return ActionResult(success, detail)

    def capture_detected_window(self, output_path: Path) -> ActionResult:
        target = self._get_primary_window()
        if target is None or target.hwnd is None:
            return ActionResult(False, "No visible WeChat window is available for capture")
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] capture window hwnd={target.hwnd}",
                screenshot_path=output_path,
            )

        success, detail = capture_window(target.hwnd, output_path)
        return ActionResult(success, detail, screenshot_path=output_path if success else None)

    def send_text(self, conversation_id: str, text: str) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] send_text via {self.name} -> {conversation_id}",
                metadata={"text": text},
            )

        target = self._get_primary_window()
        if target is None or target.hwnd is None:
            return ActionResult(False, "No visible WeChat window is available for sending")

        focus_result = self.focus_detected_window()
        if not focus_result.success:
            return focus_result
        time.sleep(0.2)

        send_result = self._send_text_to_active_conversation(
            hwnd=target.hwnd,
            text=text,
            artifact_prefix="send-text",
        )
        metadata = dict(send_result.metadata)
        metadata["conversation_id"] = conversation_id
        return ActionResult(
            send_result.success,
            send_result.message,
            screenshot_path=send_result.screenshot_path,
            metadata=metadata,
        )

    def send_handoff_notification(self, human_contact: str, text: str) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] notify handoff via {self.name} -> {human_contact}",
                metadata={"text": text},
            )

        target = self._get_primary_window()
        if target is None or target.hwnd is None:
            return ActionResult(False, "No visible WeChat window is available for handoff notification")

        focus_result = self.focus_detected_window()
        if not focus_result.success:
            return focus_result
        time.sleep(0.2)

        snapshot = self._capture_screen_snapshot("handoff-select")
        if not snapshot["ocr_probe"].get("supported"):
            return ActionResult(
                False,
                str(snapshot["ocr_probe"].get("reason") or "OCR is unavailable for handoff"),
                screenshot_path=Path(str(snapshot["screenshot_path"])),
            )

        original_contact = snapshot["context_probe"].get("contact_name")
        switch_result = self._activate_conversation(
            hwnd=target.hwnd,
            target_contact=human_contact,
            snapshot=snapshot,
        )
        if not switch_result.success:
            return switch_result

        send_result = self._send_text_to_active_conversation(
            hwnd=target.hwnd,
            text=text,
            artifact_prefix="handoff-notify",
            expected_contact=human_contact,
        )
        metadata = dict(send_result.metadata)
        metadata["human_contact"] = human_contact
        metadata["original_contact"] = original_contact

        if send_result.success and original_contact and not self._text_matches(original_contact, human_contact):
            restore_result = self._activate_conversation(
                hwnd=target.hwnd,
                target_contact=original_contact,
            )
            metadata["restore_success"] = restore_result.success
            metadata["restore_message"] = restore_result.message

        return ActionResult(
            send_result.success,
            send_result.message,
            screenshot_path=send_result.screenshot_path,
            metadata=metadata,
        )

    def inspect_ui_tree(
        self,
        max_depth: int = 2,
        max_nodes: int = 40,
        backend: str = "uia",
    ) -> dict[str, object]:
        health = self.healthcheck()
        if not health.supported:
            return {
                "executor": self.name,
                "supported": False,
                "reason": health.details,
            }
        if not health.detected_windows:
            return {
                "executor": self.name,
                "supported": False,
                "reason": "No visible WeChat window detected",
            }

        target = health.detected_windows[0]
        if target.hwnd is None:
            return {
                "executor": self.name,
                "supported": False,
                "reason": "Detected WeChat window did not expose a handle",
            }

        if backend == "all":
            return {
                "executor": self.name,
                "supported": True,
                "window": {
                    "title": target.title,
                    "pid": target.pid,
                    "class_name": target.class_name,
                    "hwnd": target.hwnd,
                },
                "inspections": [
                    self._inspect_backend(target, selected_backend, max_depth, max_nodes)
                    for selected_backend in ("uia", "win32")
                ],
            }
        return self._inspect_backend(target, backend, max_depth, max_nodes)

    def _inspect_backend(
        self,
        target,
        backend: str,
        max_depth: int,
        max_nodes: int,
    ) -> dict[str, object]:
        from pywinauto import Desktop

        root = Desktop(backend=backend).window(handle=target.hwnd).wrapper_object()
        queue = deque([(root, 0)])
        nodes: list[dict[str, object]] = []
        errors: list[str] = []

        while queue and len(nodes) < max_nodes:
            wrapper, depth = queue.popleft()
            try:
                info = wrapper.element_info
                nodes.append(
                    {
                        "depth": depth,
                        "name": info.name,
                        "control_type": info.control_type,
                        "class_name": info.class_name,
                        "automation_id": getattr(info, "automation_id", None),
                        "rectangle": str(info.rectangle),
                    }
                )
                if depth < max_depth:
                    for child in wrapper.children():
                        queue.append((child, depth + 1))
            except Exception as exc:  # pragma: no cover - depends on live UI tree
                errors.append(f"{type(exc).__name__}: {exc}")

        return {
            "executor": self.name,
            "supported": True,
            "backend": backend,
            "window": {
                "title": target.title,
                "pid": target.pid,
                "class_name": target.class_name,
                "hwnd": target.hwnd,
            },
            "nodes": nodes,
            "errors": errors,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        }

    def _send_text_to_active_conversation(
        self,
        hwnd: int,
        text: str,
        artifact_prefix: str,
        expected_contact: str | None = None,
    ) -> ActionResult:
        before_snapshot = self._capture_screen_snapshot(f"{artifact_prefix}-before")
        if not before_snapshot["ocr_probe"].get("supported"):
            return ActionResult(
                False,
                str(before_snapshot["ocr_probe"].get("reason") or "OCR is unavailable"),
                screenshot_path=Path(str(before_snapshot["screenshot_path"])),
            )

        if expected_contact:
            active_contact = before_snapshot["context_probe"].get("contact_name")
            if active_contact and not self._text_matches(active_contact, expected_contact):
                return ActionResult(
                    False,
                    f"Active conversation is '{active_contact}', expected '{expected_contact}'",
                    screenshot_path=Path(str(before_snapshot["screenshot_path"])),
                    metadata={"active_contact": active_contact, "expected_contact": expected_contact},
                )

        composer_text = str(before_snapshot["context_probe"].get("composer_text") or "")
        if composer_text:
            return ActionResult(
                False,
                "Composer input is not empty; assume operator is typing or unsent draft exists",
                screenshot_path=Path(str(before_snapshot["screenshot_path"])),
                metadata={"composer_text": composer_text},
            )

        click_result = self._click_region_center(hwnd, before_snapshot["layout_probe"], "composer_input")
        if not click_result.success:
            return click_result
        time.sleep(0.15)

        clipboard_result = set_clipboard_text(text)
        if not clipboard_result[0]:
            return ActionResult(False, clipboard_result[1], screenshot_path=Path(str(before_snapshot["screenshot_path"])))
        paste_result = send_keys_sequence("^v")
        if not paste_result[0]:
            return ActionResult(False, paste_result[1], screenshot_path=Path(str(before_snapshot["screenshot_path"])))
        time.sleep(0.25)

        draft_snapshot = self._capture_screen_snapshot(f"{artifact_prefix}-draft")
        draft_text = str(draft_snapshot["context_probe"].get("composer_text") or "")
        draft_verified = self._text_matches(draft_text, text, allow_partial=True)
        if not draft_verified and not _env_flag("WECHAT_AUTO_REPLY_ALLOW_UNVERIFIED_DRAFT_SEND"):
            return ActionResult(
                False,
                "Typed draft could not be verified in composer input",
                screenshot_path=Path(str(draft_snapshot["screenshot_path"])),
                metadata={"draft_text": draft_text, "expected_text": text},
            )

        send_button_result = self._click_send_button(hwnd, draft_snapshot)
        if not send_button_result.success:
            return send_button_result
        time.sleep(0.5)

        after_snapshot = self._capture_screen_snapshot(f"{artifact_prefix}-after")
        after_composer = str(after_snapshot["context_probe"].get("composer_text") or "")
        message_pane_text = self._get_region_text(after_snapshot["ocr_probe"], "message_pane")
        visible_echo_confirmed = self._text_matches(message_pane_text, text, allow_partial=True)

        if after_composer:
            return ActionResult(
                False,
                "Composer input is still non-empty after clicking send",
                screenshot_path=Path(str(after_snapshot["screenshot_path"])),
                metadata={
                    "composer_text": after_composer,
                    "visible_echo_confirmed": visible_echo_confirmed,
                },
            )

        if not visible_echo_confirmed:
            return ActionResult(
                False,
                "Send action was triggered but the sent text was not confirmed in message pane",
                screenshot_path=Path(str(after_snapshot["screenshot_path"])),
                metadata={"visible_echo_confirmed": False},
            )

        return ActionResult(
            True,
            "Sent text and confirmed visible echo in message pane",
            screenshot_path=Path(str(after_snapshot["screenshot_path"])),
            metadata={
                "visible_echo_confirmed": True,
                "draft_verified": draft_verified,
            },
        )

    def _activate_conversation(
        self,
        hwnd: int,
        target_contact: str,
        snapshot: dict[str, object] | None = None,
    ) -> ActionResult:
        snapshot = snapshot or self._capture_screen_snapshot("conversation-switch")
        list_item = self._find_best_contact_item(snapshot["ocr_probe"], "conversation_list", target_contact)
        if list_item is not None:
            click_result = self._click_ocr_item(
                hwnd,
                snapshot["layout_probe"],
                "conversation_list",
                list_item,
            )
            if not click_result.success:
                return click_result
            time.sleep(0.35)
            verify_snapshot = self._capture_screen_snapshot("conversation-switch-verify")
            active_contact = str(verify_snapshot["context_probe"].get("contact_name") or "")
            if self._text_matches(active_contact, target_contact):
                return ActionResult(
                    True,
                    f"Activated conversation '{target_contact}' from visible conversation list",
                    screenshot_path=Path(str(verify_snapshot["screenshot_path"])),
                )

        search_item = self._find_search_entry(snapshot["ocr_probe"])
        if search_item is None:
            return ActionResult(
                False,
                f"Could not find target contact '{target_contact}' in visible list or search box",
                screenshot_path=Path(str(snapshot["screenshot_path"])),
            )

        click_result = self._click_ocr_item(hwnd, snapshot["layout_probe"], "conversation_list", search_item, x_padding=35)
        if not click_result.success:
            return click_result
        time.sleep(0.15)
        clipboard_result = set_clipboard_text(target_contact)
        if not clipboard_result[0]:
            return ActionResult(False, clipboard_result[1], screenshot_path=Path(str(snapshot["screenshot_path"])))
        clear_result = send_keys_sequence("^a")
        if not clear_result[0]:
            return ActionResult(False, clear_result[1], screenshot_path=Path(str(snapshot["screenshot_path"])))
        paste_result = send_keys_sequence("^v")
        if not paste_result[0]:
            return ActionResult(False, paste_result[1], screenshot_path=Path(str(snapshot["screenshot_path"])))
        time.sleep(0.2)
        enter_result = send_keys_sequence("{ENTER}")
        if not enter_result[0]:
            return ActionResult(False, enter_result[1], screenshot_path=Path(str(snapshot["screenshot_path"])))
        time.sleep(0.5)

        verify_snapshot = self._capture_screen_snapshot("conversation-search-verify")
        active_contact = str(verify_snapshot["context_probe"].get("contact_name") or "")
        if not self._text_matches(active_contact, target_contact):
            return ActionResult(
                False,
                f"Search opened '{active_contact}' instead of '{target_contact}'",
                screenshot_path=Path(str(verify_snapshot["screenshot_path"])),
                metadata={"active_contact": active_contact, "expected_contact": target_contact},
            )

        return ActionResult(
            True,
            f"Activated conversation '{target_contact}' via search box",
            screenshot_path=Path(str(verify_snapshot["screenshot_path"])),
        )

    def _capture_screen_snapshot(self, prefix: str) -> dict[str, object]:
        step_dir = self._reserve_step_dir(prefix)
        screenshot_path = step_dir / "window.bmp"

        capture_result = self.capture_detected_window(screenshot_path)
        if not capture_result.success or capture_result.screenshot_path is None:
            return {
                "screenshot_path": str(screenshot_path),
                "layout_probe": {
                    "supported": False,
                    "reason": capture_result.message,
                },
                "ocr_probe": {
                    "supported": False,
                    "reason": capture_result.message,
                },
                "context_probe": {
                    "supported": False,
                    "reason": capture_result.message,
                },
                "artifact_dir": str(step_dir),
            }

        layout_payload = probe_layout_from_screenshot(
            screenshot_path=capture_result.screenshot_path,
            output_dir=step_dir,
            metadata={
                "executor": self.name,
                "prefix": prefix,
            },
        )
        ocr_payload = probe_ocr_from_layout(
            layout_payload=layout_payload,
            output_dir=step_dir,
            region_names=ACTION_OCR_REGIONS,
            metadata={"executor": self.name, "prefix": prefix},
        )
        context_payload, _incoming_message = build_context_from_ocr_payload(
            ocr_payload=ocr_payload,
            output_dir=step_dir,
            metadata={"executor": self.name, "prefix": prefix},
        )
        return {
            "screenshot_path": str(capture_result.screenshot_path),
            "layout_probe": layout_payload,
            "ocr_probe": ocr_payload,
            "context_probe": context_payload,
            "artifact_dir": str(step_dir),
        }

    def _reserve_step_dir(self, prefix: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.platform_runtime_dir / "artifacts" / f"{prefix}-{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _click_region_center(
        self,
        hwnd: int,
        layout_payload: dict[str, object],
        region_name: str,
    ) -> ActionResult:
        region = self._get_region(layout_payload, region_name)
        if region is None:
            return ActionResult(False, f"Layout region '{region_name}' was not found")
        return self._click_relative_rect(
            hwnd,
            left=int(region["left"]),
            top=int(region["top"]),
            right=int(region["right"]),
            bottom=int(region["bottom"]),
        )

    def _click_send_button(self, hwnd: int, snapshot: dict[str, object]) -> ActionResult:
        send_item = self._find_send_button_item(snapshot["ocr_probe"])
        if send_item is not None:
            click_result = self._click_ocr_item(
                hwnd,
                snapshot["layout_probe"],
                "send_button_candidate",
                send_item,
            )
            if click_result.success:
                return click_result
        return self._click_region_center(hwnd, snapshot["layout_probe"], "send_button_candidate")

    def _click_ocr_item(
        self,
        hwnd: int,
        layout_payload: dict[str, object],
        region_name: str,
        item: dict[str, object],
        x_padding: int = 0,
        y_padding: int = 0,
    ) -> ActionResult:
        region = self._get_region(layout_payload, region_name)
        if region is None:
            return ActionResult(False, f"Layout region '{region_name}' was not found")

        left = int(region["left"]) + int(item["left"]) + x_padding
        top = int(region["top"]) + int(item["top"]) + y_padding
        right = int(region["left"]) + int(item["right"]) + x_padding
        bottom = int(region["top"]) + int(item["bottom"]) + y_padding
        return self._click_relative_rect(hwnd, left, top, right, bottom)

    def _click_relative_rect(
        self,
        hwnd: int,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> ActionResult:
        rect = get_window_rect(hwnd)
        if rect is None:
            return ActionResult(False, f"Window handle {hwnd} does not have a valid rectangle")

        window_left, window_top, _window_right, _window_bottom = rect
        x = window_left + (left + right) // 2
        y = window_top + (top + bottom) // 2
        success, detail = click_screen_point(x, y)
        return ActionResult(success, detail)

    def _get_region(self, layout_payload: dict[str, object], region_name: str) -> dict[str, object] | None:
        for region in layout_payload.get("regions", []):
            if region.get("name") == region_name:
                return region
        return None

    def _get_region_text(self, ocr_payload: dict[str, object], region_name: str) -> str:
        for region in ocr_payload.get("regions", []):
            if region.get("name") == region_name:
                return str(region.get("text") or "")
        return ""

    def _find_send_button_item(self, ocr_payload: dict[str, object]) -> dict[str, object] | None:
        items = self._get_region_items(ocr_payload, "send_button_candidate")
        for item in items:
            if self._text_matches(str(item["text"]), "发送", allow_partial=True):
                return item

        composer_items = self._get_region_items(ocr_payload, "composer_input")
        for item in composer_items:
            if self._text_matches(str(item["text"]), "发送", allow_partial=True):
                return item
        return None

    def _find_search_entry(self, ocr_payload: dict[str, object]) -> dict[str, object] | None:
        items = self._get_region_items(ocr_payload, "conversation_list")
        best_item = None
        best_score = 0.0
        for item in items:
            score = self._text_similarity(str(item["text"]), "搜索")
            if score > best_score:
                best_score = score
                best_item = item
        if best_score >= 0.45:
            return best_item
        return None

    def _find_best_contact_item(
        self,
        ocr_payload: dict[str, object],
        region_name: str,
        target_contact: str,
    ) -> dict[str, object] | None:
        items = self._get_region_items(ocr_payload, region_name)
        best_item = None
        best_score = 0.0
        for item in items:
            score = self._text_similarity(str(item["text"]), target_contact)
            if self._normalized_text(target_contact) in self._normalized_text(str(item["text"])):
                score = max(score, 0.95)
            if score > best_score:
                best_score = score
                best_item = item
        if best_score >= 0.72:
            return best_item
        return None

    def _get_region_items(self, ocr_payload: dict[str, object], region_name: str) -> list[dict[str, object]]:
        for region in ocr_payload.get("regions", []):
            if region.get("name") == region_name and region.get("success"):
                return list(region.get("items", []))
        return []

    def _normalized_text(self, text: str) -> str:
        return "".join(character for character in text.casefold().strip() if character.isalnum())

    def _text_similarity(self, left: str, right: str) -> float:
        left_key = self._normalized_text(left)
        right_key = self._normalized_text(right)
        if not left_key or not right_key:
            return 0.0
        if left_key == right_key:
            return 1.0
        return SequenceMatcher(a=left_key, b=right_key).ratio()

    def _text_matches(self, left: str, right: str, allow_partial: bool = False) -> bool:
        left_key = self._normalized_text(left)
        right_key = self._normalized_text(right)
        if not left_key or not right_key:
            return False
        if left_key == right_key:
            return True
        if allow_partial and (left_key in right_key or right_key in left_key):
            return True
        return self._text_similarity(left_key, right_key) >= 0.84

    def _get_primary_window(self):
        health = self.healthcheck()
        if not health.detected_windows:
            return None
        return health.detected_windows[0]
