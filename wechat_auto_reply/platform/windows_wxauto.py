from __future__ import annotations

import hashlib
import importlib
import sys
from collections import deque
from threading import Lock, Thread
from pathlib import Path
from typing import Mapping

from ..models import ActionResult, ExecutorCheck, ExecutorHealth, IncomingMessage
from .base import PlatformExecutor
from .windows_common import has_python_module, is_windows_host, list_wechat_processes, list_wechat_windows


WXAUTO_RUNTIME_CANDIDATES = (
    ("wxautox4", "wxautox4"),
    ("wxauto4", "wxauto4"),
    ("wxauto", "wxauto"),
)


def is_documented_supported_python() -> bool:
    major_minor = (sys.version_info.major, sys.version_info.minor)
    return (3, 9) <= major_minor < (3, 14)


def resolve_wxauto_runtime() -> tuple[str | None, str | None]:
    for module_name, label in WXAUTO_RUNTIME_CANDIDATES:
        if has_python_module(module_name):
            return module_name, label
    return None, None


def load_wxauto_client_class():
    if not is_documented_supported_python():
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise RuntimeError(f"wxauto v4.x currently documents Python 3.9-3.13 support; current interpreter is {version}")

    module_name, runtime_label = resolve_wxauto_runtime()
    if module_name is None or runtime_label is None:
        raise RuntimeError("wxauto runtime is not installed; install wxautox4, wxauto4, or wxauto")

    try:
        module = importlib.import_module(module_name)
        client_class = getattr(module, "WeChat")
    except Exception as exc:  # pragma: no cover - exercised through monkeypatch in tests
        raise RuntimeError(f"{runtime_label} import failed: {type(exc).__name__}: {exc}") from exc
    return client_class, module_name, runtime_label


def probe_wxauto_runtime() -> tuple[bool, str]:
    try:
        _client_class, module_name, runtime_label = load_wxauto_client_class()
    except Exception as exc:  # pragma: no cover - exercised through monkeypatch in tests
        return False, str(exc)
    return True, f"{runtime_label} runtime imported successfully ({module_name})"


