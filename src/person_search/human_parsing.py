"""Human Parsing：快速区域分割（默认）+ 可选 LIP ONNX 精细分割。"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

import cv2
import numpy as np

from src.person_search.model_assets import get_parsing_onnx_path
from src.person_search.utils import strip_segmentation_border, _silhouette_mask

logger = logging.getLogger(__name__)

# LIP 20 类（与 parsing_lip.onnx 常见导出一致）
LIP_LABELS = {
    0: "background",
    1: "hat",
    2: "hair",
    3: "glove",
    4: "sunglasses",
    5: "upper_clothes",
    6: "dress",
    7: "coat",
    8: "socks",
    9: "pants",
    10: "jumpsuits",
    11: "scarf",
    12: "skirt",
    13: "face",
    14: "left_arm",
    15: "right_arm",
    16: "left_leg",
    17: "right_leg",
    18: "left_shoe",
    19: "right_shoe",
}

UPPER_IDS = {5, 6, 7, 11}
LOWER_IDS = {9, 10, 12}
SHOE_IDS = {8, 18, 19}


@dataclass
class ParseResult:
    source: str
    upper_mask: np.ndarray
    lower_mask: np.ndarray
    person_mask: np.ndarray
    label_map: Optional[np.ndarray] = None


_parser = None


def _estimate_hip_row(person_mask: np.ndarray) -> int:
    h, _ = person_mask.shape[:2]
    if h < 8 or not np.any(person_mask):
        return int(h * 0.54)

    y_start = int(h * 0.28)
    y_end = int(h * 0.78)
    widths = []
    for y in range(y_start, y_end):
        cols = np.where(person_mask[y])[0]
        if cols.size:
            widths.append((y, float(cols[-1] - cols[0] + 1)))
    if len(widths) < 3:
        return int(h * 0.54)

    max_width = max(item[1] for item in widths)
    hip_candidates = [y for y, w in widths if w >= max_width * 0.88]
    if hip_candidates:
        return int(np.median(hip_candidates))
    return int(h * 0.54)


def fast_zone_parse(bgr: np.ndarray) -> ParseResult:
    clean = strip_segmentation_border(bgr)
    h, w = clean.shape[:2]
    person_mask = _silhouette_mask(clean)
    if not np.any(person_mask):
        person_mask = np.ones((h, w), dtype=bool)

    hip_y = _estimate_hip_row(person_mask)
    upper_mask = person_mask.copy()
    upper_mask[hip_y:, :] = False
    lower_mask = person_mask.copy()
    lower_mask[:hip_y, :] = False
    return ParseResult(
        source="fast_zone",
        upper_mask=upper_mask,
        lower_mask=lower_mask,
        person_mask=person_mask,
    )


class OnnxLipParser:
    """可选 LIP ONNX 解析（输入通常为 512/473，输出 argmax label map）。"""

    def __init__(self, model_path: str):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, int(os.getenv("PERSON_PARSING_THREADS", "4")))
        self.session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        shape = self.session.get_inputs()[0].shape
        self.input_h = int(shape[2]) if len(shape) == 4 and isinstance(shape[2], int) else 512
        self.input_w = int(shape[3]) if len(shape) == 4 and isinstance(shape[3], int) else 384
        logger.info("LIP ONNX 解析已加载: %s (%sx%s)", model_path, self.input_w, self.input_h)

    def parse(self, bgr: np.ndarray) -> ParseResult:
        clean = strip_segmentation_border(bgr)
        h, w = clean.shape[:2]
        resized = cv2.resize(clean, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = ((rgb - mean) / std).transpose(2, 0, 1)[None, ...].astype(np.float32)

        outputs = self.session.run(None, {self.input_name: tensor})
        logits = outputs[0]
        if logits.ndim == 4:
            label_small = np.argmax(logits[0], axis=0).astype(np.int32)
        elif logits.ndim == 3:
            label_small = np.argmax(logits, axis=0).astype(np.int32)
        else:
            return fast_zone_parse(bgr)

        label_map = cv2.resize(label_small, (w, h), interpolation=cv2.INTER_NEAREST)
        upper_mask = np.isin(label_map, list(UPPER_IDS))
        lower_mask = np.isin(label_map, list(LOWER_IDS))
        person_mask = label_map > 0
        if not np.any(upper_mask):
            upper_mask = fast_zone_parse(bgr).upper_mask
        if not np.any(lower_mask):
            lower_mask = fast_zone_parse(bgr).lower_mask
        return ParseResult(
            source="onnx_lip",
            upper_mask=upper_mask,
            lower_mask=lower_mask,
            person_mask=person_mask,
            label_map=label_map,
        )


class HumanParser:
    def __init__(self) -> None:
        self._onnx: Optional[OnnxLipParser] = None
        path = get_parsing_onnx_path()
        if path:
            try:
                self._onnx = OnnxLipParser(path)
            except Exception as exc:
                logger.warning("LIP ONNX 解析加载失败，回退快速分割: %s", exc)

    @property
    def mode(self) -> str:
        return "onnx_lip" if self._onnx is not None else "fast_zone"

    def parse(self, bgr: np.ndarray) -> ParseResult:
        if bgr is None or bgr.size == 0:
            h, w = 8, 8
            empty = np.zeros((h, w), dtype=bool)
            return ParseResult(source="empty", upper_mask=empty, lower_mask=empty, person_mask=empty)
        if self._onnx is not None:
            try:
                return self._onnx.parse(bgr)
            except Exception as exc:
                logger.debug("ONNX 解析失败，回退 fast_zone: %s", exc)
        return fast_zone_parse(bgr)


def get_human_parser() -> HumanParser:
    global _parser
    if _parser is None:
        _parser = HumanParser()
    return _parser
