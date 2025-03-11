import asyncio
import json
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import base64
from io import BytesIO
from PIL import Image
import time
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor
import torch
import logging
from pathlib import Path
from contextlib import nullcontext
import struct
from typing import Dict
from api.routes import router as api_router

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(api_router, prefix="/api/v1")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
models_cache = {}
frame_queues = {}
max_queue_size = 1  # 减小队列大小以降低延迟
executor = ThreadPoolExecutor(max_workers=2)  # 减少线程数以避免资源竞争
previous_boxes = {}
box_smooth_factor = 0.2  # 减小平滑因子以降低延迟
max_latency = 1000  # 增加最大延迟阈值(ms)，避免跳过太多帧
max_size = 320  # 减小处理尺寸以提高性能

# 添加 WebSocket 连接管理
active_connections: Dict[str, WebSocket] = {}

class FrameProcessor:
    def __init__(self):
        self.processing_times = deque(maxlen=50)  # 存储最近50次处理时间
        self.last_predictions = {}  # 存储每个目标的上一次预测结果
    
    def get_avg_processing_time(self):
        if not self.processing_times:
            return 0
        return sum(self.processing_times) / len(self.processing_times)
    
    def smooth_boxes(self, current_boxes, frame_id):
        """平滑检测框的位置"""
        if frame_id not in previous_boxes:
            previous_boxes[frame_id] = current_boxes
            return current_boxes
        
        smoothed_boxes = []
        prev_boxes = previous_boxes[frame_id]
        
        # 对每个当前检测框
        for curr_box in current_boxes:
            # 在上一帧中找到最匹配的框
            best_match = None
            min_dist = float('inf')
            
            for prev_box in prev_boxes:
                if prev_box["class"] == curr_box["class"]:
                    # 计算框中心点距离
                    curr_center = (curr_box["bbox"][0] + curr_box["bbox"][2]/2,
                                 curr_box["bbox"][1] + curr_box["bbox"][3]/2)
                    prev_center = (prev_box["bbox"][0] + prev_box["bbox"][2]/2,
                                 prev_box["bbox"][1] + prev_box["bbox"][3]/2)
                    
                    dist = ((curr_center[0] - prev_center[0])**2 +
                           (curr_center[1] - prev_center[1])**2)**0.5
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_match = prev_box
            
            # 如果找到匹配的框，进行平滑处理
            if best_match and min_dist < 100:  # 设置最大匹配距离阈值
                smooth_box = {
                    "class": curr_box["class"],
                    "confidence": curr_box["confidence"],
                    "bbox": [
                        best_match["bbox"][0] * box_smooth_factor + curr_box["bbox"][0] * (1 - box_smooth_factor),
                        best_match["bbox"][1] * box_smooth_factor + curr_box["bbox"][1] * (1 - box_smooth_factor),
                        best_match["bbox"][2] * box_smooth_factor + curr_box["bbox"][2] * (1 - box_smooth_factor),
                        best_match["bbox"][3] * box_smooth_factor + curr_box["bbox"][3] * (1 - box_smooth_factor)
                    ]
                }
                smoothed_boxes.append(smooth_box)
            else:
                smoothed_boxes.append(curr_box)
        
        previous_boxes[frame_id] = smoothed_boxes
        return smoothed_boxes

frame_processor = FrameProcessor()

def get_model(models_name):
    """获取或加载YOLO模型"""
    if models_name not in models_cache:
        models_path = f"models/{models_name}.pt"
        try:
            if not Path(models_path).exists():
                logger.error(f"Model file not found: {models_path}")
                return None
            
            model = YOLO(models_path)
            
            # 使用GPU并进行优化
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            if device == 'cuda':
                model.to(device)
                # 使用半精度浮点数以提高性能
                if hasattr(model, 'model'):
                    model.model.half()
                logger.info("Using half precision on GPU")
            
            # 导出ONNX模型以提高性能
            try:
                onnx_path = f"models/{models_name}.onnx"
                if not Path(onnx_path).exists():
                    model.export(format='onnx', dynamic=True, half=True)
                    logger.info(f"Model exported to ONNX: {onnx_path}")
                    
                    # 尝试使用ONNX Runtime
                    import onnxruntime as ort
                    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if device == 'cuda' else ['CPUExecutionProvider']
                    session = ort.InferenceSession(onnx_path, providers=providers)
                    models_cache[models_name] = {
                        'type': 'onnx',
                        'session': session,
                        'model': model
                    }
                    logger.info("Using ONNX Runtime for inference")
                    return models_cache[models_name]
            except Exception as e:
                logger.warning(f"ONNX optimization failed: {e}")
            
            models_cache[models_name] = {
                'type': 'pytorch',
                'model': model
            }
            logger.info(f"Model {models_name} loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Error loading model {models_name}: {e}")
            return None
    return models_cache.get(models_name)

