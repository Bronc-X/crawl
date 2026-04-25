from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from wechat_auto_reply.main import (
    build_context_probe_payload,
    build_layout_probe_payload,
    build_ocr_probe_payload,
    format_health,
    process_live_once,
)
from wechat_auto_reply.audit_store import AuditStore
from wechat_auto_reply.context_extractor import ContextExtractor
from wechat_auto_reply.decision_engine import DecisionEngine
from wechat_auto_reply.handoff_notifier import HandoffNotifier
from wechat_auto_reply.layout_probe import build_wechat_layout_regions, probe_layout_from_screenshot
from wechat_auto_reply.material_service import MaterialNotFoundError, MaterialService
from wechat_auto_reply.monitor import MonitorStateStore
from wechat_auto_reply.models import (
    ActionResult,
    ConversationState,
    DecisionKind,
    DetectedProcess,
    DetectedWindow,
    ExecutorCheck,
    FAQRule,
    IncomingMessage,
)
from wechat_auto_reply.orchestrator import Orchestrator
from wechat_auto_reply.ocr_probe import parse_ocr_region_names, probe_ocr_from_layout
from wechat_auto_reply.platform.base import PlatformExecutor
from wechat_auto_reply.platform.base import get_available_executor_names
from wechat_auto_reply.platform import windows_common
from wechat_auto_reply.platform.windows_astron import WindowsAstronExecutor
from wechat_auto_reply.platform.windows_pywinauto import WindowsPywinautoExecutor
from wechat_auto_reply.platform.windows_wxauto import WindowsWxautoExecutor
from wechat_auto_reply.screen_context import build_context_from_ocr_payload
from wechat_auto_reply.state_machine import ConversationStateMachine, InvalidTransitionError


class FakeExecutor(PlatformExecutor):
    def __init__(self, fail_send: bool = False, fail_handoff: bool = False) -> None:
        super().__init__(dry_run=True)
        self.fail_send = fail_send
        self.fail_handoff = fail_handoff
        self.sent_text: list[tuple[str, str]] = []
        self.sent_materials: list[tuple[str, Path, str | None]] = []
        self.handoffs: list[tuple[str, str]] = []
        self.focus_calls = 0
        self.capture_calls = 0
        self.polled_message: IncomingMessage | None = None

    @property
    def name(self) -> str:
        return "fake"

    def healthcheck(self):
        raise NotImplementedError

    def poll_message(self) -> IncomingMessage | None:
        return self.polled_message

    def send_text(self, conversation_id: str, text: str) -> ActionResult:
        self.sent_text.append((conversation_id, text))
        return ActionResult(not self.fail_send, "send_text")

    def send_material(self, conversation_id: str, material_path: Path, caption: str | None = None) -> ActionResult:
        self.sent_materials.append((conversation_id, material_path, caption))
        return ActionResult(not self.fail_send, "send_material")

    def send_handoff_notification(self, human_contact: str, text: str) -> ActionResult:
        self.handoffs.append((human_contact, text))
        return ActionResult(not self.fail_handoff, "handoff")

    def focus_detected_window(self) -> ActionResult:
        self.focus_calls += 1
        return ActionResult(True, "focused")

    def capture_detected_window(self, output_path: Path) -> ActionResult:
        self.capture_calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("fake", encoding="utf-8")
        return ActionResult(True, "captured", screenshot_path=output_path)


def build_engine() -> DecisionEngine:
    return DecisionEngine(
        faq_rules=(
            FAQRule(
                rule_id="faq-text",
                name="Text Reply",
                keywords=("你好",),
                reply_text="收到，我来处理。",
            ),
            FAQRule(
                rule_id="faq-material",
                name="Material Reply",
                keywords=("资料",),
                reply_text="给您发资料。",
                material_id="brochure",
            ),
        ),
        redline_keywords=("价格", "退款"),
        manual_only_contacts=frozenset({"manual-contact"}),
    )


def build_orchestrator(tmp_path: Path, executor: FakeExecutor) -> Orchestrator:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    brochure = materials_dir / "brochure.pdf"
    brochure.write_text("placeholder", encoding="utf-8")

    return Orchestrator(
        executor=executor,
        decision_engine=build_engine(),
        material_service=MaterialService(materials_dir, {"brochure": "brochure.pdf"}),
        audit_store=AuditStore(tmp_path / "runtime", tmp_path / "runtime" / "screenshots"),
        handoff_notifier=HandoffNotifier("ops-owner"),
        context_extractor=ContextExtractor(),
        state_machine=ConversationStateMachine(),
    )


def test_state_machine_rejects_invalid_transition():
    machine = ConversationStateMachine()

    with pytest.raises(InvalidTransitionError):
        machine.transition(ConversationState.SENDING)


def test_decision_engine_returns_safe_material():
    engine = build_engine()
    message = IncomingMessage(
        message_id="1",
        conversation_id="c1",
        contact_name="张三",
        text="发我一份资料",
    )

    decision = engine.classify(message)

    assert decision.kind is DecisionKind.SAFE_MATERIAL
    assert decision.material_id == "brochure"


