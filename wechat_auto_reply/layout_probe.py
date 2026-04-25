from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LayoutRegion:
    name: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def as_dict(self) -> dict[str, int | str]:
        payload = asdict(self)
        payload["width"] = self.width
        payload["height"] = self.height
        return payload


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def _region(name: str, width: int, height: int, left_ratio: float, top_ratio: float, right_ratio: float, bottom_ratio: float) -> LayoutRegion:
    left = _clamp(int(width * left_ratio), 0, width)
    top = _clamp(int(height * top_ratio), 0, height)
    right = _clamp(int(width * right_ratio), left + 1, width)
    bottom = _clamp(int(height * bottom_ratio), top + 1, height)
    return LayoutRegion(name=name, left=left, top=top, right=right, bottom=bottom)


def build_wechat_layout_regions(width: int, height: int) -> tuple[LayoutRegion, ...]:
    return (
        _region("window", width, height, 0.0, 0.0, 1.0, 1.0),
        _region("nav_rail", width, height, 0.0, 0.0, 0.08, 1.0),
        _region("conversation_list", width, height, 0.08, 0.0, 0.33, 1.0),
        _region("chat_header", width, height, 0.33, 0.0, 1.0, 0.12),
        _region("message_pane", width, height, 0.33, 0.12, 1.0, 0.76),
        _region("composer_toolbar", width, height, 0.33, 0.76, 1.0, 0.84),
        _region("composer_input", width, height, 0.33, 0.84, 1.0, 1.0),
        _region("send_button_candidate", width, height, 0.84, 0.90, 0.98, 0.985),
        _region("latest_message_band", width, height, 0.36, 0.50, 0.94, 0.76),
    )


def _detect_selected_conversation_region(image, conversation_region: LayoutRegion) -> LayoutRegion | None:
    crop = image.crop(
        (
            conversation_region.left,
            conversation_region.top,
            conversation_region.right,
            conversation_region.bottom,
        )
    ).convert("RGB")
    width, height = crop.size
    min_green_pixels = max(12, int(width * 0.35))
    min_run_height = max(24, int(height * 0.04))

    best_run: tuple[int, int, int] | None = None
    run_start: int | None = None
    run_score = 0

    for y in range(height):
        green_pixels = 0
        for x in range(width):
            red, green, blue = crop.getpixel((x, y))
            if green > 140 and green > red + 20 and green > blue + 20:
                green_pixels += 1

        if green_pixels >= min_green_pixels:
            if run_start is None:
                run_start = y
                run_score = 0
            run_score += green_pixels
            continue

        if run_start is not None:
            run_height = y - run_start
            if run_height >= min_run_height and (best_run is None or run_score > best_run[2]):
                best_run = (run_start, y, run_score)
            run_start = None
            run_score = 0

    if run_start is not None:
        run_height = height - run_start
        if run_height >= min_run_height and (best_run is None or run_score > best_run[2]):
            best_run = (run_start, height, run_score)

    if best_run is None:
        return None

    row_top, row_bottom, _score = best_run
    row_height = max(1, row_bottom - row_top)
    left = conversation_region.left + int(width * 0.20)
    right = conversation_region.left + int(width * 0.78)
    top = conversation_region.top + row_top + int(row_height * 0.08)
    bottom = conversation_region.top + row_top + int(row_height * 0.52)

    return LayoutRegion(
        name="selected_conversation",
        left=_clamp(left, conversation_region.left, conversation_region.right - 1),
        top=_clamp(top, conversation_region.top, conversation_region.bottom - 1),
        right=_clamp(right, left + 1, conversation_region.right),
        bottom=_clamp(bottom, top + 1, conversation_region.bottom),
    )


def probe_layout_from_screenshot(
    screenshot_path: Path,
    output_dir: Path,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)

    def write_failure(reason: str) -> dict[str, object]:
        payload = {
            "supported": False,
            "reason": reason,
            "screenshot_path": str(screenshot_path),
            "metadata": metadata or {},
        }
        artifact_path = output_dir / "layout-probe.json"
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        payload["artifact_path"] = str(artifact_path)
        return payload

    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # pragma: no cover - depends on host dependency state
        return write_failure(f"Pillow is unavailable: {type(exc).__name__}: {exc}")

    if not screenshot_path.exists():
        dry_run_hint = ""
        if metadata and metadata.get("dry_run"):
            dry_run_hint = " (dry-run mode does not create a real screenshot; rerun with --no-dry-run)"
        return write_failure(f"screenshot does not exist: {screenshot_path}{dry_run_hint}")

    image = Image.open(screenshot_path)
    width, height = image.size
    regions = list(build_wechat_layout_regions(width, height))
    conversation_region = next((region for region in regions if region.name == "conversation_list"), None)
    if conversation_region is not None:
        selected_region = _detect_selected_conversation_region(image, conversation_region)
        if selected_region is not None:
            regions.append(selected_region)

    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for region in regions:
        draw.rectangle((region.left, region.top, region.right, region.bottom), outline="red", width=3)

    overlay_path = output_dir / "layout-overlay.png"
    overlay.save(overlay_path)

    region_exports: list[dict[str, object]] = []
    for region in regions:
        crop_path = output_dir / f"{region.name}.png"
        crop = image.crop((region.left, region.top, region.right, region.bottom))
        crop.save(crop_path)
        region_payload = region.as_dict()
        region_payload["crop_path"] = str(crop_path)
        region_exports.append(region_payload)

    artifact = {
        "supported": True,
        "screenshot_path": str(screenshot_path),
        "overlay_path": str(overlay_path),
        "image_size": {"width": width, "height": height},
        "regions": region_exports,
        "metadata": metadata or {},
    }
    artifact_path = output_dir / "layout-probe.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    artifact["artifact_path"] = str(artifact_path)
    return artifact
