-- 清理系统日志表，因为它有外键约束
DELETE FROM syslog;

-- 清理用户表
DELETE FROM users;

-- 插入管理员用户（密码未哈希，我们将在程序中再次使用脚本创建管理员）
INSERT INTO users (user_id, username, password_hash, role, allowed_devices)
VALUES ('admin', 'admin', 'admin123', 'admin', '{}'); 