def test_decision_engine_returns_handoff_for_redline():
    engine = build_engine()
    message = IncomingMessage(
        message_id="1",
        conversation_id="c1",
        contact_name="张三",
        text="价格是多少",
    )

    decision = engine.classify(message)

    assert decision.kind is DecisionKind.HANDOFF
    assert "redline" in decision.reason


def test_material_service_raises_for_missing_file(tmp_path: Path):
    service = MaterialService(tmp_path, {"brochure": "missing.pdf"})

    with pytest.raises(MaterialNotFoundError):
        service.resolve("brochure")


def test_handoff_notifier_formats_message():
    executor = FakeExecutor()
    notifier = HandoffNotifier("ops-owner")
    message = IncomingMessage(
        message_id="1",
        conversation_id="c1",
        contact_name="张三",
        text="我要退款",
    )
    decision = build_engine().classify(message)

    result = notifier.notify(executor, message, decision)

    assert result.success is True
    assert executor.handoffs[0][0] == "ops-owner"
    assert "张三" in executor.handoffs[0][1]


def test_orchestrator_sends_safe_reply(tmp_path: Path):
    executor = FakeExecutor()
    orchestrator = build_orchestrator(tmp_path, executor)

    result = orchestrator.handle_message(
        IncomingMessage(
            message_id="1",
            conversation_id="c1",
            contact_name="张三",
            text="你好",
        )
    )

    assert result.decision.kind is DecisionKind.SAFE_REPLY
    assert result.send_result is not None
    assert result.send_result.success is True
    assert result.handoff_result is None
    assert executor.sent_text == [("c1", "收到，我来处理。")]
    assert result.final_state is ConversationState.IDLE


def test_orchestrator_escalates_after_send_failure(tmp_path: Path):
    executor = FakeExecutor(fail_send=True)
    orchestrator = build_orchestrator(tmp_path, executor)

    result = orchestrator.handle_message(
        IncomingMessage(
            message_id="1",
            conversation_id="c1",
            contact_name="张三",
            text="发我一份资料",
        )
    )

    assert result.decision.kind is DecisionKind.SAFE_MATERIAL
    assert result.send_result is not None
    assert result.send_result.success is False
    assert result.handoff_result is not None
    assert result.handoff_result.success is True
    assert executor.sent_materials[0][0] == "c1"
    assert executor.handoffs[0][0] == "ops-owner"


