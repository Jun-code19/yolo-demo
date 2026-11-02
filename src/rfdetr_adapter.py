"""RF-DETR 推理适配器：输出兼容 Ultralytics Results 的最小结构，供现有检测任务复用。"""
from __future__ import annotations

import logging
import os
import warnings
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)


@contextmanager
def _suppress_rfdetr_noise():
    """屏蔽 rfdetr 依赖在加载期打出的已知噪音（非业务错误）。"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module=r"pydantic\..*")
        warnings.filterwarnings("ignore", category=FutureWarning, module=r"torch\.jit\..*")
        warnings.filterwarnings(
            "ignore",
            message=r".*protected namespace \"model_\".*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r".*torch\.jit\.script.*deprecated.*",
            category=FutureWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r".*Pydantic serializer warnings.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r".*RFDETR(Base|LargeDeprecated|SegPreview).*deprecated.*",
            category=FutureWarning,
        )
        yield

# 默认 COCO 80 类（连续下标 0-79，与前端 target_classes / YOLO 一致）
_COCO80 = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]

# RF-DETR 预训练权重输出的是 COCO 稀疏 category_id（1-90），需映射到连续 0-79
_COCO_CATEGORY_IDS = [
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
    27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 49, 50, 51,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 67, 70, 72, 73, 74, 75, 76, 77,
    78, 79, 80, 81, 82, 84, 85, 86, 87, 88, 89, 90,
]
_COCO_ID_TO_CONTIG = {cid: i for i, cid in enumerate(_COCO_CATEGORY_IDS)}
_COCO_NAME_TO_CONTIG = {name: i for i, name in enumerate(_COCO80)}


def default_coco_class_names() -> Dict[int, str]:
    return {i: name for i, name in enumerate(_COCO80)}


def resolve_contiguous_class_id(
    raw_id: int,
    class_name: Optional[str] = None,
    names: Optional[Dict[int, str]] = None,
) -> int:
    """将 RF-DETR/COCO 类别对齐为连续下标，供 target_classes 过滤。"""
    if class_name:
        name = str(class_name).strip()
        if names:
            for k, v in names.items():
                if str(v) == name:
                    return int(k)
        if name in _COCO_NAME_TO_CONTIG:
            return _COCO_NAME_TO_CONTIG[name]
    rid = int(raw_id)
    if rid in _COCO_ID_TO_CONTIG:
        return _COCO_ID_TO_CONTIG[rid]
    return rid


def normalize_backend(value: Optional[str]) -> str:
    raw = (value or "yolo").strip().lower()
    if raw in ("rfdetr", "rf-detr", "rf_detr"):
        return "rfdetr"
    return "yolo"


class _FakeBox:
    def __init__(self, xyxy: List[float], conf: float, cls_id: int):
        # 形状对齐 Ultralytics Boxes 单条记录，便于 .item() / [0] / .numpy()[0]
        self.xyxy = torch.tensor([xyxy], dtype=torch.float32)
        self.conf = torch.tensor([conf], dtype=torch.float32)
        self.cls = torch.tensor([cls_id], dtype=torch.float32)


class _FakeBoxes:
    def __init__(self, boxes: List[_FakeBox]):
        self._boxes = boxes

    def __iter__(self):
        return iter(self._boxes)

    def __len__(self):
        return len(self._boxes)

    @property
    def data(self):
        """兼容 Ultralytics Boxes.data：Nx6 [x1,y1,x2,y2,conf,cls]。"""
        if not self._boxes:
            return torch.zeros((0, 6), dtype=torch.float32)
        rows = []
        for box in self._boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            rows.append([
                float(x1), float(y1), float(x2), float(y2),
                float(box.conf[0].item()),
                float(box.cls[0].item()),
            ])
        return torch.tensor(rows, dtype=torch.float32)


class _FakeResult:
    def __init__(self, boxes: List[_FakeBox], names: Dict[int, str], speed_ms: float = 0.0):
        self.boxes = _FakeBoxes(boxes) if boxes else None
        self.names = names
        self.masks = None
        self.speed = {"preprocess": 0.0, "inference": speed_ms, "postprocess": 0.0}


class RfDetrAdapter:
    """封装 rfdetr 包，对外行为接近 YOLO/OnnxYoloAdapter。"""

    names: Dict[int, str]

    def __init__(
        self,
        model_path: str,
        class_names: Optional[Dict[int, str]] = None,
        use_cuda: bool = False,
        model_size: str = "base",
    ):
        with _suppress_rfdetr_noise():
            try:
                import rfdetr  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    "检测服务无法 import rfdetr（请确认 detect-server 进程使用的 Python "
                    f"已安装该包，Python>=3.10）。底层错误: {type(exc).__name__}: {exc}"
                ) from exc

            self.model_path = model_path
            self.use_cuda = bool(use_cuda and torch.cuda.is_available())
            self.names = dict(class_names) if class_names else default_coco_class_names()
            self._model = self._load_model(model_path, model_size=model_size)
            if self.use_cuda:
                try:
                    inner = getattr(self._model, "model", None)
                    if inner is not None and hasattr(inner, "to"):
                        inner.to("cuda")
                except Exception as exc:
                    logger.warning("RF-DETR 迁到 CUDA 失败，将使用默认设备: %s", exc)

            try:
                if hasattr(self._model, "inference"):
                    dtype = torch.float16 if self.use_cuda else torch.float32
                    self._model.inference(compile=False, dtype=dtype)
            except Exception as exc:
                logger.debug("RF-DETR inference() 优化跳过: %s", exc)

        logger.info(
            "RfDetrAdapter 已加载 path=%s cuda=%s classes=%s",
            model_path,
            self.use_cuda,
            len(self.names),
        )

    @staticmethod
    def _infer_size_from_path(model_path: str) -> Optional[str]:
        name = os.path.basename(model_path or "").lower()
        for key in ("nano", "small", "medium", "base", "xlarge", "2xlarge", "large"):
            if key in name:
                return "xlarge" if key == "2xlarge" else key
        return None

    @staticmethod
    def _load_model(model_path: str, model_size: str = "nano"):
        """按规格用 pretrain_weights 加载；仅 size=auto 且无法推断时才试 from_checkpoint。"""
        import rfdetr

        size = (model_size or "").strip().lower()
        # 上传后的 UUID 文件名没有 model_name，from_checkpoint 必失败；
        # 已明确 nano/small/... 时直接构造，不再打那条「失败回退」日志。
        if size in ("", "auto"):
            size = RfDetrAdapter._infer_size_from_path(model_path) or ""
            if not size and hasattr(rfdetr, "RFDETR") and hasattr(rfdetr.RFDETR, "from_checkpoint"):
                try:
                    return rfdetr.RFDETR.from_checkpoint(model_path)
                except Exception as exc:
                    logger.info("RFDETR.from_checkpoint 失败，回退规格构造: %s", exc)
            size = size or "nano"

        ctor_map = {
            "nano": "RFDETRNano",
            "small": "RFDETRSmall",
            "s": "RFDETRSmall",
            "medium": "RFDETRMedium",
            "m": "RFDETRMedium",
            "base": "RFDETRBase",
            "b": "RFDETRBase",
            "large": "RFDETRLarge",
            "l": "RFDETRLarge",
            "xlarge": "RFDETRXLarge",
            "xl": "RFDETRXLarge",
        }
        ctor_name = ctor_map.get(size)
        if not ctor_name:
            raise RuntimeError(
                f"未知 RF-DETR 规格 rfdetr_size={model_size!r}，"
                "请使用 nano/small/medium/base/large/xlarge"
            )
        ctor = getattr(rfdetr, ctor_name, None)
        if ctor is None:
            raise RuntimeError(f"当前 rfdetr 包不支持 {ctor_name}，请升级 rfdetr")
        logger.info("使用 %s(pretrain_weights=...) 加载 RF-DETR，size=%s", ctor_name, size)
        return ctor(pretrain_weights=model_path)

    def predict_numpy(
        self,
        frame_bgr: np.ndarray,
        *,
        confidence: float = 0.5,
    ) -> List[_FakeBox]:
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        # rfdetr.predict 期望 RGB；关闭 source_image 以降低 CPU 内存与延迟
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        try:
            detections = self._model.predict(
                rgb,
                threshold=float(confidence),
                include_source_image=False,
            )
        except TypeError:
            detections = self._model.predict(rgb, threshold=float(confidence))
        boxes: List[_FakeBox] = []
        if detections is None:
            return boxes

        # supervision.Detections
        xyxy = getattr(detections, "xyxy", None)
        conf = getattr(detections, "confidence", None)
        cls_ids = getattr(detections, "class_id", None)
        if xyxy is None:
            return boxes

        class_names_arr = None
        data = getattr(detections, "data", None) or {}
        if isinstance(data, dict):
            class_names_arr = data.get("class_name")

        n = len(xyxy)
        for i in range(n):
            score = float(conf[i]) if conf is not None else 0.0
            raw_cid = int(cls_ids[i]) if cls_ids is not None else 0
            cname = None
            if class_names_arr is not None and i < len(class_names_arr):
                cname = str(class_names_arr[i])
            cid = resolve_contiguous_class_id(raw_cid, cname, self.names)
            box = [float(v) for v in xyxy[i]]
            boxes.append(_FakeBox(box, score, cid))
        return boxes

    def __call__(self, frame: np.ndarray, **kwargs) -> List[_FakeResult]:
        conf = float(kwargs.get("conf", kwargs.get("confidence", 0.5)))
        import time

        t0 = time.perf_counter()
        boxes = self.predict_numpy(frame, confidence=conf)
        ms = (time.perf_counter() - t0) * 1000.0
        return [_FakeResult(boxes, self.names, speed_ms=ms)]


def load_rfdetr_class_names(
    model_path: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[int, str]:
    """上传校验：尝试从 checkpoint / 参数解析类别，否则默认 COCO80。"""
    params = parameters or {}
    raw_classes = params.get("classes") if isinstance(params, dict) else None
    if isinstance(raw_classes, dict) and raw_classes:
        return {int(k): str(v) for k, v in raw_classes.items()}
    if isinstance(raw_classes, (list, tuple)) and raw_classes:
        return {i: str(v) for i, v in enumerate(raw_classes)}

    # 尝试读 checkpoint 内类别
    try:
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
        if isinstance(ckpt, dict):
            for key in ("class_names", "classes", "names"):
                raw = ckpt.get(key)
                if isinstance(raw, dict) and raw:
                    return {int(k): str(v) for k, v in raw.items()}
                if isinstance(raw, (list, tuple)) and raw:
                    return {i: str(v) for i, v in enumerate(raw)}
            args = ckpt.get("args")
            if args is not None:
                for attr in ("class_names", "classes", "names"):
                    raw = args.get(attr) if isinstance(args, dict) else getattr(args, attr, None)
                    if isinstance(raw, dict) and raw:
                        return {int(k): str(v) for k, v in raw.items()}
                    if isinstance(raw, (list, tuple)) and raw:
                        return {i: str(v) for i, v in enumerate(raw)}
    except Exception as exc:
        logger.debug("读取 RF-DETR checkpoint 类别失败: %s", exc)

    # 能 import 则顺便校验包可用；类别仍用 COCO
    try:
        import rfdetr  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "检测服务无法 import rfdetr（需在 detect-server 的运行 Python 中可用，"
            f"Python>=3.10）。底层错误: {type(exc).__name__}: {exc}"
        ) from exc

    return default_coco_class_names()
