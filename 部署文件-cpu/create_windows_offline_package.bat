@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: YOLO项目离线安装包制作脚本 (Windows版本)
:: 使用方法：create_offline_package.bat

set PACKAGE_NAME=yolo-windows-x64-offline
for /f "delims=" %%a in ('wmic os get localdatetime /value ^| find "="') do set "%%a"
set CURRENT_DATE=%LocalDateTime:~0,8%
set CURRENT_TIME=%LocalDateTime:~8,6%
set PACKAGE_VERSION=%CURRENT_DATE%_%CURRENT_TIME%
set PACKAGE_DIR=%PACKAGE_NAME%_%PACKAGE_VERSION%

echo === 开始制作YOLO项目离线安装包 ===

:: 创建打包目录
mkdir %PACKAGE_DIR% 2>nul

echo 1. 构建Docker镜像...
:: 构建所有镜像 (强制重新构建以应用依赖修复)
docker-compose build --no-cache

echo 2. 保存Docker镜像...
:: 创建镜像存储目录
mkdir %PACKAGE_DIR%\docker_images 2>nul

:: 获取实际的镜像名称
for /f "tokens=1" %%i in ('docker images --format "table {{.Repository}}" ^| findstr yolo-demo') do (
    echo 保存镜像: %%i
    docker save %%i -o %PACKAGE_DIR%\docker_images\%%i.tar
)

:: 保存基础镜像
echo 保存镜像: postgres:14
docker save postgres:14 -o %PACKAGE_DIR%\docker_images\postgres_14.tar

echo 3. 复制项目文件...
:: 复制必要的配置文件，创建离线版本的docker-compose.yml
copy nginx.conf %PACKAGE_DIR%\ >nul

:: 复制Dockerfile文件
copy Dockerfile.data-server %PACKAGE_DIR%\ >nul
copy Dockerfile.detect-server %PACKAGE_DIR%\ >nul
copy Dockerfile.frontend %PACKAGE_DIR%\ >nul

:: 复制其他配置文件
if exist requirements.base.txt copy requirements.base.txt %PACKAGE_DIR%\ >nul
if exist requirements.data-server.txt copy requirements.data-server.txt %PACKAGE_DIR%\ >nul
if exist requirements.detect-server.txt copy requirements.detect-server.txt %PACKAGE_DIR%\ >nul
if exist pip.conf copy pip.conf %PACKAGE_DIR%\ >nul
if exist base_data_server.py copy base_data_server.py %PACKAGE_DIR%\ >nul
if exist base_detect_server.py copy base_detect_server.py %PACKAGE_DIR%\ >nul

:: 复制目录
if exist models xcopy models %PACKAGE_DIR%\models\ /E /I /Q
if exist storage xcopy storage %PACKAGE_DIR%\storage\ /E /I /Q
if exist uploads xcopy uploads %PACKAGE_DIR%\uploads\ /E /I /Q
if exist src xcopy src %PACKAGE_DIR%\src\ /E /I /Q
if exist api xcopy api %PACKAGE_DIR%\api\ /E /I /Q
if exist yolo-client xcopy yolo-client %PACKAGE_DIR%\yolo-client\ /E /I /Q

echo 4. 创建离线版docker-compose.yml...
:: 创建离线版本的docker-compose.yml，使用镜像而不是构建
(
echo # 离线安装版docker-compose.yml
echo services:
echo   # 数据服务
echo   data-server:
echo     image: yolo-demo-data-server:latest
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
echo.
echo   # 检测服务
echo   detect-server:
echo     image: yolo-demo-detect-server:latest
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
echo.
echo   # 前端
echo   frontend:
echo     image: yolo-demo-frontend:latest
echo     container_name: yolo-frontend
echo     ports:
echo       - "80:80"
echo     depends_on:
echo       - detect-server
echo       - data-server
echo     restart: always
echo     networks:
echo       - yolo-network
echo.
echo   # 数据库
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
echo.
echo networks:
echo   yolo-network:
echo     driver: bridge
echo.
echo volumes:
echo   postgres-data:
echo     driver: local
) > %PACKAGE_DIR%\docker-compose.yml

