@echo off
chcp 65001 >nul
:: 修复网络问题并制作Linux离线包

echo === 修复网络问题并制作Linux x86_64离线安装包 ===
echo.

echo 步骤1: 诊断网络问题...

:: 检测代理和镜像源配置
echo 检查Docker配置...
docker info | findstr "Proxy\|Registry Mirrors"
echo.

echo 步骤2: 清理和重置构建环境...

:: 清理所有buildx构建器
echo 清理现有构建器...
for /f "tokens=1" %%i in ('docker buildx ls ^| findstr -v "^NAME"') do (
    if not "%%i"=="default" (
        docker buildx rm %%i 2>nul
    )
)

:: 重置到默认构建器
echo 切换到默认构建器...
docker buildx use default

echo 步骤3: 尝试直接构建（不使用buildx）...
echo 这将使用本地Docker引擎构建，避免buildx网络问题

set PACKAGE_NAME=yolo-linux-x64-offline
for /f "delims=" %%a in ('wmic os get localdatetime /value ^| find "="') do set "%%a"
set DATE=%LocalDateTime:~0,8%
set TIME=%LocalDateTime:~8,6%
set VERSION=%DATE%_%TIME%
set DIR=%PACKAGE_NAME%_%VERSION%

mkdir %DIR%\docker_images 2>nul

echo 步骤4: 使用标准docker build构建镜像...

:: 构建数据服务镜像（使用标准docker build）
echo 🔨 构建数据服务镜像（标准模式）...
docker build -f Dockerfile.data-server -t yolo-linux-data .
if errorlevel 1 (
    echo ❌ 数据服务镜像构建失败，尝试清理缓存后重试...
    docker builder prune -f
    docker build --no-cache -f Dockerfile.data-server -t yolo-linux-data .
    if errorlevel 1 (
        echo ❌ 构建仍然失败，请检查网络连接或Dockerfile
        pause
        exit /b 1
    )
)
echo ✅ 数据服务镜像构建完成

:: 构建检测服务镜像
echo 🔨 构建检测服务镜像（标准模式）...
docker build -f Dockerfile.detect-server -t yolo-linux-detect .
if errorlevel 1 (
    echo ❌ 检测服务镜像构建失败，尝试清理缓存后重试...
    docker builder prune -f
    docker build --no-cache -f Dockerfile.detect-server -t yolo-linux-detect .
    if errorlevel 1 (
        echo ❌ 构建仍然失败，请检查网络连接或Dockerfile
        pause
        exit /b 1
    )
)
echo ✅ 检测服务镜像构建完成

:: 构建前端镜像
echo 🔨 构建前端镜像（标准模式）...
docker build -f Dockerfile.frontend -t yolo-linux-frontend .
if errorlevel 1 (
    echo ❌ 前端镜像构建失败，尝试清理缓存后重试...
    docker builder prune -f
    docker build --no-cache -f Dockerfile.frontend -t yolo-linux-frontend .
    if errorlevel 1 (
        echo ❌ 构建仍然失败，请检查网络连接或Dockerfile
        pause
        exit /b 1
    )
)
echo ✅ 前端镜像构建完成

:: 拉取PostgreSQL（如果还没有）
echo 🔨 确保PostgreSQL镜像可用...
docker images postgres:14 | findstr "postgres" >nul
if errorlevel 1 (
    echo 拉取PostgreSQL镜像...
    docker pull postgres:14
    if errorlevel 1 (
        echo ❌ PostgreSQL镜像拉取失败
        pause
        exit /b 1
    )
)
echo ✅ PostgreSQL镜像可用

echo.
echo 步骤5: 验证镜像构建结果...
echo 检查镜像列表...
docker images | findstr "yolo-linux\|postgres"
echo.

echo 步骤6: 保存镜像为tar文件...
docker save yolo-linux-data -o %DIR%\docker_images\data-server.tar
docker save yolo-linux-detect -o %DIR%\docker_images\detect-server.tar  
docker save yolo-linux-frontend -o %DIR%\docker_images\frontend.tar
docker save postgres:14 -o %DIR%\docker_images\postgres.tar

echo ✅ 镜像保存完成
echo.

