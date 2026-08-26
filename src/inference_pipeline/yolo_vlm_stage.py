"""YOLO 初筛后的 VLM 复检 / 行为分析"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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


def _resolve_verify_prompt(
    prompt_id: str,
    detection: Dict[str, Any],
    prompt_override: Optional[str] = None,
) -> Dict[str, str]:
    class_name = detection.get("class_name") or "目标"
    confidence = float(detection.get("confidence") or 0)
    if prompt_override and prompt_override.strip():
        user = (
            prompt_override.replace("{yolo_class}", class_name)
            .replace("{yolo_conf}", f"{confidence:.2f}")
        )
        return {
            "system": (
                "你是视觉复检助手。只输出 JSON，不要 markdown。"
                "必须根据裁剪图实际内容判断，禁止臆测。"
            ),
            "user": user,
        }

    registry_prompt = resolve_prompt(prompt_id, alert_labels=[class_name])
    user = (
        registry_prompt["user"]
        .replace("{yolo_class}", class_name)
        .replace("{yolo_conf}", f"{confidence:.2f}")
    )
    return {"system": registry_prompt["system"], "user": user}


def normalize_verify_result(
    parsed: Optional[Dict[str, Any]],
    reject_below: float = 0.6,
) -> Dict[str, Any]:
    if not parsed or not isinstance(parsed, dict):
        return {"verified": False, "confidence": 0.0, "reason": "VLM 无有效返回"}

    verified = bool(parsed.get("verified"))
    try:
        confidence = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    reason = str(parsed.get("reason") or parsed.get("reject_reason") or "")
    ok = verified and confidence >= reject_below
    return {
        "verified": ok,
        "confidence": confidence,
        "reason": reason,
    }


def run_yolo_verify(
    frame: np.ndarray,
    detection: Dict[str, Any],
    model_record,
    pipeline: Dict[str, Any],
) -> Dict[str, Any]:
    trigger = pipeline.get("trigger") or {}
    verify_cfg = pipeline.get("verify") or {}
    input_cfg = pipeline.get("input") or {}
    margin = float(trigger.get("margin_ratio") or 0.15)
    context = trigger.get("context") or "crop_with_margin"

    if context == "full_frame":
        crop = frame.copy()
    else:
        crop = crop_bbox(frame, detection["bbox"], margin_ratio=margin)

    prompts = _resolve_verify_prompt(
        pipeline.get("prompt_id") or "yolo_verify_v1",
        detection,
        pipeline.get("prompt_override"),
    )
    image_b64 = encode_frame_to_base64(
        crop,
        max_width=int(input_cfg.get("max_width") or 1280),
        jpeg_quality=int(input_cfg.get("jpeg_quality") or 85),
    )

    provider = get_vlm_provider(model_record)
    raw = provider.inspect_image(image_b64, prompts["system"], prompts["user"])
    parsed = normalize_verify_result(
        raw.get("parsed"),
        reject_below=float(verify_cfg.get("reject_below") or 0.6),
    )

    return {
        "ok": raw.get("ok") and not raw.get("error"),
        "error": raw.get("error"),
        "latency_ms": raw.get("latency_ms") or 0,
        "raw_text": raw.get("raw_text") or "",
        "result": parsed,
        "detection": detection,
    }


def run_yolo_analyze(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    model_record,
    pipeline: Dict[str, Any],
) -> Dict[str, Any]:
    trigger = pipeline.get("trigger") or {}
    context = trigger.get("context") or "crop_with_margin"
    margin = float(trigger.get("margin_ratio") or 0.15)
    input_frame = build_vlm_input_frame(frame, detections, context=context, margin_ratio=margin)

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


MAX_VERIFY_CANDIDATES_PER_FRAME = 5


def pick_verify_candidates(
    detections: List[Dict[str, Any]],
    max_count: int = MAX_VERIFY_CANDIDATES_PER_FRAME,
) -> List[Dict[str, Any]]:
    """按置信度降序返回待复检目标（默认最多 5 个）"""
    if not detections:
        return []
    ordered = sorted(detections, key=lambda d: float(d.get("confidence") or 0), reverse=True)
    return ordered[: max(1, int(max_count or MAX_VERIFY_CANDIDATES_PER_FRAME))]


def pick_verify_candidate(detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates = pick_verify_candidates(detections, max_count=1)
    return candidates[0] if candidates else None
