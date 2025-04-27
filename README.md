YOLO 目标检测系统 - 说明文档与使用指南
一、项目概述
本系统是一个基于YOLO的实时目标检测平台，采用前后端分离架构，支持多设备管理、多模型检测、事件记录和第三方数据推送。系统具有高可扩展性，支持多种检测场景和数据流转方案。
主要特性
多模型支持：集成YOLO系列模型，支持物体检测、姿态识别等多种检测任务
实时监控：通过RTSP协议接入摄像头，提供低延迟视频流分析
区域检测：支持拌线、区域等多种检测区域定义
事件记录：检测结果自动记录并提供查询功能
数据推送：支持HTTP/HTTPS、TCP、MQTT多种推送方式
可视化界面：直观的Web界面，便于配置和管理
对象追踪：支持目标追踪功能，可记录目标运动轨迹
二、系统架构
技术栈
后端：Python、FastAPI、SQLAlchemy、OpenCV、YOLO
前端：Vue.js、Element Plus
数据库：PostgreSQL
通信：WebSocket、HTTP/HTTPS、TCP、MQTT
核心模块
检测服务：负责与摄像机连接并进行实时图像分析
数据推送：将检测结果推送至第三方系统
设备管理：管理连接的摄像设备
模型管理：管理和配置检测模型
事件记录：存储和查询检测事件
用户界面：提供可视化操作界面
三、使用说明
1. 系统要求
Python 3.8+
CUDA支持的NVIDIA显卡(推荐用于性能优化)
PostgreSQL数据库
网络摄像机(支持RTSP协议)
2. 安装步骤
克隆代码库
Apply to README.md
Run
安装后端依赖
Apply to README.md
Run
安装前端依赖
Apply to README.md
Run
配置数据库
修改models/database.py中的数据库连接信息：
Apply to README.md
初始化数据库
Apply to README.md
Run
3. 启动系统
启动后端服务
Apply to README.md
Run
启动前端服务(开发模式)
Apply to README.md
Run
4. 使用流程
设备管理
添加摄像设备，配置IP、端口、用户名和密码
测试连接以确保设备可访问
模型管理
上传YOLO模型文件
配置模型参数和类别信息
检测配置
创建检测配置，关联设备和模型
设置检测参数（灵敏度、目标类别等）
可选：配置检测区域或拌线
启动检测
在实时检测页面启动检测任务
查看实时检测结果
数据推送
创建推送配置，选择推送方式（HTTP/HTTPS、TCP、MQTT）
配置目标地址、认证信息等
通过标签关联数据源
查看事件
在检测事件页面查看和管理历史事件
对事件进行筛选、标记和导出
四、数据推送配置
支持的推送方式
HTTP/HTTPS
配置目标URL和请求方法
支持自定义请求头
数据以JSON格式推送
TCP
配置目标主机和端口
数据以JSON格式推送，每条消息以换行符分隔
MQTT
配置代理服务器、端口和主题
支持用户名/密码认证和TLS加密
数据以JSON格式推送
标签系统
使用标签系统灵活关联推送配置与数据源：
detection: 关联所有检测结果
device_xxx: 关联特定设备的数据
alarm: 关联报警事件
自定义标签：可根据需求自定义其他标签
五、打包发布准备
后端打包
使用PyInstaller打包
Apply to README.md
Run
Docker容器化
创建Dockerfile：
Apply to README.md
构建和运行：
Apply to README.md
Run
前端打包
构建生产版本
Apply to README.md
Run
配置Nginx
Apply to README.md
数据库迁移
创建迁移脚本
Apply to README.md
Run
应用迁移
Apply to README.md
Run
环境变量配置
创建.env文件：
Apply to README.md
六、常见问题与排错
推送服务未启动
检查数据库中是否有启用的推送配置
确认startup_push_service函数正常执行
查看服务日志确认推送器状态
检测性能问题
检查GPU是否正常工作
调整帧率和检测间隔
考虑降低视频分辨率
摄像机连接失败
验证网络连接和摄像机状态
确认RTSP URL格式正确
检查用户名和密码是否正确
数据库连接问题
确认PostgreSQL服务正在运行
验证数据库连接字符串
检查数据库用户权限
七、API文档
完整API文档可通过以下URL访问：
Apply to README.md
主要API端点包括：
/api/detection/{config_id}/start - 启动检测任务
/api/detection/{config_id}/stop - 停止检测任务
/api/detection/status - 获取检测状态
/api/push/list - 获取推送配置列表
/api/push/create - 创建推送配置
/ws/detection/preview/{config_id} - WebSocket实时预览
通过这份文档，您应该能够理解系统架构、完成安装部署、使用核心功能并准备系统发布。如有其他问题，请参考项目代码或联系开发团队。

## 人群分析模块重构说明

人群分析模块已进行重构，主要变更如下：

1. **模块化改进**：
   - 将YOLO模型加载和摄像头访问功能封装为独立方法
   - 拆分人员检测逻辑，减少与实时检测模块的耦合

2. **服务生命周期优化**：
   - 优化了应用启动和关闭流程，确保服务按照正确顺序启动和关闭
   - 增强了异常处理和错误恢复能力

3. **API改进**：
   - 增强了设备验证逻辑
   - 添加了更完善的错误处理和状态反馈
   - 改进了获取可用设备的接口，确保只返回有检测配置的设备

4. **功能扩展**：
   - 支持热力图生成
   - 支持人数预警
   - 支持多种时间调度方式(间隔和Cron表达式)

### 使用说明

人群分析模块通过API进行管理，主要接口如下：

- `POST /api/v2/crowd-analysis/jobs`: 创建人群分析任务
- `GET /api/v2/crowd-analysis/jobs`: 获取所有人群分析任务
- `GET /api/v2/crowd-analysis/jobs/{job_id}`: 获取特定任务详情
- `DELETE /api/v2/crowd-analysis/jobs/{job_id}`: 删除分析任务
- `POST /api/v2/crowd-analysis/jobs/{job_id}/run`: 立即执行分析任务
- `GET /api/v2/crowd-analysis/available-devices`: 获取可用于人群分析的设备列表
- `POST /api/v2/crowd-analysis/jobs/{job_id}/pause`: 暂停分析任务
- `POST /api/v2/crowd-analysis/jobs/{job_id}/resume`: 恢复分析任务