echo 步骤7: 创建Linux配置文件...
(
echo version: '3.8'
echo services:
echo   data-server:
echo     image: yolo-linux-data
echo     container_name: yolo-data-server
echo     volumes:
echo       - ./models:/app/models
echo       - ./storage:/app/storage
echo       - ./uploads:/app/uploads
echo     ports:
echo       - "8001:8001"
echo     environment:
echo       - DATABASE_URL=postgresql://postgres:admin123@postgres:5432/yolo
echo     depends_on:
echo       - postgres
echo     restart: always
echo     networks:
echo       - yolo-network
echo   detect-server:
echo     image: yolo-linux-detect
echo     container_name: yolo-detect-server  
echo     volumes:
echo       - ./models:/app/models
echo       - ./storage:/app/storage
echo       - ./uploads:/app/uploads
echo     ports:
echo       - "8000:8000"
echo     environment:
echo       - DATABASE_URL=postgresql://postgres:admin123@postgres:5432/yolo
echo     depends_on:
echo       - postgres
echo     restart: always
echo     networks:
echo       - yolo-network
echo   frontend:
echo     image: yolo-linux-frontend
echo     container_name: yolo-frontend
echo     ports:
echo       - "80:80"
echo     depends_on:
echo       - detect-server
echo       - data-server
echo     restart: always
echo     networks:
echo       - yolo-network
echo   postgres:
echo     image: postgres:14
echo     container_name: yolo-postgres
echo     volumes:
echo       - postgres-data:/var/lib/postgresql/data
echo     environment:
echo       - POSTGRES_PASSWORD=admin123
echo       - POSTGRES_USER=postgres
echo       - POSTGRES_DB=yolo
echo     ports:
echo       - "5432:5432"
echo     restart: always
echo     networks:
echo       - yolo-network
echo networks:
echo   yolo-network:
echo     driver: bridge
echo volumes:
echo   postgres-data:
echo     driver: local
) > %DIR%\docker-compose.yml

copy nginx.conf %DIR%\ >nul 2>&1

echo 步骤8: 创建Linux安装脚本...
(
echo #!/bin/bash
echo echo "=== YOLO Linux安装脚本 ==="
echo echo "系统架构: $(uname -m)"
echo echo ""
echo # 检查Docker
echo if ! command -v docker ^&^> /dev/null; then
echo     echo "❌ Docker未安装"
echo     echo "Ubuntu/Debian安装命令:"
echo     echo "  curl -fsSL https://get.docker.com | sh"
echo     echo "  sudo usermod -aG docker \$USER"
echo     echo "  newgrp docker"
echo     exit 1
echo fi
echo echo "✅ Docker已安装"
echo # 检查Docker Compose
echo if ! command -v docker-compose ^&^> /dev/null; then
echo     echo "❌ Docker Compose未安装"
echo     echo "安装命令:"
echo     echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-Linux-x86_64\" -o /usr/local/bin/docker-compose"
echo     echo "  sudo chmod +x /usr/local/bin/docker-compose"
echo     exit 1  
echo fi
echo echo "✅ Docker Compose已安装"
echo echo ""
echo echo "🔄 加载Docker镜像..."
echo docker load ^< docker_images/data-server.tar
echo docker load ^< docker_images/detect-server.tar
echo docker load ^< docker_images/frontend.tar
echo docker load ^< docker_images/postgres.tar
echo echo "✅ 镜像加载完成"
echo echo ""
echo echo "📁 创建目录..."
echo mkdir -p models storage uploads
echo chmod 755 models storage uploads
echo echo "✅ 目录创建完成"
echo echo ""
echo echo "🚀 启动服务..."
echo docker-compose up -d
echo echo ""
echo echo "⏳ 等待服务启动..."
echo sleep 15
echo echo ""
echo echo "📊 检查服务状态..."
echo docker-compose ps
echo echo ""
echo echo "🎉 === 安装完成! ==="
echo echo "📱 前端访问: http://localhost"
echo echo "🔧 检测API: http://localhost:8000/docs"
echo echo "📊 数据API: http://localhost:8001/docs"
echo echo ""
echo echo "📋 常用命令:"
echo echo "  docker-compose ps        # 查看状态"
echo echo "  docker-compose logs -f   # 查看日志"
echo echo "  docker-compose down      # 停止服务"
echo echo "  docker-compose restart   # 重启服务"
) > %DIR%\install.sh

echo 步骤9: 创建管理脚本...
(
echo #!/bin/bash
echo case "$1" in
echo   start^)
echo     echo "🚀 启动YOLO服务..."
echo     docker-compose up -d
echo     ;;
echo   stop^)
echo     echo "🛑 停止YOLO服务..."
echo     docker-compose down
echo     ;;
echo   restart^)
echo     echo "🔄 重启YOLO服务..."
echo     docker-compose restart
echo     ;;
echo   status^)
echo     echo "📊 服务状态:"
echo     docker-compose ps
echo     ;;
echo   logs^)
echo     echo "📜 查看日志:"
echo     docker-compose logs -f
echo     ;;
echo   *^)
echo     echo "YOLO Linux管理工具"
echo     echo "用法: $0 {start|stop|restart|status|logs}"
echo     ;;
echo esac
) > %DIR%\manage.sh

echo 步骤10: 复制项目文件...

REM 复制Dockerfile文件（重要！）
echo 复制Dockerfile文件...
copy Dockerfile.data-server %DIR%\ >nul 2>&1
copy Dockerfile.detect-server %DIR%\ >nul 2>&1
copy Dockerfile.frontend %DIR%\ >nul 2>&1

