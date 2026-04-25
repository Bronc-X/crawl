from __future__ import annotations

import csv
import ctypes
import importlib.util
import io
import os
import shutil
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from ..models import DetectedProcess, DetectedWindow


WECHAT_PROCESS_NAMES = ("Weixin.exe", "WeChat.exe", "WeChatAppEx.exe")


def is_windows_host() -> bool:
    return sys.platform.startswith("win")


def has_python_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def probe_pywinauto_runtime() -> tuple[bool, str]:
    try:
        from pywinauto import Desktop

        Desktop  # keep the import referenced for lint clarity
    except Exception as exc:  # pragma: no cover - exercised through monkeypatch in tests
        return False, f"{type(exc).__name__}: {exc}"
    return True, "pywinauto UIA backend imported successfully"


def find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def list_wechat_processes() -> tuple[DetectedProcess, ...]:
    if not is_windows_host():
        return ()

    command = [
        "tasklist",
        "/FO",
        "CSV",
        "/NH",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if completed.returncode != 0:
        return ()

    output = completed.stdout.strip()
    if not output:
        return ()

    by_pid = {
        window.pid: window.title
        for window in list_visible_windows()
        if window.title
    }

    rows = csv.reader(io.StringIO(output))
    processes: list[DetectedProcess] = []
    allowed_names = {name.casefold() for name in WECHAT_PROCESS_NAMES}
    for row in rows:
        if len(row) < 2:
            continue
        image_name = row[0].strip()
        if image_name.casefold() not in allowed_names:
            continue
        pid_text = row[1].strip().replace(",", "")
        if not pid_text.isdigit():
            continue
        pid = int(pid_text)
        processes.append(
            DetectedProcess(
                process_name=image_name.rsplit(".", 1)[0],
                pid=pid,
                executable_path=None,
                window_title=by_pid.get(pid),
            )
        )
    return tuple(processes)


def list_visible_windows() -> tuple[DetectedWindow, ...]:
    if not is_windows_host():
        return ()

    user32 = ctypes.windll.user32

    windows: list[DetectedWindow] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        title = title_buffer.value.strip()
        if not title:
            return True

        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buffer, 256)
        class_name = class_buffer.value.strip() or None

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append(
            DetectedWindow(
                title=title,
                pid=int(pid.value),
                class_name=class_name,
                hwnd=int(hwnd),
            )
        )
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return tuple(windows)


def list_wechat_windows() -> tuple[DetectedWindow, ...]:
    process_ids = {process.pid for process in list_wechat_processes()}
    if not process_ids:
        return ()
    return tuple(window for window in list_visible_windows() if window.pid in process_ids)


def focus_window(hwnd: int) -> tuple[bool, str]:
    if not is_windows_host():
        return False, "Window focusing is only supported on Windows hosts"

    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    if not user32.IsWindow(hwnd):
        return False, f"Window handle {hwnd} is not valid"

    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    success = bool(user32.SetForegroundWindow(hwnd))
    if success:
        return True, f"Focused window handle {hwnd}"
    return False, f"SetForegroundWindow returned false for handle {hwnd}"


def capture_window(hwnd: int, output_path: Path) -> tuple[bool, str]:
    if not is_windows_host():
        return False, "Window capture is only supported on Windows hosts"

    try:
        import win32con
        import win32gui
        import win32ui
    except Exception as exc:  # pragma: no cover - depends on host package state
        return False, f"pywin32 is unavailable: {type(exc).__name__}: {exc}"

    if not win32gui.IsWindow(hwnd):
        return False, f"Window handle {hwnd} is not valid"

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = max(right - left, 0)
    height = max(bottom - top, 0)
    if width == 0 or height == 0:
        return False, f"Window handle {hwnd} has an empty rectangle"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)
        render_flags = 0
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), render_flags)
        if result != 1:
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
        bitmap.SaveBitmapFile(save_dc, os.fspath(output_path))
        return True, f"Captured window handle {hwnd} to {output_path}"
    except Exception as exc:  # pragma: no cover - depends on live host UI
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    if not is_windows_host():
        return None

    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return None

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def click_screen_point(x: int, y: int) -> tuple[bool, str]:
    if not is_windows_host():
        return False, "Mouse clicking is only supported on Windows hosts"

    try:
        from pywinauto import mouse
    except Exception as exc:  # pragma: no cover - depends on host package state
        return False, f"pywinauto mouse helper is unavailable: {type(exc).__name__}: {exc}"

    try:
        mouse.click(button="left", coords=(x, y))
    except Exception as exc:  # pragma: no cover - depends on live host UI
        return False, f"{type(exc).__name__}: {exc}"
    return True, f"Clicked screen point ({x}, {y})"


def send_keys_sequence(sequence: str, pause: float = 0.02) -> tuple[bool, str]:
    if not is_windows_host():
        return False, "Keyboard input is only supported on Windows hosts"

    try:
        from pywinauto.keyboard import send_keys
    except Exception as exc:  # pragma: no cover - depends on host package state
        return False, f"pywinauto keyboard helper is unavailable: {type(exc).__name__}: {exc}"

    try:
        send_keys(sequence, pause=pause, with_spaces=True, with_newlines=True)
    except Exception as exc:  # pragma: no cover - depends on live host UI
        return False, f"{type(exc).__name__}: {exc}"
    return True, f"Sent key sequence: {sequence}"


def _set_clipboard_text_with_win32clipboard(text: str) -> tuple[bool, str]:
    try:
        import win32clipboard
    except Exception as exc:  # pragma: no cover - depends on host package state
        return False, f"win32clipboard is unavailable: {type(exc).__name__}: {exc}"

    try:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:  # pragma: no cover - depends on live host clipboard state
        return False, f"win32clipboard failed: {type(exc).__name__}: {exc}"
    return True, "Clipboard text updated via win32clipboard"


def _set_clipboard_text_with_ctypes(text: str) -> tuple[bool, str]:
    CF_UNICODETEXT = 13
    GHND = 0x0042
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    if not user32.OpenClipboard(None):
        return False, "OpenClipboard failed"

    try:
        if not user32.EmptyClipboard():
            return False, "EmptyClipboard failed"

        payload = text + "\x00"
        encoded = payload.encode("utf-16-le")
        handle = kernel32.GlobalAlloc(GHND, len(encoded))
        if not handle:
            return False, "GlobalAlloc failed"

        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            return False, "GlobalLock failed"

        try:
            ctypes.memmove(locked, encoded, len(encoded))
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False, "SetClipboardData failed"
    finally:
        user32.CloseClipboard()
    return True, "Clipboard text updated via ctypes fallback"


def set_clipboard_text(text: str) -> tuple[bool, str]:
    if not is_windows_host():
        return False, "Clipboard text is only supported on Windows hosts"

    win32_result = _set_clipboard_text_with_win32clipboard(text)
    if win32_result[0]:
        return win32_result

    ctypes_result = _set_clipboard_text_with_ctypes(text)
    if ctypes_result[0]:
        return ctypes_result
    return False, f"{win32_result[1]}; ctypes fallback failed: {ctypes_result[1]}"
