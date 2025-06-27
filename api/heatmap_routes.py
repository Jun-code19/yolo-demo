from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from src.database import get_db, HeatmapMap, HeatmapArea, HeatmapBinding, HeatmapDashboardConfig, HeatmapHistory,CrowdAnalysisJob
from typing import Optional, Dict, Any, List
import os
import json
import uuid
from datetime import datetime
from PIL import Image
import traceback
from pydantic import BaseModel

heatmap_router = APIRouter(prefix="/heatmap", tags=["热力图管理"])

# 文件上传配置
UPLOAD_FOLDER = 'uploads/heatmaps'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Pydantic 模型
class HeatmapMapCreate(BaseModel):
    name: str
    description: Optional[str] = None
    scale_factor: float = 1.0
    created_by: str = "system"

class HeatmapMapResponse(BaseModel):
    id: int
    name: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    scale_factor: float
    description: Optional[str]
    image_url: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    created_by: str

class HeatmapAreaCreate(BaseModel):
    map_id: int
    name: str
    points: List[Dict[str, float]]
    color: str = "rgba(74, 144, 226, 0.5)"
    max_capacity: Optional[int] = None
    description: Optional[str] = None
    scale_factor: float = 1.0

class HeatmapAreaResponse(BaseModel):
    id: int
    map_id: int
    name: str
    points: List[Dict[str, float]]
    color: str
    area_size: float
    max_capacity: Optional[int]
    description: Optional[str]
    data_source_type: Optional[str]
    data_source_id: Optional[str]
    data_source_name: Optional[str]
    current_count: Optional[int]
    last_update_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_active: bool

class HeatmapBindingCreate(BaseModel):
    area_id: int
    data_source_type: str
    data_source_id: Optional[str] = None
    data_source_name: Optional[str] = None
    refresh_interval: int = 30
    config: Optional[Dict[str, Any]] = None

class HeatmapDashboardConfigModel(BaseModel):
    map_id: int
    display_mode: str = "preview"
    max_areas: int = 6
    refresh_interval: int = 30
    config: Optional[Dict[str, Any]] = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_dir():
    """确保上传目录存在"""
    upload_path = os.path.join(os.getcwd(), UPLOAD_FOLDER)
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    return upload_path

@heatmap_router.get("/maps", response_model=List[HeatmapMapResponse])
async def get_maps(db: Session = Depends(get_db)):
    """获取所有地图列表"""
    try:
        maps = db.query(HeatmapMap).filter(HeatmapMap.is_active == True).order_by(HeatmapMap.created_at.desc()).all()
        
        # 转换为响应格式
        result = []
        for map_item in maps:
            map_dict = {
                "id": map_item.id,
                "name": map_item.name,
                "file_path": map_item.file_path,
                "file_name": map_item.file_name,
                "file_size": map_item.file_size,
                "mime_type": map_item.mime_type,
                "width": map_item.width,
                "height": map_item.height,
                "scale_factor": map_item.scale_factor,
                "description": map_item.description,
                "image_url": f"/api/v1/heatmap/maps/{map_item.id}/image",
                "created_at": map_item.created_at,
                "updated_at": map_item.updated_at,
                "is_active": map_item.is_active,
                "created_by": map_item.created_by or "system"
            }
            result.append(map_dict)
        
        return result
        
    except Exception as e:
        print(f"获取地图列表错误: {e}")
        raise HTTPException(status_code=500, detail="获取地图列表失败")