REM 复制配置文件
echo 复制配置文件...
if exist requirements.base.txt copy requirements.base.txt %DIR%\ >nul 2>&1
if exist requirements.data-server.txt copy requirements.data-server.txt %DIR%\ >nul 2>&1
if exist requirements.detect-server.txt copy requirements.detect-server.txt %DIR%\ >nul 2>&1
if exist pip.conf copy pip.conf %DIR%\ >nul 2>&1

REM 复制源代码目录（用于可能的重新构建）
echo 复制源代码...
if exist src xcopy src %DIR%\src\ /E /I /Q >nul 2>&1
if exist api xcopy api %DIR%\api\ /E /I /Q >nul 2>&1
if exist yolo-client xcopy yolo-client %DIR%\yolo-client\ /E /I /Q >nul 2>&1
if exist base_data_server.py copy base_data_server.py %DIR%\ >nul 2>&1
if exist base_detect_server.py copy base_detect_server.py %DIR%\ >nul 2>&1

REM 复制数据目录
echo 复制数据目录...
if exist models xcopy models %DIR%\models\ /E /I /Q >nul 2>&1
if exist storage xcopy storage %DIR%\storage\ /E /I /Q >nul 2>&1
if exist uploads xcopy uploads %DIR%\uploads\ /E /I /Q >nul 2>&1

echo 步骤11: 创建说明文档...
(
echo # YOLO Linux x86_64 离线安装包
echo.
echo ## 制作信息
echo - 制作时间: %DATE% %TIME%
echo - 目标架构: x86_64
echo - 构建模式: 标准Docker构建（非buildx）
echo.
echo ## 包含文件
echo - Docker镜像文件（docker_images/目录）
echo - Dockerfile文件（用于可能的重新构建）
echo - 源代码（src/, api/, yolo-client/等）
echo - 配置文件（requirements.txt, docker-compose.yml等）
echo - 安装和管理脚本（install.sh, manage.sh）
echo.
echo ## 使用方法
echo 1. 传输到Linux服务器: scp %PACKAGE_NAME%_%VERSION%.tar.gz user@server:/tmp/
echo 2. 解压: tar -xzf %PACKAGE_NAME%_%VERSION%.tar.gz
echo 3. 进入目录: cd %PACKAGE_NAME%_%VERSION%
echo 4. 设置权限: chmod +x *.sh
echo 5. 安装: ./install.sh
echo.
echo ## 管理命令
echo - ./manage.sh start   # 启动
echo - ./manage.sh stop    # 停止  
echo - ./manage.sh status  # 状态
echo - ./manage.sh logs    # 日志
echo.
echo ## 访问地址
echo - 前端: http://localhost
echo - 检测API: http://localhost:8000/docs
echo - 数据API: http://localhost:8001/docs
echo.
echo ## 故障排除
echo - 如果端口冲突，修改docker-compose.yml中的端口映射
echo - 如果服务启动失败，查看日志: docker-compose logs
echo - 重启服务: docker-compose restart
echo - 如果需要重新构建镜像：
echo   docker build -f Dockerfile.data-server -t yolo-linux-data .
echo   docker build -f Dockerfile.detect-server -t yolo-linux-detect .
echo   docker build -f Dockerfile.frontend -t yolo-linux-frontend .
) > %DIR%\README.md

echo 步骤12: 打包压缩...
where tar >nul 2>&1
if %errorlevel% == 0 (
    tar -czf %PACKAGE_NAME%_%VERSION%.tar.gz %DIR%
    echo ✅ 压缩包创建成功: %PACKAGE_NAME%_%VERSION%.tar.gz
) else (
    echo ⚠️  tar命令不可用，请手动压缩 %DIR% 目录
    echo 建议使用7-Zip压缩为.tar.gz格式
)

echo.
echo 🎉 === Linux离线安装包制作完成! ===
echo.
echo 📦 安装包目录: %DIR%
if exist %PACKAGE_NAME%_%VERSION%.tar.gz (
    echo 📦 压缩包文件: %PACKAGE_NAME%_%VERSION%.tar.gz
    for %%I in (%PACKAGE_NAME%_%VERSION%.tar.gz) do echo 📊 文件大小: %%~zI 字节
)
echo.
echo 🎯 解决的问题:
echo - ✅ 避免了buildx的网络连接问题
echo - ✅ 使用标准Docker构建，兼容性更好
echo - ✅ 自动清理和重试机制
echo.
echo 🚀 下一步操作:
echo 1. 传输到Linux服务器: scp %PACKAGE_NAME%_%VERSION%.tar.gz user@server:/tmp/
echo 2. 在Linux服务器执行:
echo    tar -xzf %PACKAGE_NAME%_%VERSION%.tar.gz
echo    cd %PACKAGE_NAME%_%VERSION%
echo    chmod +x *.sh
echo    ./install.sh
echo.

pause 