from __future__ import annotations

import httpx
from importlib import import_module
from fastapi.testclient import TestClient

import app.adapters as adapters_module
from app.main import create_app


def test_validation_blocks_missing_channel_attributes(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    create_response = client.post(
        "/products",
        json={
            "title": "Core Listing",
            "description": "Base product for validation checks across channels.",
            "category": "software",
            "price": 199.0,
            "currency": "CNY",
            "attributes": {"brand": "Acme"},
            "media": [
                {"url": "https://example.com/hero.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
        },
    )
    product_id = create_response.json()["id"]

    validate_response = client.post(
        f"/products/{product_id}/validate",
        json={"channels": ["taobao", "douyin"]},
    )
    payload = validate_response.json()

    assert validate_response.status_code == 200
    assert payload["blocked_channels"] == ["taobao", "douyin"]
    assert payload["publishable_channels"] == []


def test_publish_succeeds_after_required_attributes_are_present(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    create_response = client.post(
        "/products",
        json={
            "title": "Listing Ready Product",
            "description": "Prepared for channel sync with a complete bootstrap payload.",
            "category": "software",
            "price": 299.0,
            "currency": "CNY",
            "attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
                "merchant_category_id": "mc_456",
                "logistic_template_id": "lt_789",
            },
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
        },
    )
    product_id = create_response.json()["id"]

    publish_response = client.post(
        f"/products/{product_id}/publish",
        json={"channels": ["taobao", "xiaohongshu"], "action": "publish"},
    )
    tasks = publish_response.json()

    assert publish_response.status_code == 200
    assert len(tasks) == 2
    assert {task["status"] for task in tasks} == {"completed"}
    assert {task["channel"] for task in tasks} == {"taobao", "xiaohongshu"}

    listings_response = client.get(f"/products/{product_id}/listings")
    listings = {item["channel"]: item for item in listings_response.json()}
    assert listings["taobao"]["state"] == "live"
    assert listings["xiaohongshu"]["state"] == "pending_review"


def test_taobao_validation_blocks_video_only_media(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    create_response = client.post(
        "/products",
        json={
            "title": "Video Listing",
            "description": "A product that only uses video media should be blocked for Taobao in bootstrap rules.",
            "category": "software",
            "price": 129.0,
            "currency": "CNY",
            "attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
            },
            "media": [
                {"url": "https://example.com/video.mp4", "kind": "video"},
                {"url": "https://example.com/video-2.mp4", "kind": "video"},
                {"url": "https://example.com/video-3.mp4", "kind": "video"},
            ],
        },
    )
    product_id = create_response.json()["id"]

    validate_response = client.post(
        f"/products/{product_id}/validate",
        json={"channels": ["taobao"]},
    )
    payload = validate_response.json()

    assert validate_response.status_code == 200
    assert payload["blocked_channels"] == ["taobao"]
    assert any(
        issue["field"] == "media.kind"
        for issue in payload["channel_issues"]["taobao"]
    )


def test_manual_adapter_mode_queues_publish_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LISTING_TAOBAO_ADAPTER_MODE", "manual")
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    create_response = client.post(
        "/products",
        json={
            "title": "Manual Queue Product",
            "description": "Ready for manual portal submission after automated preparation.",
            "category": "software",
            "price": 239.0,
            "currency": "CNY",
            "attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
            },
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
        },
    )
    product_id = create_response.json()["id"]

    publish_response = client.post(
        f"/products/{product_id}/publish",
        json={"channels": ["taobao"], "action": "publish"},
    )
    task = publish_response.json()[0]

    assert publish_response.status_code == 200
    assert task["status"] == "queued"
    assert task["listing_state"] == "queued"
    assert task["adapter"] == "manual_taobao_adapter"


def test_channel_settings_are_saved_and_listed(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    save_response = client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
            },
        },
    )
    list_response = client.get("/channel-settings")

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["default_attributes"]["shipping_template_id"] == "st_123"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 3


