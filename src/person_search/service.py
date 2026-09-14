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

from src.database import Device, DetectionEvent, PersonGalleryItem, SessionLocal
from src.person_search.embedder import (
    EMBEDDING_VERSION,
    embedding_needs_rebuild,
    embedding_similarity,
    embedding_version,
    get_person_embedder,
    passes_match_gate,
)
from src.person_search.par_attrs import extract_person_attributes
from src.person_search.query_preprocess import prepare_query_image
from src.person_search.utils import (
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
MIN_PERSON_CONFIDENCE = 0.35
RERANK_CANDIDATE_LIMIT = int(os.getenv("PERSON_SEARCH_RERANK_LIMIT", "300"))
VERIFY_CANDIDATE_LIMIT = int(os.getenv("PERSON_SEARCH_VERIFY_LIMIT", "200"))
DEEP_PREFILTER = float(os.getenv("PERSON_SEARCH_DEEP_PREFILTER", "0.40"))
SCORE_GAP_KEEP = float(os.getenv("PERSON_SEARCH_SCORE_GAP", "0.12"))
SEARCH_INDEX_CACHE_TTL = int(os.getenv("PERSON_SEARCH_INDEX_CACHE_TTL", "300"))

_rebuild_job_lock = threading.Lock()
_rebuild_job: Dict[str, Any] = {"running": False}

_search_index_cache: Dict[str, Any] = {
    "key": None,
    "built_at": 0.0,
    "items": [],
    "embeddings": [],
    "deep_matrix": None,
}


def invalidate_search_index_cache() -> None:
    _search_index_cache["key"] = None
    _search_index_cache["items"] = []
    _search_index_cache["embeddings"] = []
    _search_index_cache["deep_matrix"] = None


def _load_search_index(
    db,
    *,
    since: datetime,
    device_id: Optional[str],
    search_limit: int,
) -> Dict[str, Any]:
    cache_key = (since.isoformat(), device_id or "", search_limit)
    now = time.time()
    if (
        _search_index_cache.get("key") == cache_key
        and now - float(_search_index_cache.get("built_at") or 0) < SEARCH_INDEX_CACHE_TTL
        and _search_index_cache.get("items")
    ):
        return _search_index_cache

    q = _active_gallery_query(db)
    q = q.filter(PersonGalleryItem.created_at >= since)
    if device_id:
        q = q.filter(PersonGalleryItem.device_id == device_id)
    rows = q.order_by(PersonGalleryItem.created_at.desc()).limit(search_limit).all()

    items: List[Dict[str, Any]] = []
    embeddings: List[Any] = []
    deep_rows: List[List[float]] = []
    legacy_skipped = 0
    for item, device_name in rows:
        embedding = item.embedding
        if not embedding or not isinstance(embedding, dict):
            legacy_skipped += 1
            continue
        deep = embedding.get("deep") or []
        if not deep:
            legacy_skipped += 1
            continue
        items.append(
            {
                "gallery_id": item.gallery_id,
                "event_id": item.event_id,
                "device_id": item.device_id,
                "device_name": device_name,
                "detection_confidence": item.confidence,
                "bbox_index": item.bbox_index,
                "bbox": item.bbox,
                "crop_path": item.crop_path,
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
    return payload


def _save_crop(crop: np.ndarray, device_id: str, event_id: str, index: int, ts: datetime) -> str:
    save_dir = Path(f"storage/person_crops/{ts.strftime('%Y-%m-%d')}/{device_id}")
    save_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
    crop_path = save_dir / f"{event_id}_{index}.jpg"
    cv2.imwrite(str(crop_path), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return str(crop_path).replace("\\", "/")


def index_frame_persons(
    frame,
    detections: List[Dict[str, Any]],
    *,
    event_id: str,
    device_id: str,
    timestamp: Optional[datetime] = None,
    min_confidence: float = MIN_PERSON_CONFIDENCE,
) -> int:
    """从帧中抠出 person 目标并写入图库，返回入库数量"""
    if frame is None:
        return 0
    ts = timestamp or datetime.now()
    persons = filter_person_detections(detections)
    if not persons:
        return 0

    try:
        embedder = get_person_embedder()
    except Exception as exc:
        logger.warning("PersonEmbedder 不可用，跳过入库: %s", exc)
        return 0

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
            if crop is None or not is_valid_person_crop(crop):
                continue
            embedding = embedder.embed_bgr(crop)
            if not embedding:
                continue
            crop_path = _save_crop(crop, device_id, event_id, idx, ts)
            item = PersonGalleryItem(
                gallery_id=str(uuid.uuid4()),
                event_id=event_id,
                device_id=device_id,
                bbox_index=idx,
                confidence=conf,
                crop_path=crop_path,
                bbox=list(bbox),
                embedding=embedding,
                created_at=ts,
            )
            db.add(item)
            saved += 1
        if saved:
            db.commit()
            invalidate_search_index_cache()
            logger.info("人员图库入库 %s 条 event=%s device=%s", saved, event_id, device_id)
    except Exception as exc:
        db.rollback()
        logger.error("人员图库入库失败: %s", exc)
    finally:
        db.close()
    return saved


def index_detection_event(event_id: str) -> Dict[str, Any]:
    """从已有检测事件回填人员图库"""
    db = SessionLocal()
    try:
        event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first()
        if not event:
            return {"event_id": event_id, "indexed": 0, "message": "事件不存在"}
        if not event.thumbnail_path or not os.path.exists(event.thumbnail_path):
            return {"event_id": event_id, "indexed": 0, "message": "事件无可用截图"}
        frame = cv2.imread(event.thumbnail_path)
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
    return {
        "current_embeddings": current,
        "legacy_embeddings": legacy,
        "stale_embeddings": stale,
    }


def _touch_rebuild_job(job: Optional[Dict[str, Any]], **fields: Any) -> None:
    if job is not None:
        job.update(fields)


def rebuild_gallery_embeddings(limit: int = 5000, job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        pending = sum(1 for item in items if embedding_needs_rebuild(item.embedding))
        _touch_rebuild_job(job, total=len(items), pending=pending, phase="running")
        logger.info("开始重建图库特征：共 %s 条记录，待升级 %s 条", len(items), pending)
        for item in items:
            if not embedding_needs_rebuild(item.embedding):
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
            embedding = embedder.embed_bgr(crop)
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
            invalidate_search_index_cache()
        _touch_rebuild_job(job, phase="done", updated=updated, failed=failed, skipped=skipped)
        logger.info("图库特征重建完成 updated=%s failed=%s skipped=%s", updated, failed, skipped)
        return {
            "updated": updated,
            "failed": failed,
            "skipped": skipped,
            "pending": pending,
            "total": len(items),
            "embedding_version": EMBEDDING_VERSION,
        }
    except Exception:
        db.rollback()
        _touch_rebuild_job(job, phase="error")
        raise
    finally:
        db.close()


def get_rebuild_gallery_job() -> Dict[str, Any]:
    with _rebuild_job_lock:
        return dict(_rebuild_job)


def start_rebuild_gallery_embeddings_async(limit: int = 5000) -> Dict[str, Any]:
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
            total=0,
            pending=0,
            updated=0,
            failed=0,
            skipped=0,
            phase="starting",
            error=None,
            started_at=datetime.now().isoformat(),
            finished_at=None,
        )
        job_ref = _rebuild_job

    def _worker() -> None:
        try:
            result = rebuild_gallery_embeddings(limit=limit, job=job_ref)
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


def search_by_image(
    query_bgr: np.ndarray,
    *,
    top_k: int = 20,
    min_similarity: float = 0.5,
    device_id: Optional[str] = None,
    days: int = 7,
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> Dict[str, Any]:
    started = time.perf_counter()
    query_bgr = prepare_query_image(query_bgr)
    embedder = get_person_embedder()
    query_vec = embedder.embed_bgr(query_bgr)
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

        deep_scores = deep_matrix @ q_deep
        rerank_n = min(RERANK_CANDIDATE_LIMIT, len(items))
        if rerank_n < len(items):
            candidate_idx = np.argpartition(deep_scores, -rerank_n)[-rerank_n:]
        else:
            candidate_idx = np.arange(len(items), dtype=np.int32)

        candidate_idx = candidate_idx[np.argsort(deep_scores[candidate_idx])[::-1]]
        candidates: List[Dict[str, Any]] = []
        reranked = 0
        for idx in candidate_idx:
            deep_sim = float(deep_scores[idx])
            if deep_sim < DEEP_PREFILTER:
                continue
            meta = items[int(idx)]
            embedding = embeddings[int(idx)]
            sims = embedding_similarity(
                query_vec,
                embedding,
                precomputed_deep_sim=deep_sim,
                allow_image_io=False,
            )
            reranked += 1
            candidates.append(
                {
                    **meta,
                    "_embedding": embedding,
                    "deep_similarity": sims["deep_similarity"],
                    "color_similarity": sims["color_similarity"],
                    "hue_similarity": sims.get("hue_similarity"),
                    "garment_similarity": sims.get("garment_similarity"),
                    "body_similarity": sims.get("body_similarity"),
                    "attr_similarity": sims.get("attr_similarity"),
                    "attrs_veto": sims.get("attrs_veto"),
                    "gender_hint": sims.get("gender_hint"),
                    "similarity": sims["similarity"],
                    "match_confidence": sims.get("confidence"),
                }
            )

        verify_targets = sorted(candidates, key=lambda x: x.get("deep_similarity", 0), reverse=True)[
            : min(VERIFY_CANDIDATE_LIMIT, len(candidates))
        ]
        verified = 0
        for item in verify_targets:
            deep_sim = float(item.get("deep_similarity") or 0)
            sims = embedding_similarity(
                query_vec,
                item["_embedding"],
                query_bgr=query_bgr,
                gallery_crop_path=item.get("crop_path"),
                precomputed_deep_sim=deep_sim,
                allow_image_io=True,
            )
            item["similarity"] = sims["similarity"]
            item["color_similarity"] = sims["color_similarity"]
            item["hue_similarity"] = sims.get("hue_similarity")
            item["garment_similarity"] = sims.get("garment_similarity")
            item["body_similarity"] = sims.get("body_similarity")
            item["attr_similarity"] = sims.get("attr_similarity")
            item["gender_hint"] = sims.get("gender_hint")
            item["match_confidence"] = sims.get("confidence")
            item["_passes_gate"] = passes_match_gate(
                sims["deep_similarity"],
                sims["color_similarity"],
                float(sims.get("hue_similarity") or 0),
                float(sims.get("garment_similarity") or -1),
                float(sims.get("body_similarity") or -1),
                bool(sims.get("attrs_veto")),
                float(sims.get("attr_similarity") or -1),
            )
            verified += 1

        scored: List[Dict[str, Any]] = []
        for item in candidates:
            if item.get("_passes_gate") is False:
                continue
            if item.get("_passes_gate") is None:
                sims = {
                    "deep_similarity": item.get("deep_similarity"),
                    "color_similarity": item.get("color_similarity"),
                    "hue_similarity": item.get("hue_similarity"),
                    "garment_similarity": item.get("garment_similarity"),
                    "body_similarity": item.get("body_similarity"),
                    "attrs_veto": item.get("attrs_veto"),
                    "attr_similarity": item.get("attr_similarity"),
                }
                if not passes_match_gate(
                    float(sims["deep_similarity"] or 0),
                    float(sims["color_similarity"] or 0),
                    float(sims["hue_similarity"] or 0),
                    float(sims["garment_similarity"] or -1),
                    float(sims["body_similarity"] or -1),
                    bool(sims.get("attrs_veto")),
                    float(sims.get("attr_similarity") or -1),
                ):
                    continue
            deep = float(item.get("deep_similarity") or item.get("similarity") or 0)
            if deep < min_similarity:
                continue
            row = {k: v for k, v in item.items() if not k.startswith("_")}
            scored.append(row)
        scored.sort(key=lambda x: (x.get("deep_similarity") or 0, x.get("similarity") or 0), reverse=True)
        results = scored[: max(1, min(top_k, 100))]
        search_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "人员搜索完成 scanned=%s reranked=%s verified=%s results=%s ms=%s",
            len(items),
            reranked,
            verified,
            len(results),
            search_ms,
        )
        if legacy_skipped and not results:
            logger.warning("人员搜索跳过 %s 条旧版特征记录，请重建图库特征", legacy_skipped)
        return {
            "results": results,
            "legacy_skipped": legacy_skipped,
            "needs_rebuild": legacy_skipped > 0 and len(results) == 0,
            "search_ms": search_ms,
            "scanned": len(items),
            "reranked": reranked,
            "verified": verified,
        }
    finally:
        db.close()


def get_gallery_stats() -> Dict[str, Any]:
    cleanup_orphan_gallery_items()
    cleanup_orphan_person_crop_files()
    db = SessionLocal()
    try:
        base = (
            db.query(PersonGalleryItem)
            .join(DetectionEvent, PersonGalleryItem.event_id == DetectionEvent.event_id)
        )
        total = base.count()
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today = base.filter(PersonGalleryItem.created_at >= today_start).count()
        devices = base.with_entities(PersonGalleryItem.device_id).distinct().count()
        version_stats = _embedding_version_stats(db)
        return {
            "total": total,
            "today": today,
            "device_count": devices,
            **version_stats,
            "embedding_version": EMBEDDING_VERSION,
            "needs_rebuild": (
                version_stats.get("legacy_embeddings", 0) > 0
                or version_stats.get("stale_embeddings", 0) > 0
            ),
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
        "color_gated": True,
        "attribute_enabled": True,
        "parsing_mode": parser.mode,
        "parsing_onnx_ready": parsing_onnx is not None,
        "parsing_onnx_path": parsing_onnx,
        "weights_path": DEFAULT_WEIGHTS_PATH,
        "weights_ready": weights_ready,
        "loaded": loaded,
        "device": device,
    }
