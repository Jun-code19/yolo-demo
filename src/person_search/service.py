"""人员图库入库与检索"""
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from sqlalchemy.orm import Session

from src.database import Device, DetectionEvent, PersonGalleryItem, PersonTrack, SessionLocal
from src.person_search.embedder import (
    EMBEDDING_VERSION,
    embedding_needs_rebuild,
    embedding_similarity,
    embedding_version,
    get_person_embedder,
)
from src.person_search.faiss_index import (
    build_faiss_index,
    faiss_available,
    has_index as has_faiss_index,
    invalidate_faiss_index,
    search_faiss,
)
from src.person_search.par_attrs import extract_person_attributes
from src.person_search.query_preprocess import prepare_query_image
from src.person_search.rerank import rerank_scores
from src.person_search.track_buffer import (
    TrackFrame,
    aggregate_deep_embedding,
    get_track_buffer,
)
from src.person_search.utils import (
    bbox_iou,
    compute_crop_quality,
    crop_person,
    extract_body_signature,
    extract_clothing_signature,
    extract_garment_signature,
    filter_person_detections,
    is_valid_person_crop,
    parse_bbox,
    strip_segmentation_border,
)

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_LIMIT = 5000
MIN_PERSON_CONFIDENCE = float(os.getenv("PERSON_SEARCH_MIN_CONF", "0.45"))
COARSE_TOP_N = int(os.getenv("PERSON_SEARCH_COARSE_TOP", "150"))
RERANK_K1 = int(os.getenv("PERSON_SEARCH_RERANK_K1", "20"))
RERANK_K2 = int(os.getenv("PERSON_SEARCH_RERANK_K2", "6"))
APPEARANCE_BLEND = float(os.getenv("PERSON_SEARCH_APPEARANCE_BLEND", "0.1"))
SEARCH_INDEX_CACHE_TTL = int(os.getenv("PERSON_SEARCH_INDEX_CACHE_TTL", "300"))
VERSION_STATS_CACHE_TTL = int(os.getenv("PERSON_SEARCH_VERSION_STATS_TTL", "300"))
DEFAULT_MIN_SIMILARITY = float(os.getenv("PERSON_SEARCH_MIN_SIMILARITY", "0.55"))
_quality_reject_count = 0

_rebuild_job_lock = threading.Lock()
_rebuild_job: Dict[str, Any] = {"running": False}

_search_index_cache: Dict[str, Any] = {
    "key": None,
    "built_at": 0.0,
    "items": [],
    "embeddings": [],
    "deep_matrix": None,
}

_version_stats_cache: Dict[str, Any] = {"built_at": 0.0, "data": None}


def invalidate_search_index_cache() -> None:
    _search_index_cache["key"] = None
    _search_index_cache["items"] = []
    _search_index_cache["embeddings"] = []
    _search_index_cache["deep_matrix"] = None
    _version_stats_cache["built_at"] = 0.0
    _version_stats_cache["data"] = None
    invalidate_faiss_index()


def _as_deep(embedding: Any) -> List[float]:
    if isinstance(embedding, dict):
        return list(embedding.get("deep") or [])
    return []


