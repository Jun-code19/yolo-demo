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
from src.data_listener_manager import data_listener_manager

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

# 配置相关接口

@router.post("/configs")
async def create_listener_config(
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建数据监听器配置"""
    try:
        # 验证必要字段
        required_fields = ['name', 'listener_type', 'connection_config']
        for field in required_fields:
            if field not in config_data:
                raise HTTPException(status_code=400, detail=f"缺少必要字段: {field}")
        
        # 验证监听器类型
        try:
            listener_type = ListenerType(config_data['listener_type'])
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的监听器类型")
        
        # 创建配置
        config = ListenerConfig(
            config_id=str(uuid.uuid4()),
            name=config_data['name'],
            description=config_data.get('description'),
            listener_type=listener_type,
            connection_config=config_data['connection_config'],
            data_mapping=config_data.get('data_mapping', {}),
            filter_rules=config_data.get('filter_rules', {}),
            edge_device_mappings=config_data.get('edge_device_mappings', []),
            algorithm_field_mappings=config_data.get('algorithm_field_mappings', {}),
            algorithm_specific_fields=config_data.get('algorithm_specific_fields', {}),
            device_name_mappings=config_data.get('device_name_mappings', {}),
            engine_name_mappings=config_data.get('engine_name_mappings', {}),
            storage_enabled=config_data.get('storage_enabled', True),
            push_enabled=config_data.get('push_enabled', False),
            push_config=config_data.get('push_config', {}),
            enabled=config_data.get('enabled', False),
            created_by=current_user.user_id
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'create_listener_config', config.config_id, 
                  f"创建数据监听器配置: {config.name}")
        
        return {
            "status": "success",
            "message": "监听器配置创建成功",
            "config_id": config.config_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建配置失败: {str(e)}")

@router.get("/configs")
async def get_listener_configs(
    listener_type: Optional[str] = Query(None, description="监听器类型过滤"),
    enabled: Optional[bool] = Query(None, description="启用状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """获取数据监听器配置列表"""
    try:
        query = db.query(ListenerConfig)
        
        # 应用过滤器
        if listener_type:
            query = query.filter(ListenerConfig.listener_type == listener_type)
        if enabled is not None:
            query = query.filter(ListenerConfig.enabled == enabled)
        
        # 分页
        total = query.count()
        configs = query.order_by(ListenerConfig.created_at.desc()).offset((page - 1) * size).limit(size).all()
        
        # 获取状态信息
        config_list = []
        for config in configs:
            config_dict = {
                "config_id": config.config_id,
                "name": config.name,
                "description": config.description,
                "listener_type": config.listener_type.value,
                "enabled": config.enabled,
                "storage_enabled": config.storage_enabled,
                "push_enabled": config.push_enabled,
                "created_at": config.created_at,
                "updated_at": config.updated_at
            }
            
            # 添加运行状态
            status = data_listener_manager.get_listener_status(config.config_id)
            config_dict["runtime_status"] = status
            
            config_list.append(config_dict)
        
        return {
            "status": "success",
            "data": {
                "configs": config_list,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": total,
                    "pages": (total + size - 1) // size
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置列表失败: {str(e)}")

@router.get("/configs/{config_id}")
async def get_listener_config(
    config_id: str,
    db: Session = Depends(get_db)
):
    """获取单个监听器配置详情"""
    try:
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 获取运行状态
        runtime_status = data_listener_manager.get_listener_status(config_id)
        
        return {
            "status": "success",
            "data": {
                "config_id": config.config_id,
                "name": config.name,
                "description": config.description,
                "listener_type": config.listener_type.value,
                "connection_config": config.connection_config,
                "data_mapping": config.data_mapping,
                "filter_rules": config.filter_rules,
                "edge_device_mappings": config.edge_device_mappings or [],
                "algorithm_field_mappings": config.algorithm_field_mappings or {},
                "algorithm_specific_fields": config.algorithm_specific_fields or {},
                "device_name_mappings": config.device_name_mappings or {},
                "engine_name_mappings": config.engine_name_mappings or {},
                "storage_enabled": config.storage_enabled,
                "push_enabled": config.push_enabled,
                "push_config": config.push_config,
                "enabled": config.enabled,
                "created_by": config.created_by,
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "runtime_status": runtime_status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置详情失败: {str(e)}")

#获取所有配置中的device_name_mappings以及engine_name_mappings，去重，返回一个列表
@router.get("/device_engine_name_mappings")
async def get_device_engine_name_mappings(
    db: Session = Depends(get_db)
    ):
    """获取所有配置中的device_name_mappings以及engine_name_mappings，去重，返回一个字典，key为device_name_mappings或者engine_name_mappings，value为对应的值"""
    try:
        configs = db.query(ListenerConfig).all()
        device_name_mappings = {}
        engine_name_mappings = {}
        for config in configs:
            if config.device_name_mappings:
                device_name_mappings.update(config.device_name_mappings)
            if config.engine_name_mappings:
                engine_name_mappings.update(config.engine_name_mappings)
        return {
            "status": "success",
            "data": {
                "device_name_mappings": device_name_mappings,
                "engine_name_mappings": engine_name_mappings
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取设备和引擎名称映射失败: {str(e)}") 
    
@router.put("/configs/{config_id}")
async def update_listener_config(
    config_id: str,
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新监听器配置"""
    try:
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 更新字段
        updateable_fields = [
            'name', 'description', 'connection_config', 'data_mapping',
            'filter_rules', 'edge_device_mappings', 'algorithm_field_mappings', 
            'algorithm_specific_fields', 'device_name_mappings', 'engine_name_mappings',
            'storage_enabled', 'push_enabled', 'push_config', 'enabled'
        ]
        
        for field in updateable_fields:
            if field in config_data:
                setattr(config, field, config_data[field])
        
        config.updated_at = datetime.now()
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'update_listener_config', config_id,
                  f"更新数据监听器配置: {config.name}")
        
        return {
            "status": "success",
            "message": "配置更新成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@router.delete("/configs/{config_id}")
async def delete_listener_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除监听器配置"""
    try:
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 先停止并移除监听器
        await data_listener_manager.remove_listener(config_id)
        
        # 删除相关的状态记录
        status_record = db.query(ListenerStatus).filter(ListenerStatus.config_id == config_id).first()
        if status_record:
            db.delete(status_record)
        
        # 删除相关的外部事件记录（可选，根据业务需求决定是否保留历史事件）
        # 如果要保留历史事件，可以将 config_id 设为 NULL 而不是删除
        # external_events = db.query(ExternalEvent).filter(ExternalEvent.config_id == config_id).all()
        # for event in external_events:
        #     db.delete(event)
        
        # 或者设置为 NULL，保留历史事件但取消关联
        db.query(ExternalEvent).filter(ExternalEvent.config_id == config_id).update(
            {ExternalEvent.config_id: None}
        )
        
        # 删除配置
        db.delete(config)
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'delete_listener_config', config_id,
                  f"删除数据监听器配置: {config.name}")
        
        return {
            "status": "success",
            "message": "配置删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除配置失败: {str(e)}")

# 控制相关接口

@router.post("/configs/{config_id}/start")
async def start_listener(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启动数据监听器"""
    try:
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 检查监听器是否已存在，如果不存在则创建
        if config_id not in data_listener_manager.listeners:
            if not await data_listener_manager.create_listener(config):
                raise HTTPException(status_code=500, detail="监听器创建失败")
        
        # 启动监听器
        if await data_listener_manager.start_listener(config_id):
            # 更新配置状态
            config.enabled = True
            config.updated_at = datetime.now()
            db.commit()
            
            # 记录操作日志
            log_action(db, current_user.user_id, 'start_listener', config_id,
                      f"启动数据监听器: {config.name}")
            
            return {
                "status": "success",
                "message": "监听器启动成功"
            }
        else:
            raise HTTPException(status_code=500, detail="监听器启动失败")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"启动监听器失败: {str(e)}")

