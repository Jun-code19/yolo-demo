"""组装送 VLM 的图像与 Prompt"""
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from src.inference_pipeline.prompt_registry_store import load_prompt_registry


_BBOX_RULE = (
    "能定位目标时填写 bbox：[x1,y1,x2,y2]，使用当前输入图像的像素坐标（整数）："
    "原点左上角，x 向右、y 向下，且 0≤x1<x2≤图像宽、0≤y1<y2≤图像高。"
    "必须框住目标主体本身，禁止框选地面反光、阴影或空白区域。"
)


def resolve_prompt(
    prompt_id: str,
    alert_labels: Optional[List[str]] = None,
    override: Optional[str] = None,
    image_width: Optional[int] = None,
    image_height: Optional[int] = None,
) -> Dict[str, str]:
    labels_text = "、".join(alert_labels or []) or "安全隐患"
    size_hint = ""
    if image_width and image_height:
        size_hint = (
            f"\n当前输入图像尺寸：宽 {int(image_width)} × 高 {int(image_height)} 像素。"
            f"bbox 必须使用该尺寸下的像素坐标。"
        )

    if override and override.strip():
        user = override.replace("{alert_labels}", labels_text)
        return {
            "system": (
                "你是视频监控图像分析助手。只输出 JSON，不要 markdown。"
                "必须根据实际画面填写，禁止照抄用户 Prompt 中的示例 label 或数值。"
                "命中关注告警项时 findings 必须写入对应 label（confidence 0.85~1.0）；"
                f"{_BBOX_RULE}"
                "未命中时 findings 必须为 []。"
            ),
            "user": user + size_hint,
        }

    registry = load_prompt_registry()
    entry = registry.get(prompt_id) or registry.get("general_patrol_v1", {})
    user_text = (entry.get("user_template") or "").replace("{alert_labels}", labels_text)
    return {
        "system": entry.get("system") or "你是视频监控安全巡检助手。只输出 JSON。",
        "user": user_text + size_hint,
    }


def encode_frame_for_vlm(
    frame: np.ndarray,
    max_width: int = 1280,
    jpeg_quality: int = 85,
) -> tuple:
    """缩放并编码；返回 (base64, sent_width, sent_height)。"""
    if frame is None or frame.size == 0:
        raise ValueError("空图像帧")
    img = frame
    h, w = img.shape[:2]
    if max_width and w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise ValueError("图像编码失败")
    return base64.b64encode(buf.tobytes()).decode("ascii"), int(w), int(h)


def encode_frame_to_base64(frame: np.ndarray, max_width: int = 1280, jpeg_quality: int = 85) -> str:
    b64, _, _ = encode_frame_for_vlm(frame, max_width=max_width, jpeg_quality=jpeg_quality)
    return b64


def canonicalize_bbox_to_norm(
    raw: Any,
    ref_width: int,
    ref_height: int,
) -> Optional[List[float]]:
    """将模型 bbox 转为相对 ref 图像的归一化 xyxy (0~1)。

    识别顺序：已是 0~1 → 百分比 0~100 → 像素（优先，qwen-vl-plus 实测）
    → 0~1000（仅当明显超出图像像素范围时）→ 其它按像素。
    """
    values = _extract_bbox_values(raw)
    if not values or ref_width <= 0 or ref_height <= 0:
        return None
    x1, y1, x2, y2 = values
    if x2 <= x1 or y2 <= y1:
        return None

    m = max(x1, y1, x2, y2)
    # 允许轻微越界（模型偶发 y2 略大于高）
    fit_w = ref_width * 1.2
    fit_h = ref_height * 1.2

    if m <= 1.5:
        # 已是 0~1
        pass
    elif m <= 100:
        # 百分比 0~100
        x1, x2 = x1 / 100.0, x2 / 100.0
        y1, y2 = y1 / 100.0, y2 / 100.0
    elif x2 <= fit_w and y2 <= fit_h and x1 >= -0.05 * ref_width and y1 >= -0.05 * ref_height:
        # 落在图像像素范围内 → 按绝对像素（DashScope qwen-vl-plus 常见）
        x1, x2 = x1 / ref_width, x2 / ref_width
        y1, y2 = y1 / ref_height, y2 / ref_height
    elif m <= 1000:
        # 超出图像像素但落在 0~1000 → 经典 Qwen 千分制
        x1, x2 = x1 / 1000.0, x2 / 1000.0
        y1, y2 = y1 / 1000.0, y2 / 1000.0
    else:
        x1, x2 = x1 / ref_width, x2 / ref_width
        y1, y2 = y1 / ref_height, y2 / ref_height

    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    x2 = max(0.0, min(1.0, x2))
    y2 = max(0.0, min(1.0, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    if (x2 - x1) * (y2 - y1) < 1e-4:
        return None
    return [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)]


def _extract_bbox_values(raw: Any) -> Optional[List[float]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p for p in raw.replace(",", " ").split() if p]
        if len(parts) < 4:
            return None
        try:
            return [float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])]
        except (TypeError, ValueError):
            return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        try:
            return [float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])]
        except (TypeError, ValueError):
            return None
    if isinstance(raw, dict):
        keys = ("x1", "y1", "x2", "y2")
        if all(k in raw for k in keys):
            try:
                return [float(raw[k]) for k in keys]
            except (TypeError, ValueError):
                return None
    return None


