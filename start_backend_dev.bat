@echo off
:: 设置开发环境变量
set DEV_MODE=true
set DATABASE_URL=postgresql://postgres:admin123@10.83.34.35:5432/eyris_core_db

echo 开发环境启动中...
echo 将连接到以下数据库:
echo   服务器: 10.83.34.35
echo   数据库: eyris_core_db
echo   用户名: postgres
echo   密码: admin123

:: 激活虚拟环境
call new_venv\Scripts\activate.bat

:: 查看环境变量是否设置成功
echo.
echo 环境变量设置:
echo DEV_MODE=%DEV_MODE%
echo DATABASE_URL=%DATABASE_URL%
echo.

:: 检查后端服务端口是否已被占用
netstat -ano | findstr :8000
if %errorlevel% equ 0 (
  echo 警告: 端口8000已被占用，检测服务可能无法启动
  echo 请检查是否有其他服务正在使用此端口
)

netstat -ano | findstr :8001
if %errorlevel% equ 0 (
  echo 警告: 端口8001已被占用，数据服务可能无法启动
  echo 请检查是否有其他服务正在使用此端口
)

netstat -ano | findstr :8765
if %errorlevel% equ 0 (
  echo 警告: 端口8765已被占用，RTSP服务可能无法启动
  echo 请检查是否有其他服务正在使用此端口
)

:: 启动后端服务
echo 启动数据服务...
start cmd /k "title 数据服务 && python base_data_server.py && pause"

echo 启动RTSP服务...
start cmd /k "title RTSP服务 && python base_rtsp_server.py && pause"

echo 启动检测服务...
start cmd /k "title 检测服务 && set DEBUG=1 && python base_detect_server.py && pause"

echo.
echo 所有后端服务已启动，请检查各窗口是否有错误信息
echo 如果服务启动失败，请查看命令窗口中的错误信息
echo. 