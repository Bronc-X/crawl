from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import uuid4

import httpx

from .schemas import (
    AdapterInfo,
    AdapterMode,
    Channel,
    ListingState,
    PublishAction,
    PublishTaskStatus,
)


CHANNEL_REQUIRED_ENVS: dict[Channel, list[str]] = {
    Channel.taobao: [
        "LISTING_TAOBAO_APP_KEY",
        "LISTING_TAOBAO_APP_SECRET",
        "LISTING_TAOBAO_SESSION_KEY",
    ],
    Channel.xiaohongshu: [
        "LISTING_XIAOHONGSHU_APP_KEY",
        "LISTING_XIAOHONGSHU_APP_SECRET",
        "LISTING_XIAOHONGSHU_ACCESS_TOKEN",
    ],
    Channel.douyin: [
        "LISTING_DOUYIN_APP_ID",
        "LISTING_DOUYIN_APP_SECRET",
        "LISTING_DOUYIN_ACCESS_TOKEN",
    ],
}


def real_send_required_envs(channel: Channel) -> list[str]:
    return [f"LISTING_{channel.name.upper()}_REAL_SEND_URL"]


def real_send_token_env(channel: Channel) -> str:
    return f"LISTING_{channel.name.upper()}_REAL_SEND_TOKEN"


CHANNEL_PORTALS: dict[Channel, str] = {
    Channel.taobao: "Taobao merchant backend",
    Channel.xiaohongshu: "Xiaohongshu merchant backend",
    Channel.douyin: "Douyin commerce backend",
}

CHANNEL_SUBMITTED_STATES: dict[Channel, ListingState] = {
    Channel.taobao: ListingState.live,
    Channel.xiaohongshu: ListingState.pending_review,
    Channel.douyin: ListingState.pending_review,
}


@dataclass(slots=True)
class AdapterResult:
    adapter: str
    task_status: PublishTaskStatus
    listing_state: ListingState
    external_id: str | None
    result: dict
    error_message: str | None = None


class BaseChannelAdapter(ABC):
    supported_actions = [
        PublishAction.publish,
        PublishAction.update,
        PublishAction.off_shelf,
    ]

    def __init__(self, channel: Channel, mode: AdapterMode) -> None:
        self.channel = channel
        self.mode = mode

    @property
    def required_env_vars(self) -> list[str]:
        return CHANNEL_REQUIRED_ENVS[self.channel]

    @property
    def missing_env_vars(self) -> list[str]:
        return [name for name in self.required_env_vars if not os.getenv(name)]

    @property
    def configured(self) -> bool:
        return True

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def notes(self) -> list[str]:
        return []

    def info(self) -> AdapterInfo:
        exposes_env = self.mode in (AdapterMode.api, AdapterMode.real_send)
        return AdapterInfo(
            channel=self.channel,
            name=self.name,
            mode=self.mode,
            configured=self.configured,
            supported_actions=self.supported_actions,
            required_env_vars=self.required_env_vars if exposes_env else [],
            missing_env_vars=self.missing_env_vars if exposes_env else [],
            notes=self.notes,
        )

    @abstractmethod
    def execute(self, action: PublishAction, payload: dict) -> AdapterResult:
        raise NotImplementedError


class MockChannelAdapter(BaseChannelAdapter):
    def __init__(self, channel: Channel) -> None:
        super().__init__(channel, AdapterMode.mock)

    @property
    def name(self) -> str:
        return f"mock_{self.channel.value}_adapter"

    @property
    def notes(self) -> list[str]:
        return [
            "Mock mode is for workflow verification only.",
            "No real channel write happens in this mode.",
        ]

    def execute(self, action: PublishAction, payload: dict) -> AdapterResult:
        if action == PublishAction.off_shelf:
            return AdapterResult(
                adapter=self.name,
                task_status=PublishTaskStatus.completed,
                listing_state=ListingState.off_shelf,
                external_id=payload.get("external_id"),
                result={"message": "Listing marked off-shelf in mock adapter."},
            )

        state = (
            CHANNEL_SUBMITTED_STATES[self.channel]
            if action == PublishAction.publish
            else ListingState.submitted
        )
        return AdapterResult(
            adapter=self.name,
            task_status=PublishTaskStatus.completed,
            listing_state=state,
            external_id=f"{self.channel.value}-{uuid4().hex[:12]}",
            result={
                "message": f"{action.value} accepted by mock adapter.",
                "channel": self.channel.value,
            },
        )


class ManualChannelAdapter(BaseChannelAdapter):
    def __init__(self, channel: Channel) -> None:
        super().__init__(channel, AdapterMode.manual)

    @property
    def name(self) -> str:
        return f"manual_{self.channel.value}_adapter"

    @property
    def notes(self) -> list[str]:
        return [
            "Manual mode prepares a payload and queues operator action.",
            "Use this while real API or browser automation is not connected.",
        ]

    def execute(self, action: PublishAction, payload: dict) -> AdapterResult:
        return AdapterResult(
            adapter=self.name,
            task_status=PublishTaskStatus.queued,
            listing_state=ListingState.queued,
            external_id=payload.get("external_id"),
            result={
                "message": f"{action.value} prepared for manual submission.",
                "portal": CHANNEL_PORTALS[self.channel],
                "payload_preview": payload,
            },
        )