def bbox_to_pixels(bbox: List[float], width: int, height: int) -> Optional[List[int]]:
    """finding.bbox（约定为 0~1 归一化）→ 像素 xyxy。兼容历史像素值。"""
    if not bbox or len(bbox) < 4 or width <= 0 or height <= 0:
        return None
    try:
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
    except (TypeError, ValueError):
        return None
    m = max(x1, y1, x2, y2)
    if m <= 1.5:
        x1, x2 = x1 * width, x2 * width
        y1, y2 = y1 * height, y2 * height
    elif m <= 1000 and m > max(width, height):
        x1, x2 = x1 / 1000.0 * width, x2 / 1000.0 * width
        y1, y2 = y1 / 1000.0 * height, y2 / 1000.0 * height
    elif m <= 1000 and max(width, height) <= 1000:
        # 可能是未规范化的 0~1000
        x1, x2 = x1 / 1000.0 * width, x2 / 1000.0 * width
        y1, y2 = y1 / 1000.0 * height, y2 / 1000.0 * height
    x1i = int(max(0, min(width - 1, round(x1))))
    y1i = int(max(0, min(height - 1, round(y1))))
    x2i = int(max(0, min(width - 1, round(x2))))
    y2i = int(max(0, min(height - 1, round(y2))))
    if x2i <= x1i or y2i <= y1i:
        return None
    return [x1i, y1i, x2i, y2i]


def annotate_frame_with_findings(frame: np.ndarray, findings: Optional[List[Dict[str, Any]]]) -> np.ndarray:
    """在帧上绘制 findings[].bbox（BGR）。无有效框时返回原图副本。"""
    if frame is None or frame.size == 0:
        return frame
    out = frame.copy()
    if not findings:
        return out
    h, w = out.shape[:2]
    for item in findings:
        if not isinstance(item, dict):
            continue
        px = bbox_to_pixels(item.get("bbox") or [], w, h)
        if not px:
            continue
        x1, y1, x2, y2 = px
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 165, 255), 2)
        label = str(item.get("label") or "")
        try:
            conf = float(item.get("confidence") or 0)
        except (TypeError, ValueError):
            conf = 0.0
        text = f"{label} {conf:.2f}".strip() if label else f"{conf:.2f}"
        if text:
            ty = max(16, y1 - 6)
            cv2.putText(
                out,
                text[:48],
                (x1, ty),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 165, 255),
                2,
                cv2.LINE_AA,
            )
    return out


def save_snapshot(frame: np.ndarray, job_id: str, finding_id: str, max_width: int = 1280) -> Optional[str]:
    try:
        root = Path("storage/vlm_inspection") / job_id
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{finding_id}.jpg"
        img = frame
        h, w = img.shape[:2]
        if max_width and w > max_width:
            scale = max_width / w
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        cv2.imwrite(str(path), img)
        return str(path).replace("\\", "/")
    except Exception:
        return None
