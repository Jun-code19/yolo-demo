@echo off
echo ===================================
echo YOLO检测系统开发环境启动工具
echo ===================================
echo.

:: 设置开发环境变量
set DEV_MODE=true
set DATABASE_URL=postgresql://postgres:admin123@10.83.34.35:5432/eyris_core_db

:: 检查PostgreSQL服务是否可访问
echo 检查数据库连接...
ping -n 1 10.83.34.35 > nul
if %errorlevel% neq 0 (
    echo 警告: 无法连接到数据库服务器 10.83.34.35
    echo 请确保数据库服务器已启动并且网络可访问
    echo.
    pause
    exit /b
)

:: 提示启动后端服务
echo 是否需要启动后端服务? (Y/N)
set /p startBackend=

if /i "%startBackend%"=="Y" (
    call start_backend_dev.bat
) else (
    echo 请确保后端服务已在其他位置启动
)

echo.
echo 数据库信息:
echo   服务器: 10.83.34.35
echo   数据库: eyris_core_db
echo   用户名: postgres
echo   密码: admin123
echo.

:: 切换到前端目录
cd yolo-client

:: 启动开发服务器
echo 启动前端开发服务器...
npm run dev 