class ApiPlaceholderChannelAdapter(BaseChannelAdapter):
    def __init__(self, channel: Channel) -> None:
        super().__init__(channel, AdapterMode.api)

    @property
    def name(self) -> str:
        return f"api_{self.channel.value}_adapter"

    @property
    def configured(self) -> bool:
        return not self.missing_env_vars

    @property
    def notes(self) -> list[str]:
        notes = [
            "API mode is the long-term write path.",
            "Credentials can be configured now, but live client wiring is still pending.",
        ]
        if self.missing_env_vars:
            notes.append("Missing required environment variables.")
        return notes

    def execute(self, action: PublishAction, payload: dict) -> AdapterResult:
        message = (
            "API mode selected, but the live client is not wired in yet."
            if self.configured
            else "API mode selected, but required credentials are missing."
        )
        return AdapterResult(
            adapter=self.name,
            task_status=PublishTaskStatus.failed,
            listing_state=ListingState.draft,
            external_id=payload.get("external_id"),
            result={
                "message": message,
                "payload_preview": payload,
                "missing_env_vars": self.missing_env_vars,
            },
            error_message=message,
        )


class RealSendChannelAdapter(BaseChannelAdapter):
    def __init__(self, channel: Channel) -> None:
        super().__init__(channel, AdapterMode.real_send)

    @property
    def name(self) -> str:
        return f"real_send_{self.channel.value}_adapter"

    @property
    def required_env_vars(self) -> list[str]:
        return real_send_required_envs(self.channel)

    @property
    def configured(self) -> bool:
        return not self.missing_env_vars

    @property
    def endpoint_url(self) -> str | None:
        return os.getenv(self.required_env_vars[0])

    @property
    def token(self) -> str | None:
        return os.getenv(real_send_token_env(self.channel))

    @property
    def notes(self) -> list[str]:
        notes = [
            "Real-send mode posts the listing payload to a configured automation bridge.",
            "The bridge must own the platform-specific login, compliance, and final submit step.",
        ]
        if self.missing_env_vars:
            notes.append("Missing required real-send endpoint environment variable.")
        return notes

    def _post_to_bridge(
        self, outbound: dict, headers: dict[str, str]
    ) -> httpx.Response:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            return client.post(self.endpoint_url, json=outbound, headers=headers)

    def execute(self, action: PublishAction, payload: dict) -> AdapterResult:
        if not self.configured or not self.endpoint_url:
            message = "Real-send mode selected, but the automation bridge URL is missing."
            return AdapterResult(
                adapter=self.name,
                task_status=PublishTaskStatus.failed,
                listing_state=ListingState.draft,
                external_id=payload.get("external_id"),
                result={
                    "message": message,
                    "missing_env_vars": self.missing_env_vars,
                    "payload_preview": payload,
                },
                error_message=message,
            )

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        outbound = {
            "channel": self.channel.value,
            "action": action.value,
            "payload": payload,
        }
        try:
            response = self._post_to_bridge(outbound, headers)
        except httpx.HTTPError as exc:
            message = f"Real-send bridge request failed: {exc}"
            return AdapterResult(
                adapter=self.name,
                task_status=PublishTaskStatus.failed,
                listing_state=ListingState.draft,
                external_id=payload.get("external_id"),
                result={"message": message, "payload_preview": payload},
                error_message=message,
            )

        try:
            response_payload: dict | list | str = response.json()
        except ValueError:
            response_payload = response.text

        if not response.is_success:
            message = f"Real-send bridge returned HTTP {response.status_code}."
            return AdapterResult(
                adapter=self.name,
                task_status=PublishTaskStatus.failed,
                listing_state=ListingState.draft,
                external_id=payload.get("external_id"),
                result={
                    "message": message,
                    "bridge_response": response_payload,
                    "payload_preview": payload,
                },
                error_message=message,
            )

        external_id = payload.get("external_id")
        if isinstance(response_payload, dict):
            external_id = response_payload.get("external_id") or external_id
        if external_id is None and action != PublishAction.off_shelf:
            external_id = f"{self.channel.value}-{uuid4().hex[:12]}"

        listing_state = (
            ListingState.off_shelf
            if action == PublishAction.off_shelf
            else CHANNEL_SUBMITTED_STATES[self.channel]
            if action == PublishAction.publish
            else ListingState.submitted
        )
        return AdapterResult(
            adapter=self.name,
            task_status=PublishTaskStatus.completed,
            listing_state=listing_state,
            external_id=external_id,
            result={
                "message": "Real-send bridge accepted the listing payload.",
                "bridge_response": response_payload,
            },
        )


class AdapterRegistry:
    def __init__(self, adapters: dict[Channel, BaseChannelAdapter]) -> None:
        self.adapters = adapters

    def for_channel(self, channel: Channel) -> BaseChannelAdapter:
        return self.adapters[channel]

    def describe(self) -> list[AdapterInfo]:
        return [self.adapters[channel].info() for channel in Channel]


def build_registry_from_env() -> AdapterRegistry:
    adapters: dict[Channel, BaseChannelAdapter] = {}
    for channel in Channel:
        env_key = f"LISTING_{channel.name.upper()}_ADAPTER_MODE"
        raw_mode = os.getenv(env_key, AdapterMode.mock.value).lower()
        try:
            mode = AdapterMode(raw_mode)
        except ValueError:
            mode = AdapterMode.mock

        if mode == AdapterMode.manual:
            adapters[channel] = ManualChannelAdapter(channel)
        elif mode == AdapterMode.api:
            adapters[channel] = ApiPlaceholderChannelAdapter(channel)
        elif mode == AdapterMode.real_send:
            adapters[channel] = RealSendChannelAdapter(channel)
        else:
            adapters[channel] = MockChannelAdapter(channel)

    return AdapterRegistry(adapters)
