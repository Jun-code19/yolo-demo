from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import asyncio
import psutil  # 导入psutil库

from src.database import (
    get_db, Device, DetectionEvent, DetectionConfig, EdgeServer, ExternalEvent, CrowdAnalysisJob, CrowdAnalysisResult,SmartScheme,SmartEvent
)
from api.logger import log_action
import GPUtil # 导入GPUtil库

router = APIRouter(prefix="/dashboard", tags=["数据大屏"])

# 定义事件类型映射
event_type_map = {
    "object_detection": "目标检测",
    "smart_behavior": "智能行为",
    "smart_counting": "智能人数统计",
    "segmentation": "图像分割",
    "keypoint": "关键点检测",
    "pose": "姿态估计",
    "face": "人脸识别",
    "other": "其他类型",
    "alarm": "订阅报警",
    "smart": "订阅智能",
    "system_log": "设备日志"
}

#数据大屏API-旧
@router.get("/overview-data")
def get_dashboard_data(db: Session = Depends(get_db)):
    """获取数据大屏数据"""
    try:
        device_count = db.query(Device).count()
        detection_event_count = db.query(DetectionEvent).count()
        detection_config_count = db.query(DetectionConfig).count()
        crowd_analysis_job_count = db.query(CrowdAnalysisJob).count()
        edge_server_count = db.query(EdgeServer).count()
        external_event_count = db.query(ExternalEvent).count()
        return {
            "data": {
                "device_count": device_count,
                "detection_event_count": detection_event_count,
                "detection_config_count": detection_config_count,
                "crowd_analysis_job_count": crowd_analysis_job_count, 
                "edge_server_count": edge_server_count,
                "external_event_count": external_event_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏数据失败")
    
@router.get("/crowd-analysis-data")
def get_dashboard_crowd_analysis_data(db: Session = Depends(get_db)):
    """获取数据大屏人群分析数据"""
    try:
        # 方法1：获取每个任务的最新分析结果
        # 使用子查询获取每个job_id的最新timestamp
        from sqlalchemy import func
        
        subquery = db.query(
            CrowdAnalysisResult.job_id,
            func.max(CrowdAnalysisResult.timestamp).label('latest_timestamp')
        ).group_by(CrowdAnalysisResult.job_id).subquery()
        
        # 主查询：关联获取最新结果
        latest_results = db.query(
            CrowdAnalysisJob.job_name,
            CrowdAnalysisResult.total_person_count,
            CrowdAnalysisResult.timestamp
        ).join(
            CrowdAnalysisResult, 
            CrowdAnalysisJob.job_id == CrowdAnalysisResult.job_id
        ).join(
            subquery,
            (CrowdAnalysisResult.job_id == subquery.c.job_id) & 
            (CrowdAnalysisResult.timestamp == subquery.c.latest_timestamp)
        ).all()
        
        result = []
        for job_name, people_count, timestamp in latest_results:
            result.append({
                "job_name": job_name,
                "people_count": people_count or 0,
                "last_update": timestamp.isoformat() if timestamp else None
            })
        return {
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏人群分析数据失败")
    
@router.get("/alert-history-data")
def get_dashboard_alert_history_data(db: Session = Depends(get_db)):
    """获取数据大屏告警历史数据"""
    try:
        events = db.query(ExternalEvent).order_by(ExternalEvent.timestamp.desc()).limit(10).all()
        return {
            "data": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏告警历史数据失败")
    
@router.get("/historical-stats-data")
def get_dashboard_historical_stats_data(db: Session = Depends(get_db)):
    """获取数据大屏历史数据事件数据"""
    try:
        from sqlalchemy import func
        
        # 获取最近5天的每天的数据条数
        events = db.query(
            func.date(ExternalEvent.timestamp).label('date'), 
            func.count(ExternalEvent.event_id).label('count')
        ).filter(
            ExternalEvent.timestamp >= datetime.now() - timedelta(days=5)
        ).group_by(
            func.date(ExternalEvent.timestamp)
        ).all()
        # 升序
        events = sorted(events, key=lambda x: x.date)
        # 转换为字典格式
        result = []
        for date, count in events:
            result.append({
                "date": date.isoformat() if date else None,
                "count": count
            })
        
        return {
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏历史数据事件数据失败")
    
@router.get("/detection-event-data")
def get_dashboard_detection_event_data(db: Session = Depends(get_db)):
    """获取数据大屏检测事件数据"""
    try:
        from sqlalchemy import func
        
        # 获取检测总数
        detection_count = db.query(ExternalEvent).count()
        
        # 根据引擎名称统计检测数量
        engine_count_query = db.query(
            ExternalEvent.engine_name,
            func.count(ExternalEvent.event_id).label('count')
        ).filter(
            ExternalEvent.engine_name.isnot(None)
        ).group_by(
            ExternalEvent.engine_name
        ).all()
        
        # 转换为列表格式
        engine_count = []
        for engine_name, count in engine_count_query:
            engine_count.append({
                "engine_name": engine_name or "未知引擎",
                "detection_count": count
            })
        
        # engine_count只保留前5个
        engine_count = engine_count[:5]
        
        engine_count.append({
            "engine_name": "异常事件",
            "detection_count": detection_count
        })

        return {
            "data": engine_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏检测事件数据失败")
    
@router.get("/detection-type-data")
def get_dashboard_detection_type_data(db: Session = Depends(get_db)):
    """获取数据大屏检测类型数据"""
    try:
        from sqlalchemy import func, and_
        
        # 计算时间范围
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        day_before_yesterday_start = today_start - timedelta(days=2)
        
        # 优化的查询：分别统计总数、昨天、前天的数据
        # 总数统计
        total_count_query = db.query(
            ExternalEvent.engine_name,
            func.count(ExternalEvent.event_id).label('total_count')
        ).filter(
            ExternalEvent.engine_name.isnot(None)
        ).group_by(ExternalEvent.engine_name)
        
        # 昨天数据统计
        yesterday_count_query = db.query(
            ExternalEvent.engine_name,
            func.count(ExternalEvent.event_id).label('yesterday_count')
        ).filter(
            and_(
                ExternalEvent.engine_name.isnot(None),
                ExternalEvent.timestamp >= yesterday_start,
                ExternalEvent.timestamp < today_start
            )
        ).group_by(ExternalEvent.engine_name)
        
        # 前天数据统计
        day_before_yesterday_count_query = db.query(
            ExternalEvent.engine_name,
            func.count(ExternalEvent.event_id).label('day_before_yesterday_count')
        ).filter(
            and_(
                ExternalEvent.engine_name.isnot(None),
                ExternalEvent.timestamp >= day_before_yesterday_start,
                ExternalEvent.timestamp < yesterday_start
            )
        ).group_by(ExternalEvent.engine_name)
        
        # 执行查询
        total_counts = {row.engine_name: row.total_count for row in total_count_query.all()}
        yesterday_counts = {row.engine_name: row.yesterday_count for row in yesterday_count_query.all()}
        day_before_yesterday_counts = {row.engine_name: row.day_before_yesterday_count for row in day_before_yesterday_count_query.all()}
        
        # 合并数据并计算同比率
        detection_type_count = []
        for engine_name in total_counts.keys():
            total = total_counts.get(engine_name, 0)
            yesterday = yesterday_counts.get(engine_name, 0)
            day_before_yesterday = day_before_yesterday_counts.get(engine_name, 0)
            
            # 计算同比率（昨天相比前天的变化率）
            if day_before_yesterday > 0:
                rate = round((yesterday - day_before_yesterday) / day_before_yesterday * 100, 2)
            else:
                rate = 0 if yesterday == 0 else 100  # 如果前天没有数据，昨天有数据则为100%增长
            
            detection_type_count.append({
                "engine_name": engine_name,
                "count": total,
                "count_yesterday": yesterday,
                "count_day_before_yesterday": day_before_yesterday,
                "count_yesterday_rate": rate
            })
        
        # 按总数排序，取前6个（为本地引擎留一个位置）
        detection_type_count.sort(key=lambda x: x["count"], reverse=True)
        detection_type_count = detection_type_count[:6]
        
        # 添加本地检测引擎数据（从DetectionEvent表查询）
        try:
            local_total = db.query(DetectionEvent).count()
            local_yesterday = db.query(DetectionEvent).filter(
                and_(
                    DetectionEvent.timestamp >= yesterday_start,
                    DetectionEvent.timestamp < today_start
                )
            ).count()
            local_day_before_yesterday = db.query(DetectionEvent).filter(
                and_(
                    DetectionEvent.timestamp >= day_before_yesterday_start,
                    DetectionEvent.timestamp < yesterday_start
                )
            ).count()
            
            # 计算本地引擎同比率
            if local_day_before_yesterday > 0:
                local_rate = round((local_yesterday - local_day_before_yesterday) / local_day_before_yesterday * 100, 2)
            else:
                local_rate = 0 if local_yesterday == 0 else 100
            
            detection_type_count.append({
                "engine_name": "本地引擎",
                "count": local_total,
                "count_yesterday": local_yesterday,
                "count_day_before_yesterday": local_day_before_yesterday,
                "count_yesterday_rate": local_rate
            })
        except Exception as local_error:
            # 如果本地引擎数据查询失败，添加默认数据
            detection_type_count.append({
                "engine_name": "本地引擎",
                "count": 0,
                "count_yesterday": 0,
                "count_day_before_yesterday": 0,
                "count_yesterday_rate": 0
            })
        
        return {
            "data": detection_type_count,
            "meta": {
                "query_time": now.isoformat(),
                "time_ranges": {
                    "today_start": today_start.isoformat(),
                    "yesterday_start": yesterday_start.isoformat(),
                    "day_before_yesterday_start": day_before_yesterday_start.isoformat()
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏检测类型数据失败")

#数据大屏API-新
@router.get("/overview-smart-data")
def get_dashboard_overview_data(db: Session = Depends(get_db)):
    """获取数据大屏数据"""
    try:
        device_count = db.query(Device).count()
        detection_config_count = db.query(DetectionConfig).count()
        crowd_analysis_job_count = db.query(CrowdAnalysisJob).count()

        smart_scheme_count = db.query(SmartScheme).count()
        smart_event_count = db.query(SmartEvent).count()
        # smart_type_count = db.query(SmartEvent.event_type, func.count(SmartEvent.id)).group_by(SmartEvent.event_type).all()

        detection_event_count = db.query(DetectionEvent).count()
        # detection_type_count = db.query(DetectionEvent.event_type, func.count(DetectionEvent.event_id)).group_by(DetectionEvent.event_type).all()
        detection_events = db.query(DetectionEvent, Device.device_name).join(Device, DetectionEvent.device_id == Device.device_id).order_by(DetectionEvent.created_at.desc()).limit(25).all()
        detection_lasted_events = db.query(DetectionEvent, Device.device_name).join(Device, DetectionEvent.device_id == Device.device_id
            ).filter(and_(DetectionEvent.thumbnail_path.isnot(None), DetectionEvent.thumbnail_path != "")
            ).order_by(DetectionEvent.created_at.desc()
            ).limit(12).all()

        external_event_count = db.query(ExternalEvent).count()
        # 根据引擎名称统计检测数量
        # external_type_count = db.query(
        #     ExternalEvent.engine_name,
        #     func.count(ExternalEvent.event_id).label('count')
        # ).filter(
        #     ExternalEvent.engine_name.isnot(None)
        # ).group_by(
        #     ExternalEvent.engine_name
        # ).all()
       
        # 转换为列表格式
        # event_count = []
        # for engine_name, count in external_type_count:
        #     event_count.append({
        #         "event_type": engine_name or "未知引擎",
        #         "event_count": count
        #     })
        # for event_type, count in smart_type_count:
        #     event_count.append({
        #         "event_type": event_type_map.get(event_type, "未知类型"),
        #         "event_count": count
        #     })
        # for event_type, count in detection_type_count:
        #     event_count.append({
        #         "event_type": event_type_map.get(event_type, "未知类型"),
        #         "event_count": count
        #     })

        detection_events_data = []
        for event, device_name in detection_events:
            event_dict = event.__dict__
            event_dict.pop('_s-instance_state', None) # 移除SQLAlchemy内部状态
            event_dict['device_name'] = device_name
             # 如果 event_type 已经是中文，则不再转换；否则，进行转换
            if event_dict['event_type'] not in event_type_map:
                # 假设已经是中文，直接使用
                pass  
            else:
                event_dict['event_type'] = event_type_map.get(event_dict['event_type'], "未知类型")
            detection_events_data.append(event_dict)

        detection_lasted_events_data = []
        for event, device_name in detection_lasted_events:
            event_dict = event.__dict__
            event_dict.pop('_s-instance_state', None)
            event_dict['device_name'] = device_name
            # 如果 event_type 已经是中文，则不再转换；否则，进行转换
            if event_dict['event_type'] not in event_type_map:
                # 假设已经是中文，直接使用
                pass  
            else:
                event_dict['event_type'] = event_type_map.get(event_dict['event_type'], "未知类型")
            detection_lasted_events_data.append(event_dict)

        return {
            "data": {
                "device_count": device_count,                
                "detection_config_count": detection_config_count,
                "crowd_analysis_job_count": crowd_analysis_job_count, 
                "smart_scheme_count": smart_scheme_count,
                "smart_event_count": smart_event_count,
                "detection_event_count": detection_event_count,
                "external_event_count":external_event_count,
                # "event_type_count":event_count,              
                "detection_events": detection_events_data,
                "detection_lasted_events": detection_lasted_events_data     
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏数据失败")
    
@router.get("/historical-smart-data")
def get_dashboard_historical_data(db: Session = Depends(get_db)):
    """获取数据大屏历史数据事件数据"""
    try:       
        # 获取最近5天的每天的数据条数
        external_event_history = db.query(
            func.date(ExternalEvent.timestamp).label('date'), 
            func.count(ExternalEvent.event_id).label('count')
        ).filter(
            ExternalEvent.timestamp >= datetime.now() - timedelta(days=5)
        ).group_by(
            func.date(ExternalEvent.timestamp)
        ).all()

        detection_event_history = db.query(
            func.date(DetectionEvent.created_at).label('date'), 
            func.count(DetectionEvent.event_id).label('count')
        ).filter(
            DetectionEvent.created_at >= datetime.now() - timedelta(days=5)
        ).group_by(
            func.date(DetectionEvent.created_at)
        ).all()

        smart_event_history = db.query(
            func.date(SmartEvent.timestamp).label('date'), 
            func.count(SmartEvent.id).label('count')
        ).filter(
            SmartEvent.timestamp >= datetime.now() - timedelta(days=5)
        ).group_by(
            func.date(SmartEvent.timestamp)
        ).all()

        # 创建一个字典来存储所有数据，以日期为键
        result_dict = {}
        # 生成过去5天的所有日期，并初始化为0
        today = datetime.now().date()
        for i in range(5, -1, -1): # 包括今天和过去5天，共6天
            date = today - timedelta(days=i)
            result_dict[date] = {
                "date": date.isoformat(),
                "external_event_count": 0,
                "detection_event_count": 0,
                "smart_event_count": 0
            }

        # 处理外部事件数据
        for date, count in external_event_history:
            if date in result_dict: # 确保日期存在于初始化后的字典中
                result_dict[date]["external_event_count"] = count

        # 处理检测事件数据
        for date, count in detection_event_history:
            if date in result_dict:
                result_dict[date]["detection_event_count"] = count

        # 处理智能事件数据
        for date, count in smart_event_history:
            if date in result_dict:
                result_dict[date]["smart_event_count"] = count

        # 转换为列表并按日期排序
        result = sorted(result_dict.values(), key=lambda x: x["date"])
        
        return {
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏历史数据事件数据失败")

@router.get("/type-smart-data")
def get_dashboard_type_data(db: Session = Depends(get_db)):
    """获取数据大屏检测类型数据"""
    try:       
        # 计算时间范围（确保时区一致性，这里使用服务器本地时间）
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start - timedelta(microseconds=1)  # 昨天结束时刻是今天开始前一微秒
        day_before_yesterday_start = today_start - timedelta(days=2)
        day_before_yesterday_end = yesterday_start - timedelta(microseconds=1)  # 前天结束时刻是昨天开始前一微秒

        # 定义一个函数来执行针对特定事件模型和分类字段的统计查询
        def get_event_stats(event_model, category_field, timestamp_field,id_field):
            """获取指定事件模型在三个时间段的统计信息（今天、昨天、前天）"""
            
            total_stats = db.query(
                category_field.label('category'),
                func.count(id_field).label('total_count')
            ).filter(
                category_field.isnot(None),
            ).group_by(category_field).all()

            # 今天数据统计
            today_stats = db.query(
                category_field.label('category'),
                func.count(id_field).label('today_count')
            ).filter(
                and_(
                    category_field.isnot(None),
                    timestamp_field >= today_start,
                    timestamp_field <= now  # 到今天当前时刻为止
                )
            ).group_by(category_field).all()
            
            # 昨天数据统计
            yesterday_stats = db.query(
                category_field.label('category'),
                func.count(id_field).label('yesterday_count')
            ).filter(
                and_(
                    category_field.isnot(None),
                    timestamp_field >= yesterday_start,
                    timestamp_field <= yesterday_end
                )
            ).group_by(category_field).all()
            
            # 前天数据统计
            day_before_yesterday_stats = db.query(
                category_field.label('category'),
                func.count(id_field).label('day_before_yesterday_count')
            ).filter(
                and_(
                    category_field.isnot(None),
                    timestamp_field >= day_before_yesterday_start,
                    timestamp_field <= day_before_yesterday_end
                )
            ).group_by(category_field).all()
            
            # 将查询结果转换为字典以便后续合并，键为 category
            total_dict = {category: count for category, count in total_stats}
            today_dict = {category: count for category, count in today_stats}
            yesterday_dict = {category: count for category, count in yesterday_stats}
            day_before_yesterday_dict = {category: count for category, count in day_before_yesterday_stats}
            
            return {
                'total_dict': total_dict,
                'today_dict': today_dict,
                'yesterday_dict': yesterday_dict,
                'day_before_yesterday_dict': day_before_yesterday_dict
            }

        # 获取三种事件类型的统计信息
        # ExternalEvent 按 engine_name 分类
        external_stats = get_event_stats(ExternalEvent, ExternalEvent.engine_name, ExternalEvent.timestamp,ExternalEvent.event_id)
        # DetectionEvent 按 event_type 分类
        detection_stats = get_event_stats(DetectionEvent, DetectionEvent.event_type, DetectionEvent.created_at,DetectionEvent.event_id)
        # SmartEvent 按 event_type 分类
        smart_stats = get_event_stats(SmartEvent, SmartEvent.event_type, SmartEvent.timestamp,SmartEvent.id)

        # 获取所有可能的分类名（合并三种事件类型中的分类名）
        all_categories = set()
        all_categories.update(external_stats['total_dict'].keys())
        all_categories.update(external_stats['today_dict'].keys())
        all_categories.update(external_stats['yesterday_dict'].keys())
        all_categories.update(external_stats['day_before_yesterday_dict'].keys())
        all_categories.update(detection_stats['total_dict'].keys())
        all_categories.update(detection_stats['today_dict'].keys())
        all_categories.update(detection_stats['yesterday_dict'].keys())
        all_categories.update(detection_stats['day_before_yesterday_dict'].keys())
        all_categories.update(smart_stats['total_dict'].keys())
        all_categories.update(smart_stats['today_dict'].keys())
        all_categories.update(smart_stats['yesterday_dict'].keys())
        all_categories.update(smart_stats['day_before_yesterday_dict'].keys())

        # 合并数据并计算增长率（昨天相比前天的变化率）
        final_result = []
        for category in all_categories:
            # 初始化各事件类型在三个时间段的计数
            external_total = external_stats['total_dict'].get(category, 0)
            external_today = external_stats['today_dict'].get(category, 0)
            external_yesterday = external_stats['yesterday_dict'].get(category, 0)
            external_day_before = external_stats['day_before_yesterday_dict'].get(category, 0)
            
            detection_total = detection_stats['total_dict'].get(category, 0)
            detection_today = detection_stats['today_dict'].get(category, 0)
            detection_yesterday = detection_stats['yesterday_dict'].get(category, 0)
            detection_day_before = detection_stats['day_before_yesterday_dict'].get(category, 0)
            
            smart_total = smart_stats['total_dict'].get(category, 0)
            smart_today = smart_stats['today_dict'].get(category, 0)
            smart_yesterday = smart_stats['yesterday_dict'].get(category, 0)
            smart_day_before = smart_stats['day_before_yesterday_dict'].get(category, 0)
            
            # 计算总计数
            event_total = external_total + detection_total + smart_total
            today_total = external_today + detection_today + smart_today
            yesterday_total = external_yesterday + detection_yesterday + smart_yesterday
            day_before_yesterday_total = external_day_before + detection_day_before + smart_day_before
            
            # 计算同比增长率（昨天相比前天的变化率）
            growth_rate = 0.0
            if day_before_yesterday_total > 0:
                growth_rate = round(((yesterday_total - day_before_yesterday_total) / day_before_yesterday_total) * 100, 2)
            elif yesterday_total > 0:
                # 如果前天为0而昨天有数据，则增长率为100%
                growth_rate = 100.0
            # 如果前天和昨天都为0，则增长率为0%（保持不变）
            
            final_result.append({
                "category": event_type_map.get(category, category),
                "event_total":event_total,
                "today_total": today_total,
                "yesterday_total": yesterday_total,
                "day_before_yesterday_total": day_before_yesterday_total,
                "growth_rate": growth_rate,  # 昨天相对于前天的增长率
            })

        # 可以根据需要按 event_total 或其他字段排序
        final_result.sort(key=lambda x: x['event_total'], reverse=True)

        return {
            "data": final_result,
            "meta": {
                "query_time": now.isoformat(),
                "time_ranges": {
                    "today_start": today_start.isoformat(),
                    "today_end": now.isoformat(),
                    "yesterday_start": yesterday_start.isoformat(),
                    "yesterday_end": yesterday_end.isoformat(),
                    "day_before_yesterday_start": day_before_yesterday_start.isoformat(),
                    "day_before_yesterday_end": day_before_yesterday_end.isoformat()
                },
                "growth_rate_note": "growth_rate is calculated as ((yesterday - day_before_yesterday) / day_before_yesterday) * 100%"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取数据大屏检测类型数据失败")

@router.get("/system-status")
def get_system_status():
    """获取系统资源状态"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count(logical=False)  # 物理核心数
        cpu_logical_count = psutil.cpu_count(logical=True) # 逻辑核心数

        memory = psutil.virtual_memory()
        memory_total_gb = round(memory.total / (1024 ** 3), 2)
        memory_used_gb = round(memory.used / (1024 ** 3), 2)
        memory_percent = memory.percent

        disk = psutil.disk_usage('/')
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_used_gb = round(disk.used / (1024 ** 3), 2)
        disk_percent = disk.percent

        # 尝试获取GPU信息，如果psutil或相关库不支持，则返回默认值
        gpu_percent = 0
        gpu_total_gb = 0
        gpu_used_gb = 0
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # 假设只有一块GPU或者只取第一块
                gpu_percent = round(gpu.load * 100, 2)
                gpu_total_gb = round(gpu.memoryTotal / 1024, 2)
                gpu_used_gb = round(gpu.memoryUsed / 1024, 2)
        except Exception:
            pass # 忽略GPU获取失败的情况

        status = "normal"
        if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90 or gpu_percent > 90:
            status = "danger"
        elif cpu_percent > 70 or memory_percent > 80 or disk_percent > 80 or gpu_percent > 70:
            status = "warning"

        return {
            "data": {
                "status": status, # 默认正常，可根据阈值判断
                "cpu": {
                    "percent": cpu_percent,
                    "total": cpu_count,
                    "used": round(cpu_percent / 100 * cpu_count, 2)  # 根据百分比估算已用核数
                },
                "memory": {
                    "percent": memory_percent,
                    "total": memory_total_gb,
                    "used": memory_used_gb
                },
                "disk": {
                    "percent": disk_percent,
                    "total": disk_total_gb,
                    "used": disk_used_gb
                },
                "gpu": {
                    "percent": gpu_percent,
                    "total": gpu_total_gb,
                    "used": gpu_used_gb
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统资源数据失败: {str(e)}")