@heatmap_router.post("/maps", response_model=Dict[str, Any])
async def upload_map(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    scale_factor: float = Form(1.0),
    created_by: str = Form("system"),
    db: Session = Depends(get_db)
):
    """上传地图文件"""
    try:
        # 验证文件
        if not file or not file.filename:
            raise HTTPException(status_code=422, detail="请选择要上传的文件")
        
        if not allowed_file(file.filename):
            raise HTTPException(status_code=422, detail="不支持的文件格式，请上传 jpg/png/gif 格式的图片")
        
        # 验证名称
        if not name or not name.strip():
            raise HTTPException(status_code=422, detail="地图名称不能为空")
        
        # 读取文件内容检查大小
        contents = await file.read()
        file_size = len(contents)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=422, detail="文件大小超过限制(10MB)")
        
        # 确保上传目录存在
        upload_path = ensure_upload_dir()
        
        # 生成唯一文件名
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_path, unique_filename)
        
        # 保存文件
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # 获取图片尺寸
        width, height = None, None
        try:
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"获取图片尺寸失败: {e}")
        
        # 存储相对路径
        relative_path = os.path.join(UPLOAD_FOLDER, unique_filename).replace('\\', '/')
        
        # 保存到数据库
        db_map = HeatmapMap(
            name=name,
            file_path=relative_path,
            file_name=file.filename,
            file_size=file_size,
            mime_type=file.content_type,
            width=width,
            height=height,
            scale_factor=scale_factor,
            description=description,
            created_by=created_by
        )
        
        db.add(db_map)
        db.commit()
        db.refresh(db_map)
        
        return {
            'success': True,
            'data': {
                'id': db_map.id,
                'name': db_map.name,
                'file_path': db_map.file_path,
                'image_url': f"/api/v1/heatmap/maps/{db_map.id}/image",
                'width': width,
                'height': height,
                'scale_factor': scale_factor
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"上传地图错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="上传地图失败")

@heatmap_router.get("/maps/{map_id}/image")
async def get_map_image(map_id: int, db: Session = Depends(get_db)):
    """获取地图图片"""
    try:
        db_map = db.query(HeatmapMap).filter(
            HeatmapMap.id == map_id,
            HeatmapMap.is_active == True
        ).first()
        
        if not db_map:
            raise HTTPException(status_code=404, detail="地图不存在")
        
        full_path = os.path.join(os.getcwd(), db_map.file_path)
        
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="图片文件不存在")
        
        return FileResponse(full_path)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取地图图片错误: {e}")
        raise HTTPException(status_code=500, detail="获取图片失败")

@heatmap_router.delete("/maps/{map_id}")
async def delete_map(map_id: int, db: Session = Depends(get_db)):
    """删除地图（级联删除相关区域、绑定和图片文件）"""
    try:
        db_map = db.query(HeatmapMap).filter(HeatmapMap.id == map_id).first()
        
        if not db_map:
            raise HTTPException(status_code=404, detail="地图不存在")
        
        map_name = db_map.name
        map_file_path = db_map.file_path
        
        # 获取该地图下的所有区域
        areas = db.query(HeatmapArea).filter(HeatmapArea.map_id == map_id).all()
        
        # 删除每个区域的绑定
        for area in areas:
            bindings = db.query(HeatmapBinding).filter(HeatmapBinding.area_id == area.id).all()
            for binding in bindings:
                binding.is_active = False
            
            # 软删除区域
            area.is_active = False
        
        # 删除相关的展板配置
        dashboard_configs = db.query(HeatmapDashboardConfig).filter(
            HeatmapDashboardConfig.map_id == map_id
        ).all()
        for config in dashboard_configs:
            config.is_active = False
        
        # 删除地图图片文件
        file_deleted = False
        file_error = None
        try:
            if map_file_path and os.path.exists(map_file_path):
                os.remove(map_file_path)
                file_deleted = True
                print(f"删除地图文件: {map_file_path}")
        except OSError as e:
            file_error = str(e)
            print(f"删除地图文件失败: {e}")
        
        # 软删除地图
        db_map.is_active = False
        db.commit()
        
        message = f"地图 '{map_name}' 及相关数据删除成功"
        if file_deleted:
            message += "，图片文件已删除"
        elif file_error:
            message += f"，但图片文件删除失败: {file_error}"
        
        return {
            "success": True, 
            "message": message,
            "file_deleted": file_deleted,
            "file_path": map_file_path if file_deleted else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"删除地图错误: {e}")
        raise HTTPException(status_code=500, detail="删除地图失败")

@heatmap_router.get("/maps/{map_id}/areas", response_model=List[HeatmapAreaResponse])
async def get_map_areas(map_id: int, db: Session = Depends(get_db)):
    """获取地图的区域列表"""
    try:
        # 使用SQLAlchemy ORM查询，包含LEFT JOIN绑定信息
        query = db.query(HeatmapArea).filter(
            HeatmapArea.map_id == map_id,
            HeatmapArea.is_active == True
        ).order_by(HeatmapArea.created_at.asc())
        
        areas = query.all()
        
        result = []
        for area in areas:
            # 获取该区域的绑定信息
            binding = db.query(HeatmapBinding).filter(
                HeatmapBinding.area_id == area.id,
                HeatmapBinding.is_active == True
            ).first()

            if binding:
                crowd_analysis = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == binding.data_source_id).first()
            else:
                crowd_analysis = None
            
            # 安全获取人数统计
            current_count = 0
            if crowd_analysis and crowd_analysis.last_result:
                try:
                    if isinstance(crowd_analysis.last_result, dict):
                        current_count = int(crowd_analysis.last_result.get("total_person_count", 0))
                    else:
                        # 如果last_result是JSON字符串，需要解析
                        import json
                        result_data = json.loads(crowd_analysis.last_result) if isinstance(crowd_analysis.last_result, str) else crowd_analysis.last_result
                        current_count = int(result_data.get("total_person_count", 0))
                except (ValueError, TypeError, json.JSONDecodeError):
                    current_count = 0
            
            area_dict = {
                "id": area.id,
                "map_id": area.map_id,
                "name": area.name,
                "points": area.points,
                "color": area.color,
                "area_size": area.area_size,
                "max_capacity": area.max_capacity,
                "description": area.description,
                "data_source_type": binding.data_source_type if binding else None,
                "data_source_id": binding.data_source_id if binding else None,
                "data_source_name": binding.data_source_name if binding else None,
                "current_count": current_count,
                "last_update_time": crowd_analysis.last_run if crowd_analysis else None,
                "created_at": area.created_at,
                "updated_at": area.updated_at,
                "is_active": area.is_active
            }
            result.append(area_dict)
        
        return result
        
    except Exception as e:
        print(f"获取区域列表错误: {e}")
        raise HTTPException(status_code=500, detail="获取区域列表失败")

