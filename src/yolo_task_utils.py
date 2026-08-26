"""YOLO 任务类型解析、分割 mask 处理与绘制"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Sequence

import cv2
import numpy as np
import torch

logger = logging.getLogger(__name__)


def resolve_yolo_task(models_type: Optional[str]) -> str:
    """将 models_type 映射为 Ultralytics task 参数。"""
    task = (models_type or "").lower()
    if task == "pose":
        return "pose"
    if task == "segmentation":
        return "segment"
    return "detect"


def is_segmentation_type(models_type: Optional[str]) -> bool:
    return (models_type or "").lower() == "segmentation"


def is_face_type(models_type: Optional[str]) -> bool:
    return (models_type or "").lower() == "face"


def event_description_for_type(models_type: Optional[str], count: int) -> str:
    task = (models_type or "").lower()
    if task == "face":
        return f"检测到{count}张人脸"
    if task == "segmentation":
        return f"检测到{count}个分割目标"
    if task == "pose":
        return f"检测到{count}个姿态目标"
    return f"检测到{count}个目标"


def simplify_polygon(points: Sequence[Sequence[float]], max_points: int = 48) -> List[List[float]]:
    if not points or len(points) < 3:
        return [list(p) for p in points] if points else []

    contour = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    peri = cv2.arcLength(contour, True)
    epsilon = max(peri * 0.002, 1.0)
    approx = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
    simplified = approx.tolist()
    if len(simplified) > max_points:
        step = max(1, len(simplified) // max_points)
        simplified = simplified[::step][:max_points]
    return simplified


def process_yolo_results(
    results,
    target_class: Sequence[str],
    include_segmentation: bool = False,
) -> List[Dict[str, Any]]:
    """从 Ultralytics 推理结果提取检测列表（可选含 mask 多边形）。"""
    detections: List[Dict[str, Any]] = []
    target_set = {str(cls_id) for cls_id in (target_class or [])}

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        masks = getattr(result, "masks", None)
        mask_xy_list = masks.xy if masks is not None and hasattr(masks, "xy") else None

        for idx, box in enumerate(boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf.item())
            class_id = int(box.cls.item())
            if target_set and str(class_id) not in target_set:
                continue

            class_name = result.names[class_id]
            detection: Dict[str, Any] = {
                "bbox": [x1, y1, x2, y2],
                "confidence": confidence,
                "class_id": class_id,
                "class_name": class_name,
            }

            if include_segmentation and mask_xy_list is not None and idx < len(mask_xy_list):
                polygon = mask_xy_list[idx]
                if polygon is not None and len(polygon) >= 3:
                    detection["has_mask"] = True
                    detection["mask_polygon"] = simplify_polygon(polygon.tolist())

            detections.append(detection)

    return detections


def draw_segmentation_detections(
    img,
    detections: List[Dict[str, Any]],
    get_class_color: Callable[[int], Sequence[int]],
    alpha: float = 0.42,
    draw_boxes: bool = True,
):
    """在 BGR 图像上绘制分割 mask 与可选检测框。"""
    if img is None or not detections:
        return img

    overlay = img.copy()
    has_mask = False
    for det in detections:
        polygon = det.get("mask_polygon")
        if not polygon or len(polygon) < 3:
            continue
        has_mask = True
        cls = int(det.get("class_id", 0))
        color = tuple(int(c) for c in get_class_color(cls))
        pts = np.array(polygon, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], color)

    if has_mask:
        cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    if not draw_boxes:
        return img

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        cls = int(det.get("class_id", 0))
        conf = float(det.get("confidence", 0.0))
        color = tuple(int(c) for c in get_class_color(cls))
        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        class_name = det.get("class_name") or f"Class {cls}"
        label = f"{class_name}: {conf:.2f}"
        cv2.putText(
            img,
            label,
            (int(x1), max(int(y1) - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )
    return img


def build_detection_meta(models_type: Optional[str], detections: List[Dict[str, Any]], target_class) -> Dict[str, Any]:
    meta = {
        "current_count": len(detections),
        "target_class": target_class,
        "event_description": event_description_for_type(models_type, len(detections)),
    }
    if is_segmentation_type(models_type):
        meta["has_segmentation"] = any(d.get("has_mask") for d in detections)
    if is_face_type(models_type):
        meta["face_detection"] = True
    return meta


def normalize_yolo_class_names(names: Any) -> Dict[int, str]:
    """将 Ultralytics model.names 规范化为 {class_id: name}。"""
    if not names:
        return {}
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list):
        return {i: str(n) for i, n in enumerate(names)}
    return {}


def classes_from_parameters(parameters: Optional[Dict[str, Any]]) -> Dict[int, str]:
    """从上传参数 JSON 中读取手动指定的类别。"""
    if not parameters:
        return {}
    raw = parameters.get("classes")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {int(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {i: str(n) for i, n in enumerate(raw)}
    return {}


def is_onnx_model_path(model_path: str) -> bool:
    return os.path.splitext(model_path or "")[1].lower() == ".onnx"


def class_names_from_onnx_metadata(model_path: str) -> Dict[int, str]:
    """从 ONNX custom metadata 读取类别，避免触发 Ultralytics 自动 pip 安装。"""
    try:
        import ast
        import onnxruntime as ort

        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        meta = session.get_modelmeta().custom_metadata_map or {}
        raw_names = meta.get("names")
        if not raw_names:
            return {}
        if isinstance(raw_names, str):
            raw_names = ast.literal_eval(raw_names)
        return normalize_yolo_class_names(raw_names)
    except Exception as exc:
        logger.debug("读取 ONNX metadata 类别失败: %s", exc)
        return {}


def load_detection_model(
    model_path: str,
    models_type: Optional[str],
    is_gpu: bool,
    class_names: Optional[Dict[int, str]] = None,
):
    """加载检测模型；ONNX 使用专用适配器，避免 Ultralytics io_binding 输入类型错误。"""
    from ultralytics import YOLO

    from src.env_loader import configure_ultralytics_env
    from src.onnx_yolo_adapter import OnnxYoloAdapter, is_onnx_model_path as _is_onnx

    configure_ultralytics_env()
    os.environ.setdefault("YOLO_VERBOSE", "0")

    abs_path = os.path.abspath(model_path)
    if not os.path.exists(abs_path):
        base_name = os.path.basename(abs_path)
        alt_path = os.path.abspath(os.path.join("models", base_name))
        if os.path.exists(alt_path):
            abs_path = alt_path
        else:
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

    use_cuda = torch.cuda.is_available() and is_gpu

    if _is_onnx(abs_path):
        names = class_names or class_names_from_onnx_metadata(abs_path)
        if not names:
            names = {0: "face"} if is_face_type(models_type) else {0: "object"}
        model = OnnxYoloAdapter(abs_path, names, use_cuda=use_cuda)
        infer_device = "0" if use_cuda else "cpu"
        return model, infer_device, True

    task_type = resolve_yolo_task(models_type)
    model = YOLO(abs_path, task=task_type)
    infer_device = torch.device("cuda" if use_cuda else "cpu")
    model.to(infer_device)
    if use_cuda and hasattr(model, "model") and hasattr(model.model, "half"):
        try:
            model.model.half()
        except Exception:
            pass
    return model, infer_device, False


def predict_detection_frame(
    model,
    frame: np.ndarray,
    *,
    infer_device,
    is_onnx: bool,
    confidence: float = 0.5,
    iou: float = 0.45,
    max_det: int = 300,
):
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        raise ValueError("无效的检测帧")
    frame = np.ascontiguousarray(frame)
    kwargs = {
        "conf": confidence,
        "iou": iou,
        "max_det": max_det,
        "verbose": False,
        "half": False,
        "device": infer_device,
    }
    return model(frame, **kwargs)


def load_yolo_model_classes(
    file_path: str,
    models_type: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[int, str]:
    """本地加载 YOLO/ONNX 模型并解析类别（上传校验与入库用）。"""
    from src.env_loader import configure_ultralytics_env

    configure_ultralytics_env()

    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"模型文件不存在: {abs_path}")

    ext = os.path.splitext(abs_path)[1].lower()
    if ext == ".onnx":
        classes = class_names_from_onnx_metadata(abs_path)
        if not classes:
            classes = classes_from_parameters(parameters)
        if not classes:
            raise RuntimeError(
                "ONNX 模型未解析到类别。"
                "若类别未嵌入模型，请在「参数」JSON 中填写 "
                '{"classes": {"0": "face"}} 后重试。'
            )
        return classes

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "当前环境未安装 ultralytics，无法本地校验模型。"
            "请安装依赖或在检测服务（8000）运行时上传。"
        ) from exc

    task = resolve_yolo_task(models_type)
    load_errors: List[str] = []

    candidates = []
    if ext == ".onnx":
        # ONNX 优先不带 task，兼容部分导出文件
        candidates.append(("auto", abs_path))
        candidates.append((task, abs_path))
    else:
        candidates.append((task, abs_path))
        candidates.append(("auto", abs_path))

    model = None
    for task_name, path in candidates:
        try:
            if task_name == "auto":
                model = YOLO(path)
            else:
                model = YOLO(path, task=task_name)
            break
        except Exception as exc:
            msg = str(exc)
            if "Unsupported model IR version" in msg:
                msg += (
                    "。请升级检测环境 onnxruntime>=1.19，"
                    "或用较低 opset 重新导出：yolo export model=xxx.pt format=onnx opset=12"
                )
            load_errors.append(f"{task_name}: {msg}")

    if model is None:
        detail = "；".join(load_errors[-2:]) if load_errors else "未知错误"
        hint = ""
        if ext == ".onnx":
            hint = (
                " ONNX 需为 Ultralytics 导出的 YOLO 格式，且已安装 onnxruntime。"
                "若类别未嵌入模型，可在「参数」JSON 中填写 {\"classes\": {\"0\":\"face\"}}。"
            )
        raise RuntimeError(f"无法加载模型: {detail}.{hint}")

    classes = normalize_yolo_class_names(getattr(model, "names", None))
    if not classes:
        classes = classes_from_parameters(parameters)
    if not classes:
        raise RuntimeError(
            "模型加载成功但未解析到类别。"
            "ONNX 若未内置类别，请在上传「参数」中填写 "
            '{"classes": {"0": "person", "1": "face"}} 后重试。'
        )
    return classes
