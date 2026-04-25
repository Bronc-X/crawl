# PRD: Windows Desktop WeChat Auto-Reply System

Status: Draft v1
Date: 2026-04-22
Primary User: Operations
Document Goal: Define a production-oriented desktop system for personal WeChat auto-reply without mixing listing or content acquisition scope.

## 1. Problem Statement

The operations team replies to prospects through a personally logged-in WeChat desktop client. Today the workflow depends on manual typing, fragmented personal knowledge, repeated sending of files and materials, and ad hoc handling of technical questions. The slowest parts are:

- closing conversations during the decision stage
- sending the right materials to many contacts repeatedly
- answering specialized questions consistently

This creates three business problems:

- response speed varies a lot by operator and time of day
- reply quality depends on memory, not a stable knowledge system
- high-value conversations are hard to scale without more headcount

## 2. Product Vision

Build a Windows-resident assistant that watches the already logged-in WeChat desktop client, understands incoming messages, retrieves internal knowledge, drafts or sends replies based on risk level, and lets operations take over instantly when needed.

This product is not a protocol bot. It is a desktop operations tool with observability, guardrails, and human override.

## 3. Target User

Primary user:
- operations staff handling inbound WeChat conversations

Secondary users:
- team lead reviewing reply quality
- knowledge owner maintaining answer sources

## 4. Goals

MVP goals:
- detect new incoming WeChat messages on Windows reliably
- classify conversations into low, medium, and high risk
- auto-send safe replies for repetitive cases
- generate draft replies for harder cases using knowledge base + LLM
- support one-click human takeover at any moment
- keep logs, screenshots, and delivery results for review

Business goals:
- reduce first-response time
- increase consistent answer quality
- reduce repeated manual sending of materials
- preserve operator control in sensitive conversations

## 5. Non-Goals

Out of scope for this PRD:
- product listing or inventory workflows
- multi-platform content crawling
- automated captcha solving
- protocol reverse engineering
- packet interception, memory injection, or login-state exfiltration
- group growth automation or bulk unsolicited outreach

## 6. Success Criteria

The product is successful when:

- operations can leave the tool running for a full workday with no manual babysitting
- low-risk repetitive inquiries are answered automatically within target SLA
- medium-risk conversations receive a high-quality draft instead of a blank input box
- high-risk conversations are paused and handed to a human instead of being auto-sent
- every send attempt has a visible result and an audit trail

Suggested MVP metrics:
- new message detection success rate >= 98%
- low-risk auto-reply success rate >= 95%
- average first-response time reduced by 60%
- repeated material-send time reduced by 80%
- manual takeover available within 3 seconds

## 7. Core User Stories

1. As an operator, when a known FAQ arrives, I want the system to send a safe approved answer automatically so I do not have to type it again.
2. As an operator, when a prospect asks a technical question, I want a draft answer with knowledge citations so I can review quickly and send.
3. As an operator, when someone asks about price, refund, legal terms, or makes a complaint, I want the system to stop auto-send and ask me to take over.
4. As an operator, when several prospects ask for the same brochure or case study, I want the system to choose and send the right material automatically.
5. As a team lead, I want logs and screenshots for every automated action so I can review failures and improve rules.

## 8. Product Scope

### MVP Scope

- Windows desktop agent
- WeChat window/process monitoring
- conversation state tracking
- message extraction from visible chat UI
- contact identification
- knowledge base retrieval
- LLM draft generation
- rule engine for auto-send vs draft vs handoff
- material library and template sending
- audit logs and screenshot capture
- operator dashboard for pause/resume and takeover

### V1 Scope

- conversation summaries
- lead tags and intent tags
- knowledge feedback loop from accepted edits
- answer quality scoring
- operator performance reports
- scheduled follow-up reminders

## 9. Functional Requirements

### 9.1 Desktop Monitoring

- Detect whether WeChat desktop client is running and logged in.
- Detect unread messages and active conversation changes.
- Detect exceptional UI states such as popup, file dialog, logout, network error, or blocked send.
- Maintain a heartbeat so the system knows whether monitoring is alive.

### 9.2 Message Understanding

- Extract the latest incoming message from the open conversation.
- Capture recent message context up to configurable window length.
- Identify sender name, chat type, and last outbound response time.
- Tag message intent such as FAQ, material request, technical question, pricing, complaint, or unknown.

### 9.3 Reply Decision Engine

- Apply deterministic rules first.
- If a conversation matches an approved FAQ, send a template response directly.
- If a conversation requires knowledge synthesis, generate a draft with retrieval-augmented context.
- If a conversation hits a red-line tag, require manual confirmation.

