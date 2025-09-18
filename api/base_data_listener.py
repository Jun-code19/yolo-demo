from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import asyncio

from src.database import (
    get_db, ListenerConfig, ExternalEvent, ListenerStatus,
    ListenerType, ExternalEventType, EventStatus, User
)
from api.auth import get_current_user
from api.logger import log_action

router = APIRouter(prefix="/data-listeners", tags=["数据监听"])

# 图片服务接口
@router.get("/images/{image_path:path}")
async def get_image(image_path: str):
    """获取图片文件"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        import urllib.parse
        import os
        
        # 解码图片路径
        decoded_path = urllib.parse.unquote(image_path)
        
        # 处理Windows路径分隔符
        decoded_path = decoded_path.replace('\\', '/')
        
        # 构建完整的文件路径
        full_path = Path(decoded_path)
        
        # 如果路径不是绝对路径，检查是否在当前工作目录下
        if not full_path.is_absolute():
            # 尝试在当前工作目录下查找
            full_path = Path.cwd() / decoded_path
        
        # 安全检查：确保文件路径存在且在合理范围内
        if not full_path.exists() or not full_path.is_file():
            # 如果文件不存在，尝试在几个常见目录中查找
            possible_dirs = [
                Path.cwd(),
                Path.cwd() / "storage",
                Path.cwd() / "images",
                Path.cwd() / "data"
            ]
            
            found = False
            for base_dir in possible_dirs:
                test_path = base_dir / decoded_path
                if test_path.exists() and test_path.is_file():
                    full_path = test_path
                    found = True
                    break
            
            if not found:
                raise HTTPException(status_code=404, detail="文件不存在")
        
        # 获取文件的MIME类型
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(full_path))
        if mime_type is None or not mime_type.startswith('image/'):
            mime_type = "image/jpeg"  # 默认JPEG类型
        
        # 返回文件
        return FileResponse(
            path=str(full_path),
            media_type=mime_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # 缓存1小时
                "Content-Disposition": f"inline; filename={full_path.name}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取图片失败: {str(e)}")

@router.get("/events")
async def get_external_events(
    config_id: Optional[str] = Query(None, description="配置ID过滤"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    device_id: Optional[str] = Query(None, description="设备ID过滤"),
    device_sn: Optional[str] = Query(None, description="设备SN码过滤"),
    channel_id: Optional[str] = Query(None, description="通道ID过滤"),
    engine_id: Optional[str] = Query(None, description="算法引擎ID过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """获取外部事件列表"""
    try:
        query = db.query(ExternalEvent)
        
        # 应用过滤器
        if config_id:
            query = query.filter(ExternalEvent.config_id == config_id)
        if event_type:
            query = query.filter(ExternalEvent.event_type == event_type)
        if device_id:
            query = query.filter(ExternalEvent.device_id == device_id)
        if device_sn:
            query = query.filter(ExternalEvent.device_sn == device_sn)
        if channel_id:
            query = query.filter(ExternalEvent.channel_id == channel_id)
        if engine_id:
            query = query.filter(ExternalEvent.engine_id == engine_id)
        if start_time:
            query = query.filter(ExternalEvent.timestamp >= start_time)
        if end_time:
            query = query.filter(ExternalEvent.timestamp <= end_time)
        
        # 按时间倒序
        query = query.order_by(ExternalEvent.timestamp.desc())
        
        # 分页
        total = query.count()
        events = query.offset((page - 1) * size).limit(size).all()
        
        event_list = []
        for event in events:
            event_dict = {
                "event_id": event.event_id,
                "config_id": event.config_id,
                "source_type": event.source_type.value,
                "event_type": event.event_type.value,
                "device_id": event.device_id,
                "device_sn": event.device_sn,
                "device_name": event.device_name,
                "channel_id": event.channel_id,
                "engine_id": event.engine_id,
                "engine_name": event.engine_name,
                "location": event.location,
                "confidence": event.confidence,
                "normalized_data": event.normalized_data,
                "algorithm_data": event.algorithm_data,
                "status": event.status.value,
                "processed": event.processed,
                "viewed_at": event.viewed_at,
                "viewed_by": event.viewed_by,
                "notes": event.notes,
                "timestamp": event.timestamp,
                "created_at": event.created_at
            }
            event_list.append(event_dict)
        
        return {
            "status": "success",
            "data": {
                "events": event_list,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": total,
                    "pages": (total + size - 1) // size
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件列表失败: {str(e)}")

@router.get("/events/{event_id}")
async def get_external_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """获取单个外部事件详情"""
    try:
        event = db.query(ExternalEvent).filter(ExternalEvent.event_id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="事件不存在")
        
        return {
            "status": "success",
            "data": {
                "event_id": event.event_id,
                "config_id": event.config_id,
                "source_type": event.source_type.value,
                "event_type": event.event_type.value,
                "device_id": event.device_id,
                "device_sn": event.device_sn,
                "device_name": event.device_name,
                "channel_id": event.channel_id,
                "engine_id": event.engine_id,
                "engine_name": event.engine_name,
                "location": event.location,
                "confidence": event.confidence,
                "original_data": event.original_data,
                "normalized_data": event.normalized_data,
                "algorithm_data": event.algorithm_data,
                "metadata": event.event_metadata,
                "status": event.status.value,
                "processed": event.processed,
                "viewed_at": event.viewed_at,
                "viewed_by": event.viewed_by,
                "notes": event.notes,
                "timestamp": event.timestamp,
                "created_at": event.created_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件详情失败: {str(e)}")

@router.put("/events/{event_id}")
async def update_external_event(
    event_id: str,
    update_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新外部事件状态、备注等信息"""
    try:
        event = db.query(ExternalEvent).filter(ExternalEvent.event_id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="事件不存在")
        
        # 更新状态
        if 'status' in update_data:
            try:
                new_status = getattr(EventStatus, update_data['status'])
                event.status = new_status
            except AttributeError:
                raise HTTPException(status_code=400, detail="无效的状态值")
        
        # 更新备注
        if 'notes' in update_data:
            event.notes = update_data['notes']
        
        # 更新查看信息
        event.viewed_by = current_user.username
        event.viewed_at = datetime.now()
        
        # 更新processed标志
        if event.status != EventStatus.new and event.status != EventStatus.viewed:
            event.processed = True
        
        db.commit()
        db.refresh(event)
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'update_external_event', event_id,
                  f"更新外部事件状态: {event.status.value}")
        
        return {
            "status": "success",
            "message": "事件更新成功",
            "data": {
                "event_id": event.event_id,
                "status": event.status.value,
                "processed": event.processed,
                "viewed_by": event.viewed_by,
                "viewed_at": event.viewed_at.isoformat() if event.viewed_at else None,
                "notes": event.notes
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新事件失败: {str(e)}")

@router.delete("/events/{event_id}")
async def delete_external_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除单个外部事件"""
    try:
        event = db.query(ExternalEvent).filter(ExternalEvent.event_id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="事件不存在")
        
        # 删除关联的图片文件（如果有）
        try:
            if event.normalized_data and event.normalized_data.get('processed_images'):
                import os
                from pathlib import Path
                
                processed_images = event.normalized_data['processed_images']
                for field_name, image_data in processed_images.items():
                    if isinstance(image_data, dict) and not image_data.get('error'):
                        # 删除原图
                        if image_data.get('original_path'):
                            original_path = Path(image_data['original_path'])
                            if original_path.exists():
                                original_path.unlink()
                        
                        # 删除缩略图
                        if image_data.get('thumbnail_path'):
                            thumbnail_path = Path(image_data['thumbnail_path'])
                            if thumbnail_path.exists():
                                thumbnail_path.unlink()
        except Exception as img_error:
            # 图片删除失败不影响事件删除
            print(f"删除事件关联图片失败: {img_error}")
        
        # 删除事件记录
        db.delete(event)
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'delete_event', event_id,
                  f"删除外部事件: {event_id}")
        
        return {
            "status": "success",
            "message": "事件删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除事件失败: {str(e)}")

@router.post("/events/batch-delete")
async def batch_delete_external_events(
    request_data: Dict[str, List[str]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量删除外部事件"""
    try:
        event_ids = request_data.get('event_ids', [])
        if not event_ids:
            raise HTTPException(status_code=400, detail="请提供要删除的事件ID列表")
        
        # 查询要删除的事件
        events = db.query(ExternalEvent).filter(ExternalEvent.event_id.in_(event_ids)).all()
        
        if not events:
            raise HTTPException(status_code=404, detail="未找到要删除的事件")
        
        deleted_count = 0
        errors = []
        
        for event in events:
            try:
                # 删除关联的图片文件（如果有）
                try:
                    if event.normalized_data and event.normalized_data.get('processed_images'):
                        import os
                        from pathlib import Path
                        
                        processed_images = event.normalized_data['processed_images']
                        for field_name, image_data in processed_images.items():
                            if isinstance(image_data, dict) and not image_data.get('error'):
                                # 删除原图
                                if image_data.get('original_path'):
                                    original_path = Path(image_data['original_path'])
                                    if original_path.exists():
                                        original_path.unlink()
                                
                                # 删除缩略图
                                if image_data.get('thumbnail_path'):
                                    thumbnail_path = Path(image_data['thumbnail_path'])
                                    if thumbnail_path.exists():
                                        thumbnail_path.unlink()
                except Exception as img_error:
                    # 图片删除失败不影响事件删除
                    print(f"删除事件关联图片失败: {img_error}")
                
                # 删除事件记录
                db.delete(event)
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"删除事件 {event.event_id} 失败: {str(e)}")
        
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'batch_delete_events', '批量删除',
                  f"批量删除外部事件: 成功{deleted_count}个, 失败{len(errors)}个")
        
        result = {
            "status": "success",
            "message": f"批量删除完成，成功删除 {deleted_count} 个事件",
            "deleted_count": deleted_count,
            "total_requested": len(event_ids)
        }
        
        if errors:
            result["errors"] = errors
            result["status"] = "partial_success"
            result["message"] += f"，{len(errors)} 个事件删除失败"
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量删除事件失败: {str(e)}")

