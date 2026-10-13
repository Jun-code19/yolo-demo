"""设备内轻量轨迹缓冲：IoU 关联，不依赖智能分析 Tracker。"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.person_search.utils import bbox_iou

logger = logging.getLogger(__name__)

IOU_MATCH_MIN = float(__import__("os").getenv("PERSON_TRACK_IOU", "0.35"))
TRACK_TTL_SEC = float(__import__("os").getenv("PERSON_TRACK_TTL", "2.5"))
MAX_KEYFRAMES = int(__import__("os").getenv("PERSON_TRACK_MAX_KEYFRAMES", "12"))


@dataclass
class TrackFrame:
    crop_path: str
    embedding: Dict[str, Any]
    quality_score: float
    confidence: float
    bbox: List[int]
    event_id: Optional[str]
    timestamp: datetime
    gallery_id: Optional[str] = None


@dataclass
class ActiveTrack:
    track_id: str
    device_id: str
    local_id: int
    bbox: Tuple[int, int, int, int]
    last_seen_ts: float
    first_seen: datetime
    last_seen: datetime
    frames: List[TrackFrame] = field(default_factory=list)
    hit_count: int = 0

    def add_frame(self, frame: TrackFrame) -> None:
        self.frames.append(frame)
        self.hit_count += 1
        # 仅保留质量最高的 Top-K 作为关键帧候选
        if len(self.frames) > MAX_KEYFRAMES * 2:
            self.frames.sort(key=lambda f: f.quality_score, reverse=True)
            self.frames = self.frames[:MAX_KEYFRAMES]


class DeviceTrackBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._next_local: Dict[str, int] = {}
        self._tracks: Dict[str, Dict[str, ActiveTrack]] = {}  # device -> track_id -> track

    def _new_local_id(self, device_id: str) -> int:
        n = self._next_local.get(device_id, 1)
        self._next_local[device_id] = n + 1
        return n

    def match_or_create(
        self,
        device_id: str,
        bbox: Tuple[int, int, int, int],
        *,
        timestamp: Optional[datetime] = None,
    ) -> ActiveTrack:
        now = time.time()
        ts = timestamp or datetime.now()
        with self._lock:
            device_tracks = self._tracks.setdefault(device_id, {})
            # 清理超时轨迹交由 flush_expired 处理；匹配时跳过过期
            best_id = None
            best_iou = IOU_MATCH_MIN
            for tid, tr in device_tracks.items():
                if now - tr.last_seen_ts > TRACK_TTL_SEC:
                    continue
                iou = bbox_iou(bbox, tr.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_id = tid
            if best_id:
                tr = device_tracks[best_id]
                tr.bbox = bbox
                tr.last_seen_ts = now
                tr.last_seen = ts
                return tr

            track_id = str(uuid.uuid4())
            local_id = self._new_local_id(device_id)
            tr = ActiveTrack(
                track_id=track_id,
                device_id=device_id,
                local_id=local_id,
                bbox=bbox,
                last_seen_ts=now,
                first_seen=ts,
                last_seen=ts,
            )
            device_tracks[track_id] = tr
            return tr

    def flush_expired(self, *, force_all: bool = False) -> List[ActiveTrack]:
        now = time.time()
        expired: List[ActiveTrack] = []
        with self._lock:
            for device_id, device_tracks in list(self._tracks.items()):
                for tid, tr in list(device_tracks.items()):
                    if force_all or (now - tr.last_seen_ts > TRACK_TTL_SEC):
                        expired.append(tr)
                        del device_tracks[tid]
                if not device_tracks:
                    self._tracks.pop(device_id, None)
        return expired

    def snapshot_active(self) -> List[ActiveTrack]:
        with self._lock:
            return [tr for d in self._tracks.values() for tr in d.values()]


def aggregate_deep_embedding(frames: List[TrackFrame]) -> Optional[Dict[str, Any]]:
    """质量加权平均 deep 特征 + L2 归一；保留最高质量帧的辅助签名。"""
    if not frames:
        return None
    vecs = []
    weights = []
    best = max(frames, key=lambda f: f.quality_score)
    for fr in frames:
        deep = (fr.embedding or {}).get("deep") or []
        if not deep:
            continue
        vecs.append(np.asarray(deep, dtype=np.float32))
        weights.append(max(0.05, float(fr.quality_score)))
    if not vecs:
        return None
    matrix = np.stack(vecs, axis=0)
    w = np.asarray(weights, dtype=np.float32)
    w = w / (w.sum() + 1e-8)
    mean = (matrix * w[:, None]).sum(axis=0)
    norm = float(np.linalg.norm(mean))
    if norm > 1e-8:
        mean = mean / norm
    base = dict(best.embedding or {})
    base["deep"] = mean.astype(np.float32).tolist()
    base["agg"] = True
    base["agg_frames"] = len(vecs)
    return base


_global_buffer = DeviceTrackBuffer()


def get_track_buffer() -> DeviceTrackBuffer:
    return _global_buffer
