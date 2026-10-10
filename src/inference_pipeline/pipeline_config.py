"""实时检测 inference_pipeline 配置解析"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

DEFAULT_INFERENCE_PIPELINE: Dict[str, Any] = {
    "mode": "yolo_only",
    "vlm_model_id": None,
    "prompt_id": "yolo_verify_v1",
    "prompt_override": None,
    "alert_labels": [],
    "min_confidence": 0.7,
    "trigger": {
        "cooldown_sec": 15,
        "max_calls_per_minute": 12,
        # 整帧复检默认送整图；裁剪模式仍可用（对全目标并集）
        "context": "full_frame",
        "margin_ratio": 0.15,
    },
    "verify": {
        # VLM 结论置信度低于此值视为 uncertain，仍入库并标重要
        "reject_below": 0.6,
    },
    "input": {
        "max_width": 1280,
        "jpeg_quality": 85,
    },
}

MODE_YOLO_ONLY = "yolo_only"
MODE_YOLO_VERIFY = "yolo_then_verify"
MODE_YOLO_ANALYZE = "yolo_then_analyze"

VLM_PIPELINE_MODES = {MODE_YOLO_VERIFY, MODE_YOLO_ANALYZE}


def normalize_inference_pipeline(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(DEFAULT_INFERENCE_PIPELINE)
    if not config:
        return merged
    merged.update({k: v for k, v in config.items() if v is not None})
    merged["trigger"] = {
        **DEFAULT_INFERENCE_PIPELINE["trigger"],
        **(merged.get("trigger") or {}),
    }
    merged["verify"] = {
        **DEFAULT_INFERENCE_PIPELINE["verify"],
        **(merged.get("verify") or {}),
    }
    merged["input"] = {
        **DEFAULT_INFERENCE_PIPELINE["input"],
        **(merged.get("input") or {}),
    }
    mode = merged.get("mode") or MODE_YOLO_ONLY
    if mode not in (MODE_YOLO_ONLY, MODE_YOLO_VERIFY, MODE_YOLO_ANALYZE):
        mode = MODE_YOLO_ONLY
    merged["mode"] = mode
    if mode == MODE_YOLO_VERIFY:
        merged["prompt_id"] = "yolo_verify_v1"
        merged["prompt_override"] = None
    elif mode == MODE_YOLO_ANALYZE and merged.get("prompt_id") == "yolo_verify_v1":
        merged["prompt_id"] = "general_patrol_v1"
    # VLM 管道统一送整帧
    merged["trigger"]["context"] = "full_frame"
    return merged


def extract_inference_pipeline(schedule_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not schedule_config:
        return normalize_inference_pipeline(None)
    return normalize_inference_pipeline(schedule_config.get("inference_pipeline"))


def is_vlm_pipeline_enabled(pipeline: Dict[str, Any]) -> bool:
    mode = pipeline.get("mode") or MODE_YOLO_ONLY
    return mode in VLM_PIPELINE_MODES and bool(pipeline.get("vlm_model_id"))
