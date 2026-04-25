# PRD: Multi-Platform Stable Listing System

Status: Draft v1
Date: 2026-04-22
Primary User: Operations
Document Goal: Define a separate product for reliable product listing and publishing across multiple e-commerce/content-commerce platforms without mixing messaging scope.

## 1. Problem Statement

Operations need to publish and maintain products across multiple platforms such as Taobao, Xiaohongshu, and Douyin. Today this is usually fragmented:

- product data lives in spreadsheets, chat threads, and operator memory
- each platform has different fields, media rules, and publishing steps
- operators repeat the same copy-paste work several times
- errors are discovered late, after review rejection or a bad listing goes live

The result is slow time-to-shelf, inconsistent product information, and high manual rework.

## 2. Product Vision

Build a stable listing workbench that lets operations prepare a single source of truth for a product, map it to each platform, publish through the safest available path, and track approval and shelf status in one place.

This product is a listing system, not a CRM, not a messaging tool, and not a content scraping engine.

## 3. Target User

Primary user:
- operations staff responsible for product setup and publishing

Secondary users:
- merchandising lead
- catalog/data owner
- QA/review owner

## 4. Goals

MVP goals:
- maintain one normalized product record
- publish to multiple platforms from a shared workflow
- prefer official APIs where available
- use desktop/web automation only as a controlled fallback
- track publish result, review result, and shelf status
- reduce repeat manual edits

Business goals:
- shorten listing lead time
- improve field consistency across channels
- reduce publish failures and rework
- make handoff between operators easy

## 5. Non-Goals

Out of scope for this PRD:
- private-message automation
- customer service conversations
- content crawling or note discovery
- automated anti-captcha workflows
- order fulfillment and customer support operations
- broad ERP replacement

## 6. Success Criteria

The product is successful when:

- an operator can create one product record and publish it to target channels without rebuilding data each time
- failed listings are explainable with visible reason codes
- channel-specific differences are handled by templates and adapters, not operator memory
- product changes can be re-published safely

Suggested MVP metrics:
- time from product-ready to first publish reduced by 50%
- field mismatch errors reduced by 70%
- successful first-pass publish rate >= 90%
- re-list or edit operation completed in under 5 minutes for standard SKUs

## 7. Core User Stories

1. As an operator, I want to create a product once and publish it to Taobao, Xiaohongshu, and Douyin without retyping core information.
2. As an operator, I want the system to tell me which fields are missing for each platform before publishing.
3. As an operator, I want each channel to use the safest available publish path automatically.
4. As a lead, I want to see which product is draft, pending review, rejected, live, or off-shelf on each channel.
5. As a reviewer, I want media, title, pricing, and attributes checked before publish.

## 8. Product Scope

### MVP Scope

- unified product data model
- media asset library
- per-platform field mapping
- draft validation
- publish queue
- channel adapter layer
- publish result tracking
- approval and rejection status sync
- audit logs

### V1 Scope

- bulk publish
- inventory sync
- price sync
- template-based category presets
- review dashboard
- re-listing and rollback support

## 9. Functional Requirements

### 9.1 Product Master

- Store product title, subtitle, description, media, price, SKU, attributes, shipping info, and compliance metadata.
- Support draft, approved, published, and archived states.
- Keep version history for edits.

### 9.2 Channel Mapping

- Define channel-specific required fields and validation rules.
- Map normalized fields into Taobao, Xiaohongshu, and Douyin payloads or UI actions.
- Allow channel-specific overrides without forking the whole product record.

### 9.3 Validation

- Validate core data completeness before publish.
- Validate media count, aspect ratio, file type, and file size rules per channel.
- Validate category-specific fields and forbidden combinations.
- Show operators exactly what is missing or invalid.

### 9.4 Publishing

- Queue publish tasks per product and per channel.
- Prefer official APIs as first path.
- Use controlled browser/desktop automation only when API capability is missing.
- Support draft save, submit for review, on-shelf, off-shelf, and edit/update.

### 9.5 Result Tracking

- Record publish ID, channel response, status, timestamps, and operator.
- Poll or sync review status when possible.
- Surface rejection reasons and required fixes.

### 9.6 Audit and Reliability

- Store a full operation log for each publish attempt.
- Capture screenshots for fallback UI automation runs.
- Retry recoverable failures with bounded rules.
- Escalate unrecoverable failures to manual review.

## 10. Channel Strategy

### First Principle

Channel writes should use the safest path:

- official API first
- official merchant backend automation second
- brittle coordinate-only RPA last

### Channel Direction

- Taobao: official API and merchant tooling first
- Xiaohongshu: official merchant/open-platform product capabilities first
- Douyin: official open-platform/e-commerce capabilities first

If a platform write path cannot be justified as stable, it should be marked unsupported for automated publish rather than quietly implemented as a fragile script.

## 11. Product Constraints

- One product source of truth must exist before multi-channel publish.
- All channel-specific logic must live in adapters, not scattered inside UI code.
- Operators must be able to rerun a failed publish without rebuilding product data.
- Publish reliability is more important than channel count in MVP.

## 12. Recommended Technical Architecture

### 12.1 Components

- product master service
- media asset service
- validation engine
- channel adapter layer
- publish orchestrator
- task queue
- result tracker
- audit log store
- review dashboard

### 12.2 Publish Paths

Path A:
- official API adapter

Path B:
- merchant backend browser automation

Path C:
- desktop automation fallback for limited edge cases

Each adapter must declare:
- capability coverage
- required credentials
- supported actions
- expected failure modes

### 12.3 Recommended Stack

- Backend: FastAPI or NestJS
- Queue: Redis
- Database: PostgreSQL
- Admin UI: Tauri or local web console
- Automation layer: Astron RPA first, browser automation second

## 13. Data Model

Core entities:
- Product
- SKU
- Asset
- ChannelListing
- PublishTask
- ValidationIssue
- ReviewResult

Key rule:
- Product is canonical
- ChannelListing is a projection for one platform

## 14. Workflow

1. Operator creates or imports product draft
2. System validates shared fields
3. Operator selects target channels
4. System expands channel-specific requirements
5. Missing fields are resolved before publish
6. Publish tasks are queued
7. Adapters execute by safest available path
8. Results are stored and surfaced
9. Review status is synced or refreshed
10. Rejections go back to operator with exact reasons

## 15. UX Requirements

- one product workspace with channel tabs
- clear validation panel before publish
- visible publish queue and retry actions
- channel status chips: draft, queued, publishing, pending review, live, rejected, off-shelf
- diff view between current product version and live channel version

## 16. Milestones

### Phase 1: Foundation

- canonical product schema
- local admin UI
- validation engine
- asset library

### Phase 2: MVP Publish

- Taobao adapter
- Xiaohongshu adapter
- Douyin adapter
- queue and audit logs

### Phase 3: Hardening

- better retries
- bulk operations
- status sync improvements
- inventory and price updates

## 17. Dependencies

- merchant accounts with valid permissions
- channel credentials or approved operator access
- approved media assets
- category mappings and business rules

## 18. Open Questions

- Which channel goes first in actual development order: Taobao, Xiaohongshu, or Douyin?
- Is the first release single-shop or multi-shop?
- Should pricing and inventory be managed here, or only initial listing?
- How much manual approval is required before clicking publish?

## 19. Assumptions for Build

- MVP serves one operations team first, not many tenants.
- Publish coverage is narrower than platform coverage and will be declared explicitly.
- Official write paths are preferred whenever available.
- Listing stability matters more than maximizing the number of automated edge cases.