class WindowsWxautoExecutor(PlatformExecutor):
    def __init__(
        self,
        dry_run: bool = True,
        runtime_dir: Path | None = None,
        listen_chats: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(dry_run=dry_run, runtime_dir=runtime_dir, listen_chats=listen_chats)
        self._wx = None
        self._runtime_module_name: str | None = None
        self._runtime_label: str | None = None
        self._listener_started = False
        self._listener_thread: Thread | None = None
        self._listener_registered_chats: set[str] = set()
        self._message_events: deque[tuple[object, object]] = deque()
        self._queue_lock = Lock()

    @property
    def name(self) -> str:
        return "windows-wxauto"

    def prefers_message_polling(self) -> bool:
        return bool(self.listen_chats) or not self.dry_run

    def healthcheck(self) -> ExecutorHealth:
        running_on_windows = is_windows_host()
        python_supported = is_documented_supported_python() if running_on_windows else False
        runtime_detected = resolve_wxauto_runtime()[0] is not None if python_supported else False
        runtime_ready = False
        runtime_detail = "wxauto runtime is not installed"
        if running_on_windows and python_supported and runtime_detected:
            runtime_ready, runtime_detail = probe_wxauto_runtime()

        listen_targets_configured = bool(self.listen_chats)
        processes = list_wechat_processes() if running_on_windows else ()
        windows = list_wechat_windows() if running_on_windows else ()
        supported = running_on_windows and python_supported and runtime_detected and runtime_ready

        if not running_on_windows:
            details = "wxauto executor only applies to Windows hosts"
        elif not python_supported:
            version = f"{sys.version_info.major}.{sys.version_info.minor}"
            details = f"wxauto runtime is not documented for Python {version}; use Python 3.9-3.13"
        elif not runtime_detected:
            details = "wxauto runtime is not installed yet; install wxautox4 or wxauto4 to enable this executor"
        elif not runtime_ready:
            details = runtime_detail
        elif listen_targets_configured:
            details = f"wxauto runtime is ready and {len(self.listen_chats)} listen chats are configured"
        else:
            details = "wxauto runtime is ready; configure WECHAT_AUTO_REPLY_LISTEN_CHATS to enable listener polling"

        checks = (
            ExecutorCheck("running_on_windows", running_on_windows, "Windows host is required"),
            ExecutorCheck("python_version_supported", python_supported, "wxauto v4.x expects Python 3.9-3.13"),
            ExecutorCheck("wxauto_runtime_detected", runtime_detected, "Install wxautox4 or wxauto4"),
            ExecutorCheck("wxauto_runtime_ready", runtime_ready, runtime_detail),
            ExecutorCheck("listen_targets_configured", listen_targets_configured, "Set WECHAT_AUTO_REPLY_LISTEN_CHATS to enable polling"),
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

    def poll_message(self) -> IncomingMessage | None:
        if self.dry_run:
            return None

        if self.listen_chats:
            self._ensure_listener_started()
            with self._queue_lock:
                if self._message_events:
                    msg, chat = self._message_events.popleft()
                    return self._convert_event_to_message(msg, chat)

        return self._poll_next_new_message()

    def send_text(self, conversation_id: str, text: str) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] send_text via {self.name} -> {conversation_id}",
                metadata={"text": text},
            )

        try:
            client = self._get_client()
            response = self._call_chat_method(client, "SendMsg", text, conversation_id)
        except Exception as exc:  # pragma: no cover - depends on live wxauto runtime
            return ActionResult(False, f"{type(exc).__name__}: {exc}")
        return self._action_result_from_wx_response(
            response,
            f"Sent text to '{conversation_id}' via wxauto",
        )

    def send_material(self, conversation_id: str, material_path: Path, caption: str | None = None) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                True,
                f"[dry-run] send_material via {self.name} -> {conversation_id}: {material_path.name}",
                metadata={"caption": caption or ""},
            )
        if not material_path.exists():
            return ActionResult(False, f"Material file was not found: {material_path}")

        try:
            client = self._get_client()
            if hasattr(client, "SendFiles"):
                response = self._call_chat_method(client, "SendFiles", str(material_path), conversation_id)
            elif hasattr(client, "SendFile"):
                response = self._call_chat_method(client, "SendFile", str(material_path), conversation_id)
            else:
                return ActionResult(False, "wxauto runtime does not expose SendFiles/SendFile")
            send_result = self._action_result_from_wx_response(
                response,
                f"Sent material to '{conversation_id}' via wxauto",
            )
            if not send_result.success:
                return send_result
            if caption:
                caption_response = self._call_chat_method(client, "SendMsg", caption, conversation_id)
                caption_result = self._action_result_from_wx_response(
                    caption_response,
                    f"Sent caption to '{conversation_id}' via wxauto",
                )
                if not caption_result.success:
                    return caption_result
        except Exception as exc:  # pragma: no cover - depends on live wxauto runtime
            return ActionResult(False, f"{type(exc).__name__}: {exc}")
        return ActionResult(True, f"Sent material to '{conversation_id}' via wxauto")

    def send_handoff_notification(self, human_contact: str, text: str) -> ActionResult:
        return self.send_text(human_contact, text)

    def _get_client(self):
        if self._wx is None:
            client_class, module_name, runtime_label = load_wxauto_client_class()
            self._runtime_module_name = module_name
            self._runtime_label = runtime_label
            self._wx = client_class()
        return self._wx

    def _ensure_listener_started(self) -> None:
        client = self._get_client()
        for chat_name in self.listen_chats:
            if chat_name in self._listener_registered_chats:
                continue
            client.AddListenChat(chat_name, self._on_message)
            self._listener_registered_chats.add(chat_name)

        if self._listener_started:
            return

        if hasattr(client, "StartListening"):
            client.StartListening()
        elif hasattr(client, "_listener_start"):
            client._listener_start()
        elif hasattr(client, "KeepRunning"):
            # Some wxauto builds only expose a blocking loop; keep it in a daemon thread.
            self._listener_thread = Thread(target=client.KeepRunning, daemon=True, name="wxauto-listener")
            self._listener_thread.start()
        else:  # pragma: no cover - depends on live wxauto runtime
            raise RuntimeError("wxauto runtime does not expose StartListening, _listener_start, or KeepRunning")
        self._listener_started = True

    def _on_message(self, msg, chat) -> None:
        with self._queue_lock:
            self._message_events.append((msg, chat))
            if len(self._message_events) > 200:
                self._message_events.popleft()

    def _poll_next_new_message(self) -> IncomingMessage | None:
        client = self._get_client()
        getter = getattr(client, "GetNextNewMessage", None)
        if getter is None:
            return None

        try:
            payload = getter(filter_mute=True)
        except TypeError:
            payload = getter()

        return self._convert_next_new_message_payload(payload)

    def _call_chat_method(self, client, method_name: str, payload: str, conversation_id: str):
        method = getattr(client, method_name)
        try:
            return method(payload, who=conversation_id, clear=True, exact=False)
        except TypeError:
            pass

        try:
            return method(payload, who=conversation_id, exact=False)
        except TypeError:
            pass

        try:
            return method(payload, who=conversation_id)
        except TypeError:
            pass

        try:
            return method(payload, conversation_id)
        except TypeError:
            pass

        if hasattr(client, "ChatWith"):
            client.ChatWith(conversation_id)
            return method(payload)
        raise RuntimeError(f"{self._runtime_label or 'wxauto'} {method_name} signature is unsupported")

    def _convert_event_to_message(self, msg, chat) -> IncomingMessage:
        content = str(self._read_value(msg, "content", "text") or "").strip()
        sender = str(self._read_value(msg, "sender", "sender_name") or "").strip() or "system"
        conversation_name = self._resolve_chat_name(chat) or sender or "unknown-chat"
        raw_id = self._read_value(msg, "id", "hash", "message_id")
        if raw_id:
            message_id = str(raw_id)
        else:
            digest = hashlib.sha1(f"{conversation_name}|{sender}|{content}".encode("utf-8")).hexdigest()
            message_id = f"wxauto-{digest}"

        metadata = {"sender": sender}
        if self._runtime_module_name:
            metadata["runtime"] = self._runtime_module_name
        message_type = self._read_value(msg, "type", "message_type")
        if message_type is not None:
            metadata["message_type"] = str(message_type)
        if isinstance(chat, Mapping):
            chat_type = chat.get("chat_type")
            if chat_type:
                metadata["chat_type"] = str(chat_type)

        raw_context = (f"sender:{sender}",) if sender else ()
        return IncomingMessage(
            message_id=message_id,
            conversation_id=conversation_name,
            contact_name=conversation_name,
            text=content,
            raw_context=raw_context,
            metadata=metadata,
        )

    def _resolve_chat_name(self, chat) -> str:
        if isinstance(chat, Mapping):
            for key in ("chat_name", "name", "who", "remark"):
                chat_name = str(chat.get(key) or "").strip()
                if chat_name:
                    return chat_name

        try:
            chat_info = chat.ChatInfo()
        except Exception:
            chat_info = None

        if isinstance(chat_info, dict):
            chat_name = str(chat_info.get("chat_name") or "").strip()
            if chat_name:
                return chat_name

        chat_name = str(getattr(chat, "who", "") or "").strip()
        if chat_name:
            return chat_name
        return ""

    def _convert_next_new_message_payload(self, payload) -> IncomingMessage | None:
        if not payload:
            return None

        if isinstance(payload, Mapping):
            if "msg" in payload or "messages" in payload:
                messages = payload.get("msg") or payload.get("messages") or ()
                return self._pick_latest_readable_message(messages, payload)

            for chat_name, messages in payload.items():
                chat_payload = {"chat_name": str(chat_name)}
                if isinstance(messages, Mapping):
                    chat_payload.update(messages)
                    nested_messages = messages.get("msg") or messages.get("messages") or ()
                    message = self._pick_latest_readable_message(nested_messages, chat_payload)
                else:
                    message = self._pick_latest_readable_message(messages, chat_payload)
                if message is not None:
                    return message
            return None

        return self._pick_latest_readable_message(payload, {"chat_name": "unknown-chat"})

    def _pick_latest_readable_message(self, messages, chat) -> IncomingMessage | None:
        if isinstance(messages, (str, bytes)) or not isinstance(messages, (list, tuple, deque)):
            messages = (messages,)

        for msg in reversed(tuple(messages)):
            if not self._is_readable_incoming_message(msg):
                continue
            return self._convert_event_to_message(msg, chat)
        return None

    def _is_readable_incoming_message(self, msg) -> bool:
        content = str(self._read_value(msg, "content", "text") or "").strip()
        if not content:
            return False

        attr = str(self._read_value(msg, "attr") or "").casefold()
        if attr and attr != "friend":
            return False

        message_type = str(self._read_value(msg, "type", "message_type") or "").casefold()
        if message_type in {"self", "system", "time"}:
            return False
        return True

    def _read_value(self, value, *names: str):
        if isinstance(value, Mapping):
            for name in names:
                if name in value:
                    return value[name]
            return None

        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
        return None

    def _action_result_from_wx_response(self, response, success_message: str) -> ActionResult:
        if response is None:
            return ActionResult(True, success_message)

        success = self._read_value(response, "success", "ok")
        if success is None:
            status = self._read_value(response, "status", "code")
            if isinstance(status, str):
                success = status.lower() in {"success", "succeeded", "ok", "true", "0"}
            elif isinstance(status, int):
                success = status == 0

        message = self._read_value(response, "message", "msg", "detail", "error")
        if message is None:
            message = success_message if success is not False else str(response)

        return ActionResult(bool(True if success is None else success), str(message))
