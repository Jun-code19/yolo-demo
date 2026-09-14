"""查询图预处理：从上传照片中自动抠出最大 person 区域。"""
import logging
from typing import Optional

import cv2
import numpy as np

from src.person_search.utils import crop_person, parse_bbox

logger = logging.getLogger(__name__)

_yolo_model = None


def _looks_like_person_crop(bgr: np.ndarray) -> bool:
    if bgr is None or bgr.size == 0:
        return False
    h, w = bgr.shape[:2]
    if h < 80 or w < 32:
        return False
    ratio = h / max(w, 1)
    return ratio >= 1.2


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO

        model_path = __import__("os").getenv("PERSON_SEARCH_YOLO_MODEL", "yolov8n.pt")
        _yolo_model = YOLO(model_path)
        logger.info("人员搜索查询抠图模型已加载: %s", model_path)
        return _yolo_model
    except Exception as exc:
        logger.warning("查询图 YOLO 抠人不可用，将使用原图: %s", exc)
        return None


def _detect_largest_person(bgr: np.ndarray) -> Optional[np.ndarray]:
    model = _get_yolo_model()
    if model is None:
        return None
    try:
        results = model(bgr, classes=[0], verbose=False, conf=0.35)
        best = None
        best_area = 0
        for result in results:
            names = getattr(result, "names", {}) or {}
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls.item()) if box.cls is not None else -1
                name = str(names.get(cls_id, "")).lower()
                if cls_id != 0 and name not in {"person", "people", "human", "行人", "人"}:
                    continue
                xyxy = box.xyxy.cpu().numpy().astype(int).flatten()
                if xyxy.size < 4:
                    continue
                x1, y1, x2, y2 = xyxy[:4]
                area = max(0, x2 - x1) * max(0, y2 - y1)
                if area > best_area:
                    best_area = area
                    best = (x1, y1, x2, y2)
        if not best:
            return None
        return crop_person(bgr, best, padding=0.06)
    except Exception as exc:
        logger.warning("查询图 YOLO 抠人失败: %s", exc)
        return None


def prepare_query_image(bgr: np.ndarray) -> np.ndarray:
    """上传图若已是行人抠图则直接用，否则尝试 YOLO 抠出最大 person。"""
    if bgr is None or bgr.size == 0:
        return bgr
    if _looks_like_person_crop(bgr):
        return bgr
    crop = _detect_largest_person(bgr)
    if crop is not None and crop.size > 0:
        logger.info("查询图已自动抠人: %sx%s -> %sx%s", bgr.shape[1], bgr.shape[0], crop.shape[1], crop.shape[0])
        return crop
    return bgr
