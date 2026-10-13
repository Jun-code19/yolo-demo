"""人员搜索 API（以图搜人 POC）"""
import logging
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from api.auth import get_current_user
from src.database import User
from src.person_search.service import (
    batch_index_recent_events,
    get_gallery_detail,
    get_gallery_stats,
    get_rebuild_gallery_job,
    get_reid_model_info,
    get_track_detail,
    index_detection_event,
    list_gallery,
    search_by_image,
    start_rebuild_gallery_embeddings_async,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/person-search", tags=["人员搜索"])


class BatchIndexBody(BaseModel):
    limit: int = Field(50, ge=1, le=200)


class RebuildEmbeddingsBody(BaseModel):
    limit: int = Field(5000, ge=1, le=20000)
    force: bool = False


@router.get("/stats")
async def person_search_stats(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_gallery_stats()}


@router.get("/model-info")
async def person_search_model_info(_: User = Depends(get_current_user)):
    return {"status": "success", "data": get_reid_model_info()}


@router.get("/gallery")
async def person_search_gallery(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    device_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    _: User = Depends(get_current_user),
):
    data = list_gallery(page=page, page_size=page_size, device_id=device_id, days=days)
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
    file: UploadFile = File(...),
    top_k: int = Query(20, ge=1, le=100),
    min_similarity: float = Query(0.55, ge=0.0, le=1.0),
    device_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    _: User = Depends(get_current_user),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="请上传查询图片")
    arr = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解析图片")

    try:
        payload = search_by_image(
            img,
            top_k=top_k,
            min_similarity=min_similarity,
            device_id=device_id,
            days=days,
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
