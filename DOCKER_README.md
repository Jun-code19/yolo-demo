# YOLO服务Docker部署指南

## 概述

本项目包含三个后端服务和一个前端应用:

1. **数据服务** - 处理基础数据操作
2. **RTSP服务** - 处理视频流
3. **检测服务** - 执行YOLO目标检测
4. **前端应用** - 用户交互界面

## 准备工作

### 安装Docker和Docker Compose

确保已安装Docker和Docker Compose:

- [Docker安装指南](https://docs.docker.com/get-docker/)
- [Docker Compose安装指南](https://docs.docker.com/compose/install/)

### NVIDIA GPU支持（推荐）

如果需要GPU加速，请安装NVIDIA Container Toolkit:

```bash
# 添加NVIDIA软件包存储库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 安装NVIDIA Container Toolkit
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 重启Docker服务
sudo systemctl restart docker
```

## 部署步骤

### 1. 克隆仓库

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. 准备模型文件

将YOLO模型文件放入`models`目录:

```bash
mkdir -p models
# 复制您的.pt格式模型文件到models目录
```

### 3. 构建并启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看容器状态
docker-compose ps

# 查看服务日志
docker-compose logs -f
```

### 4. 访问服务

- 前端应用: http://localhost
- 检测服务API: http://localhost/api/
- 数据服务API: http://localhost/api/v1/
- RTSP服务: http://localhost/rtsp/

## 管理容器

```bash
# 停止所有服务
docker-compose down

# 重新构建并启动服务
docker-compose up -d --build

# 重启特定服务
docker-compose restart <service-name>
```

## 配置

环境变量可在`docker-compose.yml`文件中修改:

- 数据库连接字符串
- 端口映射
- 存储路径等

## 故障排除

### 1. 检查容器状态和日志

```bash
# 查看容器状态
docker-compose ps

# 查看特定服务的日志
docker-compose logs -f <service-name>
```

### 2. 容器内调试

```bash
# 进入容器内部
docker-compose exec <service-name> bash
```

### 3. 常见问题

- **数据库连接失败**: 确保数据库容器正常运行，检查连接字符串
- **GPU不可用**: 检查NVIDIA驱动和容器工具包安装
- **端口冲突**: 修改`docker-compose.yml`中的端口映射 