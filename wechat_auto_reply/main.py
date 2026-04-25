from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from .audit_store import AuditStore
from .config import AutoReplyConfig
from .context_extractor import ContextExtractor
from .decision_engine import DecisionEngine
from .handoff_notifier import HandoffNotifier
from .layout_probe import probe_layout_from_screenshot
from .material_service import MaterialService
from .models import ActionResult, IncomingMessage
from .monitor import MonitorStateStore, build_message_fingerprint
from .ocr_probe import (
    get_default_ocr_command,
    get_default_ocr_languages,
    load_layout_probe_artifact,
    parse_ocr_region_names,
    probe_ocr_from_layout,
    write_ocr_failure,
)
from .orchestrator import Orchestrator
from .platform import create_executor, get_available_executor_names
from .screen_context import build_context_from_ocr_payload
from .state_machine import ConversationStateMachine


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--platform", default=None, help="Executor name override")
    parser.add_argument("--no-dry-run", action="store_true", help="Disable dry-run mode")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WeChat auto-reply shared core CLI")
    add_common_args(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Show executor health")
    add_common_args(doctor)
    doctor.add_argument("--json", action="store_true", help="Output as JSON")

    compare = subparsers.add_parser("compare-executors", help="Compare all executor probes")
    add_common_args(compare)
    compare.add_argument("--json", action="store_true", help="Output as JSON")

    inspect = subparsers.add_parser("inspect-window", help="Inspect the detected WeChat UI tree")
    add_common_args(inspect)
    inspect.add_argument("--max-depth", type=int, default=2)
    inspect.add_argument("--max-nodes", type=int, default=40)
    inspect.add_argument("--backend", choices=("uia", "win32", "all"), default="uia")
    inspect.add_argument("--json", action="store_true", help="Output as JSON")

    layout = subparsers.add_parser("probe-layout", help="Capture WeChat and export heuristic layout regions")
    add_common_args(layout)
    layout.add_argument("--json", action="store_true", help="Output as JSON")

    ocr = subparsers.add_parser("probe-ocr", help="Run OCR on layout probe regions")
    add_common_args(ocr)
    ocr.add_argument("--layout-artifact", default=None, help="Existing layout-probe.json path")
    ocr.add_argument("--regions", default=None, help="Comma-separated region names")
    ocr.add_argument("--languages", default=None, help="OCR languages, defaults to WECHAT_AUTO_REPLY_OCR_LANGUAGES or chi_sim+eng")
    ocr.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    ocr.add_argument("--ocr-command", default=None, help="Override OCR command, defaults to WECHAT_AUTO_REPLY_OCR_COMMAND or tesseract on PATH")
    ocr.add_argument("--json", action="store_true", help="Output as JSON")

    context = subparsers.add_parser("probe-context", help="Extract structured context from WeChat screenshot + OCR")
    add_common_args(context)
    context.add_argument("--layout-artifact", default=None, help="Existing layout-probe.json path")
    context.add_argument("--regions", default=None, help="Comma-separated OCR region names")
    context.add_argument("--languages", default=None, help="OCR languages, defaults to WECHAT_AUTO_REPLY_OCR_LANGUAGES or chi_sim+eng")
    context.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    context.add_argument("--ocr-command", default=None, help="Override OCR command, defaults to WECHAT_AUTO_REPLY_OCR_COMMAND or tesseract on PATH")
    context.add_argument("--contact-fallback", default=None, help="Fallback contact name when header OCR is empty")
    context.add_argument("--json", action="store_true", help="Output as JSON")

    live = subparsers.add_parser("process-live", help="Read the visible WeChat conversation and process it once")
    add_common_args(live)
    live.add_argument("--regions", default=None, help="Comma-separated OCR region names")
    live.add_argument("--languages", default=None, help="OCR languages, defaults to WECHAT_AUTO_REPLY_OCR_LANGUAGES or chi_sim+eng")
    live.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    live.add_argument("--ocr-command", default=None, help="Override OCR command, defaults to WECHAT_AUTO_REPLY_OCR_COMMAND or tesseract on PATH")
    live.add_argument("--contact-fallback", default=None, help="Fallback contact name when header OCR is empty")
    live.add_argument("--state-path", default=None, help="Override monitor state path")
    live.add_argument("--json", action="store_true", help="Output as JSON")

    loop = subparsers.add_parser("run-loop", help="Continuously process the visible WeChat conversation")
    add_common_args(loop)
    loop.add_argument("--regions", default=None, help="Comma-separated OCR region names")
    loop.add_argument("--languages", default=None, help="OCR languages, defaults to WECHAT_AUTO_REPLY_OCR_LANGUAGES or chi_sim+eng")
    loop.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode")
    loop.add_argument("--ocr-command", default=None, help="Override OCR command, defaults to WECHAT_AUTO_REPLY_OCR_COMMAND or tesseract on PATH")
    loop.add_argument("--contact-fallback", default=None, help="Fallback contact name when header OCR is empty")
    loop.add_argument("--state-path", default=None, help="Override monitor state path")
    loop.add_argument("--interval-seconds", type=float, default=3.0, help="Polling interval in seconds")
    loop.add_argument("--max-iterations", type=int, default=0, help="Stop after N iterations; 0 means run forever")
    loop.add_argument("--json", action="store_true", help="Output one JSON line per iteration")

    demo = subparsers.add_parser("process-demo", help="Process one synthetic message")
    add_common_args(demo)
    demo.add_argument("--conversation-id", default="demo-conversation")
    demo.add_argument("--contact", default="Demo Contact")
    demo.add_argument("--message", required=True)
    demo.add_argument("--message-id", default="demo-message-1")
    demo.add_argument("--json", action="store_true", help="Output as JSON")

    return parser


def build_orchestrator(config: AutoReplyConfig, platform_override: str | None) -> Orchestrator:
    executor = create_executor(
        platform_override or config.platform,
        dry_run=config.dry_run,
        runtime_dir=config.runtime_dir,
        listen_chats=config.listen_chats,
    )
    return Orchestrator(
        executor=executor,
        decision_engine=DecisionEngine(
            faq_rules=config.faq_rules,
            redline_keywords=config.redline_keywords,
            manual_only_contacts=config.manual_only_contacts,
        ),
        material_service=MaterialService(config.materials_dir, dict(config.material_map)),
        audit_store=AuditStore(config.runtime_dir, config.screenshots_dir),
        handoff_notifier=HandoffNotifier(
            config.human_contact,
            disabled=config.disable_handoff_notifications,
        ),
        context_extractor=ContextExtractor(),
        state_machine=ConversationStateMachine(),
    )


def build_layout_probe_payload(orchestrator: Orchestrator, dry_run: bool) -> dict[str, object]:
    screenshot_path = orchestrator.audit_store.reserve_screenshot_path("wechat-layout-probe")
    artifact_dir = orchestrator.audit_store.reserve_artifact_dir("layout-probe")

    if dry_run:
        reason = "probe-layout requires --no-dry-run because it needs a real screenshot"
        focus_result = ActionResult(False, reason)
        capture_result = ActionResult(False, reason, screenshot_path=screenshot_path)
    else:
        focus_result = orchestrator.executor.focus_detected_window()
        capture_result = orchestrator.executor.capture_detected_window(screenshot_path)

    layout_payload = probe_layout_from_screenshot(
        screenshot_path=screenshot_path,
        output_dir=artifact_dir,
        metadata={
            "dry_run": dry_run,
            "executor": orchestrator.executor.name,
            "focus_result": asdict(focus_result),
            "capture_result": asdict(capture_result),
        },
    )
    payload = {
        "focus_result": asdict(focus_result),
        "capture_result": asdict(capture_result),
        "layout_probe": layout_payload,
        "artifact_dir": str(artifact_dir),
    }
    orchestrator.audit_store.log_event(
        "layout_probe",
        {
            "artifact_dir": artifact_dir,
            "focus_result": focus_result,
            "capture_result": capture_result,
        },
    )
    return payload


def build_ocr_probe_payload(
    orchestrator: Orchestrator,
    dry_run: bool,
    layout_artifact_path: Path | None,
    region_names: tuple[str, ...],
    languages: str | None,
    psm: int,
    ocr_command: str | None,
) -> dict[str, object]:
    if layout_artifact_path is not None:
        output_dir = layout_artifact_path.parent
        try:
            layout_payload = load_layout_probe_artifact(layout_artifact_path)
        except Exception as exc:
            ocr_payload = write_ocr_failure(
                output_dir,
                f"failed to read layout artifact: {type(exc).__name__}: {exc}",
                metadata={"layout_artifact_path": str(layout_artifact_path)},
            )
            payload = {
                "layout_source": "artifact",
                "layout_artifact_path": str(layout_artifact_path),
                "layout_probe": None,
                "ocr_probe": ocr_payload,
                "artifact_dir": str(output_dir),
            }
            orchestrator.audit_store.log_event(
                "ocr_probe",
                {
                    "layout_source": "artifact",
                    "layout_artifact_path": layout_artifact_path,
                    "ocr_probe": ocr_payload,
                },
            )
            return payload

        ocr_payload = probe_ocr_from_layout(
            layout_payload=layout_payload,
            output_dir=output_dir,
            region_names=region_names,
            languages=languages,
            psm=psm,
            ocr_command=ocr_command,
            metadata={
                "layout_source": "artifact",
                "layout_artifact_path": str(layout_artifact_path),
            },
        )
        payload = {
            "layout_source": "artifact",
            "layout_artifact_path": str(layout_artifact_path),
            "layout_probe": layout_payload,
            "ocr_probe": ocr_payload,
            "artifact_dir": str(output_dir),
        }
        orchestrator.audit_store.log_event(
            "ocr_probe",
            {
                "layout_source": "artifact",
                "layout_artifact_path": layout_artifact_path,
                "ocr_probe": ocr_payload,
            },
        )
        return payload

    layout_bundle = build_layout_probe_payload(orchestrator, dry_run=dry_run)
    artifact_dir = Path(str(layout_bundle["artifact_dir"]))
    ocr_payload = probe_ocr_from_layout(
        layout_payload=layout_bundle["layout_probe"],
        output_dir=artifact_dir,
        region_names=region_names,
        languages=languages,
        psm=psm,
        ocr_command=ocr_command,
        metadata={
            "layout_source": "live_capture",
            "focus_result": layout_bundle["focus_result"],
            "capture_result": layout_bundle["capture_result"],
        },
    )
    payload = {
        "layout_source": "live_capture",
        "layout_probe": layout_bundle["layout_probe"],
        "ocr_probe": ocr_payload,
        "artifact_dir": str(artifact_dir),
    }
    orchestrator.audit_store.log_event(
        "ocr_probe",
        {
            "layout_source": "live_capture",
            "layout_probe": layout_bundle["layout_probe"],
            "ocr_probe": ocr_payload,
        },
    )
    return payload


def build_context_probe_payload(
    orchestrator: Orchestrator,
    dry_run: bool,
    layout_artifact_path: Path | None,
    region_names: tuple[str, ...],
    languages: str | None,
    psm: int,
    ocr_command: str | None,
    fallback_contact_name: str | None,
    include_outgoing_messages: bool = False,
) -> dict[str, object]:
    ocr_bundle = build_ocr_probe_payload(
        orchestrator=orchestrator,
        dry_run=dry_run,
        layout_artifact_path=layout_artifact_path,
        region_names=region_names,
        languages=languages,
        psm=psm,
        ocr_command=ocr_command,
    )
    artifact_dir = Path(str(ocr_bundle["artifact_dir"]))
    context_probe, incoming_message = build_context_from_ocr_payload(
        ocr_payload=ocr_bundle["ocr_probe"],
        output_dir=artifact_dir,
        fallback_contact_name=fallback_contact_name,
        metadata={
            "layout_source": ocr_bundle["layout_source"],
            "layout_artifact_path": str(layout_artifact_path) if layout_artifact_path else None,
            "include_outgoing_messages": include_outgoing_messages,
        },
    )
    decision_preview = None
    if incoming_message is not None:
        decision = orchestrator.decision_engine.classify(incoming_message)
        decision_preview = {
            "kind": decision.kind.value,
            "reason": decision.reason,
            "rule_id": decision.rule_id,
            "material_id": decision.material_id,
            "matched_keywords": list(decision.matched_keywords),
        }

    payload = {
        "layout_source": ocr_bundle["layout_source"],
        "layout_artifact_path": str(layout_artifact_path) if layout_artifact_path else None,
        "layout_probe": ocr_bundle.get("layout_probe"),
        "ocr_probe": ocr_bundle["ocr_probe"],
        "context_probe": context_probe,
        "decision_preview": decision_preview,
        "artifact_dir": str(artifact_dir),
    }
    orchestrator.audit_store.log_event(
        "context_probe",
        {
            "layout_source": ocr_bundle["layout_source"],
            "layout_artifact_path": layout_artifact_path,
            "context_probe": context_probe,
            "decision_preview": decision_preview,
        },
    )
    return payload


def serialize_orchestration_result(result) -> dict[str, object]:
    return {
        "final_state": result.final_state.value,
        "decision": {
            "kind": result.decision.kind.value,
            "reason": result.decision.reason,
            "rule_id": result.decision.rule_id,
            "material_id": result.decision.material_id,
            "matched_keywords": list(result.decision.matched_keywords),
        },
        "send_result": asdict(result.send_result) if result.send_result else None,
        "handoff_result": asdict(result.handoff_result) if result.handoff_result else None,
        "state_history": [state.value for state in result.state_history],
    }


def serialize_incoming_message(message: IncomingMessage) -> dict[str, object]:
    return {
        "message_id": message.message_id,
        "conversation_id": message.conversation_id,
        "contact_name": message.contact_name,
        "text": message.text,
        "received_at": message.received_at.isoformat(),
        "raw_context": list(message.raw_context),
        "metadata": dict(message.metadata),
    }


def build_ignored_echo_texts(config: AutoReplyConfig) -> frozenset[str]:
    return frozenset(rule.reply_text for rule in config.faq_rules if rule.reply_text)


def _blocked_by_allowed_contacts(
    message: IncomingMessage,
    allowed_contacts: frozenset[str] | None,
) -> str | None:
    if not allowed_contacts:
        return None
    allowed = {contact.casefold() for contact in allowed_contacts}
    if message.contact_name.casefold() in allowed or message.conversation_id.casefold() in allowed:
        return None
    return f"contact '{message.contact_name}' is not in allowed contacts"


def _normalize_text_for_compare(text: str) -> str:
    return " ".join(text.casefold().split())


def _is_ignored_echo(message: IncomingMessage, ignored_echo_texts: frozenset[str] | None) -> bool:
    if not ignored_echo_texts:
        return False
    message_text = _normalize_text_for_compare(message.text)
    return any(message_text == _normalize_text_for_compare(text) for text in ignored_echo_texts if text)


def process_live_once(
    orchestrator: Orchestrator,
    dry_run: bool,
    region_names: tuple[str, ...],
    languages: str | None,
    psm: int,
    ocr_command: str | None,
    fallback_contact_name: str | None,
    state_store: MonitorStateStore | None,
    allowed_contacts: frozenset[str] | None = None,
    include_outgoing_messages: bool = False,
    ignored_echo_texts: frozenset[str] | None = None,
) -> dict[str, object]:
    try:
        polled_message = orchestrator.executor.poll_message()
    except Exception as exc:
        return {
            "status": "blocked",
            "message_source": "executor_poll",
            "reason": f"executor polling failed: {type(exc).__name__}: {exc}",
        }

    if polled_message is not None:
        blocked = _blocked_by_allowed_contacts(polled_message, allowed_contacts)
        if blocked:
            return {
                "status": "blocked",
                "message_source": "executor_poll",
                "reason": blocked,
                "incoming_message": serialize_incoming_message(polled_message),
            }
        if _is_ignored_echo(polled_message, ignored_echo_texts):
            if state_store:
                state_store.mark_processed(polled_message)
            return {
                "status": "ignored",
                "message_source": "executor_poll",
                "reason": "latest message matches a known bot echo",
                "incoming_message": serialize_incoming_message(polled_message),
            }

        fingerprint = build_message_fingerprint(polled_message)
        previous_fingerprint = state_store.get_last_fingerprint(polled_message.contact_name) if state_store else None
        if previous_fingerprint == fingerprint:
            return {
                "status": "duplicate",
                "message_source": "executor_poll",
                "reason": "polled message matches the last processed fingerprint",
                "message_fingerprint": fingerprint,
                "incoming_message": serialize_incoming_message(polled_message),
            }

        result = orchestrator.handle_message(polled_message)
        if state_store:
            state_store.mark_processed(polled_message)
        return {
            "status": "processed",
            "message_source": "executor_poll",
            "message_fingerprint": fingerprint,
            "incoming_message": serialize_incoming_message(polled_message),
            "orchestration": serialize_orchestration_result(result),
        }

    if orchestrator.executor.prefers_message_polling():
        return {
            "status": "idle",
            "message_source": "executor_poll",
            "reason": "no new message is available from the polling backend yet",
        }

    context_bundle = build_context_probe_payload(
        orchestrator=orchestrator,
        dry_run=dry_run,
        layout_artifact_path=None,
        region_names=region_names,
        languages=languages,
        psm=psm,
        ocr_command=ocr_command,
        fallback_contact_name=fallback_contact_name,
        include_outgoing_messages=include_outgoing_messages,
    )
    context_probe = context_bundle["context_probe"]
    if not context_probe.get("supported"):
        return {
            "status": "blocked",
            "message_source": "ocr_context",
            "reason": context_probe.get("reason"),
            "context_bundle": context_bundle,
        }

    incoming_payload = context_probe.get("incoming_message")
    if not incoming_payload:
        return {
            "status": "idle",
            "message_source": "ocr_context",
            "reason": "no readable incoming message was found in the visible conversation",
            "context_bundle": context_bundle,
        }

    message = orchestrator.context_extractor.extract(incoming_payload)
    blocked = _blocked_by_allowed_contacts(message, allowed_contacts)
    if blocked:
        return {
            "status": "blocked",
            "message_source": "ocr_context",
            "reason": blocked,
            "context_bundle": context_bundle,
        }
    if _is_ignored_echo(message, ignored_echo_texts):
        if state_store:
            state_store.mark_processed(message)
        return {
            "status": "ignored",
            "message_source": "ocr_context",
            "reason": "latest message matches a known bot echo",
            "context_bundle": context_bundle,
        }

    fingerprint = build_message_fingerprint(message)
    previous_fingerprint = state_store.get_last_fingerprint(message.contact_name) if state_store else None
    if previous_fingerprint == fingerprint:
        return {
            "status": "duplicate",
            "message_source": "ocr_context",
            "reason": "latest visible message matches the last processed fingerprint",
            "message_fingerprint": fingerprint,
            "context_bundle": context_bundle,
        }

    result = orchestrator.handle_message(message)
    if state_store:
        state_store.mark_processed(message)
    return {
        "status": "processed",
        "message_source": "ocr_context",
        "message_fingerprint": fingerprint,
        "context_bundle": context_bundle,
        "orchestration": serialize_orchestration_result(result),
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = AutoReplyConfig.from_env()
    if args.no_dry_run:
        config = AutoReplyConfig(
            platform=config.platform,
            dry_run=False,
            listen_chats=config.listen_chats,
            runtime_dir=config.runtime_dir,
            screenshots_dir=config.screenshots_dir,
            materials_dir=config.materials_dir,
            human_contact=config.human_contact,
            faq_rules=config.faq_rules,
            redline_keywords=config.redline_keywords,
            material_map=config.material_map,
            manual_only_contacts=config.manual_only_contacts,
            allowed_contacts=config.allowed_contacts,
            include_outgoing_messages=config.include_outgoing_messages,
            disable_handoff_notifications=config.disable_handoff_notifications,
        )

    orchestrator = build_orchestrator(config, args.platform)

    if args.command == "doctor":
        health = orchestrator.executor.healthcheck()
        if args.json:
            print(json.dumps(asdict(health), ensure_ascii=False, default=str))
        else:
            print(format_health(health))
        return 0

    if args.command == "compare-executors":
        payload = []
        for executor_name in get_available_executor_names():
            executor = create_executor(
                executor_name,
                dry_run=config.dry_run,
                runtime_dir=config.runtime_dir,
            )
            health = executor.healthcheck()
            if args.json:
                payload.append(asdict(health))
            else:
                print(format_health(health))
                print("")
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        return 0

    if args.command == "inspect-window":
        focus_result = orchestrator.executor.focus_detected_window()
        screenshot_path = orchestrator.audit_store.reserve_screenshot_path("wechat-window-probe")
        capture_result = orchestrator.executor.capture_detected_window(screenshot_path)
        inspection = orchestrator.executor.inspect_ui_tree(
            max_depth=args.max_depth,
            max_nodes=args.max_nodes,
            backend=args.backend,
        )
        payload = {
            "focus_result": asdict(focus_result),
            "capture_result": asdict(capture_result),
            "inspection": inspection,
        }
        artifact_path = orchestrator.audit_store.write_artifact("window-probe", payload)
        payload["artifact_path"] = str(artifact_path)
        orchestrator.audit_store.log_event(
            "window_probe",
            {
                "artifact_path": artifact_path,
                "focus_result": focus_result,
                "capture_result": capture_result,
            },
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "probe-layout":
        payload = build_layout_probe_payload(orchestrator, dry_run=config.dry_run)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "probe-ocr":
        layout_artifact_path = Path(args.layout_artifact) if args.layout_artifact else None
        payload = build_ocr_probe_payload(
            orchestrator=orchestrator,
            dry_run=config.dry_run,
            layout_artifact_path=layout_artifact_path,
            region_names=parse_ocr_region_names(args.regions),
            languages=args.languages or get_default_ocr_languages(),
            psm=args.psm,
            ocr_command=args.ocr_command or get_default_ocr_command(),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "probe-context":
        layout_artifact_path = Path(args.layout_artifact) if args.layout_artifact else None
        payload = build_context_probe_payload(
            orchestrator=orchestrator,
            dry_run=config.dry_run,
            layout_artifact_path=layout_artifact_path,
            region_names=parse_ocr_region_names(args.regions),
            languages=args.languages or get_default_ocr_languages(),
            psm=args.psm,
            ocr_command=args.ocr_command or get_default_ocr_command(),
            fallback_contact_name=args.contact_fallback,
            include_outgoing_messages=config.include_outgoing_messages,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "process-live":
        state_path = Path(args.state_path) if args.state_path else config.runtime_dir / "monitor" / "state.json"
        payload = process_live_once(
            orchestrator=orchestrator,
            dry_run=config.dry_run,
            region_names=parse_ocr_region_names(args.regions),
            languages=args.languages or get_default_ocr_languages(),
            psm=args.psm,
            ocr_command=args.ocr_command or get_default_ocr_command(),
            fallback_contact_name=args.contact_fallback,
            state_store=MonitorStateStore(state_path),
            allowed_contacts=config.allowed_contacts,
            include_outgoing_messages=config.include_outgoing_messages,
            ignored_echo_texts=build_ignored_echo_texts(config),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "run-loop":
        state_path = Path(args.state_path) if args.state_path else config.runtime_dir / "monitor" / "state.json"
        state_store = MonitorStateStore(state_path)
        iteration = 0
        while args.max_iterations <= 0 or iteration < args.max_iterations:
            payload = process_live_once(
                orchestrator=orchestrator,
                dry_run=config.dry_run,
                region_names=parse_ocr_region_names(args.regions),
                languages=args.languages or get_default_ocr_languages(),
                psm=args.psm,
                ocr_command=args.ocr_command or get_default_ocr_command(),
                fallback_contact_name=args.contact_fallback,
                state_store=state_store,
                allowed_contacts=config.allowed_contacts,
                include_outgoing_messages=config.include_outgoing_messages,
                ignored_echo_texts=build_ignored_echo_texts(config),
            )
            payload["iteration"] = iteration + 1
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, default=str))
            else:
                status = payload["status"]
                reason = payload.get("reason", "")
                fingerprint = payload.get("message_fingerprint", "-")
                print(f"[iteration {iteration + 1}] status={status} fingerprint={fingerprint} {reason}".strip())
            iteration += 1
            if args.max_iterations > 0 and iteration >= args.max_iterations:
                break
            time.sleep(max(args.interval_seconds, 0.2))
        return 0

    message = IncomingMessage(
        message_id=args.message_id,
        conversation_id=args.conversation_id,
        contact_name=args.contact,
        text=args.message,
    )
    result = orchestrator.handle_message(message)
    payload = serialize_orchestration_result(result)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def format_health(health) -> str:
    lines = [f"{health.executor_name}: supported={health.supported} | {health.details}"]
    if health.checks:
        lines.append("checks:")
        for check in health.checks:
            status = "ok" if check.ok else "missing"
            lines.append(f"  - {check.name}: {status} | {check.detail}")

    if health.detected_processes:
        lines.append("wechat processes:")
        for process in health.detected_processes:
            title = process.window_title or "-"
            lines.append(f"  - {process.process_name} pid={process.pid} title={title}")

    if health.detected_windows:
        lines.append("wechat windows:")
        for window in health.detected_windows:
            class_name = window.class_name or "-"
            hwnd = window.hwnd if window.hwnd is not None else "-"
            lines.append(f"  - pid={window.pid} hwnd={hwnd} title={window.title} class={class_name}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
