"""人员搜索 API（以图搜人 POC）"""
import logging
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from api.auth import get_current_user
from src.database import User
from src.person_search.service import (
    batch_index_recent_events,
    drop_faiss_shards_before,
    get_faiss_index_status,
    get_gallery_detail,
    get_gallery_stats,
    get_index_rebuild_job,
    get_rebuild_gallery_job,
    get_reid_model_info,
    get_track_detail,
    index_detection_event,
    list_gallery,
    purge_orphan_person_data,
    search_by_images,
    start_rebuild_faiss_index_async,
    start_rebuild_gallery_embeddings_async,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/person-search", tags=["人员搜索"])


class BatchIndexBody(BaseModel):
    limit: int = Field(50, ge=1, le=200)


class RebuildEmbeddingsBody(BaseModel):
    limit: int = Field(5000, ge=1, le=20000)
    force: bool = False


class RebuildFaissIndexBody(BaseModel):
    days: int = Field(30, ge=1, le=90)


@router.get("/stats")
async def person_search_stats(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_gallery_stats()}


@router.post("/cleanup-orphans")
async def person_search_cleanup_orphans(_: User = Depends(get_current_user)):
    """清理无事件关联的图库帧、无帧的空轨迹、磁盘遗留抠图。"""
    data = purge_orphan_person_data()
    return {"status": "success", "data": data}


@router.get("/model-info")
async def person_search_model_info(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_reid_model_info()}


@router.get("/gallery")
async def person_search_gallery(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    device_id: Optional[str] = None,
    days: int = Query(1, ge=1, le=90),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    _: User = Depends(get_current_user),
):
    data = list_gallery(
        page=page,
        page_size=page_size,
        device_id=device_id,
        days=days,
        date_from=date_from,
        date_to=date_to,
    )
    return {"status": "success", "data": data}


@router.get("/gallery/{gallery_id}")
async def person_search_gallery_detail(gallery_id: str, _: User = Depends(get_current_user)):
    data = get_gallery_detail(gallery_id)
    if not data:
        raise HTTPException(status_code=404, detail="图库记录不存在")
    return {"status": "success", "data": data}


@router.get("/tracks/{track_id}")
async def person_search_track_detail(track_id: str, _: User = Depends(get_current_user)):
    data = get_track_detail(track_id)
    if not data:
        raise HTTPException(status_code=404, detail="轨迹不存在")
    return {"status": "success", "data": data}


@router.post("/search")
async def person_search_by_image(
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(default=None),
    top_k: int = Query(20, ge=1, le=100),
    min_similarity: float = Query(0.55, ge=0.0, le=1.0),
    device_id: Optional[str] = None,
    days: int = Query(1, ge=1, le=90),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    _: User = Depends(get_current_user),
):
    uploads: List[UploadFile] = []
    if files:
        uploads.extend([f for f in files if f is not None])
    if file is not None:
        uploads.append(file)
    # 去重同一 UploadFile 对象（部分客户端会同时带 files/file）
    seen = set()
    unique_uploads: List[UploadFile] = []
    for up in uploads:
        key = id(up)
        if key in seen:
            continue
        seen.add(key)
        unique_uploads.append(up)
    uploads = unique_uploads[:5]
    if not uploads:
        raise HTTPException(status_code=400, detail="请上传查询图片（最多 5 张，同一人）")

    images = []
    for up in uploads:
        content = await up.read()
        if not content:
            continue
        arr = np.frombuffer(content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            continue
        images.append(img)
    if not images:
        raise HTTPException(status_code=400, detail="无法解析图片")

    try:
        payload = search_by_images(
            images,
            top_k=top_k,
            min_similarity=min_similarity,
            device_id=device_id,
            days=days,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        logger.exception("人员搜索失败")
        raise HTTPException(status_code=500, detail=f"搜索失败: {exc}") from exc

    results = payload.get("results") or []
    return {
        "status": "success",
        "data": {
            "count": len(results),
            "results": results,
            "legacy_skipped": payload.get("legacy_skipped", 0),
            "needs_rebuild": payload.get("needs_rebuild", False),
            "search_ms": payload.get("search_ms", 0),
            "scanned": payload.get("scanned", 0),
            "reranked": payload.get("reranked", 0),
            "backend": payload.get("backend"),
            "query_count": payload.get("query_count", len(images)),
        },
    }


@router.post("/index-event/{event_id}")
async def person_search_index_event(event_id: str, _: User = Depends(get_current_user)):
    result = index_detection_event(event_id)
    if result.get("message") == "事件不存在":
        raise HTTPException(status_code=404, detail=result["message"])
    return {"status": "success", "data": result}


@router.post("/batch-index")
async def person_search_batch_index(
    body: BatchIndexBody,
    _: User = Depends(get_current_user),
):
    data = batch_index_recent_events(limit=body.limit)
    return {"status": "success", "data": data}


@router.post("/rebuild-embeddings")
async def person_search_rebuild_embeddings(
    body: RebuildEmbeddingsBody,
    _: User = Depends(get_current_user),
):
    data = start_rebuild_gallery_embeddings_async(limit=body.limit, force=body.force)
    return {"status": "success", "data": data}


@router.get("/rebuild-embeddings/status")
async def person_search_rebuild_status(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_rebuild_gallery_job()}


@router.get("/index/status")
async def person_search_index_status(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_faiss_index_status()}


@router.post("/index/rebuild")
async def person_search_index_rebuild(
    body: RebuildFaissIndexBody,
    _: User = Depends(get_current_user),
):
    data = start_rebuild_faiss_index_async(days=body.days)
    return {"status": "success", "data": data}


@router.get("/index/rebuild/status")
async def person_search_index_rebuild_status(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_index_rebuild_job()}


@router.post("/index/drop-before")
async def person_search_index_drop_before(
    day: str = Query(..., description="删除该日之前的分片，格式 YYYY-MM-DD"),
    _: User = Depends(get_current_user),
):
    data = drop_faiss_shards_before(day)
    return {"status": "success", "data": data}
