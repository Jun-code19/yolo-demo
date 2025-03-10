from sqlalchemy.orm import Session
from api.auth import get_password_hash
from models.database import User, SessionLocal, engine, Base
import sys

# 确保数据库表已创建
Base.metadata.create_all(bind=engine)

def create_admin_user(force=False):
    """
    创建管理员用户
    
    Args:
        force (bool): 是否强制创建（即使用户已存在也创建）
    """
    # 创建数据库会话
    db = SessionLocal()
    
    try:
        # 检查是否已存在用户
        users_count = db.query(User).count()
        if users_count > 0 and not force:
            print("系统中已存在用户。使用 --force 参数强制创建管理员。")
            return
        
        # 设置管理员信息
        admin_id = "admin"
        admin_username = "admin"
        admin_password = "admin123"
        admin_role = "admin"
        
        # 检查是否已存在同名用户
        existing_user = db.query(User).filter(User.username == admin_username).first()
        if existing_user:
            if not force:
                print(f"用户名 '{admin_username}' 已存在。使用 --force 参数覆盖现有用户。")
                return
            else:
                print(f"正在替换现有用户 '{admin_username}'...")
                db.delete(existing_user)
                db.commit()

        hashed_password = get_password_hash(admin_password)
        print(f"生成的哈希密码: {hashed_password}")
        
        # 创建用户对象
        admin_user = User(
            user_id=admin_id,
            username=admin_username,
            password_hash=hashed_password,
            role=admin_role,
            allowed_devices=[]
        )
        
        # 添加到数据库
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"管理员用户 '{admin_username}' 创建成功！")
        print(f"用户ID: {admin_id}")
        print(f"用户名: {admin_username}")
        print(f"密码: {admin_password}")
        print(f"角色: {admin_role}")
        print("")
        print("请记住这些凭据，用于登录系统。")
        
    except Exception as e:
        db.rollback()
        print(f"创建管理员失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    # 检查是否有 --force 参数
    force = True
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        force = True
        print("强制模式：将覆盖同名现有用户")
    
    create_admin_user(force) 