"""删除人员图库记录（仅 DB + 磁盘），供 data-server 使用，不依赖 cv2/torch。"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from src.database import PersonGalleryItem, SessionLocal

logger = logging.getLogger(__name__)


def delete_gallery_for_events(event_ids: List[str], db: Optional[Session] = None) -> int:
    """删除检测事件关联的人员图库记录及抠图文件。"""
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
        for item in items:
            if item.crop_path:
                try:
                    if os.path.exists(item.crop_path):
                        os.remove(item.crop_path)
                except OSError as exc:
                    logger.warning("删除人员抠图失败 %s: %s", item.crop_path, exc)
            db.delete(item)
            deleted += 1
        if deleted and own_session:
            db.commit()
            logger.info("已删除 %s 条人员图库记录 event_ids=%s", deleted, event_ids)
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()
    return deleted