@heatmap_router.post("/areas")
async def create_area(area: HeatmapAreaCreate, db: Session = Depends(get_db)):
    """创建区域"""
    try:
        # 计算区域面积
        area_size = calculate_polygon_area(area.points, area.scale_factor)
        
        db_area = HeatmapArea(
            map_id=area.map_id,
            name=area.name,
            points=area.points,
            color=area.color,
            area_size=area_size,
            max_capacity=area.max_capacity,
            description=area.description
        )
        
        db.add(db_area)
        db.commit()
        db.refresh(db_area)
        
        return {
            'success': True,
            'data': {
                'id': db_area.id,
                'area_size': area_size
            }
        }
        
    except Exception as e:
        print(f"创建区域错误: {e}")
        raise HTTPException(status_code=500, detail="创建区域失败")

@heatmap_router.put("/areas/{area_id}")
async def update_area(area_id: int, area_data: Dict[str, Any], db: Session = Depends(get_db)):
    """更新区域"""
    try:
        db_area = db.query(HeatmapArea).filter(HeatmapArea.id == area_id).first()
        
        if not db_area:
            raise HTTPException(status_code=404, detail="区域不存在")
        
        # 更新字段
        if 'name' in area_data:
            db_area.name = area_data['name']
        
        if 'points' in area_data:
            db_area.points = area_data['points']
            # 重新计算面积
            area_size = calculate_polygon_area(area_data['points'], area_data.get('scale_factor', 1.0))
            db_area.area_size = area_size
        
        if 'color' in area_data:
            db_area.color = area_data['color']
        
        if 'max_capacity' in area_data:
            db_area.max_capacity = area_data['max_capacity']
        
        if 'description' in area_data:
            db_area.description = area_data['description']
        
        db_area.updated_at = datetime.now()
        db.commit()
        
        return {"success": True, "data": {"id": db_area.id}}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"更新区域错误: {e}")
        raise HTTPException(status_code=500, detail="更新区域失败")

