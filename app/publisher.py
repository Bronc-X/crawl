from __future__ import annotations

from typing import Any

from .adapters import AdapterRegistry
from .repository import ListingRepository
from .schemas import (
    Channel,
    ListingState,
    PublishAction,
    PublishTask,
    PublishTaskStatus,
)
from .validation import has_blocking_issues, validate_product


def _apply_channel_payload_shape(channel: Channel, payload: dict[str, Any]) -> None:
    attributes = payload["attributes"]
    if (
        channel == Channel.xiaohongshu
        and attributes.get("xiaohongshu_account_type") == "personal"
        and attributes.get("publish_surface") == "note"
    ):
        payload["account_type"] = "personal"
        payload["publish_surface"] = "note"
        payload["safety_mode"] = attributes.get(
            "safety_mode", "human_confirm_required"
        )
        payload["note"] = {
            "title": payload["title"],
            "body": payload["description"],
            "image_urls": [asset["url"] for asset in payload["media"]],
            "topics": attributes.get("topics", []),
            "confirm_required": attributes.get("confirm_required", True),
        }


def _effective_payload(
    product: Any, listing: Any | None, channel: Channel
) -> dict[str, Any]:
    attributes = dict(product.attributes)
    payload = {
        "title": product.title,
        "description": product.description,
        "category": product.category,
        "price": product.price,
        "currency": product.currency,
        "media": [asset.model_dump(mode="json") for asset in product.media],
        "attributes": attributes,
        "external_id": listing.external_id if listing else None,
    }

    if listing is None:
        _apply_channel_payload_shape(channel, payload)
        return payload

    if listing.title_override:
        payload["title"] = listing.title_override
    if listing.description_override:
        payload["description"] = listing.description_override
    if listing.price_override is not None:
        payload["price"] = listing.price_override
    payload["attributes"].update(listing.attributes_override)
    _apply_channel_payload_shape(channel, payload)
    return payload


class Publisher:
    def __init__(self, repo: ListingRepository, registry: AdapterRegistry) -> None:
        self.repo = repo
        self.registry = registry

    def publish(
        self, product_id: int, channels: list[Channel], action: PublishAction
    ) -> list[PublishTask]:
        product = self.repo.get_product(product_id)
        listings = {
            listing.channel: listing
            for listing in self.repo.list_channel_listings(product_id)
        }
        tasks: list[PublishTask] = []

        validation = None
        if action != PublishAction.off_shelf:
            validation = validate_product(product, channels, listings)

        for channel in channels:
            if validation is not None:
                channel_issues = validation.channel_issues.get(channel, [])
                if has_blocking_issues(validation.core_issues) or has_blocking_issues(
                    channel_issues
                ):
                    issues = validation.core_issues + channel_issues
                    task = self.repo.save_publish_task(
                        product_id=product_id,
                        channel=channel,
                        action=action,
                        status=PublishTaskStatus.blocked_validation,
                        adapter="validation_gate",
                        listing_state=ListingState.draft,
                        external_id=None,
                        result={
                            "issues": [issue.model_dump(mode="json") for issue in issues]
                        },
                        error_message="Validation blocked publish request.",
                    )
                    self.repo.update_listing_state(
                        product_id=product_id,
                        channel=channel,
                        state=ListingState.draft,
                        external_id=None,
                        last_error="Validation blocked publish request.",
                    )
                    tasks.append(task)
                    continue

            listing = listings.get(channel)
            payload = _effective_payload(product, listing, channel)
            adapter = self.registry.for_channel(channel)
            result = adapter.execute(action, payload)

            task = self.repo.save_publish_task(
                product_id=product_id,
                channel=channel,
                action=action,
                status=result.task_status,
                adapter=result.adapter,
                listing_state=result.listing_state,
                external_id=result.external_id,
                result=result.result,
                error_message=result.error_message,
            )
            self.repo.update_listing_state(
                product_id=product_id,
                channel=channel,
                state=result.listing_state,
                external_id=result.external_id,
                last_error=result.error_message,
            )
            tasks.append(task)

        return tasks