def test_quick_create_uses_saved_defaults_and_auto_publishes(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
            },
        },
    )
    client.put(
        "/channel-settings/xiaohongshu",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "merchant_category_id": "mc_456",
            },
        },
    )

    quick_response = client.post(
        "/products/quick-create",
        json={
            "title": "Quick Create Product",
            "description": "Created from saved platform defaults and immediately published.",
            "price": 399.0,
            "channels": ["taobao", "xiaohongshu"],
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
            "auto_publish": True,
            "use_saved_defaults": True,
        },
    )

    payload = quick_response.json()

    assert quick_response.status_code == 201
    assert payload["product"]["attributes"]["brand"] == "Acme"
    assert payload["product"]["attributes"]["shipping_template_id"] == "st_123"
    assert payload["product"]["attributes"]["merchant_category_id"] == "mc_456"
    assert len(payload["publish_tasks"]) == 2
    assert {task["status"] for task in payload["publish_tasks"]} == {"completed"}


def test_quick_create_blocks_conflicting_saved_defaults(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "shipping_template_id": "st_123",
            },
        },
    )
    client.put(
        "/channel-settings/xiaohongshu",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "OtherBrand",
                "merchant_category_id": "mc_456",
            },
        },
    )

    quick_response = client.post(
        "/products/quick-create",
        json={
            "title": "Conflicting Defaults Product",
            "description": "This request should be blocked until saved defaults are consistent.",
            "price": 399.0,
            "channels": ["taobao", "xiaohongshu"],
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
            "auto_publish": True,
            "use_saved_defaults": True,
        },
    )

    assert quick_response.status_code == 409
    assert "brand" in quick_response.json()["detail"]
    assert client.get("/products").json() == []