def test_audit_store_writes_probe_artifact(tmp_path: Path):
    store = AuditStore(tmp_path / "runtime", tmp_path / "runtime" / "screenshots")

    artifact_path = store.write_artifact("window-probe", {"status": "ok"})

    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8").strip().startswith("{")


def test_audit_store_reserves_artifact_dir(tmp_path: Path):
    store = AuditStore(tmp_path / "runtime", tmp_path / "runtime" / "screenshots")

    artifact_dir = store.reserve_artifact_dir("layout-probe")

    assert artifact_dir.exists()
    assert artifact_dir.is_dir()
    assert artifact_dir.name.startswith("layout-probe-")


def test_layout_probe_builds_expected_regions():
    regions = build_wechat_layout_regions(1000, 800)
    region_map = {region.name: region for region in regions}

    assert region_map["conversation_list"].left == 80
    assert region_map["conversation_list"].right == 330
    assert region_map["composer_input"].top == 672
    assert region_map["send_button_candidate"].left >= 840
    assert region_map["send_button_candidate"].bottom <= 800
    assert region_map["latest_message_band"].left == 360
    assert region_map["latest_message_band"].top == 400


def test_layout_probe_exports_overlay_and_crops(tmp_path: Path):
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on test env dependency
        pytest.skip(f"Pillow unavailable: {exc}")

    screenshot_path = tmp_path / "probe.bmp"
    image = Image.new("RGB", (1000, 800), color=(240, 240, 240))
    for y in range(300, 365):
        for x in range(90, 320):
            image.putpixel((x, y), (7, 193, 96))
    image.save(screenshot_path)

    output_dir = tmp_path / "artifacts"
    payload = probe_layout_from_screenshot(
        screenshot_path=screenshot_path,
        output_dir=output_dir,
        metadata={"source": "test"},
    )

    assert payload["supported"] is True
    assert (output_dir / "layout-overlay.png").exists()
    assert (output_dir / "conversation_list.png").exists()
    assert (output_dir / "selected_conversation.png").exists()
    assert (output_dir / "layout-probe.json").exists()
    assert payload["metadata"]["source"] == "test"


def test_build_layout_probe_payload_blocks_dry_run(tmp_path: Path):
    executor = FakeExecutor()
    orchestrator = build_orchestrator(tmp_path, executor)

    payload = build_layout_probe_payload(orchestrator, dry_run=True)

    assert payload["focus_result"]["success"] is False
    assert "--no-dry-run" in payload["focus_result"]["message"]
    assert payload["layout_probe"]["supported"] is False
    assert executor.focus_calls == 0
    assert executor.capture_calls == 0


def test_parse_ocr_region_names_uses_defaults():
    assert parse_ocr_region_names(None) == (
        "conversation_list",
        "selected_conversation",
        "chat_header",
        "message_pane",
        "latest_message_band",
        "composer_input",
        "send_button_candidate",
    )
    assert parse_ocr_region_names("latest_message_band, composer_input") == (
        "latest_message_band",
        "composer_input",
    )


def test_probe_ocr_from_layout_reports_missing_runtime(tmp_path: Path):
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on test env dependency
        pytest.skip(f"Pillow unavailable: {exc}")

    crop_path = tmp_path / "latest_message_band.png"
    Image.new("RGB", (200, 80), color=(255, 255, 255)).save(crop_path)
    layout_payload = {
        "supported": True,
        "regions": [
            {
                "name": "latest_message_band",
                "crop_path": str(crop_path),
            }
        ],
    }

    payload = probe_ocr_from_layout(
        layout_payload=layout_payload,
        output_dir=tmp_path / "artifacts",
        region_names=("latest_message_band",),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="definitely-missing-tesseract",
        preferred_backends=("tesseract",),
    )

    assert payload["supported"] is False
    assert "not found" in payload["reason"]
    assert (tmp_path / "artifacts" / "ocr-probe.json").exists()


def test_probe_ocr_from_layout_parses_tsv(monkeypatch, tmp_path: Path):
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on test env dependency
        pytest.skip(f"Pillow unavailable: {exc}")

    crop_path = tmp_path / "latest_message_band.png"
    Image.new("RGB", (240, 80), color=(255, 255, 255)).save(crop_path)
    layout_payload = {
        "supported": True,
        "regions": [
            {
                "name": "latest_message_band",
                "crop_path": str(crop_path),
            }
        ],
    }
    tsv_output = "\n".join(
        (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
            "5\t1\t1\t1\t1\t1\t10\t10\t40\t20\t95\t你好",
            "5\t1\t1\t1\t1\t2\t55\t10\t50\t20\t88\t请报价",
        )
    )

    monkeypatch.setattr(
        "wechat_auto_reply.ocr_probe._resolve_tesseract_command",
        lambda _command: ("mock-tesseract", "mocked OCR command"),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.ocr_probe._run_tesseract_tsv",
        lambda *_args, **_kwargs: (True, tsv_output),
    )

    payload = probe_ocr_from_layout(
        layout_payload=layout_payload,
        output_dir=tmp_path / "artifacts",
        region_names=("latest_message_band",),
        languages="chi_sim+eng",
        psm=6,
        preferred_backends=("tesseract",),
    )

    assert payload["supported"] is True
    assert payload["regions"][0]["success"] is True
    assert "你好" in payload["regions"][0]["text"]
    assert payload["regions"][0]["line_count"] == 1
    assert payload["regions"][0]["word_count"] == 2
    assert payload["regions"][0]["mean_confidence"] == 91.5
    assert (tmp_path / "artifacts" / "latest_message_band-ocr.tsv").exists()


def test_probe_ocr_from_layout_resolves_crop_from_artifact_dir(monkeypatch, tmp_path: Path):
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on test env dependency
        pytest.skip(f"Pillow unavailable: {exc}")

    artifact_dir = tmp_path / "layout-probe-1"
    artifact_dir.mkdir()
    crop_path = artifact_dir / "latest_message_band.png"
    Image.new("RGB", (240, 80), color=(255, 255, 255)).save(crop_path)
    layout_payload = {
        "supported": True,
        "regions": [
            {
                "name": "latest_message_band",
                "crop_path": r"data\wechat_auto_reply\runtime\artifacts\layout-probe-1\latest_message_band.png",
            }
        ],
    }

    monkeypatch.setattr(
        "wechat_auto_reply.ocr_probe._resolve_tesseract_command",
        lambda _command: ("mock-tesseract", "mocked OCR command"),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.ocr_probe._run_tesseract_tsv",
        lambda *_args, **_kwargs: (
            True,
            "\n".join(
                (
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
                    "5\t1\t1\t1\t1\t1\t10\t10\t40\t20\t90\thello",
                )
            ),
        ),
    )

    payload = probe_ocr_from_layout(
        layout_payload=layout_payload,
        output_dir=artifact_dir,
        region_names=("latest_message_band",),
        languages="eng",
        psm=6,
        preferred_backends=("tesseract",),
    )

    assert payload["regions"][0]["success"] is True
    assert payload["regions"][0]["crop_path"] == str(crop_path)


def test_build_ocr_probe_payload_can_reuse_existing_layout_artifact(monkeypatch, tmp_path: Path):
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - depends on test env dependency
        pytest.skip(f"Pillow unavailable: {exc}")

    executor = FakeExecutor()
    orchestrator = build_orchestrator(tmp_path, executor)
    crop_path = tmp_path / "composer_input.png"
    Image.new("RGB", (300, 120), color=(255, 255, 255)).save(crop_path)
    layout_artifact_path = tmp_path / "layout-probe.json"
    layout_artifact_path.write_text(
        '{"supported": true, "regions": [{"name": "composer_input", "crop_path": "%s"}]}'
        % str(crop_path).replace("\\", "\\\\"),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "wechat_auto_reply.main.probe_ocr_from_layout",
        lambda **kwargs: {
            "supported": True,
            "metadata": kwargs["metadata"],
            "requested_regions": list(kwargs["region_names"]),
        },
    )

    payload = build_ocr_probe_payload(
        orchestrator=orchestrator,
        dry_run=True,
        layout_artifact_path=layout_artifact_path,
        region_names=("composer_input",),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="mock-tesseract",
    )

    assert payload["layout_source"] == "artifact"
    assert payload["ocr_probe"]["supported"] is True
    assert payload["ocr_probe"]["requested_regions"] == ["composer_input"]
    assert executor.focus_calls == 0
    assert executor.capture_calls == 0


def test_build_context_from_ocr_payload_extracts_message_and_composer(tmp_path: Path):
    payload, incoming_message = build_context_from_ocr_payload(
        ocr_payload={
            "supported": True,
            "regions": [
                {
                    "name": "selected_conversation",
                    "success": True,
                    "text": "张三\n",
                    "mean_confidence": 94.6,
                    "line_count": 1,
                },
                {
                    "name": "chat_header",
                    "success": True,
                    "text": "",
                    "mean_confidence": None,
                    "line_count": 0,
                },
                {
                    "name": "message_pane",
                    "success": True,
                    "text": "12:30\n我发的上一条\n你好，请发我报价单",
                    "mean_confidence": 91.2,
                    "line_count": 3,
                    "line_items": [
                        {
                            "text": "我发的上一条",
                            "left": 360,
                            "top": 120,
                            "right": 480,
                            "bottom": 145,
                            "confidence": 88.0,
                        },
                        {
                            "text": "你好，请发我报价单",
                            "left": 88,
                            "top": 210,
                            "right": 260,
                            "bottom": 240,
                            "confidence": 93.5,
                        },
                    ],
                },
                {
                    "name": "latest_message_band",
                    "success": True,
                    "text": "",
                    "mean_confidence": None,
                    "line_count": 0,
                },
                {
                    "name": "composer_input",
                    "success": True,
                    "text": "发消息\n我先整理一下",
                    "mean_confidence": 88.3,
                    "line_count": 2,
                },
            ],
        },
        output_dir=tmp_path / "artifacts",
    )

    assert payload["supported"] is True
    assert payload["contact_name"] == "张三"
    assert payload["latest_message_text"] == "你好，请发我报价单"
    assert payload["composer_text"] == "我先整理一下"
    assert incoming_message is not None
    assert incoming_message.contact_name == "张三"
    assert incoming_message.text == "你好，请发我报价单"
    assert incoming_message.raw_context == ("我先整理一下",)
    assert (tmp_path / "artifacts" / "context-probe.json").exists()


def test_build_context_from_ocr_payload_ignores_right_side_by_default(tmp_path: Path):
    payload, incoming_message = build_context_from_ocr_payload(
        ocr_payload={
            "supported": True,
            "regions": [
                {
                    "name": "chat_header",
                    "success": True,
                    "text": "文件传输助手",
                    "mean_confidence": 95.0,
                    "line_count": 1,
                },
                {
                    "name": "message_pane",
                    "success": True,
                    "text": "old incoming\n15:41\n你好",
                    "mean_confidence": 90.0,
                    "line_count": 3,
                    "line_items": [
                        {
                            "text": "old incoming",
                            "left": 80,
                            "top": 120,
                            "right": 190,
                            "bottom": 145,
                            "confidence": 90.0,
                        },
                        {
                            "text": "15:41",
                            "left": 260,
                            "top": 190,
                            "right": 310,
                            "bottom": 210,
                            "confidence": 90.0,
                        },
                        {
                            "text": "你好",
                            "left": 360,
                            "top": 240,
                            "right": 520,
                            "bottom": 270,
                            "confidence": 93.0,
                        },
                    ],
                },
            ],
        },
        output_dir=tmp_path / "artifacts",
    )

    assert payload["latest_message_text"] == "old incoming"
    assert incoming_message is not None
    assert incoming_message.text == "old incoming"


def test_build_context_from_ocr_payload_can_include_outgoing_for_loopback(tmp_path: Path):
    payload, incoming_message = build_context_from_ocr_payload(
        ocr_payload={
            "supported": True,
            "regions": [
                {
                    "name": "chat_header",
                    "success": True,
                    "text": "文件传输助手",
                    "mean_confidence": 95.0,
                    "line_count": 1,
                },
                {
                    "name": "message_pane",
                    "success": True,
                    "text": "星期天02:53\nold incoming\n你好",
                    "mean_confidence": 90.0,
                    "line_count": 3,
                    "line_items": [
                        {
                            "text": "星期天02:53",
                            "left": 240,
                            "top": 80,
                            "right": 310,
                            "bottom": 100,
                            "confidence": 90.0,
                        },
                        {
                            "text": "old incoming",
                            "left": 80,
                            "top": 120,
                            "right": 190,
                            "bottom": 145,
                            "confidence": 90.0,
                        },
                        {
                            "text": "你好",
                            "left": 360,
                            "top": 240,
                            "right": 520,
                            "bottom": 270,
                            "confidence": 93.0,
                        },
                    ],
                },
            ],
        },
        output_dir=tmp_path / "artifacts",
        metadata={"include_outgoing_messages": True},
    )

    assert payload["latest_message_text"] == "你好"
    assert incoming_message is not None
    assert incoming_message.text == "你好"


def test_build_context_from_ocr_payload_reports_ocr_failure(tmp_path: Path):
    payload, incoming_message = build_context_from_ocr_payload(
        ocr_payload={
            "supported": False,
            "reason": "tesseract is not installed or not on PATH",
        },
        output_dir=tmp_path / "artifacts",
    )

    assert payload["supported"] is False
    assert "tesseract" in payload["reason"]
    assert incoming_message is None


def test_build_context_probe_payload_adds_decision_preview(monkeypatch, tmp_path: Path):
    executor = FakeExecutor()
    orchestrator = build_orchestrator(tmp_path, executor)

    monkeypatch.setattr(
        "wechat_auto_reply.main.build_ocr_probe_payload",
        lambda **_kwargs: {
            "layout_source": "artifact",
            "layout_probe": {"supported": True},
            "ocr_probe": {
                "supported": True,
                "regions": [
                    {
                        "name": "selected_conversation",
                        "success": True,
                        "text": "张三",
                        "mean_confidence": 95.0,
                        "line_count": 1,
                    },
                    {
                        "name": "message_pane",
                        "success": True,
                        "text": "请发我资料",
                        "mean_confidence": 93.0,
                        "line_count": 1,
                        "line_items": [
                            {
                                "text": "请发我资料",
                                "left": 88,
                                "top": 220,
                                "right": 200,
                                "bottom": 248,
                                "confidence": 93.0,
                            }
                        ],
                    },
                    {
                        "name": "composer_input",
                        "success": True,
                        "text": "",
                        "mean_confidence": None,
                        "line_count": 0,
                    },
                ],
            },
            "artifact_dir": str(tmp_path / "artifacts"),
        },
    )

    payload = build_context_probe_payload(
        orchestrator=orchestrator,
        dry_run=True,
        layout_artifact_path=tmp_path / "layout-probe.json",
        region_names=("selected_conversation", "message_pane", "composer_input"),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="mock-tesseract",
        fallback_contact_name=None,
    )

    assert payload["context_probe"]["supported"] is True
    assert payload["context_probe"]["latest_message_text"] == "请发我资料"
    assert payload["decision_preview"]["kind"] == DecisionKind.SAFE_MATERIAL.value


def test_build_context_from_ocr_payload_filters_attachment_noise(tmp_path: Path):
    payload, incoming_message = build_context_from_ocr_payload(
        ocr_payload={
            "supported": True,
            "regions": [
                {
                    "name": "chat_header",
                    "success": True,
                    "text": "客户A",
                    "mean_confidence": 95.0,
                    "line_count": 1,
                },
                {
                    "name": "message_pane",
                    "success": True,
                    "text": "报价单.zip\n2.7M\n微信电脑版\n嗯好的",
                    "mean_confidence": 90.0,
                    "line_count": 4,
                    "line_items": [
                        {
                            "text": "报价单.zip",
                            "left": 80,
                            "top": 100,
                            "right": 180,
                            "bottom": 122,
                            "confidence": 90.0,
                        },
                        {
                            "text": "2.7M",
                            "left": 82,
                            "top": 126,
                            "right": 120,
                            "bottom": 144,
                            "confidence": 90.0,
                        },
                        {
                            "text": "微信电脑版",
                            "left": 80,
                            "top": 150,
                            "right": 160,
                            "bottom": 170,
                            "confidence": 90.0,
                        },
                        {
                            "text": "嗯好的",
                            "left": 78,
                            "top": 210,
                            "right": 130,
                            "bottom": 232,
                            "confidence": 92.0,
                        },
                    ],
                },
                {
                    "name": "composer_input",
                    "success": True,
                    "text": "发送",
                    "mean_confidence": 80.0,
                    "line_count": 1,
                },
            ],
        },
        output_dir=tmp_path / "artifacts",
    )

    assert payload["latest_message_text"] == "嗯好的"
    assert incoming_message is not None
    assert incoming_message.text == "嗯好的"


def test_windows_pywinauto_healthcheck_reports_dependency_gap(monkeypatch):
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.sys.platform", "win32")
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.has_python_module", lambda _name: False)
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.probe_pywinauto_runtime",
        lambda: (False, "pywinauto is not installed"),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.list_wechat_processes",
        lambda: (
            DetectedProcess(process_name="Weixin", pid=1001, window_title="微信"),
        ),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.list_wechat_windows",
        lambda: (
            DetectedWindow(title="微信", pid=1001, class_name="WeixinWnd"),
        ),
    )

    health = WindowsPywinautoExecutor().healthcheck()

    assert health.supported is False
    assert "not installed" in health.details
    assert any(check.name == "wechat_process_running" and check.ok for check in health.checks)
    assert health.detected_windows[0].title == "微信"


