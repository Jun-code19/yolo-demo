"""VLM-only 整图巡检阶段"""
import re
from typing import Any, Dict, List, Optional

import numpy as np

from src.inference_pipeline.payload_builder import (
    canonicalize_bbox_to_norm,
    encode_frame_for_vlm,
    resolve_prompt,
)
from src.inference_pipeline.providers.qwen_vl import get_vlm_provider

_COLOR_KEYWORDS = {
    "red": ("红", "red"),
    "blue": ("蓝", "blue"),
    "white": ("白", "white"),
    "black": ("黑", "black"),
    "yellow": ("黄", "yellow"),
    "green": ("绿", "green"),
    "gray": ("灰", "gray", "grey"),
    "orange": ("橙", "orange"),
}

_PLACEHOLDER_LABELS = {
    "",
    "标签",
    "none",
    "无",
    "正常",
    "null",
    "n/a",
    "unknown",
}

_DEFAULT_INFERRED_CONFIDENCE = 0.85


def _extract_color_from_label(label: str) -> Optional[str]:
    label_lower = label.lower()
    for color in _COLOR_KEYWORDS:
        if label_lower.startswith(f"{color}_") or label_lower == color:
            return color
    return None


def _is_placeholder_label(label: str) -> bool:
    text = str(label or "").strip()
    if not text:
        return True
    lower = text.lower()
    if lower in _PLACEHOLDER_LABELS:
        return True
    if text.startswith("<") and text.endswith(">"):
        return True
    if "|" in text:
        return True
    if any(token in text for token in ("填写", "如 ", "示例", "标签")):
        return True
    return False


def _clothing_finding_consistent(label: str, attributes: Optional[Dict[str, Any]]) -> bool:
    """衣着类 label 与 attributes 颜色不一致时视为模型照抄示例，丢弃该 finding。"""
    color = _extract_color_from_label(label)
    if not color or not attributes:
        return True

    label_lower = label.lower()
    if "pants" in label_lower or "bottom" in label_lower:
        field = str(attributes.get("clothing_bottom") or "")
    else:
        field = str(attributes.get("clothing_top") or "")

    if not field.strip():
        return True

    field_lower = field.lower()
    expected = _COLOR_KEYWORDS[color]
    if any(kw in field_lower for kw in expected):
        return True

    for other, keywords in _COLOR_KEYWORDS.items():
        if other == color:
            continue
        if any(kw in field_lower for kw in keywords):
            return False
    return True