def test_console_and_adapter_endpoints_are_available(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    console_response = client.get("/console")
    adapters_response = client.get("/adapters")

    assert console_response.status_code == 200
    assert '<meta charset="utf-8">' in console_response.text
    assert "<title>多平台自动上架工作台</title>" in console_response.text
    assert "自动上架工作台" in console_response.text
    assert 'class="app-shell"' in console_response.text
    assert 'id="sideNav"' in console_response.text
    assert 'data-section="import"' in console_response.text
    assert 'data-section="products"' in console_response.text
    assert 'data-section="settings"' in console_response.text
    assert 'data-section="tasks"' in console_response.text
    assert 'data-section="log"' in console_response.text
    assert 'id="workspaceTitle"' in console_response.text
    assert 'id="view-import"' in console_response.text
    assert 'id="view-products"' in console_response.text
    assert 'id="view-settings"' in console_response.text
    assert 'id="view-tasks"' in console_response.text
    assert 'id="view-log"' in console_response.text
    assert 'id="importStepRail"' in console_response.text
    assert 'id="previewResultPanel"' in console_response.text
    assert 'id="previewTitle"' in console_response.text
    assert 'id="previewMediaCount"' in console_response.text
    assert 'id="rewritePreview"' in console_response.text
    assert 'id="rewriteResultPanel"' in console_response.text
    assert 'id="rewriteTitle"' in console_response.text
    assert 'id="rewriteDescription"' in console_response.text
    assert 'id="rewriteProvider"' in console_response.text
    assert 'id="createFromPreview"' in console_response.text
    assert 'id="publishFromPreview"' in console_response.text
    assert "/xiaohongshu/rewrite" in console_response.text
    assert "lastRewriteResult" in console_response.text
    assert "LLM 二创" in console_response.text
    assert "下一步" in console_response.text
    assert 'id="productForm"' in console_response.text
    assert 'id="xiaohongshuImportForm"' in console_response.text
    assert 'id="xhsAccountPersonal"' in console_response.text
    assert 'id="xhsTopics"' in console_response.text
    assert 'id="xhsConfirmRequired"' in console_response.text
    assert 'id="adapterStatusBody"' in console_response.text
    assert 'id="scrapePreview"' in console_response.text
    assert 'id="editPreviewInput"' in console_response.text
    assert "formatPayloadForLog" in console_response.text
    assert "withButtonBusy" in console_response.text
    assert "创建并自动上架" in console_response.text
    assert "个人号笔记" in console_response.text
    assert "用二创结果自动上架" in console_response.text
    assert "真实发送状态" in console_response.text
    assert adapters_response.status_code == 200
    assert len(adapters_response.json()) == 3


def test_xiaohongshu_scrape_extracts_draft_from_html_snapshot(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/65abc123",
            "html_snapshot": """
                <html>
                  <head>
                    <meta property="og:title" content="小红书爆款商品笔记">
                    <meta name="description" content="适合多平台自动上架的商品描述。">
                    <meta property="og:image" content="https://cdn.example.com/hero.jpg">
                  </head>
                  <body>
                    <img src="https://cdn.example.com/detail-1.jpg">
                  </body>
                </html>
            """,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["draft"]["title"] == "小红书爆款商品笔记"
    assert payload["draft"]["description"] == "适合多平台自动上架的商品描述。"
    assert payload["draft"]["attributes"]["source_platform"] == "xiaohongshu"
    assert payload["draft"]["attributes"]["source_note_id"] == "65abc123"
    assert [item["url"] for item in payload["draft"]["media"]] == [
        "https://cdn.example.com/hero.jpg",
        "https://cdn.example.com/detail-1.jpg",
    ]
    assert payload["product"] is None
    assert payload["publish_tasks"] == []


def test_xiaohongshu_scrape_ignores_inline_data_images(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/inline-image-note",
            "html_snapshot": """
                <html>
                  <head>
                    <meta property="og:title" content="带内联图片的笔记">
                    <meta name="description" content="页面里有装饰性的 base64 图片，不应该进入商品素材。">
                    <meta property="og:image" content="data:image/png;base64,abcd">
                  </head>
                  <body>
                    <img src="data:image/png;base64,efgh">
                    <img src="https://cdn.example.com/real.jpg">
                  </body>
                </html>
            """,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert [item["url"] for item in payload["draft"]["media"]] == [
        "https://cdn.example.com/real.jpg"
    ]


def test_xiaohongshu_rewrite_uses_local_fallback_without_llm_config(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("LISTING_LLM_API_URL", raising=False)
    monkeypatch.delenv("LISTING_LLM_API_KEY", raising=False)
    monkeypatch.delenv("LISTING_LLM_MODEL", raising=False)
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/rewrite",
        json={
            "draft": {
                "source_url": "https://www.xiaohongshu.com/explore/65abc123",
                "title": "Hip Training Tips - 小红书",
                "description": "3 亿人的生活经验，都在小红书",
                "category": "fitness",
                "price": 129.0,
                "currency": "CNY",
                "attributes": {"source_platform": "xiaohongshu"},
                "media": [{"url": "https://cdn.example.com/hero.jpg"}],
            },
            "account_type": "personal",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "local_fallback"
    assert payload["title"] == "Hip Training Tips"
    assert len(payload["description"]) >= 20
    assert payload["topics"]
    assert payload["warnings"]


def test_xiaohongshu_rewrite_posts_to_configured_llm_bridge(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("LISTING_LLM_API_URL", "https://llm.example/rewrite")
    monkeypatch.setenv("LISTING_LLM_API_KEY", "secret-llm-token")
    monkeypatch.setenv("LISTING_LLM_MODEL", "rewrite-model")
    calls = []

    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)
    try:
        llm_module = import_module("app.llm")
    except ModuleNotFoundError:
        llm_module = None
    if llm_module is not None:
        def fake_post_to_llm(self, outbound, headers):
            calls.append(
                {
                    "url": self.endpoint_url,
                    "outbound": outbound,
                    "headers": headers,
                }
            )
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title":"LLM Rewritten Title",'
                                '"description":"This is a richer rewritten description for listing validation.",'
                                '"topics":["training","listing"]}'
                            )
                        }
                    }
                ]
            }

        monkeypatch.setattr(
            llm_module.XiaohongshuRewriteService,
            "_post_to_llm",
            fake_post_to_llm,
        )

    response = client.post(
        "/xiaohongshu/rewrite",
        json={
            "draft": {
                "source_url": "https://www.xiaohongshu.com/explore/65abc123",
                "title": "Original Title - 小红书",
                "description": "short",
                "category": "fitness",
                "price": 129.0,
                "currency": "CNY",
                "attributes": {"source_platform": "xiaohongshu"},
                "media": [{"url": "https://cdn.example.com/hero.jpg"}],
            }
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "llm_bridge"
    assert payload["title"] == "LLM Rewritten Title"
    assert payload["description"] == "This is a richer rewritten description for listing validation."
    assert payload["topics"] == ["training", "listing"]
    assert calls[0]["url"] == "https://llm.example/rewrite"
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-llm-token"
    assert calls[0]["outbound"]["model"] == "rewrite-model"
    assert "messages" in calls[0]["outbound"]


def test_xiaohongshu_scrape_accepts_rewrite_overrides_before_publish(
    tmp_path,
) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/xiaohongshu",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "merchant_category_id": "mc_456",
            },
        },
    )

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/65abc123",
            "html_snapshot": """
                <html>
                  <head>
                    <meta property="og:title" content="Original Short Title - 小红书">
                    <meta name="description" content="short">
                    <meta property="og:image" content="https://cdn.example.com/hero.jpg">
                  </head>
                </html>
            """,
            "title_override": "LLM Rewritten Listing",
            "description_override": "This rewritten description is long enough for the xiaohongshu validation gate.",
            "price": 129.0,
            "channels": ["xiaohongshu"],
            "auto_create_product": True,
            "auto_publish": True,
            "use_saved_defaults": True,
        },
    )

    payload = response.json()

    assert response.status_code == 201
    assert payload["product"]["title"] == "LLM Rewritten Listing"
    assert (
        payload["product"]["description"]
        == "This rewritten description is long enough for the xiaohongshu validation gate."
    )
    assert payload["product"]["attributes"]["creative_source"] == "llm_rewrite"
    assert payload["publish_tasks"][0]["status"] == "completed"


