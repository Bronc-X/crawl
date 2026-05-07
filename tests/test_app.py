from __future__ import annotations

import httpx
from importlib import import_module
from fastapi.testclient import TestClient

import app.adapters as adapters_module
from app.console import render_console
from app.database import uses_shared_in_memory
from app.main import create_app
from app.xiaohongshu_browser import (
    XiaohongshuBrowserBlockerError,
    build_xiaohongshu_search_url,
    detect_xiaohongshu_access_blocker,
    extract_browser_note_payload,
)


def test_in_memory_database_supports_multiple_requests() -> None:
    app = create_app(":memory:")
    client = TestClient(app)

    settings_response = client.get("/channel-settings")
    assert settings_response.status_code == 200
    assert len(settings_response.json()) == 3

    save_response = client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {"brand": "Acme", "shipping_template_id": "st_123"},
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["default_attributes"]["shipping_template_id"] == "st_123"


def test_in_memory_apps_do_not_share_state_across_instances() -> None:
    first = TestClient(create_app(":memory:"))
    second = TestClient(create_app(":memory:"))

    save_response = first.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {"brand": "Acme", "shipping_template_id": "st_123"},
        },
    )

    assert save_response.status_code == 200
    second_settings = second.get("/channel-settings")
    assert second_settings.status_code == 200
    taobao = next(item for item in second_settings.json() if item["channel"] == "taobao")
    assert taobao["default_attributes"] == {}
    assert taobao["default_category"] is None


def test_in_memory_repository_uses_shared_memory_uri_and_keeps_connection_alive() -> None:
    app = create_app(":memory:")
    repo = app.state.repo

    assert uses_shared_in_memory(repo.db_path) is True
    assert repo._keepalive_conn is not None


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