@heatmap_router.delete("/areas/{area_id}")
async def delete_area(area_id: int, db: Session = Depends(get_db)):
    """删除区域（级联删除相关绑定）"""
    try:
        db_area = db.query(HeatmapArea).filter(HeatmapArea.id == area_id).first()
        
        if not db_area:
            raise HTTPException(status_code=404, detail="区域不存在")
        
        # 先删除该区域的所有绑定
        bindings = db.query(HeatmapBinding).filter(HeatmapBinding.area_id == area_id).all()
        for binding in bindings:
            binding.is_active = False
        
        # 软删除区域
        db_area.is_active = False
        db.commit()
        
        return {"success": True, "message": "区域及相关绑定删除成功"}
        
    except Exception as e:
        print(f"删除区域错误: {e}")
        raise HTTPException(status_code=500, detail="删除区域失败")

@heatmap_router.post("/bindings")
async def create_binding(binding: HeatmapBindingCreate, db: Session = Depends(get_db)):
    """创建数据绑定"""
    try:
        # 先禁用该区域的旧绑定
        old_bindings = db.query(HeatmapBinding).filter(
            HeatmapBinding.area_id == binding.area_id
        ).all()
        
        for old_binding in old_bindings:
            old_binding.is_active = False
        
        # 创建新绑定
        db_binding = HeatmapBinding(
            area_id=binding.area_id,
            data_source_type=binding.data_source_type,
            data_source_id=binding.data_source_id,
            data_source_name=binding.data_source_name,
            refresh_interval=binding.refresh_interval,
            config=binding.config or {}
        )
        
        db.add(db_binding)
        db.commit()
        db.refresh(db_binding)
        
        return {
            'success': True,
            'data': {'id': db_binding.id}
        }
        
    except Exception as e:
        print(f"创建数据绑定错误: {e}")
        raise HTTPException(status_code=500, detail="创建数据绑定失败")