def test_xiaohongshu_scrape_can_create_product_and_auto_publish(
    tmp_path,
) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/xiaohongshu",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {
                "brand": "Acme",
                "merchant_category_id": "mc_456",
            },
        },
    )

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/discovery/item/65abc123",
            "html_snapshot": """
                <html>
                  <head>
                    <script type="application/ld+json">
                      {
                        "@type": "Product",
                        "name": "抓取后自动上架商品",
                        "description": "这段描述来自小红书来源，并进入同一个自动上架产品。",
                        "image": ["https://cdn.example.com/hero.jpg"]
                      }
                    </script>
                  </head>
                </html>
            """,
            "price": 129.0,
            "channels": ["xiaohongshu"],
            "auto_create_product": True,
            "auto_publish": True,
            "use_saved_defaults": True,
        },
    )

    payload = response.json()

    assert response.status_code == 201
    assert payload["product"]["title"] == "抓取后自动上架商品"
    assert payload["product"]["attributes"]["source_note_id"] == "65abc123"
    assert payload["product"]["attributes"]["brand"] == "Acme"
    assert payload["product"]["attributes"]["merchant_category_id"] == "mc_456"
    assert len(payload["publish_tasks"]) == 1
    assert payload["publish_tasks"][0]["status"] == "completed"
    assert payload["publish_tasks"][0]["channel"] == "xiaohongshu"


def test_xiaohongshu_personal_account_auto_publishes_without_merchant_category(
    tmp_path,
) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/personal-note-1",
            "account_type": "personal",
            "html_snapshot": """
                <html>
                  <head>
                    <meta property="og:title" content="个人号测试笔记">
                    <meta name="description" content="这是一条走个人号笔记流程的测试内容，先生成草稿并交给人工确认。">
                    <meta property="og:image" content="https://cdn.example.com/note.jpg">
                  </head>
                </html>
            """,
            "price": 99.0,
            "topics": ["测试商品", "自动上架"],
            "channels": ["xiaohongshu"],
            "auto_create_product": True,
            "auto_publish": True,
            "use_saved_defaults": False,
        },
    )

    payload = response.json()

    assert response.status_code == 201
    assert payload["product"]["attributes"]["xiaohongshu_account_type"] == "personal"
    assert payload["product"]["attributes"]["publish_surface"] == "note"
    assert payload["product"]["attributes"]["safety_mode"] == "human_confirm_required"
    assert payload["product"]["attributes"]["topics"] == ["测试商品", "自动上架"]
    assert payload["publish_tasks"][0]["status"] == "completed"


