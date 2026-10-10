"""VLM 管道运行时：限流与冷却"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Dict, Optional

from src.inference_pipeline.pipeline_config import (
    MODE_YOLO_ANALYZE,
    MODE_YOLO_VERIFY,
)


class VlmPipelineRuntime:
    """单路检测任务的 VLM 调用配额控制"""

    def __init__(self, pipeline: Dict[str, Any]):
        self.pipeline = pipeline
        trigger = pipeline.get("trigger") or {}
        self.cooldown_sec = float(trigger.get("cooldown_sec") or 15)
        self.max_calls_per_minute = int(trigger.get("max_calls_per_minute") or 12)
        self._last_run_at = 0.0
        self._call_times: Deque[float] = deque()

    def can_run(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if now - self._last_run_at < self.cooldown_sec:
            return False
        while self._call_times and now - self._call_times[0] > 60:
            self._call_times.popleft()
        if len(self._call_times) >= self.max_calls_per_minute:
            return False
        return True

    def mark_ran(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        self._last_run_at = now
        self._call_times.append(now)

    @property
    def mode(self) -> str:
        return self.pipeline.get("mode") or "yolo_only"

    @property
    def is_verify(self) -> bool:
        return self.mode == MODE_YOLO_VERIFY

    @property
    def is_analyze(self) -> bool:
        return self.mode == MODE_YOLO_ANALYZE
