"""人员检测过滤与抠图工具"""
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

PERSON_CLASS_NAMES = {"person", "people", "human", "行人", "人"}

# ReID 标准输入尺寸（高 x 宽）
REID_HEIGHT = 256
REID_WIDTH = 128
MIN_CROP_HEIGHT = 64
MIN_CROP_WIDTH = 24
MIN_CROP_ASPECT = 1.15
MAX_CROP_ASPECT = 5.0


def is_person_detection(det: Dict[str, Any]) -> bool:
    name = str(det.get("class_name") or "").strip().lower()
    if name in PERSON_CLASS_NAMES:
        return True
    class_id = det.get("class_id")
    try:
        return int(class_id) == 0
    except (TypeError, ValueError):
        return False


def filter_person_detections(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [d for d in (detections or []) if is_person_detection(d)]


def parse_bbox(det: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    bbox = det.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        x1, y1, x2, y2 = [int(float(v)) for v in bbox[:4]]
        return x1, y1, x2, y2
    if all(k in det for k in ("x1", "y1", "x2", "y2")):
        return int(det["x1"]), int(det["y1"]), int(det["x2"]), int(det["y2"])
    return None


def crop_person(frame: np.ndarray, bbox: Tuple[int, int, int, int], padding: float = 0.06) -> Optional[np.ndarray]:
    if frame is None or frame.size == 0:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    pad_x = int(bw * padding)
    pad_y = int(bh * padding)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size else None


def is_valid_person_crop(bgr: np.ndarray) -> bool:
    """过滤过小或宽高比异常的抠图，减少低质量入库。"""
    if bgr is None or bgr.size == 0:
        return False
    h, w = bgr.shape[:2]
    if h < MIN_CROP_HEIGHT or w < MIN_CROP_WIDTH:
        return False
    ratio = h / max(w, 1)
    return MIN_CROP_ASPECT <= ratio <= MAX_CROP_ASPECT


def preprocess_reid_crop(bgr: np.ndarray) -> np.ndarray:
    """按行人 ReID 常用比例缩放，保留全身轮廓。"""
    if bgr is None or bgr.size == 0:
        return bgr
    return cv2.resize(bgr, (REID_WIDTH, REID_HEIGHT), interpolation=cv2.INTER_LINEAR)


def _upper_torso_region(bgr: np.ndarray) -> np.ndarray:
    h = bgr.shape[0]
    y1 = max(0, int(h * 0.12))
    y2 = max(y1 + 1, int(h * 0.68))
    return bgr[y1:y2, :]


def _clothing_hsv_mask(hsv: np.ndarray, min_sat: int = 55) -> np.ndarray:
    """过滤低饱和与过暗像素，保留衣着/配饰等高饱和区域。"""
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    return (sat >= min_sat) & (val >= 35) & (val <= 245)


def extract_clothing_color_profile(bgr: np.ndarray) -> Optional[Dict[str, Any]]:
    """提取上身衣着颜色概况：饱和度占比 + 红/黄/蓝等主色桶。"""
    if bgr is None or bgr.size == 0:
        return None
    torso = _upper_torso_region(bgr)
    h, w = torso.shape[:2]
    if h < 4 or w < 4:
        return None

    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    total = float(h * w)

    sat_ratio_40 = float(np.count_nonzero(sat >= 40)) / total
    sat_ratio_60 = float(np.count_nonzero(sat >= 60)) / total
    mask = _clothing_hsv_mask(hsv, min_sat=55)
    colored_ratio = float(np.count_nonzero(mask)) / total
    red_yellow_ratio = 0.0
    if np.any(mask):
        masked_hue = hue[mask]
        red_yellow_mask = ((masked_hue < 12) | (masked_hue > 168) | ((masked_hue >= 14) & (masked_hue < 38)))
        red_yellow_ratio = float(np.count_nonzero(red_yellow_mask)) / total

    if not np.any(mask):
        return {
            "sat_ratio_40": sat_ratio_40,
            "sat_ratio_60": sat_ratio_60,
            "colored_ratio": colored_ratio,
            "red_yellow_ratio": red_yellow_ratio,
            "is_neutral": sat_ratio_40 < 0.22,
            "buckets": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        }

    masked_hue = hue[mask]
    n = max(len(masked_hue), 1)
    red = float(np.count_nonzero((masked_hue < 12) | (masked_hue > 168))) / n
    yellow = float(np.count_nonzero((masked_hue >= 14) & (masked_hue < 38))) / n
    green = float(np.count_nonzero((masked_hue >= 38) & (masked_hue < 85))) / n
    blue = float(np.count_nonzero((masked_hue >= 85) & (masked_hue < 130))) / n
    other = max(0.0, 1.0 - red - yellow - green - blue)
    buckets = [red, yellow, green, blue, other, 0.0]
    return {
        "sat_ratio_40": sat_ratio_40,
        "sat_ratio_60": sat_ratio_60,
        "colored_ratio": colored_ratio,
        "red_yellow_ratio": red_yellow_ratio,
        "is_neutral": sat_ratio_40 < 0.22,
        "buckets": buckets,
    }


def _safety_color_strength(profile: Dict[str, Any]) -> float:
    """红/黄高可视安全色占躯干像素比例。"""
    return float(profile.get("red_yellow_ratio") or 0.0)


def _has_safety_color_conflict(profile_a: Dict[str, Any], profile_b: Dict[str, Any]) -> bool:
    ry_a = _safety_color_strength(profile_a)
    ry_b = _safety_color_strength(profile_b)
    if ry_a >= 0.14 and ry_b <= 0.07:
        return True
    if ry_b >= 0.14 and ry_a <= 0.07:
        return True
    low = max(min(ry_a, ry_b), 0.015)
    if max(ry_a, ry_b) >= 0.14 and (max(ry_a, ry_b) / low) >= 3.2:
        return True
    return False


def _has_chromatic_neutral_conflict(profile_a: Dict[str, Any], profile_b: Dict[str, Any]) -> bool:
    """明黄/高饱和上衣 vs 白/米/灰中性上衣。"""
    buckets_a = profile_a.get("buckets") or []
    buckets_b = profile_b.get("buckets") or []
    if len(buckets_a) < 5 or len(buckets_b) < 5:
        return False

    yellow_a, yellow_b = float(buckets_a[1]), float(buckets_b[1])
    other_a, other_b = float(buckets_a[4]), float(buckets_b[4])
    sat_a = float(profile_a.get("sat_ratio_60") or 0.0)
    sat_b = float(profile_b.get("sat_ratio_60") or 0.0)

    def _strong_yellow(yellow: float, sat: float) -> bool:
        return yellow >= 0.50 and sat >= 0.30

    def _pale_top(yellow: float, sat: float, other: float) -> bool:
        return yellow <= 0.44 and (sat <= 0.40 or other >= 0.12)

    if _strong_yellow(yellow_a, sat_a) and _pale_top(yellow_b, sat_b, other_b):
        return True
    if _strong_yellow(yellow_b, sat_b) and _pale_top(yellow_a, sat_a, other_a):
        return True
    return False


def compare_clothing_color_profile(profile_a: Dict[str, Any], profile_b: Dict[str, Any]) -> float:
    """对比衣着颜色；工装/明黄 vs 中性便装做强否决。"""
    if not profile_a or not profile_b:
        return 0.0

    if _has_safety_color_conflict(profile_a, profile_b):
        return 0.22

    if _has_chromatic_neutral_conflict(profile_a, profile_b):
        return 0.26

    buckets_a = np.asarray((profile_a.get("buckets") or [])[:5], dtype=np.float32)
    buckets_b = np.asarray((profile_b.get("buckets") or [])[:5], dtype=np.float32)
    if buckets_a.size != buckets_b.size or buckets_a.size == 0:
        return 0.0

    norm_a = float(np.linalg.norm(buckets_a))
    norm_b = float(np.linalg.norm(buckets_b))
    if norm_a < 1e-8 or norm_b < 1e-8:
        bucket_sim = 1.0 if norm_a < 1e-8 and norm_b < 1e-8 else 0.55
    else:
        bucket_sim = float(np.clip(np.dot(buckets_a / norm_a, buckets_b / norm_b), 0.0, 1.0))

    sat_a = float(profile_a.get("sat_ratio_40") or 0.0)
    sat_b = float(profile_b.get("sat_ratio_40") or 0.0)
    sat_penalty = 1.0 - 0.25 * min(1.0, abs(sat_a - sat_b) / 0.50)
    return float(np.clip(bucket_sim * sat_penalty, 0.0, 1.0))


def _silhouette_mask(bgr: np.ndarray) -> np.ndarray:
    white = (
        (bgr[:, :, 0] >= 235)
        & (bgr[:, :, 1] >= 235)
        & (bgr[:, :, 2] >= 235)
    )
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    # 监控抠图常见：走廊/墙面高亮低饱和，不应算进肩臀宽度
    background = (sat < 42) & (val > 175)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return (~white) & (~background) & (gray < 252)


def _band_width_ratio(bgr: np.ndarray, y1_frac: float, y2_frac: float) -> float:
    h, w = bgr.shape[:2]
    y1 = max(0, int(h * y1_frac))
    y2 = max(y1 + 1, int(h * y2_frac))
    band = bgr[y1:y2]
    mask = _silhouette_mask(band)
    if not np.any(mask):
        return 1.0
    widths: List[float] = []
    for row_mask in mask:
        cols = np.where(row_mask)[0]
        if cols.size:
            widths.append(float(cols[-1] - cols[0] + 1) / max(w, 1))
    if not widths:
        return 1.0
    # 中位数比均值更抗单侧背景残留
    return float(np.median(widths))


def _gender_silhouette_conflict(sig_a: List[float], sig_b: List[float]) -> bool:
    """仅在性别判断较明确时否决，避免误伤同一人不同角度/抠图质量差的情况。"""
    sh_a, sh_b = float(sig_a[4]), float(sig_b[4])
    ga, ca = int(round(sig_a[5])), float(sig_a[6])
    gb, cb = int(round(sig_b[5])), float(sig_b[6])

    if ca >= 0.58 and cb >= 0.58 and ga != 0 and gb != 0 and ga != gb:
        return True

    if ca >= 0.55 and ga > 0 and cb >= 0.50 and gb < 0:
        return True
    if cb >= 0.55 and gb > 0 and ca >= 0.50 and ga < 0:
        return True

    if ga < 0 and ca >= 0.55 and sh_b >= 1.06:
        return True
    if gb < 0 and cb >= 0.55 and sh_a >= 1.06:
        return True

    if ga > 0 and ca >= 0.55 and sh_b <= 0.88:
        return True
    if gb > 0 and cb >= 0.55 and sh_a <= 0.88:
        return True

    return False


def _gender_hint(shoulder_hip: float) -> Tuple[int, float]:
    """返回 (gender_code, confidence)：-1 偏女、0 未知、1 偏男。"""
    if shoulder_hip >= 1.10:
        return 1, min(0.92, 0.58 + (shoulder_hip - 1.0) * 1.6)
    if shoulder_hip <= 0.86:
        return -1, min(0.92, 0.58 + (1.0 - shoulder_hip) * 1.6)
    if shoulder_hip >= 1.04:
        return 1, 0.52
    if shoulder_hip <= 0.94:
        return -1, 0.52
    return 0, 0.28


def extract_body_signature(bgr: np.ndarray) -> Optional[List[float]]:
    """体态轮廓签名：宽高比、肩/腰/臀宽度、性别启发式。"""
    if bgr is None or bgr.size == 0:
        return None
    clean = strip_segmentation_border(bgr)
    h, w = clean.shape[:2]
    if h < 40 or w < 16:
        return None

    aspect = float(h / max(w, 1))
    shoulder = _band_width_ratio(clean, 0.10, 0.28)
    waist = _band_width_ratio(clean, 0.36, 0.52)
    hip = _band_width_ratio(clean, 0.52, 0.72)
    shoulder_hip = float(shoulder / max(hip, 1e-3))
    gender_code, gender_conf = _gender_hint(shoulder_hip)
    return [aspect, shoulder, waist, hip, shoulder_hip, float(gender_code), gender_conf]


def compare_body_signature(sig_a: List[float], sig_b: List[float]) -> float:
    if not sig_a or not sig_b or len(sig_a) < 7 or len(sig_b) < 7:
        return -1.0

    if _gender_silhouette_conflict(sig_a, sig_b):
        return 0.0

    ga, ca = int(round(sig_a[5])), float(sig_a[6])
    gb, cb = int(round(sig_b[5])), float(sig_b[6])
    if ca >= 0.62 and cb >= 0.62 and ga != 0 and gb != 0 and ga != gb:
        return 0.0

    aspect_a, aspect_b = float(sig_a[0]), float(sig_b[0])
    aspect_diff = abs(aspect_a - aspect_b) / max(aspect_a, aspect_b, 1e-3)
    if aspect_diff >= 0.28:
        return min(0.30, 1.0 - aspect_diff)

    sh_diff = abs(float(sig_a[4]) - float(sig_b[4]))
    if sh_diff >= 0.20:
        return min(0.35, 0.65 - sh_diff)

    profile_a = np.asarray(sig_a[1:4], dtype=np.float32)
    profile_b = np.asarray(sig_b[1:4], dtype=np.float32)
    na = float(np.linalg.norm(profile_a))
    nb = float(np.linalg.norm(profile_b))
    if na < 1e-6 or nb < 1e-6:
        profile_sim = 0.55
    else:
        profile_sim = float(np.clip(np.dot(profile_a / na, profile_b / nb), 0.0, 1.0))

    aspect_sim = float(max(0.0, 1.0 - aspect_diff / 0.24))
    shape_sim = float(max(0.0, 1.0 - sh_diff / 0.18))
    return float(np.clip(0.45 * profile_sim + 0.30 * aspect_sim + 0.25 * shape_sim, 0.0, 1.0))


def body_signature_conflict(sig_a: List[float], sig_b: List[float]) -> bool:
    if _gender_silhouette_conflict(sig_a, sig_b):
        return True
    sim = compare_body_signature(sig_a, sig_b)
    if sim < 0:
        return False
    if sim <= 0.05:
        return True
    if not sig_a or not sig_b or len(sig_a) < 7 or len(sig_b) < 7:
        return False
    ga, ca = int(round(sig_a[5])), float(sig_a[6])
    gb, cb = int(round(sig_b[5])), float(sig_b[6])
    return ca >= 0.62 and cb >= 0.62 and ga != 0 and gb != 0 and ga != gb


def strip_segmentation_border(bgr: np.ndarray, white_threshold: int = 235) -> np.ndarray:
    """去掉抠图白边/分割光晕，避免污染颜色特征。"""
    if bgr is None or bgr.size == 0:
        return bgr
    white = (
        (bgr[:, :, 0] >= white_threshold)
        & (bgr[:, :, 1] >= white_threshold)
        & (bgr[:, :, 2] >= white_threshold)
    )
    if not np.any(~white):
        return bgr
    coords = np.column_stack(np.where(~white))
    y1, x1 = coords.min(axis=0)
    y2, x2 = coords.max(axis=0) + 1
    if y2 - y1 < 8 or x2 - x1 < 8:
        return bgr
    return bgr[y1:y2, x1:x2]


def _center_garment_region(bgr: np.ndarray) -> np.ndarray:
    """取胸口区域，减少背景与肢体干扰。"""
    h, w = bgr.shape[:2]
    y1 = max(0, int(h * 0.20))
    y2 = max(y1 + 1, int(h * 0.55))
    x1 = max(0, int(w * 0.22))
    x2 = max(x1 + 1, int(w * 0.78))
    return bgr[y1:y2, x1:x2]


def _garment_pixel_mask(region: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    white = (
        (region[:, :, 0] >= 235)
        & (region[:, :, 1] >= 235)
        & (region[:, :, 2] >= 235)
    )
    return (hsv[:, :, 1] >= 18) & (hsv[:, :, 2] >= 22) & (~white)


def _garment_lab_and_hue(
    region: np.ndarray, mask: np.ndarray
) -> Tuple[float, float, float, np.ndarray]:
    lab = cv2.cvtColor(region, cv2.COLOR_BGR2LAB).astype(np.float32)
    if np.any(mask):
        la = float(np.mean(lab[:, :, 0][mask]))
        aa = float(np.mean(lab[:, :, 1][mask]))
        ab = float(np.mean(lab[:, :, 2][mask]))
    else:
        flat = lab.reshape(-1, 3)
        la = float(np.mean(flat[:, 0]))
        aa = float(np.mean(flat[:, 1]))
        ab = float(np.mean(flat[:, 2]))

    hue_hist = np.zeros(36, dtype=np.float32)
    if np.any(mask):
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv[:, :, 0]], [0], mask.astype(np.uint8), [36], [0, 180])
        cv2.normalize(hist, hist)
        hue_hist = hist.flatten().astype(np.float32)
    return la, aa, ab, hue_hist


def _score_garment_features(
    la: float, aa: float, ab: float, hue_a: np.ndarray,
    lb: float, ba: float, bb: float, hue_b: np.ndarray,
) -> float:
    l_diff = abs(la - lb)
    ab_dist = float(np.hypot(aa - ba, ab - bb))
    chroma_a = float(np.hypot(aa, ab))
    chroma_b = float(np.hypot(ba, bb))
    light_sim = float(np.exp(-max(0.0, l_diff - 30.0) / 22.0))
    chroma_sim = float(np.exp(-ab_dist / 16.0))
    hue_sim = 0.55
    if float(np.sum(hue_a)) > 1e-6 and float(np.sum(hue_b)) > 1e-6:
        hue_sim = float(np.clip(np.dot(hue_a, hue_b), 0.0, 1.0))
    # 明黄 vs 白/米：色度差大时压低色相虚高
    if abs(chroma_a - chroma_b) >= 18.0 and max(chroma_a, chroma_b) >= 22.0:
        hue_sim = min(hue_sim, 0.42)
    return float(np.clip(0.40 * chroma_sim + 0.38 * light_sim + 0.22 * hue_sim, 0.0, 1.0))


def extract_garment_signature(bgr: np.ndarray) -> Optional[List[float]]:
    """可缓存的上衣外观签名：LAB 均值 + 36 维色相直方图。"""
    if bgr is None or bgr.size == 0:
        return None
    clean = strip_segmentation_border(bgr)
    region = _center_garment_region(clean)
    if region.size == 0:
        return None
    mask = _garment_pixel_mask(region)
    la, aa, ab, hue_hist = _garment_lab_and_hue(region, mask)
    return [la, aa, ab, *hue_hist.tolist()]


def compare_garment_signature(sig_a: List[float], sig_b: List[float]) -> float:
    if not sig_a or not sig_b or len(sig_a) < 39 or len(sig_b) < 39:
        return -1.0
    hue_a = np.asarray(sig_a[3:39], dtype=np.float32)
    hue_b = np.asarray(sig_b[3:39], dtype=np.float32)
    return _score_garment_features(
        float(sig_a[0]), float(sig_a[1]), float(sig_a[2]), hue_a,
        float(sig_b[0]), float(sig_b[1]), float(sig_b[2]), hue_b,
    )


def compare_garment_appearance(bgr_a: np.ndarray, bgr_b: np.ndarray) -> float:
    """对比上衣外观：LAB 亮度 + 色度 + 细粒度色相，区分橄榄绿/米黄/浅黄。"""
    if bgr_a is None or bgr_b is None or bgr_a.size == 0 or bgr_b.size == 0:
        return 0.0
    sig_a = extract_garment_signature(bgr_a)
    sig_b = extract_garment_signature(bgr_b)
    if not sig_a or not sig_b:
        return 0.0
    scored = compare_garment_signature(sig_a, sig_b)
    return scored if scored >= 0 else 0.0


def extract_hue_signature(bgr: np.ndarray) -> Optional[List[float]]:
    """提取上身衣着颜色签名：各色桶占躯干像素比 + 饱和度占比。"""
    profile = extract_clothing_color_profile(bgr)
    if not profile:
        return None
    buckets = profile.get("buckets") or []
    if len(buckets) < 5:
        return None

    torso = _upper_torso_region(bgr)
    total = float(max(torso.shape[0] * torso.shape[1], 1))
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    mask = _clothing_hsv_mask(hsv, min_sat=55)
    colored_ratio = float(np.count_nonzero(mask)) / total

    sat_ratio = float(profile.get("sat_ratio_40") or 0.0)
    neutral_flag = 1.0 if profile.get("is_neutral") else 0.0
    # [红, 黄, 绿, 蓝, 其它, 有色像素占比, 饱和占比, 是否中性衣]
    raw = [
        buckets[0] * colored_ratio,
        buckets[1] * colored_ratio,
        buckets[2] * colored_ratio,
        buckets[3] * colored_ratio,
        buckets[4] * colored_ratio,
        colored_ratio,
        sat_ratio,
        neutral_flag,
    ]
    vec = np.asarray(raw, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        return None
    return (vec / norm).tolist()


def extract_color_signature(bgr: np.ndarray) -> Optional[List[float]]:
    """提取上半身/全身 HSV 颜色分布，用于衣着颜色匹配。"""
    if bgr is None or bgr.size == 0:
        return None
    h, w = bgr.shape[:2]
    if h < 4 or w < 4:
        return None

    upper = _upper_torso_region(bgr)
    lower = bgr[int(h * 0.55) :, :] if h > 8 else upper

    parts = []
    for region in (upper, lower):
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 12], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        parts.append(hist.flatten().astype(np.float32))

    hue = extract_hue_signature(bgr)
    if hue:
        parts.append(np.asarray(hue, dtype=np.float32))

    vec = np.concatenate(parts)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-8:
        return None
    return (vec / norm).tolist()


def compare_color_similarity(sig_a: List[float], sig_b: List[float]) -> float:
    if not sig_a or not sig_b:
        return 0.0
    a = np.asarray(sig_a, dtype=np.float32)
    b = np.asarray(sig_b, dtype=np.float32)
    # 颜色直方图前缀固定 576 维；色相签名升级后总长不一致，只比直方图部分
    hist_len = 24 * 12 * 2
    if a.shape != b.shape:
        if a.size >= hist_len and b.size >= hist_len:
            a = a[:hist_len]
            b = b[:hist_len]
        else:
            return 0.0
    return float(np.clip(np.dot(a, b), 0.0, 1.0))


def extract_clothing_signature(bgr: np.ndarray) -> Optional[List[float]]:
    """可缓存的衣着概况签名，用于搜索时快速颜色否决。"""
    profile = extract_clothing_color_profile(bgr)
    if not profile:
        return None
    buckets = (profile.get("buckets") or [])[:5]
    if len(buckets) < 5:
        return None
    return [
        float(profile.get("sat_ratio_40") or 0.0),
        float(profile.get("red_yellow_ratio") or 0.0),
        float(profile.get("colored_ratio") or 0.0),
        1.0 if profile.get("is_neutral") else 0.0,
        *[float(x) for x in buckets],
    ]


def _profile_from_clothing_signature(sig: List[float]) -> Optional[Dict[str, Any]]:
    if not sig or len(sig) < 9:
        return None
    return {
        "sat_ratio_40": float(sig[0]),
        "red_yellow_ratio": float(sig[1]),
        "colored_ratio": float(sig[2]),
        "is_neutral": float(sig[3]) >= 0.5,
        "buckets": [float(sig[4]), float(sig[5]), float(sig[6]), float(sig[7]), float(sig[8]), 0.0],
    }


def compare_clothing_signature(sig_a: List[float], sig_b: List[float]) -> float:
    profile_a = _profile_from_clothing_signature(sig_a)
    profile_b = _profile_from_clothing_signature(sig_b)
    if not profile_a or not profile_b:
        return -1.0
    return compare_clothing_color_profile(profile_a, profile_b)


def compare_hue_signature(sig_a: List[float], sig_b: List[float]) -> float:
    """对比缓存的色相/衣着签名，含工装色冲突检测。"""
    if not sig_a or not sig_b:
        return 0.0
    if len(sig_a) >= 9 and len(sig_b) >= 9:
        return compare_clothing_signature(sig_a, sig_b)
    if len(sig_a) == len(sig_b) and len(sig_a) >= 8:
        neutral_a = float(sig_a[-1]) >= 0.45
        neutral_b = float(sig_b[-1]) >= 0.45
        if neutral_a != neutral_b:
            return 0.20
        ry_a = float(sig_a[0] + sig_a[1])
        ry_b = float(sig_b[0] + sig_b[1])
        if ry_a >= 0.12 and ry_b <= 0.04:
            return 0.22
        if ry_b >= 0.12 and ry_a <= 0.04:
            return 0.22
        return float(np.clip(np.dot(np.asarray(sig_a, dtype=np.float32), np.asarray(sig_b, dtype=np.float32)), 0.0, 1.0))
    return 0.0


def compare_hue_similarity(bgr_a: np.ndarray, bgr_b: np.ndarray) -> float:
    profile_a = extract_clothing_color_profile(bgr_a)
    profile_b = extract_clothing_color_profile(bgr_b)
    if profile_a and profile_b:
        return compare_clothing_color_profile(profile_a, profile_b)

    hue_a = extract_hue_signature(bgr_a)
    hue_b = extract_hue_signature(bgr_b)
    if not hue_a or not hue_b:
        return 0.0
    return compare_hue_signature(hue_a, hue_b)