@router.post("/configs/{config_id}/stop")
async def stop_listener(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止数据监听器"""
    try:
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 停止监听器
        if await data_listener_manager.stop_listener(config_id):
            # 更新配置状态
            config.enabled = False
            config.updated_at = datetime.now()
            db.commit()
            
            # 记录操作日志
            log_action(db, current_user.user_id, 'stop_listener', config_id,
                      f"停止数据监听器: {config.name}")
            
            return {
                "status": "success",
                "message": "监听器停止成功"
            }
        else:
            raise HTTPException(status_code=500, detail="监听器停止失败")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"停止监听器失败: {str(e)}")

@router.post("/configs/{config_id}/restart")
async def restart_listener(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重启数据监听器"""
    try:
        # 先停止（会自动移除监听器）
        await data_listener_manager.stop_listener(config_id)
        await asyncio.sleep(2)  # 等待停止完成
        
        # 再启动
        config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在")
        
        # 创建并启动监听器
        if await data_listener_manager.create_listener(config):
            if await data_listener_manager.start_listener(config_id):
                # 记录操作日志
                log_action(db, current_user.user_id, 'restart_listener', config_id,
                          f"重启数据监听器: {config.name}")
                
                return {
                    "status": "success",
                    "message": "监听器重启成功"
                }
        
        raise HTTPException(status_code=500, detail="监听器重启失败")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重启监听器失败: {str(e)}")

# 状态和监控接口

@router.get("/status")
async def get_all_listener_status():
    """获取所有监听器状态"""
    try:
        status = data_listener_manager.get_all_status()
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@router.get("/configs/{config_id}/status")
async def get_listener_status(
    config_id: str
):
    """获取单个监听器状态"""
    try:
        status = data_listener_manager.get_listener_status(config_id)
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取监听器状态失败: {str(e)}")

# 事件查询接口

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

# 统计接口

@router.get("/stats/summary")
async def get_listener_stats_summary(
    db: Session = Depends(get_db)
):
    """获取监听器统计摘要"""
    try:
        # 配置统计
        total_configs = db.query(ListenerConfig).count()
        enabled_configs = db.query(ListenerConfig).filter(ListenerConfig.enabled == True).count()
        
        # 事件统计
        total_events = db.query(ExternalEvent).count()
        today_events = db.query(ExternalEvent).filter(
            ExternalEvent.created_at >= datetime.now().date()
        ).count()
        
        # 按类型统计
        type_stats = {}
        for listener_type in ListenerType:
            count = db.query(ListenerConfig).filter(
                ListenerConfig.listener_type == listener_type
            ).count()
            type_stats[listener_type.value] = count
        
        # 运行状态统计
        runtime_status = data_listener_manager.get_all_status()
        
        return {
            "status": "success",
            "data": {
                "configs": {
                    "total": total_configs,
                    "enabled": enabled_configs,
                    "by_type": type_stats
                },
                "events": {
                    "total": total_events,
                    "today": today_events
                },
                "runtime": runtime_status
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

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

# 批量操作接口

@router.post("/batch/start")
async def batch_start_listeners(
    config_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量启动监听器"""
    try:
        results = []
        for config_id in config_ids:
            try:
                config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
                if not config:
                    results.append({"config_id": config_id, "status": "error", "message": "配置不存在"})
                    continue
                
                # 检查监听器是否已存在，如果不存在则创建
                if config_id not in data_listener_manager.listeners:
                    if not await data_listener_manager.create_listener(config):
                        results.append({"config_id": config_id, "status": "error", "message": "创建失败"})
                        continue
                
                if await data_listener_manager.start_listener(config_id):
                    config.enabled = True
                    config.updated_at = datetime.now()
                    results.append({"config_id": config_id, "status": "success", "message": "启动成功"})
                else:
                    results.append({"config_id": config_id, "status": "error", "message": "启动失败"})
                    
            except Exception as e:
                results.append({"config_id": config_id, "status": "error", "message": str(e)})
        
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'batch_start_listeners', ','.join(config_ids),
                  f"批量启动监听器: {len(config_ids)}个")
        
        return {
            "status": "success",
            "data": {"results": results}
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量启动失败: {str(e)}")

@router.post("/batch/stop")
async def batch_stop_listeners(
    config_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量停止监听器"""
    try:
        results = []
        for config_id in config_ids:
            try:
                if await data_listener_manager.stop_listener(config_id):
                    config = db.query(ListenerConfig).filter(ListenerConfig.config_id == config_id).first()
                    if config:
                        config.enabled = False
                        config.updated_at = datetime.now()
                    results.append({"config_id": config_id, "status": "success", "message": "停止成功"})
                else:
                    results.append({"config_id": config_id, "status": "error", "message": "停止失败"})
                    
            except Exception as e:
                results.append({"config_id": config_id, "status": "error", "message": str(e)})
        
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, 'batch_stop_listeners', ','.join(config_ids),
                  f"批量停止监听器: {len(config_ids)}个")
        
        return {
            "status": "success",
            "data": {"results": results}
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量停止失败: {str(e)}")