@router.get("/stats/overview")
async def get_external_events_overview(db: Session = Depends(get_db)):
    """
    获取外部事件统计概览数据
    """
    try:
        from sqlalchemy import func, and_
        
        # 获取当前日期（用于今日数据统计）
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        # 并行获取各种统计数据
        
        # 1. 今日总事件数
        today_events = db.query(ExternalEvent).filter(
            ExternalEvent.created_at >= today
        ).count()
        
        # 2. 各状态事件数（今日）
        new_events = db.query(ExternalEvent).filter(
            and_(
                ExternalEvent.status == EventStatus.new,
                ExternalEvent.created_at >= today
            )
        ).count()
        
        viewed_events = db.query(ExternalEvent).filter(
            and_(
                ExternalEvent.status == EventStatus.viewed,
                ExternalEvent.created_at >= today
            )
        ).count()
        
        flagged_events = db.query(ExternalEvent).filter(
            and_(
                ExternalEvent.status == EventStatus.flagged,
                ExternalEvent.created_at >= today
            )
        ).count()
        
        archived_events = db.query(ExternalEvent).filter(
            and_(
                ExternalEvent.status == EventStatus.archived,
                ExternalEvent.created_at >= today
            )
        ).count()
        
        # 3. 近1小时事件数
        recent_1hour = db.query(ExternalEvent).filter(
            ExternalEvent.created_at >= one_hour_ago
        ).count()
        
        # 4. 报警事件数（今日）
        alarms_today = db.query(ExternalEvent).filter(
            and_(
                ExternalEvent.event_type == ExternalEventType.alarm,
                ExternalEvent.created_at >= today
            )
        ).count()
        
        # 计算已处理事件数（非新事件）
        processed_events = viewed_events + flagged_events + archived_events
        
        return {
            "status": "success",
            "data": {
                "total_today": today_events,
                "processed_today": processed_events,
                "recent_1hour": recent_1hour,
                "alarms_today": alarms_today,
                "status_breakdown": {
                    "new": new_events,
                    "viewed": viewed_events,
                    "flagged": flagged_events,
                    "archived": archived_events
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取外部事件统计失败: {str(e)}")