@heatmap_router.delete("/bindings/{binding_id}")
async def delete_binding(binding_id: int, db: Session = Depends(get_db)):
    """删除数据绑定"""
    try:
        db_binding = db.query(HeatmapBinding).filter(HeatmapBinding.id == binding_id).first()
        
        if not db_binding:
            raise HTTPException(status_code=404, detail="绑定不存在")
        
        # 软删除绑定
        db_binding.is_active = False
        db.commit()
        
        return {"success": True, "message": "数据绑定删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"删除数据绑定错误: {e}")
        raise HTTPException(status_code=500, detail="删除数据绑定失败")

@heatmap_router.delete("/areas/{area_id}/bindings")
async def delete_area_bindings(area_id: int, db: Session = Depends(get_db)):
    """删除区域的所有绑定"""
    try:
        # 检查区域是否存在
        db_area = db.query(HeatmapArea).filter(HeatmapArea.id == area_id).first()
        if not db_area:
            raise HTTPException(status_code=404, detail="区域不存在")
        
        # 删除该区域的所有绑定
        bindings = db.query(HeatmapBinding).filter(HeatmapBinding.area_id == area_id).all()
        for binding in bindings:
            binding.is_active = False
        
        db.commit()
        
        return {"success": True, "message": "区域绑定删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"删除区域绑定错误: {e}")
        raise HTTPException(status_code=500, detail="删除区域绑定失败")

@heatmap_router.get("/dashboard/config")
async def get_dashboard_config(db: Session = Depends(get_db)):
    """获取展板配置"""
    try:
        config = db.query(HeatmapDashboardConfig).filter(
            HeatmapDashboardConfig.is_active == True
        ).order_by(HeatmapDashboardConfig.updated_at.desc()).first()
        
        if config:
            config_dict = {
                "id": config.id,
                "map_id": config.map_id,
                "display_mode": config.display_mode,
                "max_areas": config.max_areas,
                "refresh_interval": config.refresh_interval,
                "config": config.config,
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "is_active": config.is_active
            }
            return {'success': True, 'data': config_dict}
        else:
            return {'success': True, 'data': None}
        
    except Exception as e:
        print(f"获取展板配置错误: {e}")
        raise HTTPException(status_code=500, detail="获取展板配置失败")

@heatmap_router.post("/dashboard/config")
async def save_dashboard_config(config: HeatmapDashboardConfigModel, db: Session = Depends(get_db)):
    """保存展板配置"""
    try:
        # 先禁用旧配置
        old_configs = db.query(HeatmapDashboardConfig).all()
        for old_config in old_configs:
            old_config.is_active = False
        
        # 创建新配置
        db_config = HeatmapDashboardConfig(
            map_id=config.map_id,
            display_mode=config.display_mode,
            max_areas=config.max_areas,
            refresh_interval=config.refresh_interval,
            config=config.config or {}
        )
        
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        
        return {
            'success': True,
            'data': {'id': db_config.id}
        }
        
    except Exception as e:
        print(f"保存展板配置错误: {e}")
        raise HTTPException(status_code=500, detail="保存展板配置失败")

@heatmap_router.get("/dashboard/data")
async def get_dashboard_data(db: Session = Depends(get_db)):
    """获取展板显示数据"""
    try:
        # 获取当前活跃的配置
        config = db.query(HeatmapDashboardConfig).filter(
            HeatmapDashboardConfig.is_active == True
        ).order_by(HeatmapDashboardConfig.updated_at.desc()).first()
        
        if not config:
            return {'success': True, 'data': {'areas': [], 'map': None}}
        
        # 获取地图信息
        map_data = db.query(HeatmapMap).filter(
            HeatmapMap.id == config.map_id,
            HeatmapMap.is_active == True
        ).first()
        
        # 获取区域和绑定数据
        areas = db.query(HeatmapArea).filter(
            HeatmapArea.map_id == config.map_id,
            HeatmapArea.is_active == True
        ).order_by(HeatmapArea.created_at.asc()).all()
        
        areas_data = []
        for area in areas:
            binding = db.query(HeatmapBinding).filter(
                HeatmapBinding.area_id == area.id,
                HeatmapBinding.is_active == True
            ).first()

            if binding:
                crowd_analysis = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == binding.data_source_id).first()
            else:
                crowd_analysis = None
            
            area_dict = {
                "id": area.id,
                "map_id": area.map_id,
                "name": area.name,
                "points": area.points,
                "color": area.color,
                "area_size": area.area_size,
                "max_capacity": area.max_capacity,
                "description": area.description,
                "data_source_type": binding.data_source_type if binding else None,
                "data_source_id": binding.data_source_id if binding else None,
                "data_source_name": binding.data_source_name if binding else None,
                "current_count": crowd_analysis.last_result.get("total_person_count", 0) if crowd_analysis and crowd_analysis.last_result else 0,
                "last_update_time": crowd_analysis.last_run if crowd_analysis else None,
                "created_at": area.created_at,
                "updated_at": area.updated_at,
                "is_active": area.is_active
            }
            areas_data.append(area_dict)
        
        map_dict = None
        if map_data:
            map_dict = {
                "id": map_data.id,
                "name": map_data.name,
                "file_path": map_data.file_path,
                "file_name": map_data.file_name,
                "file_size": map_data.file_size,
                "mime_type": map_data.mime_type,
                "width": map_data.width,
                "height": map_data.height,
                "scale_factor": map_data.scale_factor,
                "description": map_data.description,
                "image_url": f"/api/v1/heatmap/maps/{map_data.id}/image",
                "created_at": map_data.created_at,
                "updated_at": map_data.updated_at,
                "is_active": map_data.is_active,
                "created_by": map_data.created_by
            }
        
        return {
            'success': True,
            'data': {
                'map': map_dict,
                'areas': areas_data
            }
        }
        
    except Exception as e:
        print(f"获取展板数据错误: {e}")
        raise HTTPException(status_code=500, detail="获取展板数据失败")

def calculate_polygon_area(points, scale_factor=1.0):
    """使用鞋带公式计算多边形面积"""
    if len(points) < 3:
        return 0
    
    area = 0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i]['x'] * points[j]['y']
        area -= points[j]['x'] * points[i]['y']
    
    area = abs(area) / 2.0
    # 转换为实际面积（平方米）
    return area * (scale_factor ** 2) 