def test_windows_pywinauto_healthcheck_reports_runtime_error(monkeypatch):
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.sys.platform", "win32")
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.has_python_module", lambda _name: True)
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.probe_pywinauto_runtime",
        lambda: (False, "SyntaxError: generated comtypes module is invalid"),
    )
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.list_wechat_processes", lambda: ())
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.list_wechat_windows", lambda: ())

    health = WindowsPywinautoExecutor().healthcheck()

    assert health.supported is False
    assert "runtime-ready" in health.details
    assert any(check.name == "pywinauto_runtime_ready" and not check.ok for check in health.checks)


def test_windows_pywinauto_focus_and_capture(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.sys.platform", "win32")
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.has_python_module", lambda _name: True)
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.probe_pywinauto_runtime",
        lambda: (True, "ok"),
    )
    monkeypatch.setattr("wechat_auto_reply.platform.windows_pywinauto.list_wechat_processes", lambda: ())
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.list_wechat_windows",
        lambda: (
            DetectedWindow(title="微信", pid=1001, class_name="WeixinWnd", hwnd=9527),
        ),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.focus_window",
        lambda hwnd: (hwnd == 9527, "focused"),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_pywinauto.capture_window",
        lambda hwnd, path: (hwnd == 9527, f"captured to {path}"),
    )

    executor = WindowsPywinautoExecutor(dry_run=False)
    focus_result = executor.focus_detected_window()
    capture_result = executor.capture_detected_window(tmp_path / "probe.bmp")

    assert focus_result.success is True
    assert capture_result.success is True
    assert capture_result.screenshot_path == tmp_path / "probe.bmp"


