from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


DEFAULT_OCR_LANGUAGES = "chi_sim+eng"
DEFAULT_OCR_BACKENDS = ("rapidocr", "tesseract")
DEFAULT_OCR_REGIONS = (
    "conversation_list",
    "selected_conversation",
    "chat_header",
    "message_pane",
    "latest_message_band",
    "composer_input",
    "send_button_candidate",
)


def get_default_ocr_languages() -> str:
    return os.getenv("WECHAT_AUTO_REPLY_OCR_LANGUAGES", DEFAULT_OCR_LANGUAGES)


def get_default_ocr_command() -> str | None:
    value = os.getenv("WECHAT_AUTO_REPLY_OCR_COMMAND")
    return value.strip() if value and value.strip() else None


def get_default_ocr_backends() -> tuple[str, ...]:
    raw_value = os.getenv("WECHAT_AUTO_REPLY_OCR_BACKENDS")
    if not raw_value:
        return DEFAULT_OCR_BACKENDS
    parsed = tuple(part.strip().lower() for part in raw_value.split(",") if part.strip())
    return parsed or DEFAULT_OCR_BACKENDS


def parse_ocr_region_names(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return DEFAULT_OCR_REGIONS
    return tuple(part.strip() for part in raw_value.split(",") if part.strip())


def load_layout_probe_artifact(artifact_path: Path) -> dict[str, object]:
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def write_ocr_failure(
    output_dir: Path,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "supported": False,
        "reason": reason,
        "metadata": metadata or {},
    }
    artifact_path = output_dir / "ocr-probe.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["artifact_path"] = str(artifact_path)
    return payload


def _resolve_backend_candidates(
    preferred_backends: tuple[str, ...] | None,
    ocr_command: str | None,
) -> tuple[str, ...]:
    if preferred_backends:
        return preferred_backends
    if ocr_command:
        return ("tesseract", "rapidocr")
    return get_default_ocr_backends()


def _resolve_tesseract_command(explicit_command: str | None) -> tuple[str | None, str]:
    candidate = explicit_command or get_default_ocr_command()
    if candidate:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return str(candidate_path), f"using explicit OCR command: {candidate_path}"
        resolved = shutil.which(candidate)
        if resolved:
            return resolved, f"resolved OCR command from explicit setting: {candidate}"
        return None, f"OCR command was configured but not found: {candidate}"

    resolved = shutil.which("tesseract")
    if resolved:
        return resolved, "resolved OCR command from PATH: tesseract"
    return None, "tesseract is not installed or not on PATH"


@lru_cache(maxsize=1)
def _load_rapidocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _probe_rapidocr_runtime() -> tuple[object | None, str]:
    try:
        return _load_rapidocr_engine(), "rapidocr-onnxruntime runtime is available"
    except Exception as exc:  # pragma: no cover - depends on host dependency state
        return None, f"RapidOCR is unavailable: {type(exc).__name__}: {exc}"


def _prepare_ocr_image(source_path: Path, output_path: Path) -> None:
    from PIL import Image, ImageFilter, ImageOps

    with Image.open(source_path) as image:
        prepared = ImageOps.autocontrast(ImageOps.grayscale(image))
        if min(prepared.size) < 120:
            prepared = prepared.resize(
                (prepared.width * 2, prepared.height * 2),
                Image.Resampling.LANCZOS,
            )
        prepared = prepared.filter(ImageFilter.SHARPEN)
        prepared.save(output_path)


def _resolve_region_crop_path(raw_path: str, artifact_dir: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or candidate.exists():
        return candidate

    artifact_relative = artifact_dir / candidate
    if artifact_relative.exists():
        return artifact_relative

    artifact_sibling = artifact_dir / candidate.name
    if artifact_sibling.exists():
        return artifact_sibling
    return candidate


def _run_tesseract_tsv(
    command: str,
    image_path: Path,
    languages: str,
    psm: int,
) -> tuple[bool, str]:
    completed = subprocess.run(
        [
            command,
            os.fspath(image_path),
            "stdout",
            "-l",
            languages,
            "--psm",
            str(psm),
            "tsv",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    if completed.returncode != 0:
        error_detail = completed.stderr.strip() or completed.stdout.strip() or "unknown tesseract error"
        return False, error_detail
    return True, completed.stdout


def _parse_tesseract_tsv(tsv_text: str) -> dict[str, object]:
    rows = csv.DictReader(tsv_text.splitlines(), delimiter="\t")
    lines: list[str] = []
    items: list[dict[str, object]] = []
    line_items: list[dict[str, object]] = []
    confidences: list[float] = []
    current_key: tuple[str | None, str | None, str | None, str | None] | None = None
    current_words: list[str] = []
    current_line_items: list[dict[str, object]] = []

    for row in rows:
        text = (row.get("text") or "").strip()
        conf_text = (row.get("conf") or "-1").strip()
        try:
            confidence = float(conf_text)
        except ValueError:
            confidence = -1
        if not text:
            continue

        line_key = (
            row.get("page_num"),
            row.get("block_num"),
            row.get("par_num"),
            row.get("line_num"),
        )
        if current_key is None:
            current_key = line_key
        elif current_key != line_key:
            collapsed = " ".join(current_words).strip()
            if collapsed:
                lines.append(collapsed)
                left = min(int(item["left"]) for item in current_line_items)
                top = min(int(item["top"]) for item in current_line_items)
                right = max(int(item["right"]) for item in current_line_items)
                bottom = max(int(item["bottom"]) for item in current_line_items)
                line_confidences = [float(item["confidence"]) for item in current_line_items if item["confidence"] is not None]
                line_items.append(
                    {
                        "text": collapsed,
                        "left": left,
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "confidence": round(sum(line_confidences) / len(line_confidences), 2) if line_confidences else None,
                    }
                )
            current_words = []
            current_line_items = []
            current_key = line_key
        current_words.append(text)

        left = int(row.get("left") or 0)
        top = int(row.get("top") or 0)
        width = int(row.get("width") or 0)
        height = int(row.get("height") or 0)
        items.append(
            {
                "text": text,
                "confidence": None if confidence < 0 else confidence,
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            }
        )
        current_line_items.append(items[-1])
        if confidence >= 0:
            confidences.append(confidence)

    if current_words:
        collapsed = " ".join(current_words).strip()
        if collapsed:
            lines.append(collapsed)
            left = min(int(item["left"]) for item in current_line_items)
            top = min(int(item["top"]) for item in current_line_items)
            right = max(int(item["right"]) for item in current_line_items)
            bottom = max(int(item["bottom"]) for item in current_line_items)
            line_confidences = [float(item["confidence"]) for item in current_line_items if item["confidence"] is not None]
            line_items.append(
                {
                    "text": collapsed,
                    "left": left,
                    "top": top,
                    "right": right,
                    "bottom": bottom,
                    "confidence": round(sum(line_confidences) / len(line_confidences), 2) if line_confidences else None,
                }
            )

    text = "\n".join(line for line in lines if line).strip()
    mean_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    return {
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "word_count": len(items),
        "mean_confidence": mean_confidence,
        "line_items": line_items,
        "items": items,
        "words": items,
    }


def _run_rapidocr(engine, image_path: Path) -> tuple[bool, object]:
    try:
        result, elapsed = engine(os.fspath(image_path))
    except Exception as exc:  # pragma: no cover - depends on live OCR runtime
        return False, f"{type(exc).__name__}: {exc}"
    return True, {"result": result or [], "elapsed": elapsed}


def _parse_rapidocr_result(result_payload: dict[str, object]) -> dict[str, object]:
    raw_items = result_payload["result"]
    items: list[dict[str, object]] = []
    line_items: list[dict[str, object]] = []
    confidences: list[float] = []
    lines: list[str] = []

    for entry in raw_items:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        box, text, score = entry[0], str(entry[1]).strip(), entry[2]
        if not text:
            continue
        points = [(float(point[0]), float(point[1])) for point in box]
        left = int(min(point[0] for point in points))
        right = int(max(point[0] for point in points))
        top = int(min(point[1] for point in points))
        bottom = int(max(point[1] for point in points))
        confidence = float(score)
        line_item = {
            "text": text,
            "confidence": confidence,
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
        }
        items.append(
            {
                "text": text,
                "confidence": confidence,
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
            }
        )
        line_items.append(line_item)
        confidences.append(confidence)

    items.sort(key=lambda item: (int(item["top"]), int(item["left"])))
    line_items.sort(key=lambda item: (int(item["top"]), int(item["left"])))
    lines = [str(item["text"]) for item in items]
    text = "\n".join(lines).strip()
    mean_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    return {
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "word_count": len(items),
        "mean_confidence": mean_confidence,
        "line_items": line_items,
        "items": items,
        "words": items,
        "elapsed": result_payload.get("elapsed"),
    }


def probe_ocr_from_layout(
    layout_payload: dict[str, object],
    output_dir: Path,
    region_names: tuple[str, ...] = DEFAULT_OCR_REGIONS,
    languages: str | None = None,
    psm: int = 6,
    ocr_command: str | None = None,
    metadata: dict[str, object] | None = None,
    preferred_backends: tuple[str, ...] | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = metadata or {}

    try:
        from PIL import Image  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on host dependency state
        return write_ocr_failure(
            output_dir,
            f"Pillow is unavailable: {type(exc).__name__}: {exc}",
            metadata=metadata,
        )

    if not layout_payload.get("supported"):
        reason = str(layout_payload.get("reason") or "layout probe is not available")
        return write_ocr_failure(output_dir, reason, metadata=metadata)

    backend_candidates = _resolve_backend_candidates(preferred_backends, ocr_command)
    backend_status: dict[str, dict[str, object]] = {}
    rapidocr_engine = None
    tesseract_command = None

    if "rapidocr" in backend_candidates:
        rapidocr_engine, detail = _probe_rapidocr_runtime()
        backend_status["rapidocr"] = {
            "available": rapidocr_engine is not None,
            "detail": detail,
        }

    if "tesseract" in backend_candidates:
        tesseract_command, detail = _resolve_tesseract_command(ocr_command)
        backend_status["tesseract"] = {
            "available": tesseract_command is not None,
            "detail": detail,
            "command": tesseract_command,
        }

    available_backends = [
        backend
        for backend in backend_candidates
        if backend_status.get(backend, {}).get("available")
    ]
    if not available_backends:
        backend_summary = "; ".join(
            f"{backend}: {status.get('detail')}"
            for backend, status in backend_status.items()
        )
        return write_ocr_failure(output_dir, backend_summary or "no OCR backend is available", metadata=metadata)

    selected_languages = languages or get_default_ocr_languages()
    available_regions = {
        str(region.get("name")): region
        for region in layout_payload.get("regions", [])
        if isinstance(region, dict) and region.get("name")
    }
    missing_regions = [name for name in region_names if name not in available_regions]
    selected_regions = [available_regions[name] for name in region_names if name in available_regions]
    if not selected_regions:
        return write_ocr_failure(
            output_dir,
            f"none of the requested regions were found: {', '.join(region_names)}",
            metadata=metadata,
        )

    region_results: list[dict[str, object]] = []
    for region in selected_regions:
        region_name = str(region["name"])
        crop_path = _resolve_region_crop_path(str(region["crop_path"]), output_dir)
        prepared_path = output_dir / f"{region_name}-ocr-input.png"
        tsv_path = output_dir / f"{region_name}-ocr.tsv"

        if not crop_path.exists():
            region_results.append(
                {
                    "name": region_name,
                    "crop_path": str(crop_path),
                    "success": False,
                    "reason": f"crop image does not exist: {crop_path}",
                }
            )
            continue

        try:
            _prepare_ocr_image(crop_path, prepared_path)
        except Exception as exc:  # pragma: no cover - depends on live OCR runtime
            region_results.append(
                {
                    "name": region_name,
                    "crop_path": str(crop_path),
                    "ocr_input_path": str(prepared_path),
                    "success": False,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        backend_failures: dict[str, str] = {}
        success_payload: dict[str, object] | None = None
        for backend in available_backends:
            if backend == "rapidocr":
                ok, result_payload = _run_rapidocr(rapidocr_engine, prepared_path)
                if not ok:
                    backend_failures[backend] = str(result_payload)
                    continue
                parsed = _parse_rapidocr_result(result_payload)
                success_payload = {
                    "name": region_name,
                    "crop_path": str(crop_path),
                    "ocr_input_path": str(prepared_path),
                    "success": True,
                    "ocr_backend": backend,
                    **parsed,
                }
                break

            if backend == "tesseract":
                ok, tsv_output = _run_tesseract_tsv(
                    str(tesseract_command),
                    prepared_path,
                    selected_languages,
                    psm,
                )
                if not ok:
                    backend_failures[backend] = str(tsv_output)
                    continue
                tsv_path.write_text(tsv_output, encoding="utf-8")
                parsed = _parse_tesseract_tsv(tsv_output)
                success_payload = {
                    "name": region_name,
                    "crop_path": str(crop_path),
                    "ocr_input_path": str(prepared_path),
                    "tsv_path": str(tsv_path),
                    "success": True,
                    "ocr_backend": backend,
                    **parsed,
                }
                break

        if success_payload is not None:
            region_results.append(success_payload)
            continue

        region_results.append(
            {
                "name": region_name,
                "crop_path": str(crop_path),
                "ocr_input_path": str(prepared_path),
                "success": False,
                "reason": "all OCR backends failed for this region",
                "attempted_backends": available_backends,
                "backend_failures": backend_failures,
            }
        )

    payload = {
        "supported": True,
        "ocr_backend": "auto",
        "backend_candidates": list(backend_candidates),
        "backend_status": backend_status,
        "languages": selected_languages,
        "psm": psm,
        "requested_regions": list(region_names),
        "missing_regions": missing_regions,
        "regions": region_results,
        "metadata": metadata,
    }
    artifact_path = output_dir / "ocr-probe.json"
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["artifact_path"] = str(artifact_path)
    return payload
