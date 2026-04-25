from __future__ import annotations

import sys

from ..models import ExecutorCheck, ExecutorHealth
from .base import PlatformExecutor


class MacOSAccessibilityExecutor(PlatformExecutor):
    @property
    def name(self) -> str:
        return "macos-accessibility"

    def healthcheck(self) -> ExecutorHealth:
        supported = sys.platform == "darwin"
        details = "dry-run spike for Apple Accessibility / UI scripting executor"
        if not supported:
            details = "macOS accessibility executor only applies to macOS hosts"
        checks = (
            ExecutorCheck("running_on_macos", supported, "macOS host is required"),
        )
        return ExecutorHealth(self.name, supported, details, checks=checks)