def test_windows_wxauto_healthcheck_reports_python_gap(monkeypatch):
    monkeypatch.setattr("wechat_auto_reply.platform.windows_wxauto.is_windows_host", lambda: True)
    monkeypatch.setattr("wechat_auto_reply.platform.windows_wxauto.sys.version_info", SimpleNamespace(major=3, minor=14))
    monkeypatch.setattr("wechat_auto_reply.platform.windows_wxauto.list_wechat_processes", lambda: ())
    monkeypatch.setattr("wechat_auto_reply.platform.windows_wxauto.list_wechat_windows", lambda: ())

    health = WindowsWxautoExecutor().healthcheck()

    assert health.supported is False
    assert "Python 3.14" in health.details
    assert any(check.name == "python_version_supported" and not check.ok for check in health.checks)


def test_executor_probe_order_uses_own_windows_backend_by_default():
    names = get_available_executor_names()

    assert "windows-pywinauto" in names
    assert "windows-wxauto" not in names


def test_windows_wxauto_poll_message_builds_incoming_message(monkeypatch):
    class FakeWx:
        def __init__(self):
            self.listen_calls = []
            self.start_calls = 0

        def AddListenChat(self, name, callback):
            self.listen_calls.append((name, callback))

        def StartListening(self):
            self.start_calls += 1

    fake_wx = FakeWx()
    fake_chat = SimpleNamespace(
        ChatInfo=lambda: {"chat_name": "文件传输助手"},
        who="ignored",
    )
    fake_msg = SimpleNamespace(id="msg-1", sender="Alice", content="你好", type="friend")

    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_wxauto.load_wxauto_client_class",
        lambda: (lambda: fake_wx, "wxauto4", "wxauto4"),
    )

    executor = WindowsWxautoExecutor(dry_run=False, listen_chats=("文件传输助手",))
    executor._on_message(fake_msg, fake_chat)

    message = executor.poll_message()

    assert message is not None
    assert message.message_id == "msg-1"
    assert message.conversation_id == "文件传输助手"
    assert message.contact_name == "文件传输助手"
    assert message.text == "你好"
    assert message.metadata["sender"] == "Alice"
    assert fake_wx.listen_calls[0][0] == "文件传输助手"
    assert fake_wx.start_calls == 1