### 9.4 Knowledge and LLM

- Support private knowledge base documents, Q&A pairs, scripts, and product materials.
- Retrieve top relevant knowledge chunks before generation.
- Include source snippets in draft view for operator trust.
- Keep prompt versioning and response logs for quality review.

### 9.5 Material Sending

- Support pre-configured text packs, images, PDFs, and file bundles.
- Map intents to material sets.
- Verify file existence and send result before marking complete.

### 9.6 Human Takeover

- Operator can pause all automation globally.
- Operator can mark a conversation as manual-only.
- Operator can approve/edit/reject suggested drafts.
- System must never fight for focus when operator is typing.

### 9.7 Logging and Review

- Log all detections, classifications, generation inputs, send attempts, outcomes, and errors.
- Capture screenshots around failures and important state transitions.
- Provide searchable history by contact, rule, material, and error type.

## 10. Risk Model

### Allowed Automation

- UI-level reading of visible WeChat desktop windows
- UI-level sending through the normal client
- OCR only as a fallback when direct UI signals are not enough
- human-in-the-loop handling for uncertain states

### Disallowed or Deferred

- reverse engineering the WeChat protocol
- reading credentials or secret login tokens from memory/storage
- hidden background sending outside the visible client
- any mechanism designed primarily to bypass platform security controls

### Safety Modes

- Safe mode: drafts only, no auto-send
- Standard mode: only approved FAQ/material replies auto-send
- Guarded mode: full pause when UI state is abnormal

## 11. Product Constraints

- Must run on Windows because the target flow is rooted in desktop WeChat.
- Must tolerate WeChat UI changes better than brittle coordinate-only scripts.
- Must be operable by non-engineers after initial setup.
- Must degrade gracefully if OCR or LLM is unavailable.
- Must preserve local operator control over final sending behavior.

## 12. Recommended Technical Architecture

### 12.1 Components

- Local desktop agent
- WeChat monitor
- UI automation executor
- conversation state machine
- OCR fallback service
- retrieval service
- LLM orchestration service
- rule engine
- material library
- local event log
- optional remote admin/reporting service

### 12.2 Execution Strategy

Primary path:
- window monitoring
- control-tree or image-anchor based UI targeting
- state machine validation
- action execution

Fallback path:
- screenshot capture
- OCR parsing
- heuristic matching
- operator escalation if confidence is low

### 12.3 Recommended Stack

- Desktop automation: Astron RPA first, OpenRPA as backup option
- Local agent: Python
- OCR: PaddleOCR
- Knowledge retrieval API: FastAPI
- Storage: PostgreSQL or SQLite for local-first MVP
- Vector search: pgvector
- Control panel: Tauri desktop app

## 13. Conversation State Machine

Core states:
- idle
- new_message_detected
- context_extracted
- classified_safe
- classified_needs_draft
- classified_handoff
- sending
- send_verified
- send_failed
- operator_takeover
- abnormal_ui_state

Rules:
- any abnormal UI state goes to guarded pause
- repeated failure on one conversation marks it manual-only
- operator activity overrides automation priority

## 14. UX Requirements

- System tray status with clear states: running, paused, error, waiting for review
- simple review queue for draft replies
- per-conversation automation badge: auto, draft, manual
- visible reason code for every blocked send
- searchable material picker for manual takeover cases

## 15. Milestones

### Phase 1: Feasibility

- monitor WeChat window and detect new messages
- read visible message text reliably
- send a text reply through the desktop client
- log screenshots and failures

### Phase 2: MVP

- knowledge retrieval
- LLM draft generation
- FAQ auto-send
- material auto-send
- operator dashboard

### Phase 3: Hardening

- confidence scoring
- better abnormal-state handling
- reporting and replay tools
- rule editor and approval workflows

## 16. Dependencies

- Windows desktop environment
- installed and logged-in WeChat desktop client
- internal knowledge base content
- approved FAQ and material library
- LLM provider and embedding pipeline

## 17. Open Questions

- Will one machine host one operator account only, or should the agent support account switching later?
- What exact conversation types are safe enough for full auto-send on day one?
- How much local-only operation is required versus optional cloud reporting?
- Which material types matter most in MVP: text, image, PDF, or all three?

## 18. Assumptions for Build

- First release is single-operator, single-Windows-machine.
- Auto-send is limited to low-risk inbound service replies.
- Sensitive topics require draft or manual mode.
- Stability is more important than stealth or hidden execution.
