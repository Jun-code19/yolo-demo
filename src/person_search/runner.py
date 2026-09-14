"""检测事件异步人员入库"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.person_search.service import index_frame_persons
from src.person_search.utils import filter_person_detections

logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    return os.getenv("PERSON_SEARCH_ENABLED", "true").lower() not in ("0", "false", "no", "off")


class PersonSearchRunner:
    def __init__(self, max_workers: int = 1):
        self.enabled = _is_enabled()
        self._executor = ThreadPoolExecutor(max_workers=max_workers) if self.enabled else None

    def shutdown(self):
        if self._executor:
            self._executor.shutdown(wait=False)

    def submit(
        self,
        frame,
        detections: List[Dict[str, Any]],
        event_id: str,
        device_id: str,
        timestamp: Optional[datetime] = None,
    ):
        if not self.enabled or not self._executor:
            return
        if not filter_person_detections(detections):
            return
        try:
            frame_copy = frame.copy()
        except Exception:
            frame_copy = frame
        ts = timestamp or datetime.now()
        self._executor.submit(
            index_frame_persons,
            frame_copy,
            detections,
            event_id=event_id,
            device_id=device_id,
            timestamp=ts,
        )


person_search_runner = PersonSearchRunner()
