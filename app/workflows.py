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

        if conflicts:
            raise DefaultAttributeConflictError(
                "平台默认配置存在冲突，请先统一这些字段后再自动上架："
                + "；".join(conflicts)
            )

        return merged_attributes

    def quick_create(self, payload: QuickCreateRequest) -> QuickCreateResponse:
        settings: dict[Channel, ChannelSetting] = {
            channel: self.repo.get_channel_setting(channel) for channel in payload.channels
        }

        merged_attributes: dict[str, Any] = {}
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
        if payload.use_saved_defaults:
            merged_attributes = self._merge_saved_defaults(settings)
        merged_attributes.update(draft.attributes)

        inferred_category = payload.category or next(
            (setting.default_category for setting in settings.values() if setting.default_category),
            draft.category,
        )
        inferred_currency = payload.currency or next(
            (setting.default_currency for setting in settings.values() if setting.default_currency),
            draft.currency,
        )

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
