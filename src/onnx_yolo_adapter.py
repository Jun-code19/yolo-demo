"""ONNX YOLO 检测适配器：绕过 Ultralytics 对静态 ONNX 硬编码 images 输入名的问题。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch

logger = logging.getLogger(__name__)


def is_onnx_model_path(model_path: str) -> bool:
    return str(model_path or "").lower().endswith(".onnx")


def _resolve_image_input(session) -> str:
    inputs = session.get_inputs()
    preferred = ("images", "input", "input.1", "data", "x")
    for name in preferred:
        for inp in inputs:
            inp_type = (inp.type or "").lower()
            if inp.name == name and "float" in inp_type:
                return inp.name
    for inp in inputs:
        inp_type = (inp.type or "").lower()
        if "float" not in inp_type:
            continue
        shape = inp.shape or []
        if len(shape) == 4:
            return inp.name
    details = [(inp.name, inp.type, inp.shape) for inp in inputs]
    raise RuntimeError(f"ONNX 模型缺少可用的浮点图像输入，当前输入: {details}")


def _resolve_imgsz(session, input_name: str, default: int = 640) -> int:
    for inp in session.get_inputs():
        if inp.name != input_name:
            continue
        shape = inp.shape or []
        if len(shape) == 4:
            for dim in shape[2:4]:
                if isinstance(dim, int) and dim > 0:
                    return int(dim)
    return default


def _normalize_prediction_tensor(pred: torch.Tensor) -> torch.Tensor:
    if pred.ndim != 3:
        return pred
    _, dim1, dim2 = pred.shape
    if dim1 > dim2 and dim2 <= 256:
        return pred.transpose(-1, -2)
    return pred


class OnnxYoloAdapter:
    """使用 onnxruntime 直接推理，兼容非标准输入名的 YOLO ONNX 模型。"""

    names: Dict[int, str]

    def __init__(
        self,
        model_path: str,
        class_names: Optional[Dict[int, str]] = None,
        use_cuda: bool = False,
        imgsz: Optional[int] = None,
    ):
        import onnxruntime as ort

        providers = ["CPUExecutionProvider"]
        if use_cuda and "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")

        self.model_path = model_path
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = _resolve_image_input(self.session)
        self.output_names = [item.name for item in self.session.get_outputs()]
        self.imgsz = imgsz or _resolve_imgsz(self.session, self.input_name)
        self.names = class_names or {0: "object"}
        self.end2end = False
        logger.info(
            "ONNX 适配器已加载: input=%s outputs=%s imgsz=%s",
            self.input_name,
            self.output_names,
            self.imgsz,
        )

    def __call__(
        self,
        source: Union[np.ndarray, List[np.ndarray]],
        conf: float = 0.25,
        iou: float = 0.45,
        max_det: int = 300,
        verbose: bool = False,
        device=None,
        half: bool = False,
        **kwargs,
    ) -> List[Any]:
        from ultralytics.data.augment import LetterBox
        from ultralytics.engine.results import Results
        from ultralytics.utils.ops import non_max_suppression, scale_boxes

        del verbose, device, half, kwargs

        frames = [source] if isinstance(source, np.ndarray) else list(source)
        letterbox = LetterBox(new_shape=(self.imgsz, self.imgsz), auto=False, stride=32)
        results: List[Any] = []

        for im0 in frames:
            if im0 is None or not isinstance(im0, np.ndarray) or im0.size == 0:
                continue

            t0 = time.perf_counter()
            im = letterbox(image=im0)
            im = im[..., ::-1].transpose(2, 0, 1)
            im = np.ascontiguousarray(im, dtype=np.float32) / 255.0
            im = im[None]
            t1 = time.perf_counter()

            outputs = self.session.run(self.output_names, {self.input_name: im})
            t2 = time.perf_counter()

            pred = _normalize_prediction_tensor(torch.from_numpy(outputs[0].astype(np.float32)))
            preds = non_max_suppression(
                pred,
                conf_thres=conf,
                iou_thres=iou,
                max_det=max_det,
                nc=len(self.names),
                end2end=self.end2end,
            )
            t3 = time.perf_counter()

            det = preds[0]
            im_tensor = torch.from_numpy(im)
            if det is not None and len(det):
                det = det.clone()
                det[:, :4] = scale_boxes(im_tensor.shape[2:], det[:, :4], im0.shape)

            speed = {
                "preprocess": (t1 - t0) * 1000,
                "inference": (t2 - t1) * 1000,
                "postprocess": (t3 - t2) * 1000,
            }
            results.append(
                Results(
                    orig_img=im0,
                    path="",
                    names=self.names,
                    boxes=det if det is not None and len(det) else None,
                    speed=speed,
                )
            )

        return results
