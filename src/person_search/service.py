"""人员图库入库与检索"""
import logging
import os
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from sqlalchemy import case, cast, exists, func, Integer, or_
from sqlalchemy.orm import Session, defer

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
from src.person_search.faiss_shards import (
    DEFAULT_DIM as FAISS_DEFAULT_DIM,
    drop_shards_before,
    get_shard_status,
    invalidate_shard_cache,
    rebuild_shard_from_rows,
    search_shards,
    shards_ready,
    upsert_track as upsert_track_shard,
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

DEFAULT_SEARCH_LIMIT = int(os.getenv("PERSON_SEARCH_LIMIT", "50000"))
MIN_PERSON_CONFIDENCE = float(os.getenv("PERSON_SEARCH_MIN_CONF", "0.45"))
COARSE_TOP_N = int(os.getenv("PERSON_SEARCH_COARSE_TOP", "300"))
RERANK_K1 = int(os.getenv("PERSON_SEARCH_RERANK_K1", "20"))
RERANK_K2 = int(os.getenv("PERSON_SEARCH_RERANK_K2", "6"))
APPEARANCE_BLEND = float(os.getenv("PERSON_SEARCH_APPEARANCE_BLEND", "0.1"))
SEARCH_INDEX_CACHE_TTL = int(os.getenv("PERSON_SEARCH_INDEX_CACHE_TTL", "300"))
VERSION_STATS_CACHE_TTL = int(os.getenv("PERSON_SEARCH_VERSION_STATS_TTL", "300"))
STATS_CACHE_TTL = int(os.getenv("PERSON_SEARCH_STATS_TTL", "30"))
DEFAULT_MIN_SIMILARITY = float(os.getenv("PERSON_SEARCH_MIN_SIMILARITY", "0.55"))
_quality_reject_count = 0

_rebuild_job_lock = threading.Lock()
_rebuild_job: Dict[str, Any] = {"running": False}
_index_rebuild_job_lock = threading.Lock()
_index_rebuild_job: Dict[str, Any] = {"running": False}

_search_index_cache: Dict[str, Any] = {
    "key": None,
    "built_at": 0.0,
    "items": [],
    "embeddings": [],
    "deep_matrix": None,
}

_version_stats_cache: Dict[str, Any] = {"built_at": 0.0, "data": None}
_gallery_stats_cache: Dict[str, Any] = {"built_at": 0.0, "data": None}


def invalidate_search_index_cache() -> None:
    """清空内存检索缓存与分片 LRU；不删除磁盘 FAISS 分片。"""
    _search_index_cache["key"] = None
    _search_index_cache["items"] = []
    _search_index_cache["embeddings"] = []
    _search_index_cache["deep_matrix"] = None
    _version_stats_cache["built_at"] = 0.0
    _version_stats_cache["data"] = None
    _gallery_stats_cache["built_at"] = 0.0
    _gallery_stats_cache["data"] = None
    invalidate_faiss_index()
    try:
        invalidate_shard_cache()
    except Exception as exc:
        logger.debug("invalidate_shard_cache: %s", exc)


def _upsert_track_to_shard(track_id: str, agg: Dict[str, Any], device_id: str, last_seen: datetime) -> None:
    deep = _as_deep(agg)
    if not deep or not last_seen:
        return
    try:
        upsert_track_shard(
            track_id,
            deep,
            device_id=device_id or "",
            last_seen=last_seen,
            embedding_version=EMBEDDING_VERSION,
            dim=len(deep),
        )
    except Exception as exc:
        logger.warning("轨迹分片 upsert 失败 track=%s: %s", track_id, exc)


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
    until: Optional[datetime] = None,
) -> Dict[str, Any]:
    """检索索引默认加载 person_track；无轨迹时回退帧级图库。"""
    until = until or datetime.now()
    cache_key = ("track", since.isoformat(), until.isoformat(), device_id or "", search_limit)
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
        .filter(PersonTrack.last_seen <= until)
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
        gq = gq.filter(PersonGalleryItem.created_at <= until)
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
    from src.storage_fs import write_bgr_image

    save_dir = Path(f"storage/person_crops/{ts.strftime('%Y-%m-%d')}/{device_id}")
    crop_path = save_dir / f"{event_id}_{index}.jpg"
    write_bgr_image(crop_path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return str(crop_path).replace("\\", "/")


def _persist_track(db, track) -> None:
    """将缓冲轨迹写入/更新 person_track，并回填帧级 track_id。

    注意：SessionLocal 为 autoflush=False。同一事务内多次入库时，
    query().first() 看不到尚未 flush 的 pending 对象，会重复 add 同一主键；
    必须用 Session.get() 先查 identity map。
    """
    frames = list(track.frames)
    if not frames:
        return
    frames.sort(key=lambda f: f.quality_score, reverse=True)
    keyframes = frames[:12]
    agg = aggregate_deep_embedding(keyframes)
    if not agg:
        return
    best = keyframes[0]
    row = db.get(PersonTrack, track.track_id)
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
        item = db.get(PersonGalleryItem, fr.gallery_id)
        if not item:
            continue
        item.track_id = track.track_id
        item.is_keyframe = fr.crop_path in key_paths

    # 增量写入日分片（失败不影响入库）
    _upsert_track_to_shard(track.track_id, agg, track.device_id, track.last_seen)


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
            # 分片已在 _persist_track 增量写入；仅清内存检索缓存
            _search_index_cache["key"] = None
            _search_index_cache["items"] = []
            _search_index_cache["embeddings"] = []
            _search_index_cache["deep_matrix"] = None
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
    touched_tracks = {}
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
            quality = compute_crop_quality(
                crop,
                detection_confidence=conf,
                bbox=bbox,
                frame_shape=getattr(frame, "shape", None),
            )
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
            touched_tracks[active.track_id] = active
            saved += 1
        # 同一帧内同一轨迹只落盘一次，避免 autoflush=False 下重复 INSERT
        for tr in touched_tracks.values():
            _persist_track(db, tr)
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
    """用 SQL 聚合统计版本，避免把全部 embedding JSON 拉进 Python。"""
    now = time.time()
    cached = _version_stats_cache.get("data")
    if cached and now - float(_version_stats_cache.get("built_at") or 0) < VERSION_STATS_CACHE_TTL:
        return dict(cached)

    base = (
        db.query(PersonGalleryItem.gallery_id)
        .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
    )
    # embedding->>'v' 缺失/非对象 → 视为旧版
    version_expr = func.coalesce(
        cast(PersonGalleryItem.embedding["v"].as_string(), Integer),
        0,
    )
    legacy = base.filter(version_expr < EMBEDDING_VERSION).count()

    current_base = base.filter(version_expr >= EMBEDDING_VERSION)

    def _json_array_len(key: str):
        node = PersonGalleryItem.embedding[key]
        return case(
            (func.jsonb_typeof(node) == "array", func.jsonb_array_length(node)),
            else_=0,
        )

    # stale：版本够但仍缺 garment/clothing/body 字段或长度不足
    stale_filter = or_(
        _json_array_len("garment") < 39,
        _json_array_len("clothing") < 9,
        _json_array_len("body") < 7,
    )
    stale = current_base.filter(stale_filter).count()
    current = max(0, current_base.count() - stale)

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
            row = db.get(PersonTrack, tid)
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
            if row.last_seen and agg:
                _upsert_track_to_shard(tid, agg, row.device_id, row.last_seen)
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


def get_faiss_index_status() -> Dict[str, Any]:
    status = get_shard_status(EMBEDDING_VERSION, FAISS_DEFAULT_DIM)
    # 若实际特征维度与默认不同，再查一遍（兼容）
    if not status.get("shard_count"):
        for dim in (512, 2048, 768):
            alt = get_shard_status(EMBEDDING_VERSION, dim)
            if alt.get("shard_count"):
                status = alt
                break
    status["search_limit"] = DEFAULT_SEARCH_LIMIT
    status["coarse_top"] = COARSE_TOP_N
    return status


def get_index_rebuild_job() -> Dict[str, Any]:
    with _index_rebuild_job_lock:
        return dict(_index_rebuild_job)


def rebuild_faiss_shards(*, days: int = 30, dim: int = FAISS_DEFAULT_DIM) -> Dict[str, Any]:
    """按日从 person_track 全量重建 FAISS 分片。"""
    days = max(1, min(int(days), 90))
    until = datetime.now()
    since = until - timedelta(days=days)
    db = SessionLocal()
    rebuilt = 0
    vectors = 0
    try:
        # 按 last_seen 落在各自然日
        cur = since.date()
        end = until.date()
        while cur <= end:
            day = cur.isoformat()
            day_start = datetime(cur.year, cur.month, cur.day)
            day_end = day_start + timedelta(days=1)
            rows = (
                db.query(PersonTrack)
                .filter(PersonTrack.last_seen >= day_start)
                .filter(PersonTrack.last_seen < day_end)
                .filter(PersonTrack.agg_embedding.isnot(None))
                .all()
            )
            payload = []
            use_dim = dim
            for row in rows:
                deep = _as_deep(row.agg_embedding)
                if not deep:
                    continue
                if use_dim and len(deep) != use_dim:
                    # 以首条有效维度为准
                    if not payload:
                        use_dim = len(deep)
                    else:
                        continue
                payload.append(
                    {
                        "track_id": row.track_id,
                        "deep": deep,
                        "device_id": row.device_id,
                        "last_seen": row.last_seen or day_start,
                    }
                )
            result = rebuild_shard_from_rows(
                day,
                payload,
                embedding_version=EMBEDDING_VERSION,
                dim=use_dim or dim,
            )
            rebuilt += 1
            vectors += int(result.get("count") or 0)
            cur += timedelta(days=1)
        invalidate_search_index_cache()
        return {
            "ok": True,
            "days": days,
            "shards_rebuilt": rebuilt,
            "vectors": vectors,
            "status": get_faiss_index_status(),
        }
    finally:
        db.close()


def start_rebuild_faiss_index_async(*, days: int = 30) -> Dict[str, Any]:
    days = max(1, min(int(days), 90))
    with _index_rebuild_job_lock:
        if _index_rebuild_job.get("running"):
            return {
                "started": False,
                "message": "已有索引重建任务进行中",
                "job": dict(_index_rebuild_job),
            }
        _index_rebuild_job.clear()
        _index_rebuild_job.update(
            running=True,
            days=days,
            phase="starting",
            shards_rebuilt=0,
            vectors=0,
            error=None,
            started_at=datetime.now().isoformat(),
            finished_at=None,
        )
        job_ref = _index_rebuild_job

    def _worker() -> None:
        try:
            with _index_rebuild_job_lock:
                job_ref["phase"] = "rebuilding"
            result = rebuild_faiss_shards(days=days)
            with _index_rebuild_job_lock:
                job_ref.update(
                    running=False,
                    phase="done",
                    shards_rebuilt=result.get("shards_rebuilt") or 0,
                    vectors=result.get("vectors") or 0,
                    finished_at=datetime.now().isoformat(),
                    status=result.get("status"),
                )
        except Exception as exc:
            logger.exception("FAISS 分片重建失败")
            with _index_rebuild_job_lock:
                job_ref.update(
                    running=False,
                    phase="error",
                    error=str(exc),
                    finished_at=datetime.now().isoformat(),
                )

    threading.Thread(target=_worker, name="faiss-shard-rebuild", daemon=True).start()
    return {"started": True, "message": f"已开始重建近 {days} 天检索索引", "job": get_index_rebuild_job()}


def drop_faiss_shards_before(day: str) -> Dict[str, Any]:
    removed = drop_shards_before(day, embedding_version=EMBEDDING_VERSION, dim=FAISS_DEFAULT_DIM)
    invalidate_shard_cache()
    return {"removed": removed, "before": day, "status": get_faiss_index_status()}


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


def purge_orphan_person_data() -> Dict[str, Any]:
    """清理孤儿图库、空轨迹与遗留抠图文件（手动/运维用）。"""
    from src.person_search.gallery_cleanup import cleanup_orphan_tracks

    gallery_deleted = cleanup_orphan_gallery_items()
    files_deleted = cleanup_orphan_person_crop_files()
    db = SessionLocal()
    try:
        tracks_deleted = cleanup_orphan_tracks(db)
        if tracks_deleted:
            db.commit()
            invalidate_search_index_cache()
    finally:
        db.close()
    return {
        "gallery_deleted": gallery_deleted,
        "tracks_deleted": tracks_deleted,
        "files_deleted": files_deleted,
    }


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
    """清理检测事件已删除但遗留的图库记录，并顺带清理空轨迹。"""
    from src.person_search.gallery_cleanup import cleanup_orphan_tracks

    db = SessionLocal()
    deleted = 0
    tracks_removed = 0
    try:
        orphans = (
            db.query(PersonGalleryItem)
            .outerjoin(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .filter(DetectionEvent.event_id.is_(None))
            .all()
        )
        affected_tracks = {item.track_id for item in orphans if item.track_id}
        from src.storage_fs import safe_unlink

        for item in orphans:
            if item.crop_path:
                if not safe_unlink(item.crop_path):
                    logger.warning("删除孤儿抠图失败 %s", item.crop_path)
            db.delete(item)
            deleted += 1
        if deleted:
            db.flush()
            tracks_removed = cleanup_orphan_tracks(db, affected_tracks)
            # 再扫一遍全量空轨迹（历史遗留）
            tracks_removed += cleanup_orphan_tracks(db)
            db.commit()
            invalidate_search_index_cache()
            logger.info(
                "已清理 %s 条孤儿人员图库、%s 条空轨迹",
                deleted,
                tracks_removed,
            )
        else:
            # 图库已干净时仍清理历史空轨迹
            tracks_removed = cleanup_orphan_tracks(db)
            if tracks_removed:
                db.commit()
                invalidate_search_index_cache()
                logger.info("已清理 %s 条空轨迹", tracks_removed)
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


def _parse_time_bound(value: Optional[str], *, is_end: bool = False) -> Optional[datetime]:
    """解析 YYYY-MM-DD 或 YYYY-MM-DD HH:mm:ss / ISO。仅日期时：起=00:00:00，止=23:59:59。"""
    if not value:
        return None
    # 查询串里空格常被编成 +，需还原
    raw = str(value).strip().replace("T", " ").replace("+", " ")
    while "  " in raw:
        raw = raw.replace("  ", " ")
    for fmt, n in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        try:
            dt = datetime.strptime(raw[:n], fmt)
            if fmt == "%Y-%m-%d" and is_end:
                return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return dt
        except (TypeError, ValueError):
            continue
    return None


def resolve_search_window(
    *,
    days: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Tuple[datetime, datetime]:
    """解析检索/图库时间窗。优先 date_from/date_to（可含时分秒），否则按 days 回滚。"""
    now = datetime.now()
    today = now.date()
    since = _parse_time_bound(date_from, is_end=False)
    until = _parse_time_bound(date_to, is_end=True)
    if since is not None or until is not None:
        if since is None:
            since = until.replace(hour=0, minute=0, second=0, microsecond=0) if until else datetime(
                today.year, today.month, today.day
            )
        if until is None:
            until = since.replace(hour=23, minute=59, second=59, microsecond=999999)
        if until < since:
            since, until = until, since
        if (until.date() - since.date()).days > 89:
            since = datetime(until.year, until.month, until.day) - timedelta(days=89)
        if until > now:
            until = now
        return since, until

    span = max(1, min(int(days or 1), 90))
    # 按自然日：近 N 天 = 含今天共 N 个日历日
    start_d = today - timedelta(days=span - 1)
    since = datetime(start_d.year, start_d.month, start_d.day)
    return since, now


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    raw = str(value).strip().replace("T", " ").replace("+", " ")
    if raw.endswith("Z"):
        raw = raw[:-1]
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M:%S.%f", 26), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(raw[:n], fmt)
        except (TypeError, ValueError):
            continue
    return None


def _best_crop_in_window(db, track_id: str, since: datetime, until: datetime) -> Optional[str]:
    """优先用时间窗内最高质量帧作展示图，避免代表图落在窗外导致误以为时间过滤失效。"""
    row = (
        db.query(PersonGalleryItem)
        .filter(PersonGalleryItem.track_id == track_id)
        .filter(PersonGalleryItem.created_at >= since)
        .filter(PersonGalleryItem.created_at <= until)
        .order_by(PersonGalleryItem.quality_score.desc())
        .first()
    )
    return row.crop_path if row and row.crop_path else None


def _load_tracks_by_ids(
    db,
    track_ids: List[str],
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Any]:
    """按候选 track_id 批量加载轨迹元数据与特征；可选按 last_seen 再过滤时间窗。"""
    if not track_ids:
        return {"items": [], "embeddings": [], "deep_matrix": np.empty((0, 0), dtype=np.float32)}
    rows = (
        db.query(PersonTrack, Device.device_name)
        .outerjoin(Device, PersonTrack.device_id == Device.device_id)
        .filter(PersonTrack.track_id.in_(track_ids))
        .all()
    )
    by_id = {row.track_id: (row, name) for row, name in rows}
    items: List[Dict[str, Any]] = []
    embeddings: List[Any] = []
    deep_rows: List[List[float]] = []
    for tid in track_ids:
        packed = by_id.get(tid)
        if not packed:
            continue
        track, device_name = packed
        if since is not None and track.last_seen and track.last_seen < since:
            continue
        if until is not None and track.last_seen and track.last_seen > until:
            continue
        embedding = track.agg_embedding
        deep = _as_deep(embedding)
        if not deep:
            continue
        crop_path = track.repr_crop_path
        if since is not None and until is not None:
            in_win = _best_crop_in_window(db, track.track_id, since, until)
            if in_win:
                crop_path = in_win
            elif not crop_path:
                continue
            else:
                # 窗内无帧：该轨迹不应作为「该时段」结果
                continue
        items.append(
            {
                "result_type": "track",
                "track_id": track.track_id,
                "gallery_id": None,
                "event_id": None,
                "device_id": track.device_id,
                "device_name": device_name,
                "crop_path": crop_path,
                "frame_count": track.frame_count or 0,
                "quality_score": track.quality_score,
                "first_seen": track.first_seen.isoformat() if track.first_seen else None,
                "last_seen": track.last_seen.isoformat() if track.last_seen else None,
                "created_at": track.last_seen.isoformat() if track.last_seen else None,
            }
        )
        embeddings.append(embedding)
        deep_rows.append(deep)
    deep_matrix = np.asarray(deep_rows, dtype=np.float32) if deep_rows else np.empty((0, 0), dtype=np.float32)
    return {"items": items, "embeddings": embeddings, "deep_matrix": deep_matrix}


def _build_query_vec(query_bgr: np.ndarray, embedder) -> Optional[Dict[str, Any]]:
    query_bgr = prepare_query_image(query_bgr)
    query_vec = embedder.embed_bgr(query_bgr, tta_flip=True)
    if not query_vec:
        return None
    clean_query = strip_segmentation_border(query_bgr)
    if not query_vec.get("garment"):
        query_vec = {**query_vec, "garment": extract_garment_signature(clean_query) or []}
    if not query_vec.get("clothing"):
        query_vec = {**query_vec, "clothing": extract_clothing_signature(clean_query) or []}
    if not query_vec.get("body"):
        query_vec = {**query_vec, "body": extract_body_signature(clean_query) or []}
    if not query_vec.get("attrs"):
        query_vec = {**query_vec, "attrs": extract_person_attributes(clean_query) or {}}
    return query_vec


def _max_fuse_sims(sim_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """多查询相似度按字段取 max，再拼一条融合结果。"""
    if not sim_rows:
        return {}
    if len(sim_rows) == 1:
        return sim_rows[0]
    keys = (
        "color_similarity",
        "hue_similarity",
        "garment_similarity",
        "body_similarity",
        "attr_similarity",
    )
    out: Dict[str, Any] = {}
    for key in keys:
        vals = [float(r.get(key) or 0) for r in sim_rows if r.get(key) is not None]
        out[key] = max(vals) if vals else None
    # 性别提示：取首个非空
    for row in sim_rows:
        if row.get("gender_hint"):
            out["gender_hint"] = row.get("gender_hint")
            break
    else:
        out["gender_hint"] = None
    return out


def search_by_image(
    query_bgr: np.ndarray,
    *,
    top_k: int = 20,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    device_id: Optional[str] = None,
    days: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> Dict[str, Any]:
    """单图检索（兼容旧调用）。"""
    return search_by_images(
        [query_bgr],
        top_k=top_k,
        min_similarity=min_similarity,
        device_id=device_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
        search_limit=search_limit,
    )


def search_by_images(
    query_bgrs: List[np.ndarray],
    *,
    top_k: int = 20,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    device_id: Optional[str] = None,
    days: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> Dict[str, Any]:
    """多图检索：各图独立提特征 → 粗检并集 → 分数按 max 融合。"""
    started = time.perf_counter()
    flush_expired_tracks()
    images = [img for img in (query_bgrs or []) if img is not None and getattr(img, "size", 0)]
    if not images:
        return {
            "results": [],
            "legacy_skipped": 0,
            "needs_rebuild": False,
            "search_ms": 0,
            "query_count": 0,
        }

    embedder = get_person_embedder()
    query_vecs: List[Dict[str, Any]] = []
    for img in images:
        vec = _build_query_vec(img, embedder)
        if vec:
            query_vecs.append(vec)
    if not query_vecs:
        return {
            "results": [],
            "legacy_skipped": 0,
            "needs_rebuild": False,
            "search_ms": int((time.perf_counter() - started) * 1000),
            "query_count": 0,
        }

    query_deeps = [np.asarray(v.get("deep") or [], dtype=np.float32) for v in query_vecs]
    if any(d.size == 0 for d in query_deeps):
        return {
            "results": [],
            "legacy_skipped": 0,
            "needs_rebuild": True,
            "search_ms": int((time.perf_counter() - started) * 1000),
            "query_count": len(query_vecs),
        }
    dim = int(query_deeps[0].size)
    if any(int(d.size) != dim for d in query_deeps):
        return {
            "results": [],
            "legacy_skipped": 0,
            "needs_rebuild": True,
            "search_ms": int((time.perf_counter() - started) * 1000),
            "query_count": len(query_vecs),
        }

    since, until = resolve_search_window(days=days, date_from=date_from, date_to=date_to)
    db = SessionLocal()
    try:
        items: List[Dict[str, Any]] = []
        embeddings: List[Any] = []
        deep_matrix = np.empty((0, 0), dtype=np.float32)
        legacy_skipped = 0
        backend = "matrix"
        scanned = 0
        candidate_idx: np.ndarray = np.arange(0, dtype=np.int32)
        multi_tag = f"x{len(query_vecs)}" if len(query_vecs) > 1 else ""

        use_shards = shards_ready(EMBEDDING_VERSION, dim or FAISS_DEFAULT_DIM)
        if use_shards:
            score_map: Dict[str, float] = {}
            day_lists: List[Any] = []
            for q_deep in query_deeps:
                shard_ids, shard_scores, shard_meta = search_shards(
                    q_deep,
                    since=since,
                    until=until,
                    device_id=device_id,
                    top_k=COARSE_TOP_N,
                    embedding_version=EMBEDDING_VERSION,
                    dim=dim,
                )
                scanned = max(scanned, int(shard_meta.get("scanned") or 0))
                backend = str(shard_meta.get("backend") or "faiss_shards")
                if shard_meta.get("day_list"):
                    day_lists.append(shard_meta.get("day_list"))
                scores_iter = shard_scores if shard_scores is not None else []
                for tid, sc in zip(shard_ids, scores_iter):
                    if not tid:
                        continue
                    prev = score_map.get(tid)
                    score = float(sc)
                    if prev is None or score > prev:
                        score_map[tid] = score
            ranked_ids = sorted(score_map.keys(), key=lambda t: score_map[t], reverse=True)[
                :COARSE_TOP_N
            ]
            loaded = _load_tracks_by_ids(db, ranked_ids, since=since, until=until)
            items = loaded["items"]
            embeddings = loaded["embeddings"]
            deep_matrix = loaded["deep_matrix"]
            order_map = {it["track_id"]: i for i, it in enumerate(items)}
            ordered = [order_map[tid] for tid in ranked_ids if tid in order_map]
            candidate_idx = np.asarray(ordered, dtype=np.int32)
            if multi_tag:
                backend = f"{backend}{multi_tag}"
            logger.info(
                "分片检索 queries=%s window=%s~%s scanned=%s candidates=%s",
                len(query_vecs),
                since.isoformat(sep=" ", timespec="seconds"),
                until.isoformat(sep=" ", timespec="seconds"),
                scanned,
                len(items),
            )

        if deep_matrix.size == 0:
            index = _load_search_index(
                db, since=since, until=until, device_id=device_id, search_limit=search_limit
            )
            fallback_ids = [it.get("track_id") for it in (index["items"] or []) if it.get("track_id")]
            if fallback_ids:
                loaded = _load_tracks_by_ids(db, fallback_ids, since=since, until=until)
                items = loaded["items"]
                embeddings = loaded["embeddings"]
                deep_matrix = loaded["deep_matrix"]
            else:
                items = index["items"]
                embeddings = index["embeddings"]
                deep_matrix = index["deep_matrix"]
            legacy_skipped = int(index.get("legacy_skipped") or 0)
            scanned = len(items)
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
                    "query_count": len(query_vecs),
                }
            if dim != deep_matrix.shape[1]:
                search_ms = int((time.perf_counter() - started) * 1000)
                return {
                    "results": [],
                    "legacy_skipped": legacy_skipped + len(items),
                    "needs_rebuild": True,
                    "search_ms": search_ms,
                    "scanned": len(items),
                    "reranked": 0,
                    "query_count": len(query_vecs),
                }
            backend = f"matrix{multi_tag}" if multi_tag else "matrix"
            coarse_n = min(COARSE_TOP_N, len(items))
            # 多查询 deep 分取 max 再选 top
            fused_scores = np.full(len(items), -1.0, dtype=np.float32)
            for q_deep in query_deeps:
                fused_scores = np.maximum(fused_scores, deep_matrix @ q_deep)
            if has_faiss_index() and len(query_deeps) == 1:
                id_to_idx = {
                    (it.get("track_id") or it.get("gallery_id")): i for i, it in enumerate(items)
                }
                faiss_ids, _faiss_scores = search_faiss(query_deeps[0], top_k=coarse_n)
                idxs = [id_to_idx[tid] for tid in faiss_ids if tid in id_to_idx]
                if idxs:
                    candidate_idx = np.asarray(idxs, dtype=np.int32)
                    backend = ("faiss" if faiss_available() else "memory_index") + multi_tag
                else:
                    if coarse_n < len(items):
                        candidate_idx = np.argpartition(fused_scores, -coarse_n)[-coarse_n:]
                    else:
                        candidate_idx = np.arange(len(items), dtype=np.int32)
                    candidate_idx = candidate_idx[np.argsort(fused_scores[candidate_idx])[::-1]]
            else:
                if coarse_n < len(items):
                    candidate_idx = np.argpartition(fused_scores, -coarse_n)[-coarse_n:]
                else:
                    candidate_idx = np.arange(len(items), dtype=np.int32)
                candidate_idx = candidate_idx[np.argsort(fused_scores[candidate_idx])[::-1]]
        elif dim != deep_matrix.shape[1]:
            search_ms = int((time.perf_counter() - started) * 1000)
            return {
                "results": [],
                "legacy_skipped": len(items),
                "needs_rebuild": True,
                "search_ms": search_ms,
                "scanned": scanned or len(items),
                "reranked": 0,
                "backend": backend,
                "query_count": len(query_vecs),
            }

        frame_fallback = bool(items) and items[0].get("result_type") == "frame"
        cand_deeps = [list(deep_matrix[int(i)]) for i in candidate_idx]
        # 各查询重排后按候选位取 max
        rr_stack: List[List[float]] = []
        if frame_fallback:
            for q_deep in query_deeps:
                rr_stack.append(
                    [float(np.dot(deep_matrix[int(i)], q_deep)) for i in candidate_idx]
                )
            backend = f"{backend}+no_rerank"
        else:
            for q_deep in query_deeps:
                rr_stack.append(
                    list(
                        rerank_scores(
                            list(q_deep),
                            cand_deeps,
                            k1=RERANK_K1,
                            k2=RERANK_K2,
                            lambda_value=0.3,
                        )
                    )
                )

        scored: List[Dict[str, Any]] = []
        for pos, idx in enumerate(candidate_idx):
            meta = items[int(idx)]
            embedding = embeddings[int(idx)]
            gal_deep = deep_matrix[int(idx)]
            deep_sims = [float(np.dot(gal_deep, q_deep)) for q_deep in query_deeps]
            deep_sim = max(deep_sims) if deep_sims else 0.0
            sim_rows = []
            for qi, query_vec in enumerate(query_vecs):
                sim_rows.append(
                    embedding_similarity(
                        query_vec,
                        embedding,
                        precomputed_deep_sim=deep_sims[qi],
                        allow_image_io=False,
                    )
                )
            sims = _max_fuse_sims(sim_rows)
            appearance = float(sims.get("hue_similarity") or 0)
            if appearance <= 0:
                appearance = float(sims.get("color_similarity") or 0)
            rr_vals = [float(row[pos]) for row in rr_stack if pos < len(row)]
            rr = max(rr_vals) if rr_vals else deep_sim
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
                "query_count": len(query_vecs),
            }
            scored.append(row)

        scored.sort(key=lambda x: x.get("similarity") or 0, reverse=True)
        results = scored[: max(1, min(top_k, 100))]

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
        scanned_out = scanned if scanned else len(items)
        logger.info(
            "人员搜索完成 queries=%s scanned=%s coarse=%s results=%s backend=%s ms=%s",
            len(query_vecs),
            scanned_out,
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
            "scanned": scanned_out,
            "reranked": len(candidate_idx),
            "backend": backend,
            "query_count": len(query_vecs),
        }
    finally:
        db.close()


def get_gallery_stats(*, run_cleanup: bool = False) -> Dict[str, Any]:
    # 页面加载默认不做全量孤儿清理；需要时由定时任务或显式传参触发
    if run_cleanup:
        cleanup_orphan_gallery_items()
        cleanup_orphan_person_crop_files()
        from src.person_search.gallery_cleanup import cleanup_orphan_tracks

        db_cleanup = SessionLocal()
        try:
            removed_tracks = cleanup_orphan_tracks(db_cleanup)
            if removed_tracks:
                db_cleanup.commit()
                invalidate_search_index_cache()
                logger.info("统计时清理空轨迹 %s 条", removed_tracks)
        finally:
            db_cleanup.close()

    now = time.time()
    cached = _gallery_stats_cache.get("data")
    if (
        not run_cleanup
        and cached
        and now - float(_gallery_stats_cache.get("built_at") or 0) < STATS_CACHE_TTL
    ):
        return dict(cached)

    db = SessionLocal()
    try:
        base = (
            db.query(PersonGalleryItem.gallery_id)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
        )
        total = base.count()
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = base.filter(PersonGalleryItem.created_at >= today_start).count()
        devices = (
            db.query(func.count(func.distinct(PersonGalleryItem.device_id)))
            .select_from(PersonGalleryItem)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .scalar()
        ) or 0
        # 只统计仍有帧图库的轨迹，避免空壳轨迹把数字顶高
        track_count = (
            db.query(func.count(PersonTrack.track_id))
            .filter(exists().where(PersonGalleryItem.track_id == PersonTrack.track_id))
            .scalar()
        ) or 0
        orphan_track_count = (
            db.query(func.count(PersonTrack.track_id))
            .filter(~exists().where(PersonGalleryItem.track_id == PersonTrack.track_id))
            .scalar()
        ) or 0
        version_stats = _embedding_version_stats(db)
        result = {
            "total": total,
            "today": today,
            "device_count": int(devices),
            "track_count": int(track_count),
            "orphan_track_count": int(orphan_track_count),
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
        _gallery_stats_cache["built_at"] = now
        _gallery_stats_cache["data"] = result
        return dict(result)
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
                    "bbox_index": f.bbox_index,
                    "bbox": f.bbox,
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
    days: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    since, until = resolve_search_window(days=days, date_from=date_from, date_to=date_to)
    db = SessionLocal()
    try:
        # count 不 join device，避免无谓开销；列表查询 defer 掉巨型 embedding
        count_q = (
            db.query(func.count(PersonGalleryItem.gallery_id))
            .select_from(PersonGalleryItem)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .filter(PersonGalleryItem.created_at >= since)
            .filter(PersonGalleryItem.created_at <= until)
        )
        if device_id:
            count_q = count_q.filter(PersonGalleryItem.device_id == device_id)
        total = int(count_q.scalar() or 0)

        q = (
            db.query(PersonGalleryItem, Device.device_name)
            .options(defer(PersonGalleryItem.embedding))
            .join(Device, PersonGalleryItem.device_id == Device.device_id)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
            .filter(PersonGalleryItem.created_at >= since)
            .filter(PersonGalleryItem.created_at <= until)
        )
        if device_id:
            q = q.filter(PersonGalleryItem.device_id == device_id)
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
        # outerjoin：设备/事件缺失时仍返回图库主字段（含 bbox_index）
        row = (
            db.query(PersonGalleryItem, Device.device_name, DetectionEvent)
            .outerjoin(Device, PersonGalleryItem.device_id == Device.device_id)
            .outerjoin(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
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
    from src.person_search import human_parsing as human_parsing_module
    from src.person_search.embedder import EMBEDDING_VERSION
    from src.person_search.model_assets import get_parsing_onnx_path
    from src.person_search.reid_loader import DEFAULT_MODEL_NAME, DEFAULT_WEIGHTS_PATH

    weights_ready = os.path.isfile(DEFAULT_WEIGHTS_PATH)
    loaded = embedder_module._embedder is not None
    device = None
    if loaded:
        device = str(embedder_module._embedder.reid.device)

    # 不在信息接口里加载 ONNX，避免首次进页卡顿
    parsing_onnx = get_parsing_onnx_path()
    parser = human_parsing_module._parser
    if parser is not None:
        parsing_mode = parser.mode
    elif parsing_onnx:
        parsing_mode = "onnx_lip(lazy)"
    else:
        parsing_mode = "fast_zone"

    shard_status = get_faiss_index_status()
    return {
        "model": DEFAULT_MODEL_NAME,
        "embedding_version": EMBEDDING_VERSION,
        "feature_dim": 512,
        "color_gated": False,
        "attribute_enabled": True,
        "search_mode": "track+faiss_shards+rerank",
        "faiss_available": faiss_available(),
        "faiss_ready": bool(shard_status.get("shard_count")) or has_faiss_index(),
        "faiss_shards": shard_status,
        "search_limit": DEFAULT_SEARCH_LIMIT,
        "coarse_top": COARSE_TOP_N,
        "parsing_mode": parsing_mode,
        "parsing_onnx_ready": parsing_onnx is not None,
        "parsing_onnx_path": parsing_onnx,
        "weights_path": DEFAULT_WEIGHTS_PATH,
        "weights_ready": weights_ready,
        "loaded": loaded,
        "device": device,
    }
