from sqlalchemy.orm import Session
from models.database import SysLog
from datetime import datetime

def log_action(db: Session, user_id: str, action_type: str, target_id: str = None, detail: str = None):
    """
    记录用户操作日志
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        action_type: 操作类型 (create, update, delete, login, etc)
        target_id: 操作对象ID
        detail: 详细信息
    """
    log = SysLog(
        user_id=user_id,
        action_type=action_type,
        target_id=target_id,
        detail=detail,
        log_time=datetime.now()
    )
    
    try:
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error logging action: {str(e)}") 