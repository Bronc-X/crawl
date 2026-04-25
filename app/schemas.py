from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Channel(str, Enum):
    taobao = "taobao"
    xiaohongshu = "xiaohongshu"
    douyin = "douyin"


class ProductStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    published = "published"
    archived = "archived"


class ListingState(str, Enum):
    draft = "draft"
    queued = "queued"
    submitted = "submitted"
    pending_review = "pending_review"
    live = "live"
    rejected = "rejected"
    off_shelf = "off_shelf"


class PublishAction(str, Enum):
    publish = "publish"
    update = "update"
    off_shelf = "off_shelf"


class PublishTaskStatus(str, Enum):
    queued = "queued"
    completed = "completed"
    blocked_validation = "blocked_validation"
    failed = "failed"


class MediaKind(str, Enum):
    image = "image"
    video = "video"
    document = "document"


class AdapterMode(str, Enum):
    mock = "mock"
    manual = "manual"
    api = "api"
    real_send = "real_send"


class XiaohongshuAccountType(str, Enum):
    merchant = "merchant"
    personal = "personal"


class MediaAsset(BaseModel):
    url: str
    kind: MediaKind = MediaKind.image
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    size_kb: int | None = Field(default=None, gt=0)
    file_type: str | None = None


class ProductBase(BaseModel):
    title: str
    description: str = ""
    category: str
    price: float = Field(gt=0)
    currency: str = "CNY"
    status: ProductStatus = ProductStatus.draft
    attributes: dict[str, Any] = Field(default_factory=dict)
    media: list[MediaAsset] = Field(default_factory=list)

    @field_validator("media", mode="before")
    @classmethod
    def normalize_media(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"url": item, "kind": MediaKind.image.value})
            else:
                normalized.append(item)
        return normalized


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    status: ProductStatus | None = None
    attributes: dict[str, Any] | None = None
    media: list[MediaAsset] | None = None

    @field_validator("media", mode="before")
    @classmethod
    def normalize_media(cls, value: Any) -> list[Any] | None:
        if value is None:
            return None
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"url": item, "kind": MediaKind.image.value})
            else:
                normalized.append(item)
        return normalized


class Product(ProductBase):
    id: int
    created_at: str
    updated_at: str


class ChannelListingUpsert(BaseModel):
    channel: Channel
    title_override: str | None = None
    description_override: str | None = None
    price_override: float | None = Field(default=None, gt=0)
    attributes_override: dict[str, Any] = Field(default_factory=dict)


class ChannelListing(BaseModel):
    id: int
    product_id: int
    channel: Channel
    state: ListingState
    external_id: str | None = None
    title_override: str | None = None
    description_override: str | None = None
    price_override: float | None = None
    attributes_override: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    created_at: str
    updated_at: str


class ChannelSettingBase(BaseModel):
    default_category: str | None = None
    default_currency: str | None = None
    default_attributes: dict[str, Any] = Field(default_factory=dict)


class ChannelSettingUpsert(ChannelSettingBase):
    pass


class ChannelSetting(ChannelSettingBase):
    channel: Channel
    updated_at: str


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: str = "error"
    channel: Channel | None = None


class ValidateRequest(BaseModel):
    channels: list[Channel] = Field(default_factory=list)


class ValidationResult(BaseModel):
    product_id: int
    core_issues: list[ValidationIssue]
    channel_issues: dict[Channel, list[ValidationIssue]]
    publishable_channels: list[Channel]
    blocked_channels: list[Channel]


class PublishRequest(BaseModel):
    channels: list[Channel]
    action: PublishAction = PublishAction.publish


class QuickCreateRequest(BaseModel):
    title: str
    description: str = ""
    price: float = Field(gt=0)
    channels: list[Channel] = Field(default_factory=list)
    category: str | None = None
    currency: str | None = None
    media: list[MediaAsset] = Field(default_factory=list)
    use_saved_defaults: bool = True
    auto_publish: bool = True

    @field_validator("media", mode="before")
    @classmethod
    def normalize_media(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        normalized: list[Any] = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"url": item, "kind": MediaKind.image.value})
            else:
                normalized.append(item)
        return normalized


class PublishTask(BaseModel):
    id: int
    product_id: int
    channel: Channel
    action: PublishAction
    status: PublishTaskStatus
    adapter: str
    listing_state: ListingState
    external_id: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: str
    updated_at: str


class ChannelRule(BaseModel):
    max_title_length: int
    min_description_length: int = 0
    required_attributes: list[str] = Field(default_factory=list)
    min_media_count: int = 1
    max_media_count: int = 9
    allowed_media_kinds: list[MediaKind] = Field(default_factory=lambda: [MediaKind.image])
    min_image_width: int | None = None
    min_image_height: int | None = None


class QuickCreateResponse(BaseModel):
    product: Product
    publish_tasks: list[PublishTask] = Field(default_factory=list)
    applied_settings: dict[Channel, ChannelSetting] = Field(default_factory=dict)


class XiaohongshuScrapeRequest(BaseModel):
    source_url: str
    account_type: XiaohongshuAccountType = XiaohongshuAccountType.merchant
    html_snapshot: str | None = None
    title_override: str | None = None
    description_override: str | None = None
    price: float | None = Field(default=None, gt=0)
    category: str | None = None
    currency: str | None = None
    topics: list[str] = Field(default_factory=list)
    confirm_required: bool = True
    channels: list[Channel] = Field(default_factory=list)
    auto_create_product: bool = False
    auto_publish: bool = False
    use_saved_defaults: bool = True


class XiaohongshuScrapeDraft(BaseModel):
    source_url: str
    title: str
    description: str = ""
    category: str
    price: float | None = Field(default=None, gt=0)
    currency: str = "CNY"
    attributes: dict[str, Any] = Field(default_factory=dict)
    media: list[MediaAsset] = Field(default_factory=list)


class XiaohongshuScrapeResponse(BaseModel):
    draft: XiaohongshuScrapeDraft
    product: Product | None = None
    publish_tasks: list[PublishTask] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class XiaohongshuRewriteRequest(BaseModel):
    draft: XiaohongshuScrapeDraft
    account_type: XiaohongshuAccountType = XiaohongshuAccountType.merchant
    style: str = Field(default="clean", max_length=40)


class XiaohongshuRewriteResponse(BaseModel):
    title: str
    description: str
    topics: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    provider: str
    warnings: list[str] = Field(default_factory=list)


class AdapterInfo(BaseModel):
    channel: Channel
    name: str
    mode: AdapterMode
    configured: bool
    supported_actions: list[PublishAction]
    required_env_vars: list[str] = Field(default_factory=list)
    missing_env_vars: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RealSendBridgeRequest(BaseModel):
    channel: Channel
    action: PublishAction
    payload: dict[str, Any]


class RealSendJob(BaseModel):
    id: int
    channel: Channel
    action: PublishAction
    status: str
    external_id: str
    payload: dict[str, Any]
    created_at: str