echo 5. 创建安装脚本...
:: 创建Windows安装脚本
(
echo @echo off
echo chcp 65001 ^>nul
echo.
echo === YOLO项目离线安装脚本 ===
echo.
echo echo 检查Docker环境...
echo docker --version ^>nul 2^>^&1
echo if errorlevel 1 ^(
echo     echo 错误: Docker未安装，请先安装Docker
echo     pause
echo     exit /b 1
echo ^)
echo.
echo docker-compose --version ^>nul 2^>^&1  
echo if errorlevel 1 ^(
echo     echo 错误: Docker Compose未安装，请先安装Docker Compose
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo 1. 加载Docker镜像...
echo for /f "tokens=*" %%%%f in ^('dir /b docker_images\*.tar'^) do ^(
echo     echo 加载镜像: %%%%f
echo     docker load -i docker_images\%%%%f
echo ^)
echo.
echo echo 2. 创建必要目录...
echo mkdir models 2^>nul
echo mkdir storage 2^>nul
echo mkdir uploads 2^>nul
echo.
echo echo 3. 停止现有服务...
echo docker-compose down 2^>nul
echo.
echo echo 4. 启动服务...
echo docker-compose up -d
echo.
echo echo 5. 等待服务启动...
echo timeout /t 15 /nobreak ^>nul
echo.
echo echo === 安装完成! ===
echo echo 前端访问地址: http://localhost
echo echo 检测服务API: http://localhost:8000/docs
echo echo 数据服务API: http://localhost:8001/docs
echo echo.
echo echo 查看服务状态: docker-compose ps
echo echo 查看日志: docker-compose logs -f
echo echo 停止服务: docker-compose down
echo pause
) > %PACKAGE_DIR%\install.bat

echo 6. 创建卸载脚本...
(
echo @echo off
echo chcp 65001 >nul
echo.
echo === YOLO项目卸载脚本 ===
echo.
echo echo 1. 停止并删除容器...
echo docker-compose down -v
echo.
echo echo 2. 删除镜像...
echo docker rmi yolo-demo-data-server yolo-demo-detect-server yolo-demo-frontend postgres:14 2^>nul
echo.
echo echo === 卸载完成! ===
echo pause
) > %PACKAGE_DIR%\uninstall.bat

echo 7. 创建说明文档...
(
echo # YOLO项目离线安装包
echo.
echo ## 系统要求
echo - Docker 20.10+
echo - Docker Compose 1.29+
echo - 可用内存: 4GB+
echo - 可用磁盘: 10GB+
echo.
echo ## 安装步骤
echo.
echo 1. 解压安装包到目标目录
echo 2. 进入解压目录
echo 3. 双击运行 install.bat
echo 4. 等待安装完成
echo.
echo ## 访问地址
echo.
echo - 前端界面: http://localhost
echo - 检测服务API: http://localhost:8000/docs  
echo - 数据服务API: http://localhost:8001/docs
echo.
echo ## 常用命令
echo.
echo ```batch
echo REM 查看服务状态
echo docker-compose ps
echo.
echo REM 查看日志
echo docker-compose logs -f
echo.
echo REM 停止服务
echo docker-compose down
echo.
echo REM 重启服务
echo docker-compose restart
echo.
echo REM 卸载项目
echo uninstall.bat
echo ```
echo.
echo ## 故障排除
echo.
echo 1. 如果端口被占用，请修改docker-compose.yml中的端口映射
echo 2. 如果内存不足，服务可能启动失败，请检查系统资源
echo 3. 如果数据库连接失败，请等待postgres容器完全启动
echo 4. 如果中文显示乱码，请在CMD中执行: chcp 65001
echo.
echo ## 技术支持
echo.
echo 如有问题请查看日志文件: docker-compose logs
) > %PACKAGE_DIR%\README.md

echo 8. 打包压缩...
:: 使用7zip或tar打包（如果可用）
where tar >nul 2>&1
if %errorlevel% == 0 (
    tar -czf %PACKAGE_NAME%_%PACKAGE_VERSION%.tar.gz %PACKAGE_DIR%
) else (
    echo 注意: 请手动压缩 %PACKAGE_DIR% 文件夹
)

echo 9. 清理临时文件...
:: rmdir /s /q %PACKAGE_DIR%

echo.
echo === 离线安装包制作完成! ===
echo 安装包目录: %PACKAGE_DIR%
if exist %PACKAGE_NAME%_%PACKAGE_VERSION%.tar.gz (
    echo 压缩包: %PACKAGE_NAME%_%PACKAGE_VERSION%.tar.gz
)

pause 