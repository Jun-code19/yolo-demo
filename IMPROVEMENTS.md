# 项目改进清单

## 后端改进

### 1. API增强
- 实现了完整的设备信息更新API (`PUT /devices/{device_id}`)，支持更新设备的所有属性
- 添加了用户认证与授权机制，使用JWT实现
- 添加了登录和获取当前用户信息API
- 处理了IPv4Address类型的转换问题

### 2. 安全性提升
- 添加了JWT认证保护API接口
- 使用了密码哈希存储，增强了安全性
- 添加了基于角色的权限控制
- 增加了数据验证和错误处理

### 3. 系统功能增强
- 添加了操作日志记录系统，记录用户关键行为
- 添加了数据库迁移支持（Alembic）

## 前端改进

### 1. 认证系统
- 添加了JWT认证机制
- 更新了登录界面
- 使用localStorage存储token和用户信息

### 2. API交互优化
- 创建了统一的API服务
- 添加了请求拦截器，自动附加认证token
- 更好的错误处理和用户反馈

### 3. 功能增强
- 更新了设备管理页面，支持完整的设备信息编辑
- 添加了系统日志查看页面
- 改进了路由配置

## 依赖管理
- 更新了后端依赖，添加了认证相关包
- 添加了数据库迁移工具

## 使用说明

### 首次设置
1. 安装后端依赖: `pip install -r requirements.txt`
2. 初始化数据库迁移: `alembic init migrations`
3. 生成迁移脚本: `alembic revision --autogenerate -m "初始迁移"`
4. 应用迁移: `alembic upgrade head`
5. 启动后端服务: `python main.py`
6. 前端安装依赖: `cd yolo-client && npm install`
7. 启动前端服务: `cd yolo-client && npm run dev`

### 访问系统
- 前端: `http://localhost:5173`
- 后端API文档: `http://localhost:8000/docs`

### 认证流程
1. 访问登录页面: `http://localhost:5173/login`
2. 使用用户名和密码登录
3. 登录成功后，系统会自动存储token和用户信息
4. 后续请求会自动附加认证token

### 默认管理员
- 用户名: admin
- 密码: admin123

## 未来改进计划
1. 添加设备状态实时监控
2. 实现视频流预览功能
3. 增加更多的数据可视化组件
4. 实现用户管理模块
5. 添加导出报表功能

## 摄像头设备检测系统需求分析

### 核心需求概述

您描述的是一个智能视频监控系统，具有以下主要功能：

1. **设备-模型绑定**：摄像头可以绑定特定的检测模型
2. **检测控制**：可开启/关闭特定设备的检测功能
3. **自动后台检测**：系统根据绑定模型自动进行目标检测
4. **事件触发存储**：检测到特定目标时保存证据（截图/短视频）
5. **历史记录查询**：前端查看摄像头的历史检测记录

### 系统架构设计

基于您的需求，系统应该包含以下组件：

#### 1. 数据库设计

需要设计以下数据表：

设备表 (Device)：
- device_id (主键)
- device_name
- device_type
- ip_address
- port
- username 
- password
- status
- 其他设备属性...

检测配置表 (DetectionConfig)：
- config_id (主键)
- device_id (外键关联设备表)
- model_id (外键关联模型表)
- enabled (检测开关状态)
- sensitivity (灵敏度)
- target_classes (要检测的目标类别，如"person,car")
- schedule (检测计划，如工作时间或全天)
- save_mode (存储模式：截图/视频片段)
- save_duration (若为视频片段，保存的时长)
- created_at
- updated_at

检测记录表 (DetectionEvent)：
- event_id (主键)
- device_id (外键关联设备表)
- config_id (外键关联配置表)
- timestamp (事件发生时间)
- event_type (检测到的对象类型)
- confidence (置信度)
- snippet_path (截图或视频片段路径)
- metadata (额外元数据，如边界框坐标等)
- thumbnail_path (缩略图路径)
- status (是否已查看/处理)

#### 2. 后端服务组件

您需要新增或扩展以下服务：

##### a. 检测配置管理服务
- 创建/编辑/删除检测配置
- 设备与模型的绑定关系管理
- 检测开关控制

##### b. 检测调度器
- 自动调度检测任务
- 根据配置的时间表启动/停止检测
- 资源管理（如GPU分配）

##### c. 检测工作器
- 连接RTSP流
- 应用绑定的模型进行检测
- 基于配置的目标类别过滤检测结果

##### d. 事件处理器
- 检测到目标时触发事件
- 截图或录制视频片段
- 保存事件记录到数据库
- 可选：发送通知

##### e. 存储管理器
- 管理检测证据（图片/视频）的存储
- 实现存储策略（如循环覆盖旧文件）
- 分类组织存储的文件

##### f. 历史记录API
- 查询特定设备的检测历史
- 提供筛选、排序、分页功能
- 支持检测事件回放

#### 3. 前端界面

新增以下界面：

##### a. 检测配置界面
```
- 设备列表视图
- 模型绑定设置表单
- 检测参数配置（类别、灵敏度等）
- 检测时间表设置
- 存储设置（截图/视频）
```

##### b. 实时监控界面
```
- 摄像头预览带检测结果叠加
- 检测状态指示器
- 手动启停检测的控制
```

##### c. 历史记录查询界面
```
- 按设备、时间、检测类型筛选
- 事件列表视图（缩略图+时间+类型）
- 事件详情视图（大图/视频+元数据）
- 导出/分享功能
```

