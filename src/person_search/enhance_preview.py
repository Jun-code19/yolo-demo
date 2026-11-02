"""显示用抠图增强（柔和 2×）。

仅用于人员搜索详情预览，不写回图库、不参与 ReID 特征提取。
小目标监控抠图噪点多，强锐化/CLAHE 会更糊更脏，故采用：轻降噪 → 放大 → 极轻锐化。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_ALLOWED_PREFIXES = (
    "storage/person_crops/",
    "storage/events/",
    "person_crops/",
    "events/",
)


def _resolve_safe_image_path(raw_path: str) -> Path:
    if not raw_path or not str(raw_path).strip():
        raise ValueError("路径为空")
    normalized = str(raw_path).replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        raise ValueError("非法路径")
    if not any(normalized.startswith(p) for p in _ALLOWED_PREFIXES):
        raise ValueError("仅允许预览 storage 下的人员抠图/事件图")

    candidate = Path(normalized)
    if not candidate.is_file():
        alt = Path("storage") / normalized[len("storage/") :] if normalized.startswith("storage/") else None
        if alt is not None and alt.is_file():
            candidate = alt
        else:
            raise FileNotFoundError(f"文件不存在: {normalized}")
    return candidate.resolve()


def enhance_bgr_for_display(
    bgr: np.ndarray,
    *,
    scale: float = 2.0,
) -> np.ndarray:
    """柔和 2×：先轻降噪再放大，避免锐化把压缩块/噪点放大。"""
    if bgr is None or bgr.size == 0:
        raise ValueError("空图像")
    scale = float(np.clip(scale, 1.0, 4.0))
    h, w = bgr.shape[:2]

    # 1) 轻降噪（小图用双边，保边去块）
    src = bgr
    try:
        if min(h, w) < 220:
            src = cv2.bilateralFilter(bgr, d=5, sigmaColor=35, sigmaSpace=35)
        else:
            src = cv2.bilateralFilter(bgr, d=5, sigmaColor=25, sigmaSpace=25)
    except Exception as exc:
        logger.debug("双边滤波跳过: %s", exc)
        src = bgr

    # 2) 放大：CUBIC 对噪声小图通常比 Lanczos 更顺、少振铃
    max_side = int(os.getenv("PERSON_SEARCH_ENHANCE_MAX_SIDE", "1280"))
    out_w = int(round(w * scale))
    out_h = int(round(h * scale))
    if max(out_w, out_h) > max_side:
        ratio = max_side / float(max(out_w, out_h))
        out_w = max(1, int(round(out_w * ratio)))
        out_h = max(1, int(round(out_h * ratio)))
    up = cv2.resize(src, (out_w, out_h), interpolation=cv2.INTER_CUBIC)

    # 3) 极轻锐化（默认几乎关；过强会更糊）
    amount = float(os.getenv("PERSON_SEARCH_ENHANCE_SHARP", "0.12"))
    amount = float(np.clip(amount, 0.0, 0.35))
    if amount > 0.01:
        blur = cv2.GaussianBlur(up, (0, 0), sigmaX=0.8)
        up = cv2.addWeighted(up, 1.0 + amount, blur, -amount, 0)

    return up


def build_enhanced_preview_jpeg(
    raw_path: str,
    *,
    scale: float = 2.0,
    jpeg_quality: int = 92,
) -> Tuple[bytes, str]:
    """读取原图 → 显示增强 → JPEG bytes。返回 (bytes, resolved_path)。"""
    path = _resolve_safe_image_path(raw_path)
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"无法解码图片: {path}")
    enhanced = enhance_bgr_for_display(bgr, scale=scale)
    ok, buf = cv2.imencode(
        ".jpg",
        enhanced,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(np.clip(jpeg_quality, 60, 95))],
    )
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    return buf.tobytes(), str(path)
