from sqlalchemy.orm import Session
from src.database import SysLog
from datetime import datetime

# 在文件开头添加新的操作类型常量
OPERATION_TYPES = {
    # 设备管理
    'create_device': '创建设备',
    'update_device': '更新设备',
    'delete_device': '删除设备',
    'device_status_change': '设备状态变更',
    
    # 检测配置
    'create_detection_config': '创建检测配置',
    'update_detection_config': '更新检测配置',
    'delete_detection_config': '删除检测配置',
    'start_detection': '启动检测任务',
    'stop_detection': '停止检测任务',
    
    # 检测事件
    'create_detection_event': '创建检测事件',
    'update_detection_event': '更新检测事件',
    'delete_detection_event': '删除检测事件',
    'export_detection_events': '导出检测事件',
    
    # 模型管理
    'upload_model': '上传模型',
    'delete_model': '删除模型',
    'toggle_model': '启用/禁用模型',
    'update_model_config': '更新模型配置',
    
    # 人群分析
    'create_crowd_task': '创建人群分析任务',
    'update_crowd_task': '更新人群分析任务',
    'delete_crowd_task': '删除人群分析任务',
    'export_crowd_results': '导出人群分析结果',
    'pause_crowd_task': '暂停人群分析任务',
    'resume_crowd_task': '恢复人群分析任务',
    
    # 数据推送
    'create_data_push': '创建推送配置',
    'update_data_push': '更新推送配置',
    'delete_data_push': '删除推送配置',
    'toggle_data_push': '启用/禁用推送配置',
    'test_data_push': '测试推送配置',

    # 系统管理
    'clear_system_logs': '清除系统日志',
    'export_system_logs': '导出系统日志',
    'update_system_config': '更新系统配置',
    'restart_service': '重启服务',
    
    # 用户管理
    'create_user': '创建用户',
    'update_user': '更新用户',
    'delete_user': '删除用户',
    'update_user_permission': '更新用户权限',
    'change_password': '修改密码',
    
    # 其他操作
    'login': '用户登录',
    'logout': '用户登出',
    'export_data': '导出数据',
    'import_data': '导入数据',
    'backup_system': '系统备份',
    'restore_system': '系统恢复'
}

# 修改日志记录函数
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
