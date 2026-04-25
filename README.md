# Multi-Platform Stable Listing MVP

This repository currently contains the first runnable backend slice for
`prd-multi-platform-stable-listing.md`.

What is implemented:

- product master CRUD
- channel listing overrides
- richer validation engine with bootstrap field and media checks
- channel default settings, so required platform fields can be saved once
- publish task creation
- pluggable adapter registry for Taobao, Xiaohongshu, and Douyin
- adapter modes: `mock`, `manual`, `api`
- quick-create plus auto-publish workflow
- Xiaohongshu source scrape/import endpoint
- real-send adapter mode for posting listing payloads to a configured automation bridge
- local Chinese admin console at `/console`
- SQLite persistence

What is not implemented yet:

- live platform API clients
- in-process browser or desktop automation write adapters
- auth and multi-tenant support

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API will start at `http://127.0.0.1:8000`.
The local console will be available at `http://127.0.0.1:8000/console`.

## Current Product Flow

1. Open `/console`
2. Save channel defaults once for Taobao / Xiaohongshu / Douyin
3. Create a product with title, description, price, and media URLs
4. Click `Create and auto-publish`

The quick-create flow will merge saved channel defaults into product attributes
before triggering publish tasks.

If the same saved attribute key has different values across selected channels,
quick-create will stop with a clear conflict error instead of silently overwriting
one platform's defaults.

## Adapter Modes

Each channel adapter can be configured through environment variables.

Examples:

```powershell
$env:LISTING_TAOBAO_ADAPTER_MODE="manual"
$env:LISTING_XIAOHONGSHU_ADAPTER_MODE="mock"
$env:LISTING_DOUYIN_ADAPTER_MODE="api"
```

Supported modes:

- `mock`: workflow verification only, no real channel write
- `manual`: payload preparation plus operator queue handoff
- `api`: reserved for live API clients, currently returns a clear failure until wired
- `real_send`: sends the validated listing payload to a configured automation bridge

API mode placeholders currently expect these environment variables:

- Taobao: `LISTING_TAOBAO_APP_KEY`, `LISTING_TAOBAO_APP_SECRET`, `LISTING_TAOBAO_SESSION_KEY`
- Xiaohongshu: `LISTING_XIAOHONGSHU_APP_KEY`, `LISTING_XIAOHONGSHU_APP_SECRET`, `LISTING_XIAOHONGSHU_ACCESS_TOKEN`
- Douyin: `LISTING_DOUYIN_APP_ID`, `LISTING_DOUYIN_APP_SECRET`, `LISTING_DOUYIN_ACCESS_TOKEN`

Real-send mode expects a bridge URL per channel:

- Taobao: `LISTING_TAOBAO_REAL_SEND_URL`
- Xiaohongshu: `LISTING_XIAOHONGSHU_REAL_SEND_URL`
- Douyin: `LISTING_DOUYIN_REAL_SEND_URL`

Optional bearer tokens can be supplied through `LISTING_<CHANNEL>_REAL_SEND_TOKEN`.
The bridge owns the platform-specific login, compliance checks, and final submit step.

## Xiaohongshu Import

`POST /xiaohongshu/scrape` extracts a product draft from a specific Xiaohongshu
source URL. It accepts either `html_snapshot` for controlled imports or fetches
the URL directly when no snapshot is provided. When `auto_create_product` is
true, the draft is saved into the same product master used by automatic listing;
when `auto_publish` is also true, normal validation and publish tasks run.

## Test

```powershell
.\.venv\Scripts\pytest
```

## Notes

The current validation rules are bootstrap defaults for internal workflow gating.
They are not official platform compliance matrices. Real channel rules should be
plugged in per adapter as we connect live integrations.