def test_windows_wxauto_poll_message_uses_get_next_new_message_without_listen_targets(monkeypatch):
    class FakeWx:
        def __init__(self):
            self.calls = []

        def GetNextNewMessage(self, filter_mute=False):
            self.calls.append(("GetNextNewMessage", filter_mute))
            return {
                "chat_name": "瀹㈡埛A",
                "chat_type": "friend",
                "msg": [
                    SimpleNamespace(id="time-1", sender="", content="", type="time"),
                    SimpleNamespace(id="msg-2", sender="Alice", content="浣犲ソ", type="friend"),
                ],
            }

    fake_wx = FakeWx()
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_wxauto.load_wxauto_client_class",
        lambda: (lambda: fake_wx, "wxauto4", "wxauto4"),
    )

    executor = WindowsWxautoExecutor(dry_run=False)
    message = executor.poll_message()

    assert message is not None
    assert message.message_id == "msg-2"
    assert message.conversation_id == "瀹㈡埛A"
    assert message.contact_name == "瀹㈡埛A"
    assert message.text == "浣犲ソ"
    assert message.metadata["sender"] == "Alice"
    assert message.metadata["chat_type"] == "friend"
    assert fake_wx.calls == [("GetNextNewMessage", True)]


def test_windows_wxauto_send_text_uses_wx_response_success(monkeypatch):
    class FakeWx:
        def __init__(self):
            self.calls = []

        def SendMsg(self, msg, who=None, clear=True, exact=False):
            self.calls.append(("SendMsg", msg, who, clear, exact))
            return SimpleNamespace(success=False, message="blocked by WeChat")

    fake_wx = FakeWx()
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_wxauto.load_wxauto_client_class",
        lambda: (lambda: fake_wx, "wxauto4", "wxauto4"),
    )

    executor = WindowsWxautoExecutor(dry_run=False)
    result = executor.send_text("瀹㈡埛A", "浣犲ソ")

    assert result.success is False
    assert "blocked by WeChat" in result.message
    assert fake_wx.calls == [("SendMsg", "浣犲ソ", "瀹㈡埛A", True, False)]


