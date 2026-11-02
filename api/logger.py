from sqlalchemy.orm import Session
from src.database import SysLog, DetectionLog, Device
from datetime import datetime

# 操作类型中文描述（与前端 System.vue / 后端 log_action 写入对齐）
OPERATION_TYPES = {
    # 设备管理
    'create_device': '创建设备',
    'update_device': '更新设备',
    'delete_device': '删除设备',
    'device_status_change': '设备状态变更',
    'import_devices': '导入设备',
    'export_devices': '导出设备',
    'export_device_template': '导出设备模板',
    'create_device_group': '创建设备组',
    'update_device_group': '更新设备组',
    'delete_device_group': '删除设备组',

    # 检测配置
    'create_detection_config': '创建检测配置',
    'update_detection_config': '更新检测配置',
    'delete_detection_config': '删除检测配置',
    'toggle_detection_active': '启用/禁用检测配置',
    'toggle_detection_config': '启用/禁用检测配置',
    'start_detection': '启动检测任务',
    'stop_detection': '停止检测任务',

    # 检测事件
    'create_detection_event': '创建检测事件',
    'update_detection_event': '更新检测事件',
    'delete_detection_event': '删除检测事件',
    'batch_delete_detection_events': '批量删除检测事件',
    'export_detection_events': '导出检测事件',
    'cleanup_detection_events': '清理过期检测事件',
    'cleanup_expired_events': '清理过期事件',

    # 模型管理
    'upload_model': '上传模型',
    'update_model': '更新模型',
    'delete_model': '删除模型',
    'activate_model': '启用模型',
    'deactivate_model': '禁用模型',
    'toggle_model': '启用/禁用模型',
    'update_model_config': '更新模型配置',

    # 人群分析
    'create_crowd_task': '创建人群分析任务',
    'update_crowd_task': '更新人群分析任务',
    'delete_crowd_task': '删除人群分析任务',
    'export_crowd_results': '导出人群分析结果',
    'pause_crowd_task': '暂停人群分析任务',
    'resume_crowd_task': '恢复人群分析任务',
    'run_crowd_task': '立即执行人群分析任务',

    # 数据推送
    'create_data_push': '创建推送配置',
    'update_data_push': '更新推送配置',
    'delete_data_push': '删除推送配置',
    'toggle_data_push': '启用/禁用推送配置',
    'test_data_push': '测试推送配置',

    # 事件订阅
    'create_smart_scheme': '创建事件订阅',
    'update_smart_scheme': '更新事件订阅',
    'delete_smart_scheme': '删除事件订阅',
    'start_smart_scheme': '启动事件订阅',
    'stop_smart_scheme': '停止事件订阅',
    'restart_smart_scheme': '重启事件订阅',
    'update_smart_event': '更新智能事件',
    'delete_smart_event': '删除智能事件',
    'batch_delete_events': '批量删除事件',
    'batch_process_events': '批量处理事件',
    'batch_ignore_events': '批量忽略事件',
    'cleanup_smart_events': '清理过期智能事件',

    # 数据监听
    'create_listener_config': '创建监听配置',
    'update_listener_config': '更新监听配置',
    'delete_listener_config': '删除监听配置',
    'start_listener': '启动监听',
    'stop_listener': '停止监听',
    'restart_listener': '重启监听',
    'batch_start_listeners': '批量启动监听',
    'batch_stop_listeners': '批量停止监听',
    'update_external_event': '更新外部事件',
    'delete_event': '删除外部事件',
    'cleanup_external_events': '清理外部事件',

    # 复合告警
    'create_alert_rule': '创建告警规则',
    'update_alert_rule': '更新告警规则',
    'delete_alert_rule': '删除告警规则',
    'evaluate_alert_rules': '手动评估告警规则',

    # VLM 巡检
    'bootstrap_qwen_vlm': '注册 Qwen-VL 模型',
    'create_vlm_model': '注册 VLM 模型',
    'update_vlm_model': '更新 VLM 模型',
    'delete_vlm_model': '删除 VLM 模型',
    'update_vlm_api_key': '更新 VLM API Key',
    'import_prompt_templates': '导入 Prompt 模板',
    'create_prompt_template': '创建 Prompt 模板',
    'update_prompt_template': '更新 Prompt 模板',
    'delete_prompt_template': '删除 Prompt 模板',
    'create_vlm_inspection': '创建 VLM 巡检任务',
    'update_vlm_inspection': '更新 VLM 巡检任务',
    'delete_vlm_inspection': '删除 VLM 巡检任务',
    'pause_vlm_inspection': '暂停 VLM 巡检任务',
    'resume_vlm_inspection': '恢复 VLM 巡检任务',
    'run_vlm_inspection': '立即执行 VLM 巡检',

    # 边缘服务器
    'create_edge_server': '创建边缘服务器',
    'update_edge_server': '更新边缘服务器',
    'update_edge_server_status': '更新边缘服务器状态',
    'delete_edge_server': '删除边缘服务器',

    # 系统管理
    'clear_system_logs': '清除系统日志',
    'export_system_logs': '导出系统日志',
    'clear_detection_logs': '清除检测日志',
    'export_detection_logs': '导出检测日志',
    'update_system_config': '更新系统配置',
    'restart_service': '重启服务',

    # 用户管理
    'create_user': '创建用户',
    'create_admin': '创建管理员',
    'update_user': '更新用户',
    'update_profile': '更新个人信息',
    'delete_user': '删除用户',
    'update_user_permission': '更新用户权限',
    'change_password': '修改密码',
    'login': '用户登录',
    'logout': '用户登出',

    # 其他
    'export_data': '导出数据',
    'import_data': '导入数据',
    'backup_system': '系统备份',
    'restore_system': '系统恢复',
}


def log_action(db: Session, user_id: str, action_type: str, target_id: str, detail: str):
    """记录系统操作日志"""
    try:
        # 获取操作类型的中文描述
        action_desc = OPERATION_TYPES.get(action_type, action_type)
        
        # 创建日志记录
        log = SysLog(
            user_id=user_id,
            action_type=action_type,
            target_id=target_id,
            detail=f"{action_desc}: {detail}",
            log_time=datetime.now()
        )
        
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"记录操作日志失败: {str(e)}")
        db.rollback()

# 添加记录检测日志的函数
def _resolve_detection_log_device_id(db, device_id: str):
    """检测日志 device_id 必须是 device 表中的 ID，分组任务等场景可为空"""
    if not device_id or device_id in ("unknown", "null"):
        return None
    exists = db.query(Device.device_id).filter(Device.device_id == device_id).first()
    return device_id if exists else None


def log_detection_action(config_id: str, device_id: str, operation: str, status: str, message: str, user_id: str = None, db = None):
    """记录检测任务操作日志"""
    from src.database import SessionLocal
    
    # 标记是否需要在函数内部关闭数据库会话
    close_db = False
    try:
        # 如果没有传入数据库会话，创建一个新的
        if db is None or isinstance(db, str):
            db = SessionLocal()
            close_db = True

        resolved_device_id = _resolve_detection_log_device_id(db, device_id)
            
        log = DetectionLog(
            config_id=config_id,
            device_id=resolved_device_id,
            operation=operation,
            status=status,
            message=message,
            created_by=user_id,
            created_at=datetime.now()
        )
        db.add(log)
        db.commit()
        # print(f"记录检测日志成功: {operation} {config_id}")
    except Exception as e:
        print(f"记录检测日志失败: {str(e)}")
        if close_db and hasattr(db, 'rollback'):
            db.rollback()
    finally:
        # 只有在函数内部创建的会话才需要关闭
        if close_db and hasattr(db, 'close'):
            db.close()