def _resolve_confidence(
    item: Dict[str, Any],
    min_confidence: float,
    configured: Optional[List[str]] = None,
) -> float:
    """模型常把 confidence 填 0；有实质描述或衣着校验通过时补默认置信度。"""
    try:
        conf = float(item.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf >= min_confidence:
        return conf

    label = str(item.get("label") or "")
    label_lower = label.lower()
    configured_lower = [str(x).lower() for x in (configured or [])]
    in_scope = not configured_lower or label_lower in configured_lower

    attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else None
    if _extract_color_from_label(label) and attrs and _clothing_finding_consistent(label, attrs):
        return max(conf, _DEFAULT_INFERRED_CONFIDENCE) if conf > 0 else _DEFAULT_INFERRED_CONFIDENCE

    description = str(item.get("description") or "").strip()
    severity = str(item.get("severity") or "").lower()
    if in_scope and description and severity in ("low", "medium", "high", "critical"):
        return max(conf, _DEFAULT_INFERRED_CONFIDENCE) if conf > 0 else _DEFAULT_INFERRED_CONFIDENCE
    if in_scope and description and len(description) >= 4:
        return max(conf, _DEFAULT_INFERRED_CONFIDENCE) if conf > 0 else _DEFAULT_INFERRED_CONFIDENCE

    return conf


def parse_finding_bbox(
    raw: Any,
    ref_width: Optional[int] = None,
    ref_height: Optional[int] = None,
) -> Optional[List[float]]:
    """解析 finding.bbox → 归一化 xyxy (0~1)。需提供送模图像尺寸以正确换算 0~1000/像素。"""
    if ref_width and ref_height:
        return canonicalize_bbox_to_norm(raw, ref_width, ref_height)
    # 无尺寸时仅接受已是 0~1 的值
    return canonicalize_bbox_to_norm(raw, 1000, 1000) if raw is not None else None


def _label_mentioned_positively(summary: str, label: str) -> bool:
    summary_lower = summary.lower()
    label_lower = label.lower()
    if label_lower not in summary_lower:
        return False

    start = 0
    while True:
        idx = summary_lower.find(label_lower, start)
        if idx == -1:
            break
        window = summary[max(0, idx - 16): idx + len(label) + 8]
        if re.search(r"未(?:发现|命中|检测到|出现)?|没有|不存在|未发现|无(?:异常|风险|人)?", window):
            start = idx + len(label_lower)
            continue
        if re.search(r"命中(?:关注项|告警项)|发现|检测到|存在|出现|确认|有", window):
            return True
        start = idx + len(label_lower)
    return False


def _infer_findings_from_summary(
    summary: str,
    alert_labels: Optional[List[str]],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    """摘要写了命中但 findings 为空时的兜底（模型只更新了 summary）。"""
    if not summary or not alert_labels:
        return []

    configured_map = {str(x).lower(): str(x) for x in alert_labels}
    inferred: List[Dict[str, Any]] = []
    seen: set = set()

    hit_section = re.search(r"命中(?:关注项|告警项)?[：:]\s*([^\n。；;]+)", summary)
    if hit_section:
        for token in re.split(r"[,，、\s]+", hit_section.group(1)):
            key = token.strip().lower()
            if key and key in configured_map and key not in seen:
                seen.add(key)
                inferred.append(
                    {
                        "label": configured_map[key],
                        "confidence": max(min_confidence, _DEFAULT_INFERRED_CONFIDENCE),
                        "description": summary,
                        "severity": "info",
                    }
                )

    if inferred:
        return inferred

    if re.search(r"未(?:发现|命中|检测到)|未发现|没有.*(?:异常|问题|风险)|无异常|正常", summary):
        return []

    for key, label in configured_map.items():
        if key in seen:
            continue
        if _label_mentioned_positively(summary, label):
            seen.add(key)
            inferred.append(
                {
                    "label": label,
                    "confidence": max(min_confidence, _DEFAULT_INFERRED_CONFIDENCE),
                    "description": summary,
                    "severity": "info",
                }
            )
    return inferred


def normalize_vlm_detect_result(
    parsed: Optional[Dict[str, Any]],
    alert_labels: Optional[List[str]] = None,
    min_confidence: float = 0.7,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
) -> Dict[str, Any]:
    if not parsed or not isinstance(parsed, dict):
        return {
            "findings": [],
            "summary": "",
            "needs_alert": False,
            "alert_labels": [],
        }

    findings = parsed.get("findings") or []
    if not isinstance(findings, list):
        findings = []

    normalized = []
    for item in findings:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if _is_placeholder_label(label):
            continue
        try:
            confidence = float(item.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        entry: Dict[str, Any] = {
            "label": label,
            "confidence": confidence,
            "description": item.get("description") or "",
            "severity": item.get("severity") or "info",
        }
        if isinstance(item.get("attributes"), dict):
            entry["attributes"] = item["attributes"]
        bbox = parse_finding_bbox(
            item.get("bbox") or item.get("box") or item.get("bounding_box"),
            ref_width=image_width,
            ref_height=image_height,
        )
        if bbox:
            entry["bbox"] = bbox
        normalized.append(entry)

    verified = []
    for item in normalized:
        attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else None
        if _clothing_finding_consistent(item["label"], attrs):
            verified.append(item)
    normalized = verified

    configured = [str(x).lower() for x in (alert_labels or [])]
    summary = str(parsed.get("summary") or "")
    existing_labels = {item["label"].lower() for item in normalized}
    for inf in _infer_findings_from_summary(summary, alert_labels, min_confidence):
        if inf["label"].lower() not in existing_labels:
            normalized.append(inf)
            existing_labels.add(inf["label"].lower())

    hit_labels: List[str] = []
    for item in normalized:
        label_lower = item["label"].lower()
        if configured and label_lower not in configured:
            continue
        effective_conf = _resolve_confidence(item, min_confidence, alert_labels)
        item["confidence"] = effective_conf
        if effective_conf >= min_confidence:
            hit_labels.append(item["label"])

    needs_alert = len(hit_labels) > 0

    return {
        "findings": normalized,
        "summary": parsed.get("summary") or "",
        "needs_alert": needs_alert,
        "alert_labels": hit_labels,
    }


def run_vlm_only_inspection(
    frame: np.ndarray,
    model_record,
    prompt_id: str,
    alert_labels: Optional[List[str]] = None,
    min_confidence: float = 0.7,
    prompt_override: Optional[str] = None,
    vlm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    vlm_config = vlm_config or {}
    input_cfg = vlm_config.get("input") or {}
    max_width = int(input_cfg.get("max_width") or 1280)
    jpeg_quality = int(input_cfg.get("jpeg_quality") or 85)

    image_b64, sent_w, sent_h = encode_frame_for_vlm(
        frame, max_width=max_width, jpeg_quality=jpeg_quality
    )
    prompts = resolve_prompt(
        prompt_id,
        alert_labels,
        prompt_override,
        image_width=sent_w,
        image_height=sent_h,
    )

    provider = get_vlm_provider(model_record)
    raw = provider.inspect_image(image_b64, prompts["system"], prompts["user"])

    parsed = normalize_vlm_detect_result(
        raw.get("parsed"),
        alert_labels=alert_labels,
        min_confidence=min_confidence,
        image_width=sent_w,
        image_height=sent_h,
    )

    return {
        "ok": raw.get("ok") and not raw.get("error"),
        "error": raw.get("error"),
        "latency_ms": raw.get("latency_ms") or 0,
        "raw_text": raw.get("raw_text") or "",
        "raw_parsed": raw.get("parsed"),
        "result": parsed,
    }