def test_windows_wxauto_poll_message_skips_self_and_system_messages(monkeypatch):
    class FakeWx:
        def GetNextNewMessage(self, filter_mute=False):
            return {
                "chat_name": "customer-a",
                "msg": [
                    SimpleNamespace(
                        id="friend-1",
                        attr="friend",
                        type="text",
                        sender="Alice",
                        content="please send material",
                    ),
                    SimpleNamespace(
                        id="self-1",
                        attr="self",
                        type="text",
                        sender="Me",
                        content="sent",
                    ),
                    SimpleNamespace(
                        id="system-1",
                        attr="system",
                        type="time",
                        sender="",
                        content="12:30",
                    ),
                ],
            }

    fake_wx = FakeWx()
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_wxauto.load_wxauto_client_class",
        lambda: (lambda: fake_wx, "wxauto4", "wxauto4"),
    )

    executor = WindowsWxautoExecutor(dry_run=False)
    message = executor.poll_message()

    assert message is not None
    assert message.message_id == "friend-1"
    assert message.metadata["sender"] == "Alice"


def test_process_live_once_prefers_executor_poll_message(tmp_path: Path, monkeypatch):
    executor = FakeExecutor()
    executor.polled_message = IncomingMessage(
        message_id="polled-1",
        conversation_id="文件传输助手",
        contact_name="文件传输助手",
        text="你好",
        metadata={"sender": "Alice"},
    )
    orchestrator = build_orchestrator(tmp_path, executor)

    monkeypatch.setattr(
        "wechat_auto_reply.main.build_context_probe_payload",
        lambda **_kwargs: pytest.fail("OCR fallback should not run when executor polling returns a message"),
    )

    payload = process_live_once(
        orchestrator=orchestrator,
        dry_run=False,
        region_names=parse_ocr_region_names(None),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="mock-tesseract",
        fallback_contact_name=None,
        state_store=None,
    )

    assert payload["status"] == "processed"
    assert payload["message_source"] == "executor_poll"
    assert payload["incoming_message"]["conversation_id"] == "文件传输助手"
    assert payload["orchestration"]["decision"]["kind"] == DecisionKind.SAFE_REPLY.value
    assert executor.sent_text == [("文件传输助手", "收到，我来处理。")]


def test_process_live_once_blocks_contacts_outside_allowlist(tmp_path: Path, monkeypatch):
    executor = FakeExecutor()
    executor.polled_message = IncomingMessage(
        message_id="polled-1",
        conversation_id="real-contact",
        contact_name="real-contact",
        text="hello",
        metadata={"sender": "Alice"},
    )
    orchestrator = build_orchestrator(tmp_path, executor)
    state_path = tmp_path / "runtime" / "monitor" / "state.json"

    monkeypatch.setattr(
        "wechat_auto_reply.main.build_context_probe_payload",
        lambda **_kwargs: pytest.fail("OCR fallback should not run when executor polling returns a message"),
    )

    payload = process_live_once(
        orchestrator=orchestrator,
        dry_run=False,
        region_names=parse_ocr_region_names(None),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="mock-tesseract",
        fallback_contact_name=None,
        state_store=MonitorStateStore(state_path),
        allowed_contacts=frozenset({"file-helper"}),
    )

    assert payload["status"] == "blocked"
    assert payload["message_source"] == "executor_poll"
    assert "not in allowed contacts" in payload["reason"]
    assert executor.sent_text == []
    assert not state_path.exists()


def test_process_live_once_ignores_known_bot_echo(tmp_path: Path, monkeypatch):
    executor = FakeExecutor()
    reply_text = build_engine().faq_rules[0].reply_text
    executor.polled_message = IncomingMessage(
        message_id="polled-echo",
        conversation_id="file-helper",
        contact_name="file-helper",
        text=reply_text,
        metadata={"sender": "self"},
    )
    orchestrator = build_orchestrator(tmp_path, executor)
    state_path = tmp_path / "runtime" / "monitor" / "state.json"

    monkeypatch.setattr(
        "wechat_auto_reply.main.build_context_probe_payload",
        lambda **_kwargs: pytest.fail("OCR fallback should not run when executor polling returns a message"),
    )

    payload = process_live_once(
        orchestrator=orchestrator,
        dry_run=False,
        region_names=parse_ocr_region_names(None),
        languages="chi_sim+eng",
        psm=6,
        ocr_command="mock-tesseract",
        fallback_contact_name=None,
        state_store=MonitorStateStore(state_path),
        allowed_contacts=frozenset({"file-helper"}),
        ignored_echo_texts=frozenset({reply_text}),
    )

    assert payload["status"] == "ignored"
    assert payload["message_source"] == "executor_poll"
    assert executor.sent_text == []
    assert executor.handoffs == []
    assert state_path.exists()


