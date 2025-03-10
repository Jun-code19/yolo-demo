from sqlalchemy import text
from models.database import SessionLocal, engine

def reset_database():
    print("开始重置数据库...")
    
    # 创建会话
    db = SessionLocal()
    
    try:
        # 清理系统日志表
        print("删除系统日志...")
        db.execute(text("DELETE FROM syslog"))
        
        # 清理用户表
        print("删除用户表数据...")
        db.execute(text("DELETE FROM users"))
        
        # 添加管理员用户（使用明文密码，方便调试）
        print("创建管理员用户...")
        db.execute(text("INSERT INTO users (user_id, username, password_hash, role, allowed_devices) VALUES ('admin', 'admin', 'admin123', 'admin', '{}')"))
        
        # 提交更改
        db.commit()
        print("数据库重置成功！")
        print("用户名: admin")
        print("密码: admin123")
    except Exception as e:
        db.rollback()
        print(f"重置数据库失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_database() 