### 技术实现要点

#### 1. 检测服务优化

需要重构当前的检测服务，使其能够：

- 支持多路RTSP流并行处理
- 高效地调度有限的GPU资源
- 实现基于模型和配置的动态检测

关键代码框架：
```python
class DetectionWorker:
    def __init__(self, config_id):
        self.config = self.load_config(config_id)
        self.device = self.get_device_info(self.config.device_id)
        self.model = self.load_model(self.config.model_id)
        self.target_classes = self.config.target_classes.split(',')
        self.stream = None
        self.running = False
        
    async def start(self):
        self.running = True
        self.stream = await self.connect_rtsp(
            self.device.ip_address, 
            self.device.port,
            self.device.username,
            self.device.password
        )
        await self.detection_loop()
        
    async def detection_loop(self):
        while self.running and self.stream:
            frame = await self.get_frame()
            if frame is None:
                continue
                
            # 执行检测
            results = self.model.detect(frame)
            
            # 过滤目标类别
            filtered_results = [r for r in results 
                               if r['class'] in self.target_classes]
            
            # 检查是否需要保存
            if filtered_results:
                await self.save_detection_event(frame, filtered_results)
```

#### 2. 存储管理

实现智能的存储管理，避免磁盘空间溢出：

```python
class StorageManager:
    def __init__(self, base_path, max_storage_gb=100):
        self.base_path = base_path
        self.max_bytes = max_storage_gb * 1024**3
        
    async def save_event(self, device_id, event_type, frame, metadata):
        # 创建事件存储路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_path = f"{device_id}/{event_type}/{timestamp}"
        abs_path = os.path.join(self.base_path, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        # 保存图像和元数据
        image_path = f"{abs_path}.jpg"
        meta_path = f"{abs_path}.json"
        
        cv2.imwrite(image_path, frame)
        with open(meta_path, 'w') as f:
            json.dump(metadata, f)
            
        # 检查存储限制
        await self.check_storage_limits(device_id)
        
        return rel_path
        
    async def check_storage_limits(self, device_id):
        # 如果超出存储限制，删除最旧的事件
        device_path = os.path.join(self.base_path, device_id)
        if not os.path.exists(device_path):
            return
            
        total_size = self.get_directory_size(device_path)
        if total_size > self.max_bytes:
            # 删除旧文件直到低于限制
            await self.cleanup_old_events(device_path)
```

#### 3. API设计

需要新增以下API端点：

```
设备配置API:
- POST /api/device/{device_id}/detection/config - 创建或更新检测配置
- GET /api/device/{device_id}/detection/config - 获取检测配置
- PUT /api/device/{device_id}/detection/enable - 启用检测
- PUT /api/device/{device_id}/detection/disable - 禁用检测

检测记录API:
- GET /api/device/{device_id}/events - 获取检测事件列表
- GET /api/events/{event_id} - 获取单个事件详情
- GET /api/events/{event_id}/image - 获取事件截图
- GET /api/events/{event_id}/video - 获取事件视频(如适用)

统计分析API:
- GET /api/device/{device_id}/stats - 获取设备检测统计
- GET /api/stats/summary - 获取系统级检测统计
```

### 实现挑战与解决方案

#### 1. 性能与资源管理

**挑战**: 多路视频流的同时处理会带来大量计算和内存压力。

**解决方案**:
- 实现视频帧缓冲池和处理队列
- 低优先级设备降低处理帧率
- 考虑使用边缘计算设备分担检测负载
- 实施资源动态分配算法

#### 2. 存储管理

**挑战**: 长期运行会产生大量数据，可能导致存储溢出。

**解决方案**:
- 实现分层存储策略（热数据在SSD，冷数据在HDD）
- 自动存档和清理机制
- 实现基于重要性的存储优先级（保留高置信度事件）

#### 3. 可靠性保障

**挑战**: 需要确保检测服务的稳定性和连续性。

**解决方案**:
- 实现心跳监测和自动恢复机制
- 关键事件的多重存储
- 服务状态监控和告警系统

### 前端界面设计建议

#### 1. 检测配置界面

![检测配置界面示意图](未包含，但应当展示设备列表、模型选择和检测参数配置)

主要功能:
- 设备选择
- 模型选择下拉框
- 目标类别多选框
- 灵敏度滑块
- 检测计划时间表
- 存储选项配置

#### 2. 历史记录查询界面

主要组件:
- 筛选区域(日期选择器、设备选择器、类型过滤器)
- 事件卡片网格或时间轴视图
- 预览缩略图
- 事件详情侧边栏或弹窗
- 导出和分享功能

### 数据流程图

```
[摄像头设备] → RTSP流 → [检测工作器] → 检测结果 → [事件处理器] 
                                           ↓
[前端界面] ← [历史记录API] ← [数据库] ← [存储管理器]
```

### 下一步实施计划

1. 扩展数据库模型，添加所需表结构
2. 开发检测配置管理服务
3. 实现检测调度器和工作器
4. 开发存储管理器
5. 实现历史记录API
6. 设计和开发前端界面
7. 测试和优化系统性能
8. 部署和监控系统运行

这套系统实现后，将能够为您提供一个智能、自动化的视频监控解决方案，根据预设配置自动检测特定目标并保存证据，同时提供便捷的历史记录查询功能。 