def test_real_send_personal_note_payload_declares_personal_publish_surface(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("LISTING_XIAOHONGSHU_ADAPTER_MODE", "real_send")
    monkeypatch.setenv(
        "LISTING_XIAOHONGSHU_REAL_SEND_URL", "https://bridge.example/send"
    )
    calls = []

    def fake_post_to_bridge(self, outbound, headers):
        calls.append(outbound)
        return httpx.Response(
            201,
            json={"external_id": "xhs-note-draft-1", "status": "accepted"},
            request=httpx.Request("POST", self.endpoint_url),
        )

    monkeypatch.setattr(
        adapters_module.RealSendChannelAdapter,
        "_post_to_bridge",
        fake_post_to_bridge,
    )

    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/scrape",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/personal-note-2",
            "account_type": "personal",
            "html_snapshot": """
                <html>
                  <head>
                    <meta property="og:title" content="个人号真实发送测试">
                    <meta name="description" content="这条内容用于验证个人号笔记 payload 会被明确发送给自动化桥。">
                    <meta property="og:image" content="https://cdn.example.com/note-a.jpg">
                  </head>
                  <body>
                    <img src="https://cdn.example.com/note-b.jpg">
                  </body>
                </html>
            """,
            "price": 88.0,
            "topics": ["新品", "个人号测试"],
            "channels": ["xiaohongshu"],
            "auto_create_product": True,
            "auto_publish": True,
            "use_saved_defaults": False,
        },
    )

    task = response.json()["publish_tasks"][0]
    sent_payload = calls[0]["payload"]

    assert response.status_code == 201
    assert task["adapter"] == "real_send_xiaohongshu_adapter"
    assert task["external_id"] == "xhs-note-draft-1"
    assert sent_payload["account_type"] == "personal"
    assert sent_payload["publish_surface"] == "note"
    assert sent_payload["safety_mode"] == "human_confirm_required"
    assert sent_payload["note"] == {
        "title": "个人号真实发送测试",
        "body": "这条内容用于验证个人号笔记 payload 会被明确发送给自动化桥。",
        "image_urls": [
            "https://cdn.example.com/note-a.jpg",
            "https://cdn.example.com/note-b.jpg",
        ],
        "topics": ["新品", "个人号测试"],
        "confirm_required": True,
    }


def test_real_send_adapter_posts_payload_to_configured_endpoint(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("LISTING_XIAOHONGSHU_ADAPTER_MODE", "real_send")
    monkeypatch.setenv(
        "LISTING_XIAOHONGSHU_REAL_SEND_URL", "https://bridge.example/send"
    )
    monkeypatch.setenv("LISTING_XIAOHONGSHU_REAL_SEND_TOKEN", "secret-token")
    calls = []

    def fake_post_to_bridge(self, outbound, headers):
        calls.append({"url": self.endpoint_url, "json": outbound, "headers": headers})
        return httpx.Response(
            201,
            json={"external_id": "xhs-live-1", "status": "accepted"},
            request=httpx.Request("POST", self.endpoint_url),
        )

    monkeypatch.setattr(
        adapters_module.RealSendChannelAdapter,
        "_post_to_bridge",
        fake_post_to_bridge,
    )

    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    create_response = client.post(
        "/products",
        json={
            "title": "Real Send Product",
            "description": "A complete payload that should be sent through the configured bridge.",
            "category": "software",
            "price": 199.0,
            "currency": "CNY",
            "attributes": {
                "brand": "Acme",
                "merchant_category_id": "mc_456",
            },
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
            ],
        },
    )
    product_id = create_response.json()["id"]

    publish_response = client.post(
        f"/products/{product_id}/publish",
        json={"channels": ["xiaohongshu"], "action": "publish"},
    )
    task = publish_response.json()[0]

    assert publish_response.status_code == 200
    assert task["status"] == "completed"
    assert task["adapter"] == "real_send_xiaohongshu_adapter"
    assert task["external_id"] == "xhs-live-1"
    assert calls == [
        {
            "url": "https://bridge.example/send",
            "json": {
                "channel": "xiaohongshu",
                "action": "publish",
                "payload": {
                    "title": "Real Send Product",
                    "description": "A complete payload that should be sent through the configured bridge.",
                    "category": "software",
                    "price": 199.0,
                    "currency": "CNY",
                    "media": [
                        {
                            "url": "https://example.com/1.png",
                            "kind": "image",
                            "width": 1080,
                            "height": 1080,
                            "size_kb": None,
                            "file_type": None,
                        }
                    ],
                    "attributes": {
                        "brand": "Acme",
                        "merchant_category_id": "mc_456",
                    },
                    "external_id": None,
                },
            },
            "headers": {
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            },
        }
    ]
