"""监控抠图区域主色识别（HSV + LAB，映射到 PA-100K 颜色词表）。"""
from typing import List, Optional, Tuple

import cv2
import numpy as np

STANDARD_COLORS = (
    "black",
    "white",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "brown",
    "unknown",
)

CHROMATIC_COLORS = {"red", "orange", "yellow", "green", "blue", "purple"}
NEUTRAL_COLORS = {"black", "white", "gray", "brown"}


def _classify_hsv(h: float, s: float, v: float) -> str:
    if v < 50:
        return "black"
    if s < 32:
        if v > 205:
            return "white"
        if v > 95:
            return "gray"
        return "black"
    # 肤色不参与主色统计
    if (h < 20 or h > 160) and 18 <= s <= 95 and v >= 55:
        return "unknown"
    if h < 8 or h >= 168:
        return "red"
    if h < 16:
        return "orange"
    if h < 42:
        return "yellow"
    if h < 85:
        return "green"
    if h < 130:
        return "blue"
    if h < 155:
        return "purple"
    return "red"


def region_dominant_color(
    bgr: np.ndarray,
    mask: np.ndarray,
    *,
    min_pixels: int = 24,
) -> Tuple[str, float, List[float]]:
    """返回 (颜色名, 置信度, LAB 均值)。"""
    if bgr is None or mask is None or bgr.size == 0 or not np.any(mask):
        return "unknown", 0.0, []

    pixels = bgr[mask.astype(bool)]
    if pixels.shape[0] < min_pixels:
        return "unknown", 0.0, []

    hsv = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    votes = {name: 0 for name in STANDARD_COLORS}
    for hue, sat, val in hsv:
        name = _classify_hsv(float(hue), float(sat), float(val))
        if name == "unknown":
            continue
        votes[name] += 1

    total = float(max(sum(votes.values()), 1))
    color = max(votes.items(), key=lambda item: item[1])[0]
    confidence = float(votes[color] / total)
    if color == "unknown" or confidence < 0.12:
        return "unknown", 0.0, []

    lab = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    la, aa, ba = [float(x) for x in np.mean(lab, axis=0)]
    return color, confidence, [la, aa, ba]


def lab_color_distance(lab_a: List[float], lab_b: List[float]) -> float:
    if not lab_a or not lab_b or len(lab_a) < 3 or len(lab_b) < 3:
        return -1.0
    a = np.asarray(lab_a[:3], dtype=np.float32)
    b = np.asarray(lab_b[:3], dtype=np.float32)
    return float(np.linalg.norm(a - b))


def lab_garment_conflict(lab_a: List[float], lab_b: List[float], min_dist: float = 36.0) -> bool:
    dist = lab_color_distance(lab_a, lab_b)
    return dist >= 0 and dist >= min_dist


def upper_color_conflict(color_a: str, color_b: str) -> bool:
    """高置信外观否决：明显不同的上下衣主色。"""
    if not color_a or not color_b or color_a == "unknown" or color_b == "unknown":
        return False
    if color_a == color_b:
        return False
    warm = {"yellow", "orange", "brown"}
    if color_a in warm and color_b in {"white", "gray", "black", "blue", "green"}:
        return True
    if color_b in warm and color_a in {"white", "gray", "black", "blue", "green"}:
        return True
    if color_a in CHROMATIC_COLORS and color_b in NEUTRAL_COLORS and color_a not in warm:
        return color_b in {"white", "gray", "black"}
    if color_b in CHROMATIC_COLORS and color_a in NEUTRAL_COLORS and color_b not in warm:
        return color_a in {"white", "gray", "black"}
    # 黄 vs 橙在监控里常混，但白/灰仍应区分
    if color_a == "yellow" and color_b in {"white", "gray"}:
        return True
    if color_b == "yellow" and color_a in {"white", "gray"}:
        return True
    return False


def color_name_similarity(color_a: str, color_b: str) -> float:
    if not color_a or not color_b or color_a == "unknown" or color_b == "unknown":
        return -1.0
    if color_a == color_b:
        return 1.0
    warm = {"yellow", "orange", "brown"}
    neutral = {"white", "gray", "black"}
    if color_a in warm and color_b in warm:
        return 0.72
    if color_a in neutral and color_b in neutral:
        return 0.68
    if upper_color_conflict(color_a, color_b):
        return 0.18
    return 0.45
