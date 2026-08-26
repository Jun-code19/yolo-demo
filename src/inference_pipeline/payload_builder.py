"""组装送 VLM 的图像与 Prompt"""
import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

PROMPT_REGISTRY_PATH = Path(__file__).resolve().parent / "prompts" / "registry.json"


def load_prompt_registry() -> Dict[str, Any]:
    if not PROMPT_REGISTRY_PATH.exists():
        return {}
    with open(PROMPT_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_prompt(prompt_id: str, alert_labels: Optional[List[str]] = None, override: Optional[str] = None) -> Dict[str, str]:
    if override and override.strip():
        labels_text = "、".join(alert_labels or []) or "安全隐患"
        return {
            "system": (
                "你是视频监控图像分析助手。只输出 JSON，不要 markdown。"
                "必须根据实际画面填写，禁止照抄用户 Prompt 中的示例 label 或数值。"
                "命中关注告警项时 findings 必须写入对应 label（confidence 0.85~1.0）；"
                "未命中时 findings 必须为 []。"
            ),
            "user": override.replace("{alert_labels}", labels_text),
        }

    registry = load_prompt_registry()
    entry = registry.get(prompt_id) or registry.get("general_patrol_v1", {})
    labels_text = "、".join(alert_labels or []) or "安全隐患"
    user_text = (entry.get("user_template") or "").replace("{alert_labels}", labels_text)
    return {
        "system": entry.get("system") or "你是视频监控安全巡检助手。只输出 JSON。",
        "user": user_text,
    }


def encode_frame_to_base64(frame: np.ndarray, max_width: int = 1280, jpeg_quality: int = 85) -> str:
    if frame is None or frame.size == 0:
        raise ValueError("空图像帧")
    img = frame
    h, w = img.shape[:2]
    if max_width and w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise ValueError("图像编码失败")
    return base64.b64encode(buf.tobytes()).decode("ascii")


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
