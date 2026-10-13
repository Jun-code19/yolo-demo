"""删除人员图库记录（仅 DB + 磁盘），供 data-server 使用，不依赖 cv2/torch。"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Set

from sqlalchemy import exists, func
from sqlalchemy.orm import Session

from src.database import PersonGalleryItem, PersonTrack, SessionLocal

logger = logging.getLogger(__name__)


def cleanup_orphan_tracks(db: Session, candidate_track_ids: Optional[Set[str]] = None) -> int:
    """删除已无任何帧图库的轨迹行。"""
    removed = 0
    if candidate_track_ids is not None:
        tids = [t for t in candidate_track_ids if t]
        if not tids:
            return 0
        for tid in tids:
            remain = (
                db.query(func.count(PersonGalleryItem.gallery_id))
                .filter(PersonGalleryItem.track_id == tid)
                .scalar()
            )
            if int(remain or 0) == 0:
                row = db.query(PersonTrack).filter(PersonTrack.track_id == tid).first()
                if row:
                    db.delete(row)
                    removed += 1
        return removed

    # 全量：无任何 gallery 帧的轨迹
    orphans = (
        db.query(PersonTrack)
        .filter(
            ~exists().where(PersonGalleryItem.track_id == PersonTrack.track_id)
        )
        .all()
    )
    for row in orphans:
        db.delete(row)
        removed += 1
    return removed


def delete_gallery_for_events(event_ids: List[str], db: Optional[Session] = None) -> int:
    """删除检测事件关联的人员图库记录及抠图文件，并清理空轨迹。"""
    if not event_ids:
        return 0
    own_session = db is None
    if own_session:
        db = SessionLocal()
    deleted = 0
    try:
        items = (
            db.query(PersonGalleryItem)
            .filter(PersonGalleryItem.event_id.in_(event_ids))
            .all()
        )
        affected_tracks = {item.track_id for item in items if item.track_id}
        for item in items:
            if item.crop_path:
                try:
                    if os.path.exists(item.crop_path):
                        os.remove(item.crop_path)
                except OSError as exc:
                    logger.warning("删除人员抠图失败 %s: %s", item.crop_path, exc)
            db.delete(item)
            deleted += 1
        tracks_removed = cleanup_orphan_tracks(db, affected_tracks) if deleted else 0
        if deleted and own_session:
            db.commit()
            logger.info(
                "已删除 %s 条人员图库、%s 条空轨迹 event_ids=%s",
                deleted,
                tracks_removed,
                event_ids,
            )
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()
    return deleted
