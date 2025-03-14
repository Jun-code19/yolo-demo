# YOLO Detection Server

这是一个基于 FastAPI 和 WebSocket 的实时目标检测服务器，支持使用 YOLO 模型进行实时视频流检测。

## 功能特点

- 支持实时视频流处理
- 支持多种 YOLO 模型（YOLOv11）
- WebSocket 通信，低延迟
- 自动模型缓存
- 支持跨域请求
- 实时目标检测和边界框绘制

## 环境要求

- Python 3.8+
- CUDA 支持（推荐，用于GPU加速）

## 安装步骤

1. 克隆仓库：
```bash
git clone <repository-url>
cd yolo-detection-server
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 下载 YOLO 模型：
将下载的 YOLO 模型文件（.pt）放在 `models` 目录下。
支持的模型：
- YOLO11n.pt
- YOLO11s.pt

## 运行服务器

```bash
python server.py
```

服务器将在 http://localhost:8765 上运行。

## WebSocket API

连接地址：`ws://localhost:8765/ws`

### 发送帧数据格式：
```json
{
    "type": "frame",
    "model": "yolo11n",
    "data": "base64_encoded_image"
}
```

### 接收检测结果格式：
```json
{
    "objects": [
        {
            "class": "person",
            "confidence": 0.95,
            "bbox": [x, y, width, height]
        }
    ]
}
```

## 注意事项

1. 确保模型文件放在正确的位置
2. 在生产环境中配置适当的 CORS 策略
3. 根据服务器性能调整帧率和图像质量
4. 使用 GPU 可以显著提升检测性能

## 许可证

MIT License 