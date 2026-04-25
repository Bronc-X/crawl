from __future__ import annotations

import sys

from ..models import ExecutorCheck, ExecutorHealth
from .base import PlatformExecutor
from .windows_common import find_command, list_wechat_processes, list_wechat_windows


class WindowsAstronExecutor(PlatformExecutor):
    @property
    def name(self) -> str:
        return "windows-astron"

    def healthcheck(self) -> ExecutorHealth:
        running_on_windows = sys.platform.startswith("win")
        astron_command = find_command("astron", "astron.exe", "astron-cli", "astron-cli.exe")
        processes = list_wechat_processes() if running_on_windows else ()
        windows = list_wechat_windows() if running_on_windows else ()
        supported = running_on_windows and astron_command is not None

        if not running_on_windows:
            details = "Astron executor only applies to Windows hosts"
        elif not astron_command:
            details = "Astron CLI/runtime was not found on PATH"
        elif not processes:
            details = "Astron runtime was found, but no WeChat process is running"
        elif not windows:
            details = "Astron runtime was found and WeChat is running, but no visible WeChat window was found"
        else:
            details = f"Astron runtime was detected at {astron_command}"

        checks = (
            ExecutorCheck("running_on_windows", running_on_windows, "Windows host is required"),
            ExecutorCheck("astron_runtime_found", astron_command is not None, "Install Astron and expose its CLI on PATH"),
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
