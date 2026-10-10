"""YOLO 初筛后的 VLM 复检 / 行为分析"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from src.inference_pipeline.payload_builder import encode_frame_to_base64, resolve_prompt
from src.inference_pipeline.providers.qwen_vl import get_vlm_provider
from src.inference_pipeline.vlm_only_stage import normalize_vlm_detect_result, run_vlm_only_inspection


def crop_bbox(
    frame: np.ndarray,
    bbox: List[float],
    margin_ratio: float = 0.15,
) -> np.ndarray:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [float(v) for v in bbox]
    bw = max(x2 - x1, 1.0)
    bh = max(y2 - y1, 1.0)
    mx = bw * margin_ratio
    my = bh * margin_ratio
    cx1 = int(max(0, x1 - mx))
    cy1 = int(max(0, y1 - my))
    cx2 = int(min(w, x2 + mx))
    cy2 = int(min(h, y2 + my))
    if cx2 <= cx1 or cy2 <= cy1:
        return frame.copy()
    return frame[cy1:cy2, cx1:cx2].copy()


def union_bbox(detections: List[Dict[str, Any]]) -> Optional[List[float]]:
    if not detections:
        return None
    x1 = min(d["bbox"][0] for d in detections)
    y1 = min(d["bbox"][1] for d in detections)
    x2 = max(d["bbox"][2] for d in detections)
    y2 = max(d["bbox"][3] for d in detections)
    return [x1, y1, x2, y2]


def build_vlm_input_frame(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    context: str = "crop_with_margin",
    margin_ratio: float = 0.15,
) -> np.ndarray:
    if context == "full_frame" or not detections:
        return frame.copy()
    bbox = union_bbox(detections)
    if not bbox:
        return frame.copy()
    if context == "crop":
        x1, y1, x2, y2 = [int(v) for v in bbox]
        return frame[y1:y2, x1:x2].copy()
    return crop_bbox(frame, bbox, margin_ratio=margin_ratio)


def build_yolo_class_counts(detections: List[Dict[str, Any]]) -> Dict[str, int]:
    counter: Counter = Counter()
    for det in detections or []:
        name = str(det.get("class_name") or det.get("name") or "unknown").strip() or "unknown"
        counter[name] += 1
    return dict(counter)


def format_yolo_summary_text(counts: Dict[str, int]) -> str:
    if not counts:
        return "（无检出）"
    parts = [f"- {name} × {cnt}" for name, cnt in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    return "\n".join(parts)


def _normalize_count_map(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, int] = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        try:
            out[name] = int(value)
        except (TypeError, ValueError):
            try:
                out[name] = int(float(value))
            except (TypeError, ValueError):
                continue
    return out


def _normalize_diffs(raw: Any, yolo_counts: Dict[str, int], vlm_counts: Dict[str, int]) -> List[Dict[str, Any]]:
    diffs: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            class_name = str(item.get("class_name") or item.get("label") or "").strip()
            try:
                yolo_n = int(item["yolo"]) if item.get("yolo") is not None else yolo_counts.get(class_name, 0)
            except (TypeError, ValueError):
                yolo_n = yolo_counts.get(class_name, 0)
            try:
                vlm_n = int(item["vlm"]) if item.get("vlm") is not None else vlm_counts.get(class_name, 0)
            except (TypeError, ValueError):
                vlm_n = vlm_counts.get(class_name, 0)
            diffs.append(
                {
                    "type": str(item.get("type") or "count_mismatch"),
                    "class_name": class_name or "unknown",
                    "yolo": yolo_n,
                    "vlm": vlm_n,
                    "note": str(item.get("note") or item.get("reason") or ""),
                }
            )
    if diffs:
        return diffs
    # 模型未给 diffs 时，按计数差自动生成
    all_names = sorted(set(yolo_counts) | set(vlm_counts))
    for name in all_names:
        yolo_n = int(yolo_counts.get(name, 0))
        vlm_n = int(vlm_counts.get(name, 0))
        if yolo_n == vlm_n:
            continue
        if yolo_n == 0:
            diff_type = "extra"
            note = f"画面多出 {name}×{vlm_n}"
        elif vlm_n == 0:
            diff_type = "missing"
            note = f"YOLO 多报 {name}×{yolo_n}"
        else:
            diff_type = "count_mismatch"
            note = f"{name}: YOLO {yolo_n} → 画面约 {vlm_n}"
        diffs.append(
            {
                "type": diff_type,
                "class_name": name,
                "yolo": yolo_n,
                "vlm": vlm_n,
                "note": note,
            }
        )
    return diffs


def _resolve_scene_verify_prompt(
    prompt_id: str,
    detections: List[Dict[str, Any]],
    yolo_counts: Dict[str, int],
    prompt_override: Optional[str] = None,
) -> Dict[str, str]:
    summary_text = format_yolo_summary_text(yolo_counts)
    total = str(len(detections or []))
    if prompt_override and prompt_override.strip():
        user = (
            prompt_override.replace("{yolo_summary}", summary_text)
            .replace("{yolo_total}", total)
        )
        return {
            "system": (
                "你是视觉复检助手。只输出 JSON，不要 markdown。"
                "必须根据整帧画面核对 YOLO 初筛的类别与数量，禁止臆测。"
            ),
            "user": user,
        }

    registry_prompt = resolve_prompt(prompt_id or "yolo_verify_v1")
    user = (
        registry_prompt["user"]
        .replace("{yolo_summary}", summary_text)
        .replace("{yolo_total}", total)
    )
    return {"system": registry_prompt["system"], "user": user}


def normalize_scene_verify_result(
    parsed: Optional[Dict[str, Any]],
    yolo_counts: Dict[str, int],
    reject_below: float = 0.6,
) -> Dict[str, Any]:
    """整帧复检结果：consistency = match | mismatch | uncertain。"""
    if not parsed or not isinstance(parsed, dict):
        return {
            "consistency": "uncertain",
            "verified": False,
            "confidence": 0.0,
            "reason": "VLM 无有效返回",
            "summary": "VLM 无有效返回",
            "yolo_summary": yolo_counts,
            "observed_counts": {},
            "diffs": [],
        }

    try:
        confidence = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    reason = str(parsed.get("reason") or parsed.get("summary") or parsed.get("reject_reason") or "")
    observed = _normalize_count_map(
        parsed.get("observed_counts") or parsed.get("vlm_summary") or parsed.get("counts")
    )
    diffs = _normalize_diffs(parsed.get("diffs"), yolo_counts, observed)

    raw_consistency = str(parsed.get("consistency") or "").strip().lower()
    if raw_consistency in ("match", "ok", "consistent", "same"):
        consistency = "match"
    elif raw_consistency in ("mismatch", "diff", "inconsistent", "different"):
        consistency = "mismatch"
    elif "verified" in parsed:
        consistency = "match" if bool(parsed.get("verified")) else "mismatch"
    elif diffs:
        consistency = "mismatch"
    else:
        consistency = "match" if observed == yolo_counts or not observed else "mismatch"

    if confidence < float(reject_below or 0):
        consistency = "uncertain"

    return {
        "consistency": consistency,
        "verified": consistency == "match",
        "confidence": confidence,
        "reason": reason,
        "summary": reason,
        "yolo_summary": yolo_counts,
        "observed_counts": observed,
        "diffs": diffs,
    }


def run_yolo_scene_verify(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    model_record,
    pipeline: Dict[str, Any],
) -> Dict[str, Any]:
    """整帧一次复检：对照 YOLO 类别/数量是否与画面一致。"""
    verify_cfg = pipeline.get("verify") or {}
    input_cfg = pipeline.get("input") or {}
    yolo_counts = build_yolo_class_counts(detections)
    # 复检固定整帧，且固定使用复检模板（忽略自定义覆盖）
    input_frame = build_vlm_input_frame(
        frame, detections, context="full_frame", margin_ratio=0.15
    )
    prompts = _resolve_scene_verify_prompt(
        "yolo_verify_v1",
        detections,
        yolo_counts,
        prompt_override=None,
    )
    image_b64 = encode_frame_to_base64(
        input_frame,
        max_width=int(input_cfg.get("max_width") or 1280),
        jpeg_quality=int(input_cfg.get("jpeg_quality") or 85),
    )

    provider = get_vlm_provider(model_record)
    raw = provider.inspect_image(image_b64, prompts["system"], prompts["user"])
    parsed = normalize_scene_verify_result(
        raw.get("parsed"),
        yolo_counts=yolo_counts,
        reject_below=float(verify_cfg.get("reject_below") or 0.6),
    )

    return {
        "ok": raw.get("ok") and not raw.get("error"),
        "error": raw.get("error"),
        "latency_ms": raw.get("latency_ms") or 0,
        "raw_text": raw.get("raw_text") or "",
        "result": parsed,
        "detections": detections,
    }


def run_yolo_analyze(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    model_record,
    pipeline: Dict[str, Any],
) -> Dict[str, Any]:
    # 行为分析固定整帧
    input_frame = build_vlm_input_frame(
        frame, detections, context="full_frame", margin_ratio=0.15
    )

    vlm_config = {"input": pipeline.get("input") or {}}
    inspection = run_vlm_only_inspection(
        input_frame,
        model_record,
        prompt_id=pipeline.get("prompt_id") or "general_patrol_v1",
        alert_labels=pipeline.get("alert_labels") or None,
        min_confidence=float(pipeline.get("min_confidence") or 0.7),
        prompt_override=pipeline.get("prompt_override"),
        vlm_config=vlm_config,
    )
    return {
        **inspection,
        "detections": detections,
    }