def _load_search_index(
    db,
    *,
    since: datetime,
    device_id: Optional[str],
    search_limit: int,
) -> Dict[str, Any]:
    """检索索引默认加载 person_track；无轨迹时回退帧级图库。"""
    cache_key = ("track", since.isoformat(), device_id or "", search_limit)
    now = time.time()
    if (
        _search_index_cache.get("key") == cache_key
        and now - float(_search_index_cache.get("built_at") or 0) < SEARCH_INDEX_CACHE_TTL
        and _search_index_cache.get("items")
    ):
        return _search_index_cache

    q = (
        db.query(PersonTrack, Device.device_name)
        .outerjoin(Device, PersonTrack.device_id == Device.device_id)
        .filter(PersonTrack.last_seen >= since)
        .filter(PersonTrack.agg_embedding.isnot(None))
    )
    if device_id:
        q = q.filter(PersonTrack.device_id == device_id)
    rows = q.order_by(PersonTrack.last_seen.desc()).limit(search_limit).all()

    items: List[Dict[str, Any]] = []
    embeddings: List[Any] = []
    deep_rows: List[List[float]] = []
    legacy_skipped = 0
    for track, device_name in rows:
        embedding = track.agg_embedding
        deep = _as_deep(embedding)
        if not deep:
            legacy_skipped += 1
            continue
        items.append(
            {
                "result_type": "track",
                "track_id": track.track_id,
                "gallery_id": None,
                "event_id": None,
                "device_id": track.device_id,
                "device_name": device_name,
                "crop_path": track.repr_crop_path,
                "frame_count": track.frame_count or 0,
                "quality_score": track.quality_score,
                "first_seen": track.first_seen.isoformat() if track.first_seen else None,
                "last_seen": track.last_seen.isoformat() if track.last_seen else None,
                "created_at": track.last_seen.isoformat() if track.last_seen else None,
            }
        )
        embeddings.append(embedding)
        deep_rows.append(deep)

    # 尚无轨迹数据时回退到帧级（兼容旧库）
    if not items:
        gq = _active_gallery_query(db)
        gq = gq.filter(PersonGalleryItem.created_at >= since)
        if device_id:
            gq = gq.filter(PersonGalleryItem.device_id == device_id)
        grows = gq.order_by(PersonGalleryItem.created_at.desc()).limit(search_limit).all()
        for item, device_name in grows:
            embedding = item.embedding
            deep = _as_deep(embedding)
            if not deep:
                legacy_skipped += 1
                continue
            items.append(
                {
                    "result_type": "frame",
                    "track_id": item.track_id,
                    "gallery_id": item.gallery_id,
                    "event_id": item.event_id,
                    "device_id": item.device_id,
                    "device_name": device_name,
                    "detection_confidence": item.confidence,
                    "quality_score": item.quality_score,
                    "bbox_index": item.bbox_index,
                    "bbox": item.bbox,
                    "crop_path": item.crop_path,
                    "frame_count": 1,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
            )
            embeddings.append(embedding)
            deep_rows.append(deep)

    deep_matrix = np.asarray(deep_rows, dtype=np.float32) if deep_rows else np.empty((0, 0), dtype=np.float32)
    payload = {
        "key": cache_key,
        "built_at": now,
        "items": items,
        "embeddings": embeddings,
        "deep_matrix": deep_matrix,
        "legacy_skipped": legacy_skipped,
    }
    _search_index_cache.update(payload)

    # 同步刷新 FAISS（全量小库可接受）
    try:
        track_ids = [it.get("track_id") or it.get("gallery_id") for it in items]
        if track_ids and deep_matrix.size:
            build_faiss_index(track_ids, deep_matrix, embedding_version=EMBEDDING_VERSION)
    except Exception as exc:
        logger.debug("构建 FAISS 索引跳过: %s", exc)

    return payload


def _save_crop(crop: np.ndarray, device_id: str, event_id: str, index: int, ts: datetime) -> str:
    save_dir = Path(f"storage/person_crops/{ts.strftime('%Y-%m-%d')}/{device_id}")
    save_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
    crop_path = save_dir / f"{event_id}_{index}.jpg"
    cv2.imwrite(str(crop_path), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return str(crop_path).replace("\\", "/")


def _persist_track(db, track) -> None:
    """将缓冲轨迹写入/更新 person_track，并回填帧级 track_id。"""
    frames = list(track.frames)
    if not frames:
        return
    frames.sort(key=lambda f: f.quality_score, reverse=True)
    keyframes = frames[:12]
    agg = aggregate_deep_embedding(keyframes)
    if not agg:
        return
    best = keyframes[0]
    row = db.query(PersonTrack).filter(PersonTrack.track_id == track.track_id).first()
    if row is None:
        row = PersonTrack(track_id=track.track_id, device_id=track.device_id)
        db.add(row)
    row.local_track_id = track.local_id
    row.agg_embedding = agg
    row.repr_crop_path = best.crop_path
    row.frame_count = len(frames)
    row.quality_score = float(best.quality_score)
    row.first_seen = track.first_seen
    row.last_seen = track.last_seen
    row.updated_at = datetime.now()

    key_paths = {f.crop_path for f in keyframes}
    for fr in frames:
        if not fr.gallery_id:
            continue
        item = db.query(PersonGalleryItem).filter(PersonGalleryItem.gallery_id == fr.gallery_id).first()
        if not item:
            continue
        item.track_id = track.track_id
        item.is_keyframe = fr.crop_path in key_paths


def flush_expired_tracks(*, force_all: bool = False) -> int:
    """落盘超时/全部轨迹。"""
    buffer = get_track_buffer()
    expired = buffer.flush_expired(force_all=force_all)
    if not expired:
        return 0
    db = SessionLocal()
    saved = 0
    try:
        for tr in expired:
            if not tr.frames:
                continue
            _persist_track(db, tr)
            saved += 1
        if saved:
            db.commit()
            invalidate_search_index_cache()
            logger.info("轨迹落盘 %s 条", saved)
    except Exception as exc:
        db.rollback()
        logger.error("轨迹落盘失败: %s", exc)
    finally:
        db.close()
    return saved


def index_frame_persons(
    frame,
    detections: List[Dict[str, Any]],
    *,
    event_id: str,
    device_id: str,
    timestamp: Optional[datetime] = None,
    min_confidence: float = MIN_PERSON_CONFIDENCE,
) -> int:
    """抠人 → 质量门 → 轨迹缓冲 → 帧级入库；超时轨迹异步落盘。"""
    global _quality_reject_count
    if frame is None:
        return 0
    ts = timestamp or datetime.now()
    persons = filter_person_detections(detections)
    if not persons:
        flush_expired_tracks()
        return 0

    try:
        embedder = get_person_embedder()
    except Exception as exc:
        logger.warning("PersonEmbedder 不可用，跳过入库: %s", exc)
        return 0

    buffer = get_track_buffer()
    saved = 0
    db = SessionLocal()
    try:
        for idx, det in enumerate(persons):
            conf = float(det.get("confidence") or 0)
            if conf < min_confidence:
                continue
            bbox = parse_bbox(det)
            if not bbox:
                continue
            crop = crop_person(frame, bbox)
            if crop is None:
                continue
            quality = compute_crop_quality(crop, detection_confidence=conf)
            if not quality.get("ok"):
                _quality_reject_count += 1
                continue
            embedding = embedder.embed_bgr(crop, tta_flip=True)
            if not embedding:
                continue
            crop_path = _save_crop(crop, device_id, event_id, idx, ts)
            active = buffer.match_or_create(device_id, bbox, timestamp=ts)
            gallery_id = str(uuid.uuid4())
            item = PersonGalleryItem(
                gallery_id=gallery_id,
                event_id=event_id,
                device_id=device_id,
                track_id=active.track_id,
                bbox_index=idx,
                confidence=conf,
                quality_score=float(quality["quality_score"]),
                is_keyframe=False,
                crop_path=crop_path,
                bbox=list(bbox),
                embedding=embedding,
                created_at=ts,
            )
            db.add(item)
            active.add_frame(
                TrackFrame(
                    crop_path=crop_path,
                    embedding=embedding,
                    quality_score=float(quality["quality_score"]),
                    confidence=conf,
                    bbox=list(bbox),
                    event_id=event_id,
                    timestamp=ts,
                    gallery_id=gallery_id,
                )
            )
            # 在线增量更新轨迹聚合，便于即时可搜
            _persist_track(db, active)
            saved += 1
        if saved:
            db.commit()
            invalidate_search_index_cache()
            logger.info("人员图库入库 %s 条 event=%s device=%s", saved, event_id, device_id)
        flush_expired_tracks()
    except Exception as exc:
        db.rollback()
        logger.error("人员图库入库失败: %s", exc)
    finally:
        db.close()
    return saved


def _resolve_event_frame_path(event: DetectionEvent) -> Optional[str]:
    """优先无框原图，避免从带检测框缩略图抠人导致入库看不清。"""
    meta = event.meta_data if isinstance(event.meta_data, dict) else {}
    raw_path = meta.get("raw_frame_path") if meta else None
    if raw_path and os.path.exists(raw_path):
        return raw_path
    thumb = event.thumbnail_path or ""
    if thumb:
        stem, ext = os.path.splitext(thumb)
        candidate = f"{stem}_raw{ext or '.jpg'}"
        if os.path.exists(candidate):
            return candidate
    if thumb and os.path.exists(thumb):
        return thumb
    return None


def index_detection_event(event_id: str) -> Dict[str, Any]:
    """从已有检测事件回填人员图库"""
    db = SessionLocal()
    try:
        event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first()
        if not event:
            return {"event_id": event_id, "indexed": 0, "message": "事件不存在"}
        frame_path = _resolve_event_frame_path(event)
        if not frame_path:
            return {"event_id": event_id, "indexed": 0, "message": "事件无可用截图"}
        frame = cv2.imread(frame_path)
        if frame is None:
            return {"event_id": event_id, "indexed": 0, "message": "截图读取失败"}
        detections = event.bounding_box or []
        existing = (
            db.query(PersonGalleryItem)
            .filter(PersonGalleryItem.event_id == event_id)
            .count()
        )
        if existing:
            db.query(PersonGalleryItem).filter(PersonGalleryItem.event_id == event_id).delete()
            db.commit()
        indexed = index_frame_persons(
            frame,
            detections,
            event_id=event.event_id,
            device_id=event.device_id,
            timestamp=event.timestamp or event.created_at,
        )
        return {"event_id": event_id, "indexed": indexed, "message": "ok"}
    finally:
        db.close()


def batch_index_recent_events(limit: int = 50, only_with_person: bool = True) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        q = (
            db.query(DetectionEvent)
            .filter(DetectionEvent.thumbnail_path.isnot(None))
            .order_by(DetectionEvent.created_at.desc())
        )
        events = q.limit(max(1, min(limit, 200))).all()
        total_indexed = 0
        processed = 0
        for event in events:
            detections = event.bounding_box or []
            if only_with_person and not filter_person_detections(detections):
                continue
            result = index_detection_event(event.event_id)
            total_indexed += int(result.get("indexed") or 0)
            processed += 1
        return {"processed_events": processed, "indexed_persons": total_indexed}
    finally:
        db.close()


def _embedding_version_stats(db) -> Dict[str, int]:
    now = time.time()
    cached = _version_stats_cache.get("data")
    if cached and now - float(_version_stats_cache.get("built_at") or 0) < VERSION_STATS_CACHE_TTL:
        return dict(cached)

    rows = (
        db.query(PersonGalleryItem.embedding)
        .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
        .all()
    )
    current = 0
    legacy = 0
    stale = 0
    for (embedding,) in rows:
        if embedding_version(embedding) < EMBEDDING_VERSION:
            legacy += 1
        elif embedding_needs_rebuild(embedding):
            stale += 1
        else:
            current += 1
    result = {
        "current_embeddings": current,
        "legacy_embeddings": legacy,
        "stale_embeddings": stale,
    }
    _version_stats_cache["built_at"] = now
    _version_stats_cache["data"] = result
    return dict(result)


def _touch_rebuild_job(job: Optional[Dict[str, Any]], **fields: Any) -> None:
    if job is not None:
        job.update(fields)


LEGACY_TRACK_GAP_SEC = float(os.getenv("PERSON_TRACK_BACKFILL_GAP", "8"))
LEGACY_TRACK_IOU_MIN = float(os.getenv("PERSON_TRACK_BACKFILL_IOU", "0.30"))
LEGACY_TRACK_COSINE_MIN = float(os.getenv("PERSON_TRACK_BACKFILL_COSINE", "0.78"))


def _bbox_tuple(raw: Any) -> Optional[tuple]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        return tuple(int(float(v)) for v in raw[:4])
    return None


def _cosine_deep(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-8
    return float(np.dot(va, vb) / denom)


def assign_missing_track_ids(db: Session) -> int:
    """历史图库若无 track_id，按设备+时间+IoU/特征补轨迹，否则搜图会退回帧级并被重排打乱。

    person_gallery.track_id 有外键，必须先插入 person_track 再回填图库。
    """
    items = (
        db.query(PersonGalleryItem)
        .filter(PersonGalleryItem.track_id.is_(None))
        .order_by(PersonGalleryItem.device_id.asc(), PersonGalleryItem.created_at.asc())
        .all()
    )
    if not items:
        return 0
    last_by_device: Dict[str, Dict[str, Any]] = {}
    planned: List[tuple] = []
    for item in items:
        bbox = _bbox_tuple(item.bbox)
        ts = item.created_at or datetime.now()
        deep = _as_deep(item.embedding)
        prev = last_by_device.get(item.device_id or "")
        track_id = None
        if prev:
            dt = abs((ts - prev["ts"]).total_seconds()) if prev.get("ts") else 9999.0
            iou = bbox_iou(bbox, prev["bbox"]) if bbox and prev.get("bbox") else 0.0
            cos = _cosine_deep(deep, prev.get("deep") or [])
            if dt <= LEGACY_TRACK_GAP_SEC and (iou >= LEGACY_TRACK_IOU_MIN or cos >= LEGACY_TRACK_COSINE_MIN):
                track_id = prev["track_id"]
        if not track_id:
            track_id = str(uuid.uuid4())
        planned.append((item, track_id, ts))
        last_by_device[item.device_id or ""] = {
            "track_id": track_id,
            "ts": ts,
            "bbox": bbox,
            "deep": deep,
        }

    existing = {
        tid
        for (tid,) in db.query(PersonTrack.track_id)
        .filter(PersonTrack.track_id.in_({tid for _, tid, _ in planned}))
        .all()
    }
    created = 0
    for item, track_id, ts in planned:
        if track_id not in existing:
            db.add(
                PersonTrack(
                    track_id=track_id,
                    device_id=item.device_id,
                    first_seen=ts,
                    last_seen=ts,
                    frame_count=0,
                )
            )
            existing.add(track_id)
            created += 1
    db.flush()
    for item, track_id, _ in planned:
        item.track_id = track_id
    logger.info("已为无轨迹图库补 track_id：%s 条，新建轨迹 %s 条", len(planned), created)
    return len(planned)


def rebuild_gallery_embeddings(
    limit: int = 5000,
    job: Optional[Dict[str, Any]] = None,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """基于已有抠图文件，用当前 ReID 模型重建图库特征。"""
    embedder = get_person_embedder()
    db = SessionLocal()
    updated = 0
    failed = 0
    skipped = 0
    try:
        items = (
            db.query(PersonGalleryItem)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .order_by(PersonGalleryItem.created_at.desc())
            .limit(max(1, min(limit, 20000)))
            .all()
        )
        pending = sum(
            1 for item in items if force or embedding_needs_rebuild(item.embedding)
        )
        _touch_rebuild_job(job, total=len(items), pending=pending, phase="running")
        logger.info(
            "开始重建图库特征：共 %s 条记录，待升级 %s 条 force=%s",
            len(items),
            pending,
            force,
        )
        for item in items:
            if not force and not embedding_needs_rebuild(item.embedding):
                skipped += 1
                _touch_rebuild_job(job, updated=updated, failed=failed, skipped=skipped)
                continue
            if not item.crop_path or not os.path.exists(item.crop_path):
                failed += 1
                _touch_rebuild_job(job, updated=updated, failed=failed, skipped=skipped)
                continue
            crop = cv2.imread(item.crop_path)
            if crop is None:
                failed += 1
                _touch_rebuild_job(job, updated=updated, failed=failed, skipped=skipped)
                continue
            embedding = embedder.embed_bgr(crop, tta_flip=True)
            if not embedding:
                failed += 1
                _touch_rebuild_job(job, updated=updated, failed=failed, skipped=skipped)
                continue
            item.embedding = embedding
            updated += 1
            if updated % 50 == 0 or updated == pending:
                logger.info("图库特征重建进度：%s/%s", updated, pending)
                _touch_rebuild_job(job, updated=updated, failed=failed, skipped=skipped)
        if updated:
            db.commit()
        track_ids_assigned = assign_missing_track_ids(db)
        tracks_updated = rebuild_track_aggregates(db)
        db.commit()
        invalidate_search_index_cache()
        _touch_rebuild_job(
            job,
            phase="done",
            updated=updated,
            failed=failed,
            skipped=skipped,
            tracks_updated=tracks_updated,
            track_ids_assigned=track_ids_assigned,
        )
        logger.info(
            "图库特征重建完成 updated=%s failed=%s skipped=%s tracks=%s assigned_track_id=%s",
            updated,
            failed,
            skipped,
            tracks_updated,
            track_ids_assigned,
        )
        return {
            "updated": updated,
            "failed": failed,
            "skipped": skipped,
            "pending": pending,
            "total": len(items),
            "tracks_updated": tracks_updated,
            "track_ids_assigned": track_ids_assigned,
            "embedding_version": EMBEDDING_VERSION,
        }
    except Exception:
        db.rollback()
        _touch_rebuild_job(job, phase="error")
        raise
    finally:
        db.close()


def rebuild_track_aggregates(db: Optional[Session] = None) -> int:
    """按 track_id 从帧级 embedding 重算轨迹聚合特征。"""
    own = db is None
    if own:
        db = SessionLocal()
    updated = 0
    try:
        track_ids = [
            tid
            for (tid,) in db.query(PersonGalleryItem.track_id)
            .filter(PersonGalleryItem.track_id.isnot(None))
            .distinct()
            .all()
        ]
        for tid in track_ids:
            frames = (
                db.query(PersonGalleryItem)
                .filter(PersonGalleryItem.track_id == tid)
                .order_by(PersonGalleryItem.quality_score.desc())
                .limit(16)
                .all()
            )
            if not frames:
                continue
            tf_list = [
                TrackFrame(
                    crop_path=f.crop_path,
                    embedding=f.embedding or {},
                    quality_score=float(f.quality_score or 0.5),
                    confidence=float(f.confidence or 0),
                    bbox=list(f.bbox or []),
                    event_id=f.event_id,
                    timestamp=f.created_at or datetime.now(),
                    gallery_id=f.gallery_id,
                )
                for f in frames
            ]
            agg = aggregate_deep_embedding(tf_list)
            if not agg:
                continue
            best = max(tf_list, key=lambda x: x.quality_score)
            row = db.query(PersonTrack).filter(PersonTrack.track_id == tid).first()
            if row is None:
                device_id = frames[0].device_id
                row = PersonTrack(track_id=tid, device_id=device_id)
                db.add(row)
            row.agg_embedding = agg
            row.repr_crop_path = best.crop_path
            row.frame_count = (
                db.query(PersonGalleryItem).filter(PersonGalleryItem.track_id == tid).count()
            )
            row.quality_score = best.quality_score
            times = [f.created_at for f in frames if f.created_at]
            if times:
                row.first_seen = min(times)
                row.last_seen = max(times)
            row.updated_at = datetime.now()
            for f in frames[:8]:
                f.is_keyframe = True
            updated += 1
        if own:
            db.commit()
            invalidate_search_index_cache()
        return updated
    except Exception:
        if own:
            db.rollback()
        raise
    finally:
        if own:
            db.close()


def get_rebuild_gallery_job() -> Dict[str, Any]:
    with _rebuild_job_lock:
        return dict(_rebuild_job)


def start_rebuild_gallery_embeddings_async(limit: int = 5000, force: bool = False) -> Dict[str, Any]:
    """后台线程重建，避免 HTTP 长时间无响应。"""
    limit = max(1, min(int(limit), 20000))
    with _rebuild_job_lock:
        if _rebuild_job.get("running"):
            return {
                "started": False,
                "message": "已有重建任务进行中，请稍候",
                "job": dict(_rebuild_job),
            }
        _rebuild_job.clear()
        _rebuild_job.update(
            running=True,
            limit=limit,
            force=bool(force),
            total=0,
            pending=0,
            updated=0,
            failed=0,
            skipped=0,
            tracks_updated=0,
            track_ids_assigned=0,
            phase="starting",
            error=None,
            started_at=datetime.now().isoformat(),
            finished_at=None,
        )
        job_ref = _rebuild_job

    def _worker() -> None:
        try:
            result = rebuild_gallery_embeddings(limit=limit, job=job_ref, force=force)
            with _rebuild_job_lock:
                job_ref.update(running=False, phase="done", finished_at=datetime.now().isoformat(), **result)
        except Exception as exc:
            logger.exception("后台重建图库特征失败")
            with _rebuild_job_lock:
                job_ref.update(
                    running=False,
                    phase="error",
                    error=str(exc),
                    finished_at=datetime.now().isoformat(),
                )

    threading.Thread(target=_worker, daemon=True, name="person-gallery-rebuild").start()
    return {
        "started": True,
        "message": "重建任务已在后台启动（首次会加载 ReID 模型，可能需数十秒才有进度）",
        "job": get_rebuild_gallery_job(),
    }


def _active_gallery_query(db):
    """仅关联仍存在的检测事件（排除已删事件遗留的孤儿图库记录）"""
    return (
        db.query(PersonGalleryItem, Device.device_name)
        .join(Device, PersonGalleryItem.device_id == Device.device_id)
        .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
    )


def delete_gallery_for_events(event_ids: List[str], db: Optional[Session] = None) -> int:
    """删除检测事件关联的人员图库记录及抠图文件（detect 侧会刷新搜索索引缓存）。"""
    from src.person_search.gallery_cleanup import delete_gallery_for_events as _delete

    deleted = _delete(event_ids, db=db)
    if deleted:
        invalidate_search_index_cache()
    return deleted


def cleanup_orphan_person_crop_files() -> int:
    """清理检测事件已删除但磁盘仍遗留的人员抠图文件"""
    crop_root = Path("storage/person_crops")
    if not crop_root.is_dir():
        return 0

    db = SessionLocal()
    deleted = 0
    try:
        event_ids = {row[0] for row in db.query(DetectionEvent.event_id).all()}
        db_paths = {
            os.path.normpath(path).replace("\\", "/")
            for path, in db.query(PersonGalleryItem.crop_path).filter(PersonGalleryItem.crop_path.isnot(None)).all()
        }
        event_id_pattern = re.compile(r"^([0-9a-f-]{36})_\d+\.", re.IGNORECASE)

        for crop_path in crop_root.rglob("*"):
            if not crop_path.is_file():
                continue
            normalized = os.path.normpath(str(crop_path)).replace("\\", "/")
            if normalized in db_paths:
                continue
            match = event_id_pattern.match(crop_path.name)
            if match and match.group(1) in event_ids:
                continue
            try:
                crop_path.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning("删除遗留抠图失败 %s: %s", crop_path, exc)

        if deleted:
            logger.info("已清理 %s 个遗留人员抠图文件", deleted)
    finally:
        db.close()
    return deleted


def cleanup_orphan_gallery_items() -> int:
    """清理检测事件已删除但遗留的图库记录"""
    db = SessionLocal()
    deleted = 0
    try:
        orphans = (
            db.query(PersonGalleryItem)
            .outerjoin(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .filter(DetectionEvent.event_id.is_(None))
            .all()
        )
        for item in orphans:
            if item.crop_path:
                try:
                    if os.path.exists(item.crop_path):
                        os.remove(item.crop_path)
                except OSError as exc:
                    logger.warning("删除孤儿抠图失败 %s: %s", item.crop_path, exc)
            db.delete(item)
            deleted += 1
        if deleted:
            db.commit()
            invalidate_search_index_cache()
            logger.info("已清理 %s 条孤儿人员图库记录", deleted)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return deleted


def _confidence_from_score(score: float) -> str:
    if score >= 0.82:
        return "high"
    if score >= 0.68:
        return "medium"
    if score >= 0.55:
        return "low"
    return "weak"


def search_by_image(
    query_bgr: np.ndarray,
    *,
    top_k: int = 20,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    device_id: Optional[str] = None,
    days: int = 7,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> Dict[str, Any]:
    """轨迹级检索：粗检(FAISS/矩阵) → k-reciprocal 重排 → 弱外观融合。"""
    started = time.perf_counter()
    flush_expired_tracks()
    query_bgr = prepare_query_image(query_bgr)
    embedder = get_person_embedder()
    query_vec = embedder.embed_bgr(query_bgr, tta_flip=True)
    if not query_vec:
        return {"results": [], "legacy_skipped": 0, "needs_rebuild": False, "search_ms": 0}

    clean_query = strip_segmentation_border(query_bgr)
    if not query_vec.get("garment"):
        query_vec = {**query_vec, "garment": extract_garment_signature(clean_query) or []}
    if not query_vec.get("clothing"):
        query_vec = {**query_vec, "clothing": extract_clothing_signature(clean_query) or []}
    if not query_vec.get("body"):
        query_vec = {**query_vec, "body": extract_body_signature(clean_query) or []}
    if not query_vec.get("attrs"):
        query_vec = {**query_vec, "attrs": extract_person_attributes(clean_query) or {}}

    since = datetime.now() - timedelta(days=max(1, min(days, 90)))
    db = SessionLocal()
    try:
        index = _load_search_index(db, since=since, device_id=device_id, search_limit=search_limit)
        items = index["items"]
        embeddings = index["embeddings"]
        deep_matrix = index["deep_matrix"]
        legacy_skipped = int(index.get("legacy_skipped") or 0)

        if deep_matrix.size == 0:
            search_ms = int((time.perf_counter() - started) * 1000)
            return {
                "results": [],
                "legacy_skipped": legacy_skipped,
                "needs_rebuild": legacy_skipped > 0,
                "search_ms": search_ms,
                "scanned": 0,
                "reranked": 0,
                "backend": "empty",
            }

        q_deep = np.asarray(query_vec.get("deep") or [], dtype=np.float32)
        if q_deep.size != deep_matrix.shape[1]:
            search_ms = int((time.perf_counter() - started) * 1000)
            return {
                "results": [],
                "legacy_skipped": legacy_skipped + len(items),
                "needs_rebuild": True,
                "search_ms": search_ms,
                "scanned": len(items),
                "reranked": 0,
            }

        # 粗检：优先 FAISS，否则矩阵
        backend = "matrix"
        coarse_n = min(COARSE_TOP_N, len(items))
        id_to_idx = {
            (it.get("track_id") or it.get("gallery_id")): i for i, it in enumerate(items)
        }
        candidate_idx: np.ndarray
        if has_faiss_index() and (device_id is None):
            faiss_ids, faiss_scores = search_faiss(q_deep, top_k=coarse_n)
            idxs = []
            for tid in faiss_ids:
                if tid in id_to_idx:
                    idxs.append(id_to_idx[tid])
            if idxs:
                candidate_idx = np.asarray(idxs, dtype=np.int32)
                backend = "faiss" if faiss_available() else "memory_index"
            else:
                deep_scores = deep_matrix @ q_deep
                if coarse_n < len(items):
                    candidate_idx = np.argpartition(deep_scores, -coarse_n)[-coarse_n:]
                else:
                    candidate_idx = np.arange(len(items), dtype=np.int32)
                candidate_idx = candidate_idx[np.argsort(deep_scores[candidate_idx])[::-1]]
        else:
            deep_scores = deep_matrix @ q_deep
            if coarse_n < len(items):
                candidate_idx = np.argpartition(deep_scores, -coarse_n)[-coarse_n:]
            else:
                candidate_idx = np.arange(len(items), dtype=np.int32)
            candidate_idx = candidate_idx[np.argsort(deep_scores[candidate_idx])[::-1]]

        # 帧级回退时近重复极多，k-reciprocal 会把分数抹平；仅轨迹粗检后重排
        frame_fallback = bool(items) and items[0].get("result_type") == "frame"
        cand_deeps = [list(deep_matrix[int(i)]) for i in candidate_idx]
        if frame_fallback:
            rr_scores = [float(np.dot(deep_matrix[int(i)], q_deep)) for i in candidate_idx]
            backend = f"{backend}+no_rerank"
        else:
            rr_scores = rerank_scores(
                list(q_deep),
                cand_deeps,
                k1=RERANK_K1,
                k2=RERANK_K2,
                lambda_value=0.3,
            )

        scored: List[Dict[str, Any]] = []
        for pos, idx in enumerate(candidate_idx):
            meta = items[int(idx)]
            embedding = embeddings[int(idx)]
            deep_sim = float(np.dot(deep_matrix[int(idx)], q_deep))
            sims = embedding_similarity(
                query_vec,
                embedding,
                precomputed_deep_sim=deep_sim,
                allow_image_io=False,
            )
            appearance = float(sims.get("hue_similarity") or 0)
            if appearance <= 0:
                appearance = float(sims.get("color_similarity") or 0)
            rr = float(rr_scores[pos]) if pos < len(rr_scores) else deep_sim
            # 最终分：重排为主，外观弱融合；不做 hard veto
            final = (1.0 - APPEARANCE_BLEND) * rr + APPEARANCE_BLEND * max(appearance, deep_sim)
            if final < min_similarity and deep_sim < min_similarity:
                continue
            row = {
                **meta,
                "deep_similarity": round(deep_sim, 4),
                "rerank_similarity": round(rr, 4),
                "color_similarity": sims.get("color_similarity"),
                "hue_similarity": sims.get("hue_similarity"),
                "garment_similarity": sims.get("garment_similarity"),
                "body_similarity": sims.get("body_similarity"),
                "attr_similarity": sims.get("attr_similarity"),
                "gender_hint": sims.get("gender_hint"),
                "similarity": round(float(final), 4),
                "match_confidence": _confidence_from_score(final),
            }
            scored.append(row)

        scored.sort(key=lambda x: x.get("similarity") or 0, reverse=True)
        results = scored[: max(1, min(top_k, 100))]

        # 轨迹结果附加关键帧路径（最多 6）
        for row in results:
            tid = row.get("track_id")
            if not tid or row.get("result_type") != "track":
                continue
            frames = (
                db.query(PersonGalleryItem)
                .filter(PersonGalleryItem.track_id == tid)
                .order_by(PersonGalleryItem.quality_score.desc())
                .limit(6)
                .all()
            )
            row["frames"] = [
                {
                    "gallery_id": f.gallery_id,
                    "crop_path": f.crop_path,
                    "quality_score": f.quality_score,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                    "is_keyframe": bool(f.is_keyframe),
                }
                for f in frames
            ]

        search_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "人员搜索完成 scanned=%s coarse=%s results=%s backend=%s ms=%s",
            len(items),
            len(candidate_idx),
            len(results),
            backend,
            search_ms,
        )
        return {
            "results": results,
            "legacy_skipped": legacy_skipped,
            "needs_rebuild": legacy_skipped > 0 and len(results) == 0,
            "search_ms": search_ms,
            "scanned": len(items),
            "reranked": len(candidate_idx),
            "backend": backend,
        }
    finally:
        db.close()


def get_gallery_stats(*, run_cleanup: bool = False) -> Dict[str, Any]:
    # 页面加载默认不做全量孤儿清理；需要时由定时任务或显式传参触发
    if run_cleanup:
        cleanup_orphan_gallery_items()
        cleanup_orphan_person_crop_files()
    db = SessionLocal()
    try:
        # 顺手清掉「图库已删、轨迹还在」的孤儿，避免轨迹数虚高
        from src.person_search.gallery_cleanup import cleanup_orphan_tracks

        removed_tracks = cleanup_orphan_tracks(db)
        if removed_tracks:
            db.commit()
            invalidate_search_index_cache()
            logger.info("统计时清理空轨迹 %s 条", removed_tracks)

        base = (
            db.query(PersonGalleryItem)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
        )
        total = base.count()
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = base.filter(PersonGalleryItem.created_at >= today_start).count()
        devices = base.with_entities(PersonGalleryItem.device_id).distinct().count()
        track_count = db.query(PersonTrack).count()
        version_stats = _embedding_version_stats(db)
        return {
            "total": total,
            "today": today,
            "device_count": devices,
            "track_count": track_count,
            "quality_rejected": _quality_reject_count,
            "faiss_ready": has_faiss_index(),
            "faiss_available": faiss_available(),
            **version_stats,
            "embedding_version": EMBEDDING_VERSION,
            "needs_rebuild": (
                version_stats.get("legacy_embeddings", 0) > 0
                or version_stats.get("stale_embeddings", 0) > 0
            ),
        }
    finally:
        db.close()


def get_track_detail(track_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        track = (
            db.query(PersonTrack, Device.device_name)
            .outerjoin(Device, PersonTrack.device_id == Device.device_id)
            .filter(PersonTrack.track_id == track_id)
            .first()
        )
        if not track:
            return None
        row, device_name = track
        frames = (
            db.query(PersonGalleryItem)
            .filter(PersonGalleryItem.track_id == track_id)
            .order_by(PersonGalleryItem.created_at.desc())
            .limit(48)
            .all()
        )
        return {
            "track_id": row.track_id,
            "device_id": row.device_id,
            "device_name": device_name,
            "frame_count": row.frame_count,
            "quality_score": row.quality_score,
            "repr_crop_path": row.repr_crop_path,
            "first_seen": row.first_seen.isoformat() if row.first_seen else None,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            "frames": [
                {
                    "gallery_id": f.gallery_id,
                    "crop_path": f.crop_path,
                    "quality_score": f.quality_score,
                    "confidence": f.confidence,
                    "is_keyframe": bool(f.is_keyframe),
                    "event_id": f.event_id,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in frames
            ],
        }
    finally:
        db.close()


def list_gallery(
    *,
    page: int = 1,
    page_size: int = 24,
    device_id: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    since = datetime.now() - timedelta(days=max(1, min(days, 90)))
    db = SessionLocal()
    try:
        q = _active_gallery_query(db)
        q = q.filter(PersonGalleryItem.created_at >= since)
        if device_id:
            q = q.filter(PersonGalleryItem.device_id == device_id)
        total = q.count()
        rows = (
            q.order_by(PersonGalleryItem.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            {
                "gallery_id": item.gallery_id,
                "event_id": item.event_id,
                "device_id": item.device_id,
                "device_name": device_name,
                "confidence": item.confidence,
                "bbox_index": item.bbox_index,
                "bbox": item.bbox,
                "crop_path": item.crop_path,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item, device_name in rows
        ]
        return {"total": total, "page": page, "page_size": page_size, "items": items}
    finally:
        db.close()


def get_gallery_detail(gallery_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        row = (
            db.query(PersonGalleryItem, Device.device_name, DetectionEvent)
            .join(Device, PersonGalleryItem.device_id == Device.device_id)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .filter(PersonGalleryItem.gallery_id == gallery_id)
            .first()
        )
        if not row:
            return None
        item, device_name, event = row
        embedding = item.embedding or []
        if isinstance(embedding, dict):
            deep_dim = len(embedding.get("deep") or [])
            color_dim = len(embedding.get("color") or [])
            model_name = embedding.get("model") or "unknown"
            embedding_dim = f"{model_name} deep {deep_dim} + color {color_dim} (v{embedding.get('v', 1)})"
        else:
            embedding_dim = str(len(embedding)) if isinstance(embedding, list) else "0"
        return {
            "gallery_id": item.gallery_id,
            "event_id": item.event_id,
            "device_id": item.device_id,
            "device_name": device_name,
            "confidence": item.confidence,
            "bbox_index": item.bbox_index,
            "bbox": item.bbox,
            "crop_path": item.crop_path,
            "embedding_dim": embedding_dim,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "event": {
                "event_type": event.event_type if event else None,
                "timestamp": event.timestamp.isoformat() if event and event.timestamp else None,
                "thumbnail_path": event.thumbnail_path if event else None,
                "config_id": event.config_id if event else None,
            }
            if event
            else None,
        }
    finally:
        db.close()


def get_reid_model_info() -> Dict[str, Any]:
    from src.person_search import embedder as embedder_module
    from src.person_search.embedder import EMBEDDING_VERSION
    from src.person_search.human_parsing import get_human_parser
    from src.person_search.model_assets import get_parsing_onnx_path
    from src.person_search.reid_loader import DEFAULT_MODEL_NAME, DEFAULT_WEIGHTS_PATH

    weights_ready = os.path.isfile(DEFAULT_WEIGHTS_PATH)
    loaded = embedder_module._embedder is not None
    device = None
    if loaded:
        device = str(embedder_module._embedder.reid.device)

    parser = get_human_parser()
    parsing_onnx = get_parsing_onnx_path()

    return {
        "model": DEFAULT_MODEL_NAME,
        "embedding_version": EMBEDDING_VERSION,
        "feature_dim": 512,
        "color_gated": False,
        "attribute_enabled": True,
        "search_mode": "track+rerank",
        "faiss_available": faiss_available(),
        "faiss_ready": has_faiss_index(),
        "parsing_mode": parser.mode,
        "parsing_onnx_ready": parsing_onnx is not None,
        "parsing_onnx_path": parsing_onnx,
        "weights_path": DEFAULT_WEIGHTS_PATH,
        "weights_ready": weights_ready,
        "loaded": loaded,
        "device": device,
    }
