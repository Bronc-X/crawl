from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from .adapters import build_registry_from_env
from .console import render_console
from .llm import XiaohongshuRewriteService
from .publisher import Publisher
from .repository import ListingRepository
from .schemas import (
    AdapterInfo,
    Channel,
    ChannelListing,
    ChannelListingUpsert,
    ChannelSetting,
    ChannelSettingUpsert,
    Product,
    ProductCreate,
    ProductUpdate,
    PublishRequest,
    PublishTask,
    QuickCreateRequest,
    QuickCreateResponse,
    RealSendBridgeRequest,
    RealSendJob,
    ValidateRequest,
    ValidationResult,
    XiaohongshuScrapeRequest,
    XiaohongshuScrapeResponse,
    XiaohongshuRewriteRequest,
    XiaohongshuRewriteResponse,
)
from .validation import CHANNEL_RULES, validate_product
from .workflows import DefaultAttributeConflictError, ProductWorkflowService
from .xiaohongshu import XiaohongshuScrapeError, XiaohongshuScraper


def _repo(request: Request) -> ListingRepository:
    return request.app.state.repo


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="多平台稳定上架 API",
        version="0.3.0",
        description="商品主数据、平台默认配置、校验、自动上架任务和中文操作台。",
    )
    app.state.repo = ListingRepository(
        db_path or os.getenv("LISTING_DB_PATH", "data/listing.db")
    )
    app.state.adapter_registry = build_registry_from_env()
    app.state.publisher = Publisher(app.state.repo, app.state.adapter_registry)
    app.state.workflow = ProductWorkflowService(app.state.repo, app.state.publisher)
    app.state.xiaohongshu_scraper = XiaohongshuScraper()
    app.state.xiaohongshu_rewriter = XiaohongshuRewriteService.from_env()

    @app.get("/")
    def root() -> dict:
        return {
            "service": "multi-platform-stable-listing",
            "version": "0.3.0",
            "docs": "/docs",
            "console": "/console",
        }

    @app.get("/console", response_class=HTMLResponse)
    def console() -> str:
        return render_console()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/channel-rules")
    def channel_rules() -> dict:
        return {
            channel.value: rule.model_dump(mode="json")
            for channel, rule in CHANNEL_RULES.items()
        }

    @app.get("/adapters", response_model=list[AdapterInfo])
    def adapters(request: Request) -> list[AdapterInfo]:
        return request.app.state.adapter_registry.describe()

    @app.get("/channel-settings", response_model=list[ChannelSetting])
    def list_channel_settings(request: Request) -> list[ChannelSetting]:
        return _repo(request).list_channel_settings()

    @app.put("/channel-settings/{channel}", response_model=ChannelSetting)
    def upsert_channel_setting(
        channel: Channel, payload: ChannelSettingUpsert, request: Request
    ) -> ChannelSetting:
        return _repo(request).upsert_channel_setting(channel, payload)

    @app.post("/products", response_model=Product, status_code=201)
    def create_product(payload: ProductCreate, request: Request) -> Product:
        return _repo(request).create_product(payload)

    @app.post("/products/quick-create", response_model=QuickCreateResponse, status_code=201)
    def quick_create(payload: QuickCreateRequest, request: Request) -> QuickCreateResponse:
        workflow: ProductWorkflowService = request.app.state.workflow
        try:
            return workflow.quick_create(payload)
        except DefaultAttributeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/xiaohongshu/scrape", response_model=XiaohongshuScrapeResponse)
    def scrape_xiaohongshu(
        payload: XiaohongshuScrapeRequest, request: Request, response: Response
    ) -> XiaohongshuScrapeResponse:
        scraper: XiaohongshuScraper = request.app.state.xiaohongshu_scraper
        try:
            draft = scraper.scrape(payload)
        except XiaohongshuScrapeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not payload.auto_create_product:
            return XiaohongshuScrapeResponse(draft=draft)

        workflow: ProductWorkflowService = request.app.state.workflow
        try:
            result = workflow.create_from_xiaohongshu_scrape(draft, payload)
        except DefaultAttributeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        response.status_code = 201
        return result

    @app.post("/xiaohongshu/rewrite", response_model=XiaohongshuRewriteResponse)
    def rewrite_xiaohongshu(
        payload: XiaohongshuRewriteRequest, request: Request
    ) -> XiaohongshuRewriteResponse:
        rewriter: XiaohongshuRewriteService = request.app.state.xiaohongshu_rewriter
        return rewriter.rewrite(payload)

    @app.get("/products", response_model=list[Product])
    def list_products(request: Request) -> list[Product]:
        return _repo(request).list_products()

    @app.get("/products/{product_id}", response_model=Product)
    def get_product(product_id: int, request: Request) -> Product:
        try:
            return _repo(request).get_product(product_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/products/{product_id}", response_model=Product)
    def update_product(
        product_id: int, payload: ProductUpdate, request: Request
    ) -> Product:
        try:
            return _repo(request).update_product(product_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/products/{product_id}/listings", response_model=ChannelListing)
    def upsert_listing(
        product_id: int, payload: ChannelListingUpsert, request: Request
    ) -> ChannelListing:
        try:
            return _repo(request).upsert_channel_listing(product_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/products/{product_id}/listings", response_model=list[ChannelListing])
    def list_listings(product_id: int, request: Request) -> list[ChannelListing]:
        try:
            return _repo(request).list_channel_listings(product_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/products/{product_id}/validate", response_model=ValidationResult)
    def validate(
        product_id: int, payload: ValidateRequest, request: Request
    ) -> ValidationResult:
        try:
            product = _repo(request).get_product(product_id)
            listings = {
                listing.channel: listing
                for listing in _repo(request).list_channel_listings(product_id)
            }
            return validate_product(product, payload.channels, listings)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/products/{product_id}/publish", response_model=list[PublishTask])
    def publish(
        product_id: int, payload: PublishRequest, request: Request
    ) -> list[PublishTask]:
        try:
            publisher: Publisher = request.app.state.publisher
            return publisher.publish(product_id, payload.channels, payload.action)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/publish-tasks", response_model=list[PublishTask])
    def list_publish_tasks(request: Request) -> list[PublishTask]:
        return _repo(request).list_publish_tasks()

    @app.get("/publish-tasks/{task_id}", response_model=PublishTask)
    def get_publish_task(task_id: int, request: Request) -> PublishTask:
        try:
            return _repo(request).get_publish_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/real-send/{channel}", response_model=RealSendJob, status_code=202)
    def accept_real_send_job(
        channel: Channel, payload: RealSendBridgeRequest, request: Request
    ) -> RealSendJob:
        if payload.channel != channel:
            raise HTTPException(
                status_code=422,
                detail="Bridge channel path does not match payload channel.",
            )
        return _repo(request).save_real_send_job(payload)

    @app.get("/real-send-jobs", response_model=list[RealSendJob])
    def list_real_send_jobs(request: Request) -> list[RealSendJob]:
        return _repo(request).list_real_send_jobs()

    return app


app = create_app()
