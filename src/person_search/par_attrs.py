"""PA-100K 风格行人属性：Parsing 主色 + 体态启发式（轻量 PAR）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from src.person_search.color_vocab import (
    color_name_similarity,
    region_dominant_color,
)
from src.person_search.human_parsing import ParseResult, get_human_parser
from src.person_search.utils import extract_body_signature

ATTR_VERSION = 1
GENDER_LABELS = ("female", "male", "unknown")
SLEEVE_LABELS = ("long", "short", "unknown")
LOWER_LABELS = ("trousers", "shorts", "skirt_dress", "unknown")


def _gender_from_body(body: Optional[List[float]]) -> Tuple[str, float]:
    if not body or len(body) < 7:
        return "unknown", 0.0
    code = int(round(body[5]))
    conf = float(body[6])
    if code > 0:
        return "male", conf
    if code < 0:
        return "female", conf
    return "unknown", conf


def _infer_sleeve(bgr: np.ndarray, parse_result: ParseResult) -> str:
    h = bgr.shape[0]
    upper = parse_result.upper_mask
    if not np.any(upper):
        return "unknown"

    y_shoulder = int(h * 0.18)
    y_wrist = int(h * 0.48)
    y_shoulder = max(0, min(y_shoulder, h - 1))
    y_wrist = max(y_shoulder + 1, min(y_wrist, h - 1))

    upper_ratio = float(np.count_nonzero(upper)) / float(max(h * bgr.shape[1], 1))
    band = upper[y_shoulder:y_wrist]
    if band.size == 0:
        return "unknown"
    fill = float(np.count_nonzero(band)) / float(max(band.size, 1))
    if fill >= 0.42 and upper_ratio >= 0.16:
        return "long"
    if fill <= 0.28:
        return "short"
    return "unknown"


def _infer_lower_type(parse_result: ParseResult) -> str:
    label_map = parse_result.label_map
    if label_map is not None:
        if np.any(label_map == 12):
            return "skirt_dress"
        if np.any(np.isin(label_map, [9, 10])):
            return "trousers"
    lower = parse_result.lower_mask
    if not np.any(lower):
        return "unknown"
    h = lower.shape[0]
    upper_half = lower[: max(1, int(h * 0.55)), :]
    lower_half = lower[max(0, int(h * 0.55)) :, :]
    top_fill = float(np.count_nonzero(upper_half)) / float(max(upper_half.size, 1))
    bottom_fill = float(np.count_nonzero(lower_half)) / float(max(lower_half.size, 1))
    if bottom_fill > top_fill * 1.35:
        return "shorts"
    return "trousers"


def extract_person_attributes(bgr: np.ndarray, parse_result: Optional[ParseResult] = None) -> Dict[str, Any]:
    """从抠图提取结构化行人属性（Parsing + 体态）。"""
    if bgr is None or bgr.size == 0:
        return {}

    parser = get_human_parser()
    parsed = parse_result or parser.parse(bgr)
    upper_color, upper_conf, upper_lab = region_dominant_color(bgr, parsed.upper_mask)
    lower_color, lower_conf, lower_lab = region_dominant_color(bgr, parsed.lower_mask)

    body = extract_body_signature(bgr) or []
    gender, gender_conf = _gender_from_body(body)

    return {
        "v": ATTR_VERSION,
        "source": parsed.source,
        "gender": gender,
        "gender_conf": round(gender_conf, 4),
        "upper_color": upper_color,
        "upper_color_conf": round(upper_conf, 4),
        "lower_color": lower_color,
        "lower_color_conf": round(lower_conf, 4),
        "upper_sleeve": _infer_sleeve(bgr, parsed),
        "lower_type": _infer_lower_type(parsed),
        "upper_lab": [round(float(x), 2) for x in upper_lab] if upper_lab else [],
        "lower_lab": [round(float(x), 2) for x in lower_lab] if lower_lab else [],
    }


def _attrs_valid(attrs: Optional[Dict[str, Any]]) -> bool:
    return bool(
        attrs
        and attrs.get("upper_color")
        and attrs.get("upper_color") != "unknown"
        and float(attrs.get("upper_color_conf") or 0) > 0
    )


def compare_person_attributes(
    attrs_a: Optional[Dict[str, Any]],
    attrs_b: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """属性比对：仅高置信性别冲突否决，其余供展示/参考。"""
    if not _attrs_valid(attrs_a) or not _attrs_valid(attrs_b):
        return {"veto": False, "similarity": -1.0, "conflicts": []}

    conflicts: List[str] = []
    ga = str(attrs_a.get("gender") or "unknown")
    gb = str(attrs_b.get("gender") or "unknown")
    gca = float(attrs_a.get("gender_conf") or 0)
    gcb = float(attrs_b.get("gender_conf") or 0)
    if gca >= 0.58 and gcb >= 0.58 and ga != gb and ga != "unknown" and gb != "unknown":
        conflicts.append("gender")
        return {"veto": True, "similarity": 0.0, "conflicts": conflicts}

    ua = str(attrs_a.get("upper_color") or "unknown")
    ub = str(attrs_b.get("upper_color") or "unknown")
    uca = float(attrs_a.get("upper_color_conf") or 0)
    ucb = float(attrs_b.get("upper_color_conf") or 0)
    la = str(attrs_a.get("lower_color") or "unknown")
    lb = str(attrs_b.get("lower_color") or "unknown")
    lca = float(attrs_a.get("lower_color_conf") or 0)
    lcb = float(attrs_b.get("lower_color_conf") or 0)

    scores: List[float] = []
    upper_sim = color_name_similarity(ua, ub)
    if upper_sim >= 0:
        scores.append(upper_sim * min(1.0, (uca + ucb) / 2.0 + 0.35))
    lower_sim = color_name_similarity(la, lb)
    if lower_sim >= 0 and la != "unknown" and lb != "unknown":
        scores.append(lower_sim * min(1.0, (lca + lcb) / 2.0 + 0.35))
    if ga == gb and ga != "unknown":
        scores.append(0.75 + 0.2 * min(gca, gcb))
    sleeve_a = attrs_a.get("upper_sleeve")
    sleeve_b = attrs_b.get("upper_sleeve")
    if sleeve_a and sleeve_b and sleeve_a == sleeve_b and sleeve_a != "unknown":
        scores.append(0.85)

    similarity = float(np.mean(scores)) if scores else -1.0
    return {"veto": False, "similarity": similarity, "conflicts": conflicts}


def attributes_summary(attrs: Optional[Dict[str, Any]]) -> str:
    if not attrs:
        return "-"
    parts = []
    gender = attrs.get("gender")
    if gender and gender != "unknown":
        parts.append("女" if gender == "female" else "男")
    upper = attrs.get("upper_color")
    if upper and upper != "unknown":
        parts.append(f"上装:{upper}")
    lower = attrs.get("lower_color")
    if lower and lower != "unknown":
        parts.append(f"下装:{lower}")
    sleeve = attrs.get("upper_sleeve")
    if sleeve and sleeve != "unknown":
        parts.append("长袖" if sleeve == "long" else "短袖")
    return " · ".join(parts) if parts else "-"