def process_frame(frame, models_info, frame_id, timestamp, total_frames=None, start_time=None):
    """处理单帧图像"""
    start_process_time = time.time()
    
    try:
        # 预处理图像
        orig_h, orig_w = frame.shape[:2]
        scale = min(max_size / orig_h, max_size / orig_w)
        
        if scale < 1:
            new_h, new_w = int(orig_h * scale), int(orig_w * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)  # 使用INTER_AREA以提高性能
        
        # 运行检测
        if models_info['type'] == 'onnx':
            # 使用ONNX Runtime进行推理
            session = models_info['session']
            # 预处理图像
            input_name = session.get_inputs()[0].name
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = frame.transpose(2, 0, 1)
            frame = np.expand_dims(frame, axis=0)
            frame = frame.astype(np.float32) / 255.0
            
            # 运行推理
            outputs = session.run(None, {input_name: frame})
            # 处理输出
            boxes = outputs[0]
            scores = outputs[1]
            classes = outputs[2]
            
            detections = []
            for i in range(len(boxes)):
                if scores[i] > 0.5:
                    box = boxes[i]
                    x1, y1, x2, y2 = box
                    w = x2 - x1
                    h = y2 - y1
                    
                    if scale < 1:
                        x1, x2 = x1 / scale, x2 / scale
                        y1, y2 = y1 / scale, y2 / scale
                        w = w / scale
                        h = h / scale
                    
                    class_id = int(classes[i])
                    class_name = models_info['model'].names[class_id]
                    
                    detections.append({
                        "class": class_name,
                        "confidence": float(scores[i]),
                        "bbox": [float(x1), float(y1), float(w), float(h)],
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2)
                    })
        else:
            # 使用PyTorch模型
            with torch.cuda.amp.autocast() if torch.cuda.is_available() else nullcontext():
                results = models_info['model'](frame, conf=0.5)[0]
            
            detections = []
            for r in results.boxes.data.tolist():
                x1, y1, x2, y2, conf, cls = r
                
                if scale < 1:
                    x1, x2 = x1 / scale, x2 / scale
                    y1, y2 = y1 / scale, y2 / scale
                
                w = x2 - x1
                h = y2 - y1
                
                class_name = results.names[int(cls)]
                
                detections.append({
                    "class": class_name,
                    "confidence": round(conf, 3),
                    "bbox": [float(x1), float(y1), float(w), float(h)],
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2)
                })
        
        # 应用框平滑
        smoothed_detections = frame_processor.smooth_boxes(detections, frame_id)
        
        processing_time = time.time() - start_process_time
        frame_processor.processing_times.append(processing_time)

        # 计算进度和剩余时间
        progress = None
        remaining_time = None
        if total_frames and start_time:
            progress = (frame_id + 1) / total_frames * 100
            elapsed_time = time.time() - start_time
            avg_time_per_frame = elapsed_time / (frame_id + 1)
            remaining_frames = total_frames - (frame_id + 1)
            remaining_time = remaining_frames * avg_time_per_frame
        
        return {
            "type": "detection_result",
            "objects": smoothed_detections,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "processing_time": processing_time,
            "avg_processing_time": frame_processor.get_avg_processing_time(),
            "progress": progress,
            "remaining_time": remaining_time,
            "total_frames": total_frames,
            "image_width": orig_w,
            "image_height": orig_h
        }
    
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return None

def decode_binary_frame(binary_data):
    """解码二进制帧数据"""
    try:
        # 解析头部信息
        header_size = struct.calcsize('!QQII')  # frame_id, timestamp, width, height
        frame_id, timestamp, width, height = struct.unpack('!QQII', binary_data[:header_size])
        
        # 解析图像数据
        image_data = np.frombuffer(binary_data[header_size:], dtype=np.uint8)
        frame = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise ValueError("Failed to decode image data")
        
        return {
            'frame_id': frame_id,
            'timestamp': timestamp,
            'frame': frame
        }
    except Exception as e:
        logger.error(f"Error decoding binary frame: {e}")
        return None

