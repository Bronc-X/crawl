from __future__ import annotations

from typing import Any

from .publisher import Publisher
from .repository import ListingRepository
from .schemas import (
    Channel,
    ChannelSetting,
    PublishAction,
    ProductCreate,
    QuickCreateRequest,
    QuickCreateResponse,
    XiaohongshuScrapeDraft,
    XiaohongshuScrapeRequest,
    XiaohongshuScrapeResponse,
)


class DefaultAttributeConflictError(ValueError):
    pass


class ProductWorkflowService:
    def __init__(self, repo: ListingRepository, publisher: Publisher) -> None:
        self.repo = repo
        self.publisher = publisher

    def _collect_scalar_default_conflicts(
        self, settings: dict[Channel, ChannelSetting], field_name: str
    ) -> list[str]:
        attr_name = f"default_{field_name}"
        selected_values = [
            (channel, getattr(setting, attr_name))
            for channel, setting in settings.items()
            if getattr(setting, attr_name)
        ]
        if len(selected_values) < 2:
            return []

        source_channel, source_value = selected_values[0]
        conflicts: list[str] = []
        for channel, value in selected_values[1:]:
            if value != source_value:
                conflicts.append(
                    f"{field_name} ({source_channel.value}={source_value!r}, {channel.value}={value!r})"
                )
        return conflicts

    def _merge_saved_defaults(
        self, settings: dict[Channel, ChannelSetting]
    ) -> dict[str, Any]:
        merged_attributes: dict[str, Any] = {}
        attribute_sources: dict[str, Channel] = {}
        conflicts: list[str] = []

        for channel, setting in settings.items():
            for key, value in setting.default_attributes.items():
                if key not in merged_attributes:
                    merged_attributes[key] = value
                    attribute_sources[key] = channel
                    continue

                if merged_attributes[key] != value:
                    conflicts.append(
                        f"{key} ({attribute_sources[key].value}={merged_attributes[key]!r}, "
                        f"{channel.value}={value!r})"
                    )

        conflicts.extend(self._collect_scalar_default_conflicts(settings, "category"))
        conflicts.extend(self._collect_scalar_default_conflicts(settings, "currency"))

        if conflicts:
            raise DefaultAttributeConflictError(
                "\u5e73\u53f0\u9ed8\u8ba4\u914d\u7f6e\u5b58\u5728\u51b2\u7a81\uff0c\u8bf7\u5148\u7edf\u4e00\u8fd9\u4e9b\u5b57\u6bb5\u540e\u518d\u81ea\u52a8\u4e0a\u67b6\uff1a"
                + "\uff1b".join(conflicts)
            )

        return merged_attributes

    def quick_create(self, payload: QuickCreateRequest) -> QuickCreateResponse:
        settings: dict[Channel, ChannelSetting] = {
            channel: self.repo.get_channel_setting(channel) for channel in payload.channels
        }

        merged_attributes: dict[str, Any] = {}
        inferred_category = payload.category or "general"
        inferred_currency = payload.currency or "CNY"
        if payload.use_saved_defaults:
            merged_attributes = self._merge_saved_defaults(settings)
            inferred_category = payload.category or next(
                (setting.default_category for setting in settings.values() if setting.default_category),
                "general",
            )
            inferred_currency = payload.currency or next(
                (setting.default_currency for setting in settings.values() if setting.default_currency),
                "CNY",
            )

        product = self.repo.create_product(
            ProductCreate(
                title=payload.title,
                description=payload.description,
                category=inferred_category,
                price=payload.price,
                currency=inferred_currency,
                attributes=merged_attributes,
                media=payload.media,
            )
        )

        tasks = []
        if payload.auto_publish and payload.channels:
            tasks = self.publisher.publish(
                product.id, payload.channels, action=PublishAction.publish
            )

        applied_settings: dict = {
            channel: ChannelSetting(**setting.model_dump(mode="json"))
            for channel, setting in settings.items()
        }
        return QuickCreateResponse(
            product=product,
            publish_tasks=tasks,
            applied_settings=applied_settings,
        )

    def create_from_xiaohongshu_scrape(
        self, draft: XiaohongshuScrapeDraft, payload: XiaohongshuScrapeRequest
    ) -> XiaohongshuScrapeResponse:
        if draft.price is None:
            raise ValueError("Price is required before creating a product from scrape.")

        settings: dict[Channel, ChannelSetting] = {
            channel: self.repo.get_channel_setting(channel) for channel in payload.channels
        }
        merged_attributes: dict[str, Any] = {}
        inferred_category = payload.category or draft.category
        inferred_currency = payload.currency or draft.currency
        if payload.use_saved_defaults:
            merged_attributes = self._merge_saved_defaults(settings)
            inferred_category = payload.category or next(
                (setting.default_category for setting in settings.values() if setting.default_category),
                draft.category,
            )
            inferred_currency = payload.currency or next(
                (setting.default_currency for setting in settings.values() if setting.default_currency),
                draft.currency,
            )
        merged_attributes.update(draft.attributes)

        product = self.repo.create_product(
            ProductCreate(
                title=draft.title,
                description=draft.description,
                category=inferred_category,
                price=draft.price,
                currency=inferred_currency,
                attributes=merged_attributes,
                media=draft.media,
            )
        )

        tasks = []
        if payload.auto_publish and payload.channels:
            tasks = self.publisher.publish(
                product.id, payload.channels, action=PublishAction.publish
            )

        return XiaohongshuScrapeResponse(
            draft=draft,
            product=product,
            publish_tasks=tasks,
        )
