from __future__ import annotations

from typing import Any

from .schemas import (
    Channel,
    ChannelListing,
    ChannelRule,
    MediaAsset,
    MediaKind,
    Product,
    ValidationIssue,
    ValidationResult,
)


# These are internal workflow defaults, not official platform compliance matrices.
CHANNEL_RULES: dict[Channel, ChannelRule] = {
    Channel.taobao: ChannelRule(
        max_title_length=60,
        min_description_length=30,
        required_attributes=["brand", "shipping_template_id"],
        min_media_count=3,
        max_media_count=9,
        allowed_media_kinds=[MediaKind.image],
        min_image_width=800,
        min_image_height=800,
    ),
    Channel.xiaohongshu: ChannelRule(
        max_title_length=80,
        min_description_length=20,
        required_attributes=["brand", "merchant_category_id"],
        min_media_count=1,
        max_media_count=9,
        allowed_media_kinds=[MediaKind.image, MediaKind.video],
        min_image_width=720,
        min_image_height=720,
    ),
    Channel.douyin: ChannelRule(
        max_title_length=60,
        min_description_length=20,
        required_attributes=["brand", "logistic_template_id"],
        min_media_count=3,
        max_media_count=9,
        allowed_media_kinds=[MediaKind.image, MediaKind.video],
        min_image_width=600,
        min_image_height=600,
    ),
}


def _effective_value(
    *, base_value: Any, override_value: Any | None, default: Any = None
) -> Any:
    if override_value is None:
        if base_value is None:
            return default
        return base_value
    return override_value


def has_blocking_issues(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _validate_media_dimensions(
    *,
    asset: MediaAsset,
    channel: Channel,
    rule: ChannelRule,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if asset.kind != MediaKind.image:
        return issues

    if rule.min_image_width and asset.width is None:
        issues.append(
            ValidationIssue(
                field="media.width",
                message=(
                    f"Image width metadata is missing for {asset.url}. "
                    f"Recommended minimum is {rule.min_image_width}px."
                ),
                severity="warning",
                channel=channel,
            )
        )
    elif rule.min_image_width and asset.width < rule.min_image_width:
        issues.append(
            ValidationIssue(
                field="media.width",
                message=(
                    f"Image width {asset.width}px is below the bootstrap minimum "
                    f"{rule.min_image_width}px for {channel.value}."
                ),
                channel=channel,
            )
        )

    if rule.min_image_height and asset.height is None:
        issues.append(
            ValidationIssue(
                field="media.height",
                message=(
                    f"Image height metadata is missing for {asset.url}. "
                    f"Recommended minimum is {rule.min_image_height}px."
                ),
                severity="warning",
                channel=channel,
            )
        )
    elif rule.min_image_height and asset.height < rule.min_image_height:
        issues.append(
            ValidationIssue(
                field="media.height",
                message=(
                    f"Image height {asset.height}px is below the bootstrap minimum "
                    f"{rule.min_image_height}px for {channel.value}."
                ),
                channel=channel,
            )
        )

    return issues


def _is_xiaohongshu_personal_note(
    channel: Channel, attributes: dict[str, Any]
) -> bool:
    return (
        channel == Channel.xiaohongshu
        and attributes.get("xiaohongshu_account_type") == "personal"
        and attributes.get("publish_surface") == "note"
    )


def validate_product(
    product: Product,
    channels: list[Channel],
    listing_overrides: dict[Channel, ChannelListing],
) -> ValidationResult:
    core_issues: list[ValidationIssue] = []

    if not product.title.strip():
        core_issues.append(ValidationIssue(field="title", message="Title is required."))
    if not product.category.strip():
        core_issues.append(
            ValidationIssue(field="category", message="Category is required.")
        )
    if product.price <= 0:
        core_issues.append(
            ValidationIssue(field="price", message="Price must be greater than zero.")
        )
    if not product.media:
        core_issues.append(
            ValidationIssue(
                field="media", message="At least one media asset is required."
            )
        )
    if not product.description.strip():
        core_issues.append(
            ValidationIssue(
                field="description",
                message="Description is empty. Publishing is possible but review risk is higher.",
                severity="warning",
            )
        )

    target_channels = channels or list(Channel)
    channel_issues: dict[Channel, list[ValidationIssue]] = {}
    publishable_channels: list[Channel] = []
    blocked_channels: list[Channel] = []

    for channel in target_channels:
        issues: list[ValidationIssue] = []
        listing = listing_overrides.get(channel)
        effective_title = _effective_value(
            base_value=product.title,
            override_value=listing.title_override if listing else None,
            default="",
        )
        effective_description = _effective_value(
            base_value=product.description,
            override_value=listing.description_override if listing else None,
            default="",
        )
        effective_attributes = dict(product.attributes)
        if listing:
            effective_attributes.update(listing.attributes_override)

        rule = CHANNEL_RULES[channel]
        if len(effective_title) > rule.max_title_length:
            issues.append(
                ValidationIssue(
                    field="title",
                    message=f"Title exceeds bootstrap max length {rule.max_title_length}.",
                    channel=channel,
                )
            )

        if len(effective_description.strip()) < rule.min_description_length:
            issues.append(
                ValidationIssue(
                    field="description",
                    message=(
                        f"Description is shorter than bootstrap minimum "
                        f"{rule.min_description_length} characters."
                    ),
                    channel=channel,
                )
            )

        required_attributes = (
            []
            if _is_xiaohongshu_personal_note(channel, effective_attributes)
            else rule.required_attributes
        )
        for attr in required_attributes:
            value = effective_attributes.get(attr)
            if value in (None, "", []):
                issues.append(
                    ValidationIssue(
                        field=f"attributes.{attr}",
                        message=f"Missing required attribute '{attr}'.",
                        channel=channel,
                    )
                )

        if len(product.media) < rule.min_media_count:
            issues.append(
                ValidationIssue(
                    field="media",
                    message=(
                        f"{channel.value} needs at least {rule.min_media_count} media assets."
                    ),
                    channel=channel,
                )
            )
        if len(product.media) > rule.max_media_count:
            issues.append(
                ValidationIssue(
                    field="media",
                    message=(
                        f"{channel.value} allows at most {rule.max_media_count} media assets."
                    ),
                    channel=channel,
                )
            )

        for asset in product.media:
            if asset.kind not in rule.allowed_media_kinds:
                issues.append(
                    ValidationIssue(
                        field="media.kind",
                        message=(
                            f"{channel.value} bootstrap rules do not allow "
                            f"{asset.kind.value} assets in this workflow."
                        ),
                        channel=channel,
                    )
                )
                continue
            issues.extend(
                _validate_media_dimensions(asset=asset, channel=channel, rule=rule)
            )

        channel_issues[channel] = issues
        if has_blocking_issues(core_issues) or has_blocking_issues(issues):
            blocked_channels.append(channel)
        else:
            publishable_channels.append(channel)

    return ValidationResult(
        product_id=product.id,
        core_issues=core_issues,
        channel_issues=channel_issues,
        publishable_channels=publishable_channels,
        blocked_channels=blocked_channels,
    )