def encode_detection_result(result):
    """将检测结果编码为二进制格式"""
    try:
        # 将结果转换为紧凑的二进制格式
        detections = result['objects']
        frame_id = result['frame_id']
        timestamp = result['timestamp']
        
        # 头部: frame_id, timestamp, number of detections
        header = struct.pack('!QQI', frame_id, int(timestamp), len(detections))
        
        # 检测结果数据
        detection_data = bytearray()
        for det in detections:
            # 每个检测结果: class_id, confidence, x, y, w, h
            class_id = 0  # 这里需要根据实际类别映射设置
            conf = float(det['confidence'])
            x, y, w, h = map(float, det['bbox'])
            detection_data.extend(struct.pack('!IfFFFF', class_id, conf, x, y, w, h))
        
        return header + detection_data
    except Exception as e:
        logger.error(f"Error encoding detection result: {e}")
        return None

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(id(websocket))
        self.active_connections[connection_id] = websocket
        return connection_id

    async def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            del self.active_connections[connection_id]
            try:
                await websocket.close()
            except Exception:
                pass

        # 取消并清理相关任务
        if connection_id in self.connection_tasks:
            task = self.connection_tasks[connection_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.connection_tasks[connection_id]

    async def send_json(self, connection_id: str, message: dict):
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await self.disconnect(connection_id)

# 创建连接管理器实例
manager = ConnectionManager()


async def process_frame_queue(connection_id: str):
    """异步处理帧队列"""
    queue = frame_queues.get(connection_id)
    if not queue:
        return
        
    last_processed_time = 0
    skip_count = 0
    
    try:
        while connection_id in frame_queues and connection_id in manager.active_connections:
            try:
                if queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                
                current_time = time.time()
                
                # 智能帧选择
                if queue.qsize() > 1:
                    while queue.qsize() > 1:
                        queue.get_nowait()
                        skip_count += 1
                    
                    if skip_count >= 10:
                        logger.info(f"Skipped {skip_count} frames for client {connection_id} to reduce latency")
                        skip_count = 0
                
                frame_data = queue.get_nowait()
                
                # 检查延迟
                latency = (current_time - frame_data["timestamp"]/1000) * 1000
                if latency > max_latency:
                    logger.debug(f"Dropping frame {frame_data['frame_id']} for client {connection_id} due to high latency: {latency:.0f}ms")
                    continue
                
                # 控制处理频率
                if current_time - last_processed_time < 0.033:
                    continue
                
                result = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    process_frame,
                    frame_data["frame"],
                    frame_data["model"],
                    frame_data["frame_id"],
                    frame_data["timestamp"],
                    frame_data.get("total_frames"),
                    frame_data.get("start_time")
                )
                
                if result:
                    await manager.send_json(connection_id, result)
                    last_processed_time = current_time
            
            except Exception as e:
                logger.error(f"Error in frame queue processing for client {connection_id}: {e}")
                await asyncio.sleep(0.1)
    
    except asyncio.CancelledError:
        logger.info(f"Frame queue processing cancelled for client {connection_id}")
    except Exception as e:
        logger.error(f"Unexpected error in frame queue processing for client {connection_id}: {e}")
    finally:
        logger.info(f"Frame queue processing ended for client {connection_id}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    models_info = None
    
    try:
        # 等待客户端的连接请求
        while True:
            message = await websocket.receive_json()
            
            if message["type"] == "connect":
                # 发送连接确认
                await websocket.send_json({
                    "type": "connect_confirm"
                })
                logger.info(f"Client {connection_id} connected")
                continue
                
            elif message["type"] == "config":
                # 处理模型配置
                models_name = message.get("models_name")
                if not models_name:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No model specified in configuration"
                    })
                    continue

                try:
                    logger.info(f"Loading model {models_name} for client {connection_id}")
                    models_info = get_model(message.get("models_id"))
                    
                    if not models_info:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Failed to load model: {models_name}"
                        })
                        continue
                                        
                    # 发送配置确认
                    await websocket.send_json({
                        "type": "config_confirm",
                        "model": models_name
                    })
                    logger.info(f"Model {models_name} configured successfully for client {connection_id}")
                
                except Exception as e:
                    error_msg = f"Error configuring model {models_name}: {str(e)}"
                    logger.error(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                continue
                
            elif message["type"] == "video_info":
                # 处理视频信息
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                                        
                frame_queues[connection_id] = asyncio.Queue(maxsize=max_queue_size)
                logger.info(f"Video info received from client {connection_id}")
                
                # 启动帧处理任务
                task = asyncio.create_task(process_frame_queue(connection_id))
                manager.connection_tasks[connection_id] = task
                
            elif message["type"] == "frame":
                # 处理视频帧
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                                        
                try:
                    frame_data = message.get("frame")
                    frame_id = message.get("frame_id", 0)
                    current_time = time.time()
                    
                    # 检查帧延迟
                    frame_timestamp = message.get("timestamp", current_time)
                    latency = (current_time - frame_timestamp) * 1000
                    
                    if latency > max_latency:
                        logger.debug(f"Skipping frame {frame_id} for client {connection_id} due to high latency: {latency:.0f}ms")
                        continue
                    
                    if not frame_data:
                        continue
                                        
                    # 解码图像
                    img_data = base64.b64decode(frame_data)
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        raise ValueError("Failed to decode image")
                    
                    # 将帧数据放入队列
                    results =await frame_queues[connection_id].put({
                        "frame": frame,
                        "model": models_info,
                        "frame_id": frame_id,
                        "timestamp": frame_timestamp,
                        "total_frames": message.get("total_frames"),
                        "start_time": message.get("start_time")
                    })
                    if results:
                        # 添加延迟信息到结果中
                        results["latency"] = latency
                        await websocket.send_json(results)
                    
                except Exception as e:
                    logger.error(f"Error processing frame: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to process frame: {str(e)}"
                    })
            
            elif message["type"] == "stop":
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {connection_id}: {str(e)}")
    finally:
        await manager.disconnect(connection_id)

@app.get("/")
async def root():
    return {"message": "YOLO Detection Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8765, reload=True)