def test_set_clipboard_text_prefers_win32clipboard(monkeypatch):
    calls: list[object] = []
    fake_clipboard = SimpleNamespace(
        CF_UNICODETEXT=13,
        OpenClipboard=lambda: calls.append("open"),
        EmptyClipboard=lambda: calls.append("empty"),
        SetClipboardText=lambda text, fmt: calls.append(("set", text, fmt)),
        CloseClipboard=lambda: calls.append("close"),
    )

    monkeypatch.setattr(windows_common, "is_windows_host", lambda: True)
    monkeypatch.setitem(sys.modules, "win32clipboard", fake_clipboard)
    monkeypatch.setattr(
        windows_common,
        "_set_clipboard_text_with_ctypes",
        lambda _text: pytest.fail("ctypes fallback should not run when win32clipboard succeeds"),
    )

    result = windows_common.set_clipboard_text("hello from pywin32")

    assert result == (True, "Clipboard text updated via win32clipboard")
    assert calls == [
        "open",
        "empty",
        ("set", "hello from pywin32", 13),
        "close",
    ]


def test_set_clipboard_text_falls_back_to_ctypes(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(windows_common, "is_windows_host", lambda: True)
    monkeypatch.setattr(
        windows_common,
        "_set_clipboard_text_with_win32clipboard",
        lambda _text: (False, "win32clipboard is unavailable"),
    )
    monkeypatch.setattr(
        windows_common,
        "_set_clipboard_text_with_ctypes",
        lambda text: calls.append(text) or (True, "Clipboard text updated via ctypes fallback"),
    )

    result = windows_common.set_clipboard_text("fallback text")

    assert result == (True, "Clipboard text updated via ctypes fallback")
    assert calls == ["fallback text"]


def test_ctypes_clipboard_fallback_sets_64bit_safe_signatures(monkeypatch):
    class FakeWinApiFunction:
        def __init__(self, callback):
            self.callback = callback
            self.argtypes = None
            self.restype = None

        def __call__(self, *args):
            return self.callback(*args)

    state: dict[str, object] = {}
    memmove_calls: list[tuple[object, bytes, int]] = []
    allocated_handle = 0x1234567887654321
    locked_pointer = 0x2345678987654321

    def record_alloc(flags, size):
        state["alloc"] = (flags, size)
        return allocated_handle

    def record_lock(handle):
        state["lock"] = handle
        return locked_pointer

    def record_unlock(handle):
        state["unlock"] = handle
        return True

    def record_free(handle):
        state["free"] = handle
        return 0

    def record_open(owner):
        state["open"] = owner
        return True

    def record_empty():
        state["empty"] = True
        return True

    def record_close():
        state["close"] = True
        return True

    def record_set(fmt, handle):
        state["set"] = (fmt, handle)
        return handle

    fake_kernel32 = SimpleNamespace(
        GlobalAlloc=FakeWinApiFunction(record_alloc),
        GlobalLock=FakeWinApiFunction(record_lock),
        GlobalUnlock=FakeWinApiFunction(record_unlock),
        GlobalFree=FakeWinApiFunction(record_free),
    )
    fake_user32 = SimpleNamespace(
        OpenClipboard=FakeWinApiFunction(record_open),
        EmptyClipboard=FakeWinApiFunction(record_empty),
        CloseClipboard=FakeWinApiFunction(record_close),
        SetClipboardData=FakeWinApiFunction(record_set),
    )

    monkeypatch.setattr(windows_common, "is_windows_host", lambda: True)
    monkeypatch.setattr(
        windows_common.ctypes,
        "windll",
        SimpleNamespace(kernel32=fake_kernel32, user32=fake_user32),
    )
    monkeypatch.setattr(
        windows_common.ctypes,
        "memmove",
        lambda destination, source, size: memmove_calls.append((destination, bytes(source), size)),
    )

    result = windows_common._set_clipboard_text_with_ctypes("64-bit safe")

    expected_payload = "64-bit safe\x00".encode("utf-16-le")
    assert result == (True, "Clipboard text updated via ctypes fallback")
    assert state["open"] is None
    assert state["alloc"] == (0x0042, len(expected_payload))
    assert state["lock"] == allocated_handle
    assert state["unlock"] == allocated_handle
    assert state["set"] == (13, allocated_handle)
    assert memmove_calls == [(locked_pointer, expected_payload, len(expected_payload))]
    assert fake_kernel32.GlobalAlloc.restype is windows_common.wintypes.HGLOBAL
    assert fake_kernel32.GlobalLock.restype is windows_common.wintypes.LPVOID
    assert fake_user32.SetClipboardData.argtypes == [windows_common.wintypes.UINT, windows_common.wintypes.HANDLE]


def test_windows_astron_healthcheck_reports_runtime(monkeypatch):
    monkeypatch.setattr("wechat_auto_reply.platform.windows_astron.sys.platform", "win32")
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_astron.find_command",
        lambda *_args: "C:/Astron/astron.exe",
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_astron.list_wechat_processes",
        lambda: (
            DetectedProcess(process_name="Weixin", pid=1001, window_title="微信"),
        ),
    )
    monkeypatch.setattr(
        "wechat_auto_reply.platform.windows_astron.list_wechat_windows",
        lambda: (
            DetectedWindow(title="微信", pid=1001, class_name="WeixinWnd"),
        ),
    )

    health = WindowsAstronExecutor().healthcheck()
    rendered = format_health(health)

    assert health.supported is True
    assert "Astron runtime" in health.details
    assert "wechat windows" in rendered
    assert "astron_runtime_found: ok" in rendered