def test_quick_create_blocks_conflicting_saved_category_and_currency(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "CNY",
            "default_attributes": {"brand": "Acme", "shipping_template_id": "st_123"},
        },
    )
    client.put(
        "/channel-settings/xiaohongshu",
        json={
            "default_category": "beauty",
            "default_currency": "USD",
            "default_attributes": {"brand": "Acme", "merchant_category_id": "mc_456"},
        },
    )

    quick_response = client.post(
        "/products/quick-create",
        json={
            "title": "Category Conflict Product",
            "description": "Conflicting saved category and currency should block auto create.",
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
    detail = quick_response.json()["detail"]
    assert "category" in detail
    assert "currency" in detail
    assert client.get("/products").json() == []


def test_quick_create_without_saved_defaults_does_not_reuse_saved_category_or_currency(
    tmp_path,
) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    client.put(
        "/channel-settings/taobao",
        json={
            "default_category": "software",
            "default_currency": "USD",
            "default_attributes": {"brand": "Acme", "shipping_template_id": "st_123"},
        },
    )

    quick_response = client.post(
        "/products/quick-create",
        json={
            "title": "Manual Draft Product",
            "description": "Saved defaults should stay unused when the toggle is off.",
            "price": 99.0,
            "channels": ["taobao"],
            "media": [
                {"url": "https://example.com/1.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/2.png", "width": 1080, "height": 1080},
                {"url": "https://example.com/3.png", "width": 1080, "height": 1080},
            ],
            "auto_publish": False,
            "use_saved_defaults": False,
        },
    )

    payload = quick_response.json()

    assert quick_response.status_code == 201
    assert payload["product"]["category"] == "general"
    assert payload["product"]["currency"] == "CNY"
    assert payload["product"]["attributes"] == {}


def test_console_and_adapter_endpoints_are_available(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    console_response = client.get("/console")
    adapters_response = client.get("/adapters")
    console_html = console_response.text

    assert console_response.status_code == 200
    assert '<meta charset="utf-8">' in console_html
    assert '&#22810;&#24179;&#21488;&#33258;&#21160;&#19978;&#26550;&#24037;&#20316;&#21488;' in console_html
    assert '&#33258;&#21160;&#19978;&#26550;&#24037;&#20316;&#21488;' in console_html
    assert 'class="app-shell"' in console_html
    assert 'id="sideNav"' in console_html
    assert 'data-section="import"' in console_html
    assert 'data-section="products"' in console_html
    assert 'data-section="settings"' in console_html
    assert 'data-section="tasks"' in console_html
    assert 'data-section="checks"' in console_html
    assert 'data-section="log"' in console_html
    assert 'id="workspaceTitle"' in console_html
    assert 'id="view-import"' in console_html
    assert 'id="view-products"' in console_html
    assert 'id="view-settings"' in console_html
    assert 'id="view-tasks"' in console_html
    assert 'id="view-checks"' in console_html
    assert 'id="view-log"' in console_html
    assert 'id="runFunctionCheck"' in console_html
    assert 'id="checkSummary"' in console_html
    assert 'id="checkResultsBody"' in console_html
    assert 'id="importStepRail"' in console_html
    assert 'id="previewResultPanel"' in console_html
    assert 'id="previewTitle"' in console_html
    assert 'id="previewMediaCount"' in console_html
    assert 'id="rewritePreview"' in console_html
    assert 'id="rewriteResultPanel"' in console_html
    assert 'id="rewriteTitle"' in console_html
    assert 'id="rewriteDescription"' in console_html
    assert 'id="rewriteProvider"' in console_html
    assert 'id="createFromPreview"' in console_html
    assert 'id="publishFromPreview"' in console_html
    assert '/xiaohongshu/rewrite' in console_html
    assert 'runFunctionCheck' in console_html
    assert 'runCheckStep' in console_html
    assert 'renderCheckResults' in console_html
    assert 'buildCheckProductPayload' in console_html
    assert '"/health"' in console_html
    assert '"/products"' in console_html
    assert '"/publish-tasks"' in console_html
    assert '"/xiaohongshu/scrape"' in console_html
    assert '"/xiaohongshu/rewrite"' in console_html
    assert 'validate`' in console_html
    assert 'publish`' in console_html
    assert 'lastRewriteResult' in console_html
    assert 'updateWorkspaceHeader' in console_html
    assert 'markImportStep("preview")' in console_html
    assert 'markImportStep("rewrite")' in console_html
    assert 'markImportStep("next")' in console_html
    assert 'split(/[,\\n]/)' in console_html
    assert 'LLM &#20108;&#21019;' in console_html
    assert '&#19979;&#19968;&#27493;' in console_html
    assert 'id="productForm"' in console_html
    assert 'id="xiaohongshuImportForm"' in console_html
    assert 'id="xhsAccountPersonal"' in console_html
    assert 'id="xhsTopics"' in console_html
    assert '<textarea id="xhsHtmlSnapshot" spellcheck="false"></textarea>' in console_html
    assert 'withButtonBusy("createDraft", "\u521b\u5efa\u4e2d", () => quickCreate(false))' in console_html
    assert 'withButtonBusy("autoPublish", "\u4e0a\u67b6\u4e2d", () => quickCreate(true))' in console_html
    assert 'id="xhsConfirmRequired"' in console_html
    assert 'id="adapterStatusBody"' in console_html
    assert 'id="scrapePreview"' in console_html
    assert 'id="browserExtractPreview"' in console_html
    assert 'id="editPreviewInput"' in console_html
    assert '/xiaohongshu/browser/extract' in console_html
    assert 'browserExtractXiaohongshu' in console_html
    assert "buildSettingPayload" in console_html
    assert 'fetchJson(`/channel-settings/${channel}`' in console_html
    assert 'formatPayloadForLog' in console_html
    assert 'log("scrape", { error: error.message })' in console_html
    assert 'log("rewrite", { error: error.message })' in console_html
    assert 'log("create_from_preview", { error: error.message })' in console_html
    assert 'log("publish_from_preview", { error: error.message })' in console_html
    assert 'withButtonBusy' in console_html
    assert '&#21019;&#24314;&#24182;&#33258;&#21160;&#19978;&#26550;' in console_html
    assert '&#20010;&#20154;&#21495;&#31508;&#35760;' in console_html
    assert '&#29992;&#20108;&#21019;&#32467;&#26524;&#33258;&#21160;&#19978;&#26550;' in console_html
    assert '&#30495;&#23454;&#21457;&#36865;&#29366;&#24577;' in console_html
    assert adapters_response.status_code == 200
    assert len(adapters_response.json()) == 3


def test_console_inline_script_keeps_valid_topic_split_regex() -> None:
    html = render_console()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]

    assert 'split(/[,\\n]/)' in script
    assert 'split(/[,\n' not in script


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


def test_xiaohongshu_browser_worker_builds_search_url_without_direct_note_entry() -> None:
    assert (
        build_xiaohongshu_search_url("site:xiaohongshu.com/explore 提臀塑形")
        == "https://www.xiaohongshu.com/search_result?keyword=%E6%8F%90%E8%87%80%E5%A1%91%E5%BD%A2"
    )


def test_xiaohongshu_browser_worker_detects_access_blockers() -> None:
    assert (
        detect_xiaohongshu_access_blocker(
            title="安全验证",
            body="访问过于频繁，请稍后再试",
            final_url="https://www.xiaohongshu.com/search_result?keyword=test",
        )
        == "access_blocked"
    )
    assert (
        detect_xiaohongshu_access_blocker(
            title="登录",
            body="登录后查看搜索结果，扫码登录",
            final_url="https://www.xiaohongshu.com/search_result?keyword=test",
        )
        == "login_required"
    )
    assert (
        detect_xiaohongshu_access_blocker(
            title="验证码",
            body="请完成验证码后继续访问",
            final_url="https://www.xiaohongshu.com/captcha",
        )
        == "captcha_required"
    )


def test_xiaohongshu_browser_worker_extracts_note_payload_from_visible_detail_html() -> None:
    payload = extract_browser_note_payload(
        source_url="https://www.xiaohongshu.com/explore/browser-note-1",
        final_url="https://www.xiaohongshu.com/explore/browser-note-1",
        html="""
          <html>
            <head>
              <meta property="og:title" content="浏览器采集标题">
              <meta name="description" content="浏览器采集描述">
              <meta property="og:image" content="https://cdn.example.com/a.jpg">
            </head>
            <body>
              <div class="author-container"><a href="/user/profile/u1"><span class="username">作者A</span></a></div>
              <h1 id="detail-title">浏览器采集标题</h1>
              <div id="detail-desc">浏览器采集正文 #测试 #自动上架</div>
              <time>2026-05-07</time>
              <img src="https://cdn.example.com/b.jpg">
            </body>
          </html>
        """,
    )

    assert payload.note_id == "browser-note-1"
    assert payload.title == "浏览器采集标题"
    assert payload.description == "浏览器采集正文 #测试 #自动上架"
    assert payload.author_name == "作者A"
    assert payload.validated is True
    assert payload.blocker is None
    assert payload.tags == ["#测试", "#自动上架"]
    assert [item.url for item in payload.media] == [
        "https://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
    ]


def test_xiaohongshu_browser_worker_prefers_structured_initial_state() -> None:
    payload = extract_browser_note_payload(
        source_url="https://www.xiaohongshu.com/explore/structured-note-1",
        final_url="https://www.xiaohongshu.com/explore/structured-note-1",
        html="""
          <html>
            <head><meta property="og:title" content="兜底标题"></head>
            <body>
              <script>
                window.__INITIAL_STATE__ = {
                  "note": {
                    "noteDetailMap": {
                      "structured-note-1": {
                        "note": {
                          "noteId": "structured-note-1",
                          "title": "结构化标题",
                          "desc": "结构化正文 #结构化 #自动上架",
                          "time": "2026-05-07",
                          "user": {
                            "nickname": "结构化作者",
                            "userId": "user-structured"
                          },
                          "imageList": [
                            {"url": "https://cdn.example.com/state-a.jpg"},
                            {"infoList": [{"url": "https://cdn.example.com/state-b.jpg"}]}
                          ]
                        }
                      }
                    }
                  }
                };
              </script>
              <h1 id="detail-title">可见标题</h1>
              <div id="detail-desc">可见正文</div>
              <img src="https://cdn.example.com/dom.jpg">
            </body>
          </html>
        """,
    )

    assert payload.title == "结构化标题"
    assert payload.description == "结构化正文 #结构化 #自动上架"
    assert payload.author_name == "结构化作者"
    assert payload.author_profile_url == "https://www.xiaohongshu.com/user/profile/user-structured"
    assert payload.publish_time == "2026-05-07"
    assert payload.tags == ["#结构化", "#自动上架"]
    assert [item.url for item in payload.media] == [
        "https://cdn.example.com/state-a.jpg",
        "https://cdn.example.com/state-b.jpg",
    ]


def test_xiaohongshu_browser_worker_cli_accepts_cdp_url_for_real_browser_mode() -> None:
    worker = import_module("scripts.xhs_browser_worker")

    args = worker.build_parser().parse_args(
        [
            "scrape-search",
            "--keyword",
            "提臀塑形",
            "--limit",
            "2",
            "--cdp-url",
            "http://127.0.0.1:9222",
        ]
    )

    assert args.cdp_url == "http://127.0.0.1:9222"
    assert args.limit == 2
    assert args.storage_state == ".auth/xhs-storage.json"


def test_xiaohongshu_browser_worker_raises_instead_of_bypassing_captcha() -> None:
    try:
        extract_browser_note_payload(
            source_url="https://www.xiaohongshu.com/explore/browser-note-2",
            final_url="https://www.xiaohongshu.com/captcha",
            html="<html><title>安全验证</title><body>请完成验证码后继续访问</body></html>",
        )
    except XiaohongshuBrowserBlockerError as exc:
        assert exc.reason == "captcha_required"
        assert "人工介入" in str(exc)
    else:
        raise AssertionError("captcha blocker should stop browser scraping")


def test_xiaohongshu_browser_extract_endpoint_returns_existing_draft_shape(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/browser/extract",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/browser-api-note",
            "final_url": "https://www.xiaohongshu.com/explore/browser-api-note",
            "html": """
              <html>
                <head>
                  <meta property="og:title" content="浏览器 API 采集商品">
                  <meta name="description" content="来自浏览器 worker 的详情页内容。">
                  <meta property="og:image" content="https://cdn.example.com/api-a.jpg">
                </head>
                <body>
                  <div id="detail-desc">来自浏览器 worker 的正文 #浏览器采集</div>
                  <img src="https://cdn.example.com/api-b.jpg">
                </body>
              </html>
            """,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["draft"]["title"] == "浏览器 API 采集商品"
    assert payload["draft"]["description"] == "来自浏览器 worker 的正文 #浏览器采集"
    assert payload["draft"]["attributes"]["source_platform"] == "xiaohongshu"
    assert payload["draft"]["attributes"]["source_method"] == "browser_worker"
    assert payload["draft"]["attributes"]["source_note_id"] == "browser-api-note"
    assert payload["warnings"] == []


def test_xiaohongshu_browser_extract_endpoint_stops_on_captcha(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/browser/extract",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/browser-api-note",
            "final_url": "https://www.xiaohongshu.com/captcha",
            "html": "<html><title>验证码</title><body>请完成验证码后继续访问</body></html>",
        },
    )

    assert response.status_code == 423
    assert response.json()["detail"]["reason"] == "captcha_required"


def test_xiaohongshu_browser_extract_endpoint_rejects_empty_html(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/xiaohongshu/browser/extract",
        json={
            "source_url": "https://www.xiaohongshu.com/explore/browser-api-note",
            "final_url": "https://www.xiaohongshu.com/explore/browser-api-note",
            "html": "",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "browser extract html is required"


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
    monkeypatch.setenv("LISTING_LLM_API_URL", "https://llm.example/v1")
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
    assert calls[0]["url"] == "https://llm.example/v1/chat/completions"
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


def test_local_real_send_bridge_accepts_and_lists_xiaohongshu_jobs(tmp_path) -> None:
    app = create_app(str(tmp_path / "test.db"))
    client = TestClient(app)

    response = client.post(
        "/real-send/xiaohongshu",
        json={
            "channel": "xiaohongshu",
            "action": "publish",
            "payload": {
                "title": "Bridge Accepted Product",
                "description": "Ready for a human-confirmed real-send bridge handoff.",
                "price": 129.0,
            },
        },
    )
    jobs_response = client.get("/real-send-jobs")

    job = response.json()
    jobs = jobs_response.json()

    assert response.status_code == 202
    assert job["channel"] == "xiaohongshu"
    assert job["action"] == "publish"
    assert job["status"] == "awaiting_human_confirm"
    assert job["external_id"].startswith("local-real-send-xiaohongshu-")
    assert jobs_response.status_code == 200
    assert jobs[0]["external_id"] == job["external_id"]
