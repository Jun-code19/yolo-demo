from fastapi import APIRouter, WebSocket,WebSocketDisconnect # 导入FastAPI相关模块
from typing import Dict, Tuple # 导入字典类型和元组类型
import cv2 # 导入OpenCV模块
import base64 # 导入base64编码
import time # 导入时间模块
import threading # 导入线程模块
import asyncio # 导入异步I/O模块
from concurrent.futures import ThreadPoolExecutor # 导入线程池
import logging # 导入日志模块
import numpy as np # 导入NumPy模块
from collections import deque # 导入双端队列
from ultralytics import YOLO # 导入YOLO模型
import torch # 导入PyTorch
from contextlib import nullcontext # 导入上下文管理器
from pathlib import Path # 导入路径模块
import os # 导入操作系统模块
import re # 导入正则表达式模块
from urllib.parse import urlparse # 导入URL解析模块

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建API路由
router = APIRouter(prefix="/rtsp", tags=["RTSP流处理"])

# 全局变量
models_cache = {} # 模型缓存
frame_queues = {} # 帧队列
max_queue_size = 1  # 减小队列大小以降低延迟
executor = ThreadPoolExecutor(max_workers=2)  # 减少线程数以避免资源竞争
previous_boxes = {} # 前一帧的检测框
box_smooth_factor = 0.2  # 减小平滑因子以降低延迟
max_latency = 1000  # 增加最大延迟阈值(ms)，避免跳过太多帧
max_size = 320  # 减小处理尺寸以提高性能

# 添加 WebSocket 连接管理
active_connections: Dict[str, WebSocket] = {}
rtsp_sessions: Dict[str, dict] = {}

def extract_ip_and_channel_from_rtsp_url(rtsp_url: str) -> Tuple[str, str]:
    """从RTSP URL中提取IP地址和通道号"""
    try:
        ip_address = "unknown_device"
        channel = "1"  # 默认通道号
        
        # 使用正则表达式匹配IP地址
        # rtsp://username:password@ip:port/path 格式
        ip_pattern = r'@(\d+\.\d+\.\d+\.\d+):'
        match = re.search(ip_pattern, rtsp_url)
        if match:
            ip_address = match.group(1)
        else:
            # 备用方法：使用urlparse
            parsed_url = urlparse(rtsp_url)
            if parsed_url.hostname:
                # 检查是否是IP地址格式
                ip_regex = r'^\d+\.\d+\.\d+\.\d+$'
                if re.match(ip_regex, parsed_url.hostname):
                    ip_address = parsed_url.hostname
        
        # 提取通道号
        # 匹配 channel=数字 格式
        channel_pattern = r'channel=(\d+)'
        channel_match = re.search(channel_pattern, rtsp_url)
        if channel_match:
            channel = channel_match.group(1)
        
        if ip_address == "unknown_device":
            logger.warning(f"无法从RTSP URL中提取IP地址: {rtsp_url}")
        
        return ip_address, channel
    except Exception as e:
        logger.error(f"提取IP地址和通道号时出错: {e}")
        return "unknown_device", "1"

def ensure_storage_directory():
    """确保storage/devices目录存在"""
    storage_dir = Path("storage/devices")
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir
    except Exception as e:
        logger.error(f"创建storage/devices目录失败: {e}")
        return None

def save_device_snapshot(frame, ip_address: str, channel: str = "1"):
    """保存设备快照图片"""
    try:
        storage_dir = ensure_storage_directory()
        if storage_dir is None:
            return False
        
        # 使用IP地址和通道号组成文件名
        filename = f"{ip_address}_ch{channel}.jpg"
        filepath = storage_dir / filename
        
        # 保存图片，使用高质量JPEG压缩
        success = cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        if success:
            logger.info(f"设备快照已保存: {filepath}")
            return True
        else:
            logger.error(f"保存设备快照失败: {filepath}")
            return False
    except Exception as e:
        logger.error(f"保存设备快照时出错: {e}")
        return False

class RTSPManager:
    """管理RTSP流的类"""
    
    def __init__(self):
        self.active_streams = {}
        self.stop_events = {}
        self.frame_buffers = {}
        self.frame_ready_events = {}
        self.thread_executors = ThreadPoolExecutor(max_workers=4)  # 专用于RTSP的线程池
        self.stream_status = {}  # 用于线程和异步任务间通信
        self.stream_urls = {}  # 存储连接ID对应的流URL
    
    async def start_stream(self, connection_id: str, stream_url: str) -> bool:
        """启动RTSP流处理"""
        if connection_id in self.active_streams:
            return False
        
        # 设置停止事件和帧缓冲
        stop_event = threading.Event()
        self.stop_events[connection_id] = stop_event
        self.frame_buffers[connection_id] = deque(maxlen=5)  # 存储最多5帧
        self.stream_status[connection_id] = {"status": "connecting", "info": None, "error": None}
        self.stream_urls[connection_id] = stream_url  # 存储流URL
        
        # 在单独的线程中运行RTSP捕获
        self.thread_executors.submit(
            self._capture_rtsp_frames,
            connection_id,
            stream_url,
            stop_event
        )
        
        # 创建异步任务处理流
        task = asyncio.create_task(
            self._process_frames_async(connection_id)
        )
        self.active_streams[connection_id] = task
        
        return True
    
    async def stop_stream(self, connection_id: str) -> bool:
        """停止RTSP流处理"""
        if connection_id not in self.active_streams:
            return False
        
        # 设置停止事件
        if connection_id in self.stop_events:
            self.stop_events[connection_id].set()
        
        # 等待任务结束
        task = self.active_streams[connection_id]
        if not task.done():
            await asyncio.wait([task], timeout=5)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 清理资源
        self.active_streams.pop(connection_id, None)
        self.stop_events.pop(connection_id, None)
        if connection_id in self.frame_buffers:
            self.frame_buffers.pop(connection_id)
        if connection_id in self.stream_status:
            self.stream_status.pop(connection_id)
        if connection_id in self.stream_urls:
            self.stream_urls.pop(connection_id)
        
        return True
    
    def _capture_rtsp_frames(self, connection_id: str, stream_url: str, stop_event):
        """在单独的线程中从RTSP流捕获帧"""
        frame_count = 0
        frame_buffer = self.frame_buffers.get(connection_id)
        skip_frame_count = 0
        
        try:
            # 尝试从RTSP连接视频源
            try:
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 设置缓冲区大小为1，减少延迟

                if not cap.isOpened():                   
                    return False
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        
                if connection_id in self.stream_status:
                    self.stream_status[connection_id] = {
                        "status": "connected",
                        "info": {
                            "width": width,
                            "height": height,
                            "fps": float(fps) if fps else 30.0
                        },
                        "error": None
                    }
                
                target_fps = min(30, fps if fps else 30)
                frame_interval = 1.0 / target_fps
                
                last_frame_time = time.time()
                
                # 循环处理视频帧
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    if stop_event.is_set():
                        break
                    
                    current_time = time.time()
                    elapsed = current_time - last_frame_time
                    
                    # 控制帧率，避免缓冲区溢出
                    if elapsed < frame_interval * 0.5:  # 如果时间间隔过短，跳过该帧
                        skip_frame_count += 1
                        if skip_frame_count % 30 == 0:
                            logger.debug(f"跳过帧以控制帧率，已跳过: {skip_frame_count}")
                        continue
                    
                    # 将PyAV帧转换为OpenCV格式
                    # img = frame.to_ndarray(format='bgr24')
                    img = frame
                    # 添加帧信息
                    frame_data = {
                        "frame": img,
                        "frame_id": frame_count,
                        "timestamp": current_time,
                        "width": img.shape[1],
                        "height": img.shape[0]
                    }
                    
                    # 将帧放入共享缓冲区
                    if frame_buffer is not None:
                        if len(frame_buffer) >= frame_buffer.maxlen:
                            frame_buffer.popleft()  # 移除最老的帧，避免延迟累积
                        frame_buffer.append(frame_data)
                    
                    frame_count += 1
                    last_frame_time = current_time
                    
                    # 避免CPU占用过高
                    time.sleep(0.001)
                
                # logger.info(f"RTSP捕获完成，共捕获 {frame_count} 帧，跳过 {skip_frame_count} 帧")
                
            except Exception as e:
                logger.error(f"无法打开RTSP流: {e}")
                # 设置错误状态
                if connection_id in self.stream_status:
                    self.stream_status[connection_id] = {
                        "status": "error", 
                        "error": f"无法连接到RTSP流: {str(e)}"
                    }
                return
                
        except Exception as e:
            # 设置错误状态
            if connection_id in self.stream_status:
                self.stream_status[connection_id] = {
                    "status": "error", 
                    "error": f"视频流处理错误: {str(e)}"
                }
        finally:
            # 关闭容器
            try:
                if 'cap' in locals():
                    cap.release()
            except Exception as e:
                logger.error(f"关闭RTSP容器时发生错误: {e}")
    
    async def _process_frames_async(self, connection_id: str):
        """异步处理并发送捕获的帧"""
        frame_buffer = self.frame_buffers.get(connection_id)
        stop_event = self.stop_events.get(connection_id)
        last_send_time = time.time()
        send_interval = 1.0 / 30.0  # 控制发送帧率，最高30fps
        processed_frames = 0
        
        # 通知参数
        stream_notified = False
        retry_count = 0
        max_retry = 50  # 最多等待5秒
        
        try:
            # 等待RTSP连接成功或失败
            while retry_count < max_retry:
                if connection_id in self.stream_status:
                    status = self.stream_status[connection_id]
                    
                    # 检查是否有错误
                    if status.get("status") == "error":
                        websocket = active_connections.get(connection_id)
                        if websocket:
                            await websocket.send_json({
                                "type": "error",
                                "message": status.get("error", "未知错误")
                            })
                        return
                    
                    # 检查是否已连接
                    if status.get("status") == "connected" and status.get("info"):
                        websocket = active_connections.get(connection_id)
                        if websocket:
                            # 发送流信息
                            await websocket.send_json({
                                "type": "stream_info",
                                "width": status["info"].get("width"),
                                "height": status["info"].get("height"),
                                "fps": status["info"].get("fps")
                            })
                            
                            # 发送预览开始通知
                            await websocket.send_json({
                                "type": "preview_start",
                                "width": status["info"].get("width"),
                                "height": status["info"].get("height")
                            })
                            stream_notified = True
                        break
                
                retry_count += 1
                await asyncio.sleep(0.1)
            
            # 主循环处理帧
            while not stop_event.is_set():
                # 检查是否有新帧
                if frame_buffer and len(frame_buffer) > 0:
                    # 获取最新的帧
                    frame_data = frame_buffer[-1]  # 总是处理最新的帧
                    img = frame_data["frame"]
                    frame_id = frame_data["frame_id"]
                    
                    current_time = time.time()
                    elapsed = current_time - last_send_time
                    
                    # 控制发送频率
                    if elapsed >= send_interval:
                        # 处理图像质量
                        try:
                            # 原始分辨率
                            orig_h, orig_w = img.shape[:2]
                            
                            # 调整尺寸（可选，保持高质量）
                            max_dim = 1920  # 增加到1920以提高质量
                            resized = False
                            processed_img = img
                            
                            if max(orig_h, orig_w) > max_dim:
                                scale = max_dim / max(orig_h, orig_w)
                                new_width = int(orig_w * scale)
                                new_height = int(orig_h * scale)
                                processed_img = cv2.resize(img, (new_width, new_height), 
                                                         interpolation=cv2.INTER_AREA)
                                resized = True
                                
                            # 使用更高的JPEG质量
                            _, buffer = cv2.imencode('.jpg', processed_img, 
                                                   [cv2.IMWRITE_JPEG_QUALITY, 90])
                            jpeg_data = base64.b64encode(buffer).decode('utf-8')
                            
                            # 获取当前帧的宽高
                            current_width = processed_img.shape[1]
                            current_height = processed_img.shape[0]
                            
                            # 发送数据到WebSocket
                            websocket = active_connections.get(connection_id)
                            if websocket:
                                # 发送帧数据
                                await websocket.send_json({
                                    "type": "stream_data",
                                    "format": "jpeg",
                                    "data": jpeg_data,
                                    "frame_id": frame_id,
                                    "width": current_width,
                                    "height": current_height,
                                    "original_width": orig_w,
                                    "original_height": orig_h,
                                    "resized": resized
                                })
                                
                                processed_frames += 1
                                last_send_time = current_time
                            else:
                                logger.info(f"WebSocket连接已关闭，停止流处理: {connection_id}")
                                break
                                
                        except Exception as e:
                            logger.error(f"处理帧时发生错误: {e}")
                    
                # 检查WebSocket连接是否仍然活跃
                if connection_id not in active_connections:
                    logger.info(f"WebSocket连接已关闭，停止帧处理: {connection_id}")
                    break
                    
                # 短暂休眠，让出控制权
                await asyncio.sleep(0.01)
                
            logger.info(f"帧处理任务完成，共处理 {processed_frames} 帧")
            
        except asyncio.CancelledError:
            logger.info(f"帧处理任务被取消: {connection_id}")
        except Exception as e:
            logger.error(f"帧处理任务错误: {e}")
            # 通知客户端发生错误
            websocket = active_connections.get(connection_id)
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": f"帧处理错误: {str(e)}"
                })
        finally:
            logger.info(f"帧处理任务已结束: {connection_id}")
# 创建RTSP管理器实例
rtsp_manager = RTSPManager()

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
# 创建帧处理器实例
frame_processor = FrameProcessor()

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
# 获取或加载YOLO模型
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
# 处理单帧图像
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
                results = models_info['model'](frame, conf=0.25)[0]
            
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
# 异步处理帧队列
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
# 非极大值抑制(NMS)
def non_max_suppression(boxes, scores, iou_threshold=0.45):
    """
    执行非极大值抑制(NMS)，去除重叠的检测框
    
    参数:
        boxes: 边界框列表 [[x, y, w, h], ...]
        scores: 对应的置信度分数
        iou_threshold: IoU阈值，高于此值的框会被抑制
        
    返回:
        保留的检测框的索引列表
    """
    try:
        # 检查输入有效性
        if len(boxes) == 0 or len(scores) != len(boxes):
            return []
        
        # 转换成numpy数组
        boxes = np.array(boxes)
        scores = np.array(scores)
        
        # 计算每个框的面积和右下角坐标
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        w = boxes[:, 2]
        h = boxes[:, 3]
        x2 = x1 + w
        y2 = y1 + h
        area = w * h
        
        # 按照分数从高到低排序
        idxs = np.argsort(scores)[::-1]
        
        # 保留的框的索引
        keep = []
        
        while len(idxs) > 0:
            # 取分数最高的框
            i = idxs[0]
            keep.append(i)
            
            # 计算其他框与当前框的IoU
            xx1 = np.maximum(x1[i], x1[idxs[1:]])
            yy1 = np.maximum(y1[i], y1[idxs[1:]])
            xx2 = np.minimum(x2[i], x2[idxs[1:]])
            yy2 = np.minimum(y2[i], y2[idxs[1:]])
            
            # 计算重叠区域的宽和高
            w_inter = np.maximum(0, xx2 - xx1)
            h_inter = np.maximum(0, yy2 - yy1)
            
            # 计算重叠区域的面积
            intersection = w_inter * h_inter
            
            # 计算IoU
            union = area[i] + area[idxs[1:]] - intersection
            iou = intersection / (union + 1e-8)  # 避免除以0
            
            # 保留IoU小于阈值的框
            idxs = idxs[1:][iou < iou_threshold]
        
        return keep
    except Exception as e:
        logger.error(f"Error in NMS: {e}")
        return list(range(len(boxes)))  # 出错时返回所有框
# 检测预览WebSocket端点
@router.websocket("/preview")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    rtsp_sessions[connection_id] = {"status": "connected"}
    models_info = None
    
    try:
        # 等待客户端的连接请求
        while True:
            message = await websocket.receive_json()
            # 增加处理连接请求的逻辑
            if message["type"] == "connect":
                # 发送连接确认
                await websocket.send_json({
                    "type": "connect_confirm"
                })
                continue
            # 增加处理RTSP预览请求的逻辑
            elif message["type"] == "preview_request":
                # 获取RTSP URL
                stream_url = message.get("stream_url")
                device_id = message.get("device_id")
                
                if not stream_url:
                    await websocket.send_json({
                        "type": "error",
                        "message": "缺少流URL"
                    })
                    continue
                
                # 将WebSocket连接添加到活动连接字典
                active_connections[connection_id] = websocket
                
                # 启动RTSP流处理
                await websocket.send_json({
                    "type": "preview_connecting",
                    "message": "正在连接RTSP流，请稍候..."
                })
                
                result = await rtsp_manager.start_stream(connection_id, stream_url)
                
                if not result:
                    await websocket.send_json({
                        "type": "error",
                        "message": "启动流处理失败，可能该流已在处理中"
                    })
                continue
            # 增加处理模型配置请求的逻辑
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
                
                except Exception as e:
                    error_msg = f"Error configuring model {models_name}: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                continue
            # 增加处理图片检测请求的逻辑
            elif message["type"] == "image":
                # 处理单张图片检测请求
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                
                start_time = time.time()
                try:
                    # 获取图片信息
                    image_id = message.get("image_id", 0)
                    image_name = message.get("image_name", f"image_{image_id}")
                    timestamp = message.get("timestamp", time.time())
                    width = message.get("width", 0)
                    height = message.get("height", 0)
                    original_width = message.get("original_width", width)
                    original_height = message.get("original_height", height)
                    scale = message.get("scale", 1.0)               
                    
                    # 解码图像
                    decode_start_time = time.time()
                    try:
                        img_data = base64.b64decode(message.get("frame"))
                        nparr = np.frombuffer(img_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is None:
                            raise ValueError("Failed to decode image")
                        
                        decode_time = time.time() - decode_start_time
                    except Exception as e:
                        error_msg = f"Error decoding image: {str(e)}"
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                        continue
                    
                    # 处理图片
                    try:
                        # 性能优化：如果图像尺寸过大，可以缩小后处理
                        max_dim = 1280  # 最大尺寸
                        orig_h, orig_w = frame.shape[:2]
                        target_frame = frame
                        target_scale = 1.0
                        
                        # 如果原始图像过大，先缩小进行检测，再缩放结果
                        if max(orig_h, orig_w) > max_dim:
                            resize_scale = max_dim / max(orig_h, orig_w)
                            new_h, new_w = int(orig_h * resize_scale), int(orig_w * resize_scale)
                            target_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                            target_scale = resize_scale
                        
                        # 检测开始时间
                        detect_start_time = time.time()
                        
                        # 使用process_frame函数处理图片
                        result = process_frame(
                            frame=target_frame,
                            models_info=models_info,
                            frame_id=image_id,
                            timestamp=timestamp
                        )
                        
                        # 检测时间
                        detect_time = time.time() - detect_start_time
                        
                        if not result:
                            raise ValueError("Failed to process image")
                        
                        # 处理缩放以匹配原始尺寸
                        if target_scale < 1.0:
                            for obj in result["objects"]:
                                if "bbox" in obj:
                                    x, y, w, h = obj["bbox"]
                                    obj["bbox"] = [
                                        x / target_scale,
                                        y / target_scale,
                                        w / target_scale,
                                        h / target_scale
                                    ]
                                if all(k in obj for k in ["x1", "y1", "x2", "y2"]):
                                    obj["x1"] /= target_scale
                                    obj["y1"] /= target_scale
                                    obj["x2"] /= target_scale
                                    obj["y2"] /= target_scale
                        
                        # 应用非极大值抑制(NMS)处理重叠检测框
                        nms_start_time = time.time()
                        nms_applied = False
                        try:
                            if len(result["objects"]) > 1:
                                
                                # 提取边界框和分数
                                boxes = []
                                scores = []
                                for obj in result["objects"]:
                                    if "bbox" in obj:
                                        boxes.append(obj["bbox"])
                                        scores.append(obj["confidence"])
                                
                                # 应用NMS
                                if boxes and scores:
                                    keep_indices = non_max_suppression(boxes, scores, iou_threshold=0.45)
                                    
                                    # 仅保留NMS后的检测结果
                                    filtered_objects = [result["objects"][i] for i in keep_indices]
                                    result["objects"] = filtered_objects
                                    nms_applied = True
                        except Exception as e:
                            logger.error(f"Error applying NMS: {e}")
                            # 继续使用原始检测结果
                        
                        nms_time = time.time() - nms_start_time
                        
                        # 如果图片进行了缩放，需要调整检测框坐标
                        if scale != 1.0 and original_width > 0 and original_height > 0:
                            scale_factor = 1.0 / scale
                            for obj in result["objects"]:
                                # 调整检测框坐标和尺寸
                                if "bbox" in obj:
                                    x, y, w, h = obj["bbox"]
                                    obj["bbox"] = [
                                        x * scale_factor,
                                        y * scale_factor,
                                        w * scale_factor,
                                        h * scale_factor
                                    ]
                                # 更新x1, y1, x2, y2坐标(如果存在)
                                if all(k in obj for k in ["x1", "y1", "x2", "y2"]):
                                    obj["x1"] *= scale_factor
                                    obj["y1"] *= scale_factor
                                    obj["x2"] *= scale_factor
                                    obj["y2"] *= scale_factor
                        
                        # 添加图片ID和名称到结果
                        result["image_id"] = image_id
                        result["image_name"] = image_name
                        result["original_width"] = original_width
                        result["original_height"] = original_height
                        
                        # 添加性能信息
                        total_time = time.time() - start_time
                        result["performance"] = {
                            "decode_time": round(decode_time * 1000, 2),  # ms
                            "detection_time": round(detect_time * 1000, 2),  # ms
                            "nms_time": round(nms_time * 1000, 2),  # ms
                            "total_time": round(total_time * 1000, 2),  # ms
                            "nms_applied": nms_applied
                        }
                                             
                        # 发送检测结果
                        await websocket.send_json(result)
                        
                    except Exception as e:
                        error_msg = f"Error processing image: {str(e)}"
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                except Exception as e:
                    error_msg = f"Error handling image detection request: {str(e)}"
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                continue
            # 增加处理视频信息请求的逻辑
            elif message["type"] == "video_info":
                # 处理视频信息
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                                        
                frame_queues[connection_id] = asyncio.Queue(maxsize=max_queue_size)
                
                # 启动帧处理任务
                task = asyncio.create_task(process_frame_queue(connection_id))
                manager.connection_tasks[connection_id] = task               
            # 增加处理视频帧请求的逻辑
            elif message["type"] == "video":
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
                    results = await frame_queues[connection_id].put({
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
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to process frame: {str(e)}"
                    })
            else:
                # 处理其他现有命令...
                pass

    except WebSocketDisconnect:
        logger.info(f"Client {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {connection_id}: {str(e)}")
    finally:
        # 确保断开连接时停止所有流处理
        if connection_id in active_connections:
            await rtsp_manager.stop_stream(connection_id)
        await manager.disconnect(connection_id)

# 标准RTSP拉流API
import socket
import struct
import hashlib
import random
import string
from typing import Optional, Dict, Any, Tuple

class RTSPClient:
    """标准RTSP客户端，实现完整的RTSP协议流程"""
    
    def __init__(self, ip_address: str, port: int = 554, username: str = "", password: str = ""):
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password
        self.session_id = None
        self.cseq = 0
        self.socket = None
        self.is_connected = False
        
        # 添加nonce缓存机制
        self.nonce_cache = {}  # 缓存nonce信息: {realm: {nonce, expiry_time, auth_response}}
        self.nonce_expiry = {}  # 缓存过期时间: {realm:nonce: expiry_time}
        self.max_nonce_age = 300  # nonce最大有效期，默认5分钟
        
    def _is_nonce_valid(self, realm: str, nonce: str) -> bool:
        """检查nonce是否仍然有效"""
        cache_key = f"{realm}:{nonce}"
        if cache_key in self.nonce_expiry:
            return time.time() < self.nonce_expiry[cache_key]
        return False
    
    def _cache_nonce(self, realm: str, nonce: str, auth_response: str, max_age: int = None):
        """缓存nonce信息"""
        if max_age is None:
            max_age = self.max_nonce_age
            
        cache_key = f"{realm}:{nonce}"
        expiry_time = time.time() + max_age
        
        self.nonce_cache[cache_key] = {
            "nonce": nonce,
            "expiry_time": expiry_time,
            "auth_response": auth_response
        }
        self.nonce_expiry[cache_key] = expiry_time
        
        logger.debug(f"缓存nonce: {realm}, 过期时间: {expiry_time}")
    
    def _get_cached_auth_response(self, realm: str, nonce: str) -> str:
        """获取缓存的认证响应"""
        cache_key = f"{realm}:{nonce}"
        if cache_key in self.nonce_cache:
            cache_data = self.nonce_cache[cache_key]
            if time.time() < cache_data["expiry_time"]:
                logger.debug(f"使用缓存的认证响应: {realm}")
                return cache_data["auth_response"]
            else:
                # 清理过期的缓存
                self._cleanup_expired_nonce(realm, nonce)
        return None
    
    def _cleanup_expired_nonce(self, realm: str = None, nonce: str = None):
        """清理过期的nonce缓存"""
        current_time = time.time()
        
        if realm and nonce:
            # 清理特定的nonce
            cache_key = f"{realm}:{nonce}"
            if cache_key in self.nonce_cache:
                del self.nonce_cache[cache_key]
            if cache_key in self.nonce_expiry:
                del self.nonce_expiry[cache_key]
        else:
            # 清理所有过期的nonce
            expired_keys = []
            for key, expiry_time in self.nonce_expiry.items():
                if current_time >= expiry_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                if key in self.nonce_cache:
                    del self.nonce_cache[key]
                if key in self.nonce_expiry:
                    del self.nonce_expiry[key]
            
            if expired_keys:
                logger.debug(f"清理了 {len(expired_keys)} 个过期的nonce缓存")
    
    def _check_stale_nonce(self, auth_header: str) -> bool:
        """检查nonce是否已过期（stale=true）"""
        if 'stale=true' in auth_header.lower():
            logger.info("检测到stale=true，nonce已过期，需要重新认证")
            return True
        return False
    
    def _extract_nonce_info(self, auth_header: str) -> Dict[str, str]:
        """从WWW-Authenticate头中提取nonce信息"""
        auth_info = {}
        regex = r'(\w+)="([^"]*)"'
        matches = re.findall(regex, auth_header)
        
        for key, value in matches:
            auth_info[key] = value
        
        return auth_info
    
    def _generate_random_string(self, length: int = 16) -> str:
        """生成随机字符串"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def _calculate_md5(self, data: str) -> str:
        """计算MD5哈希值"""
        return hashlib.md5(data.encode()).hexdigest()
    
    def _generate_digest_auth(self, auth_header: str, method: str, uri: str) -> str:
        """生成Digest认证响应，优先使用缓存"""
        try:
            # 解析WWW-Authenticate头
            auth_info = self._extract_nonce_info(auth_header)
            
            realm = auth_info.get('realm', '')
            nonce = auth_info.get('nonce', '')
            qop = auth_info.get('qop', '')
            algorithm = auth_info.get('algorithm', 'MD5')
            
            # 检查是否有缓存的认证响应
            cached_response = self._get_cached_auth_response(realm, nonce)
            if cached_response:
                logger.debug(f"使用缓存的Digest认证响应: {realm}")
                return cached_response
            
            # 检查nonce是否已过期
            if self._check_stale_nonce(auth_header):
                # 清理过期的nonce缓存
                self._cleanup_expired_nonce(realm, nonce)
                logger.info("nonce已过期，清理缓存并重新生成认证")
            
            # 生成新的认证响应
            cnonce = self._generate_random_string(16)
            nc = '00000001'
            
            # 计算HA1 = MD5(username:realm:password)
            ha1 = self._calculate_md5(f"{self.username}:{realm}:{self.password}")
            
            # 计算HA2 = MD5(method:uri)
            ha2 = self._calculate_md5(f"{method}:{uri}")
            
            # 计算response
            if qop:
                response = self._calculate_md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
            else:
                response = self._calculate_md5(f"{ha1}:{nonce}:{ha2}")
            
            # 构造成认证头
            auth_response = f'Digest username="{self.username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'
            
            if qop:
                auth_response += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
            
            # 缓存新的认证响应
            self._cache_nonce(realm, nonce, auth_response)
            logger.debug(f"生成并缓存新的Digest认证响应: {realm}")
            
            return auth_response
            
        except Exception as e:
            logger.error(f"生成Digest认证失败: {e}")
            return ""
    
    def connect(self) -> bool:
        """建立TCP连接"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.ip_address, self.port))
            self.is_connected = True
            logger.info(f"RTSP连接成功: {self.ip_address}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"RTSP连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.is_connected = False
        self.session_id = None
        
        # 清理过期的nonce缓存
        self._cleanup_expired_nonce()
        logger.debug("已清理过期的nonce缓存")
    
    def _send_request(self, method: str, uri: str, headers: Dict[str, str] = None) -> str:
        """发送RTSP请求"""
        if not self.is_connected:
            raise Exception("RTSP连接未建立")
        
        self.cseq += 1
        
        # 构建请求头
        request_lines = [
            f"{method} {uri} RTSP/1.0",
            f"CSeq: {self.cseq}",
            f"User-Agent: YOLO-RTSP-Client/1.0"
        ]
        
        # 添加认证头
        if self.username and self.password:
            if headers and 'Authorization' in headers:
                request_lines.append(f"Authorization: {headers['Authorization']}")
        
        # 添加会话ID
        if self.session_id:
            request_lines.append(f"Session: {self.session_id}")
        
        # 添加其他自定义头
        if headers:
            for key, value in headers.items():
                if key.lower() not in ['authorization', 'session']:
                    request_lines.append(f"{key}: {value}")
        
        # 添加空行和请求体结束
        request_lines.extend(["", ""])
        
        request_data = "\r\n".join(request_lines)
        logger.debug(f"发送RTSP请求:\n{request_data}")
        
        try:
            self.socket.send(request_data.encode())
            
            # 接收响应
            response = b""
            while True:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\r\n\r\n" in response:
                    break
            
            response_text = response.decode('utf-8', errors='ignore')
            logger.info(f"收到RTSP响应:\n{response_text}")
            
            return response_text
            
        except Exception as e:
            logger.error(f"RTSP请求失败: {e}")
            raise
    
    def describe(self, channel: int = 1, subtype: int = 0) -> Dict[str, Any]:
        """发送DESCRIBE命令获取媒体描述"""
        try:
            # 构建相对路径URI（用于RTSP请求行）
            request_uri = f"/cam/realmonitor?channel={channel}&subtype={subtype}"
            # 构建完整URL（用于Digest认证）
            full_uri = f"rtsp://{self.ip_address}:{self.port}{request_uri}"
            
            # 检查是否有缓存的认证信息可以直接使用
            if self.username and self.password:
                # 尝试使用缓存的认证信息
                for cache_key, cache_data in self.nonce_cache.items():
                    if cache_data["expiry_time"] > time.time():
                        # 使用缓存的认证信息
                        auth_headers = {"Authorization": cache_data["auth_response"]}
                        try:
                            response = self._send_request("DESCRIBE", full_uri, auth_headers)
                            lines = response.split('\r\n')
                            status_line = lines[0]
                            
                            if "200 OK" in status_line:
                                # 提取SDP信息
                                sdp_start = response.find('\r\n\r\n')
                                if sdp_start != -1:
                                    sdp_content = response[sdp_start + 4:]
                                    media_info = self._parse_sdp(sdp_content)
                                    logger.info(f"DESCRIBE (缓存认证)成功，媒体信息: {media_info}")
                                    return {
                                        "success": True,
                                        "media_info": media_info,
                                        "response": response,
                                        "cached_auth": True
                                    }
                        except Exception as e:
                            logger.debug(f"缓存认证失败，尝试重新认证: {e}")
                            # 继续执行正常的认证流程
            
            # 第一次请求，不包含认证信息
            response = self._send_request("DESCRIBE", full_uri)
            
            # 解析响应
            lines = response.split('\r\n')
            status_line = lines[0]
            
            if "200 OK" in status_line:
                # 提取SDP信息
                sdp_start = response.find('\r\n\r\n')
                if sdp_start != -1:
                    sdp_content = response[sdp_start + 4:]
                    
                    # 解析SDP获取媒体信息
                    media_info = self._parse_sdp(sdp_content)
                    
                    logger.info(f"DESCRIBE成功，媒体信息: {media_info}")
                    return {
                        "success": True,
                        "media_info": media_info,
                        "response": response
                    }
                else:
                    return {"success": False, "error": "未找到SDP内容"}
            elif "401 Unauthorized" in status_line:
                # 需要认证，查找WWW-Authenticate头
                auth_header = None
                for line in lines:
                    if line.lower().startswith('www-authenticate:'):
                        auth_header = line.split(':', 1)[1].strip()
                        break
                
                if auth_header and self.username and self.password:
                    logger.info(f"收到401认证挑战，开始Digest认证: {auth_header}")
                    
                    # 生成Digest认证响应，使用完整URI
                    auth_response = self._generate_digest_auth(auth_header, "DESCRIBE", full_uri)
                    if not auth_response:
                        return {"success": False, "error": "生成Digest认证失败"}
                    
                    logger.info(f"生成的认证响应: {auth_response}")

                    # 重试请求，包含认证信息
                    headers = {"Authorization": auth_response}
                    retry_response = self._send_request("DESCRIBE", full_uri, headers)
                    
                    # 解析重试响应
                    retry_lines = retry_response.split('\r\n')
                    retry_status_line = retry_lines[0]
                    
                    if "200 OK" in retry_status_line:
                        # 提取SDP信息
                        sdp_start = retry_response.find('\r\n\r\n')
                        if sdp_start != -1:
                            sdp_content = retry_response[sdp_start + 4:]
                            
                            # 解析SDP获取媒体信息
                            media_info = self._parse_sdp(sdp_content)
                            
                            logger.info(f"DESCRIBE (Digest认证)成功，媒体信息: {media_info}")
                            return {
                                "success": True,
                                "media_info": media_info,
                                "response": retry_response
                            }
                        else:
                            return {"success": False, "error": "Digest认证后未找到SDP内容"}
                    else:
                        return {"success": False, "error": f"Digest认证后DESCRIBE失败: {retry_status_line}"}
                else:
                    if not auth_header:
                        return {"success": False, "error": "401 Unauthorized但缺少WWW-Authenticate头"}
                    else:
                        return {"success": False, "error": "需要认证但未提供用户名和密码"}
            else:
                # 记录完整的响应内容以便调试
                logger.error(f"DESCRIBE失败，完整响应:\n{response}")
                return {"success": False, "error": f"DESCRIBE失败: {status_line}"}
                
        except Exception as e:
            logger.error(f"DESCRIBE命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_sdp(self, sdp_content: str) -> Dict[str, Any]:
        """解析SDP内容"""
        media_info = {
            "video_codec": "unknown",
            "framerate": 25.0,
            "resolution": "unknown"
        }
        
        try:
            lines = sdp_content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('m=video'):
                    # 解析视频媒体行
                    parts = line.split()
                    if len(parts) >= 4:
                        media_info["video_codec"] = parts[3]
                elif line.startswith('a=framerate:'):
                    # 解析帧率
                    try:
                        framerate = float(line.split(':')[1])
                        media_info["framerate"] = framerate
                    except:
                        pass
                elif line.startswith('a=control:trackID='):
                    # 解析轨道ID
                    track_id = line.split('=')[1]
                    media_info["track_id"] = track_id
                    
        except Exception as e:
            logger.warning(f"解析SDP失败: {e}")
        
        return media_info
    
    def setup(self, channel: int = 1, subtype: int = 0, client_port_start: int = 63088) -> Dict[str, Any]:
        """发送SETUP命令建立传输通道"""
        try:
            # 生成客户端端口
            client_port_rtp = client_port_start
            client_port_rtcp = client_port_start + 1
            
            # 构建相对路径URI（用于RTSP请求行）
            request_uri = f"/cam/realmonitor?channel={channel}&subtype={subtype}/trackID=0"
            # 构建完整URL（用于Digest认证）
            full_uri = f"rtsp://{self.ip_address}:{self.port}{request_uri}"
            
            headers = {
                "Transport": f"RTP/AVP;unicast;client_port={client_port_rtp}-{client_port_rtcp}"
            }
            
            # 检查是否有缓存的认证信息可以直接使用
            if self.username and self.password:
                # 尝试使用缓存的认证信息
                for cache_key, cache_data in self.nonce_cache.items():
                    if cache_data["expiry_time"] > time.time():
                        # 使用缓存的认证信息
                        auth_headers = {**headers, "Authorization": cache_data["auth_response"]}
                        try:
                            response = self._send_request("SETUP", full_uri, auth_headers)
                            lines = response.split('\r\n')
                            status_line = lines[0]
                            
                            if "200 OK" in status_line:
                                # 提取会话ID和传输信息
                                session_id, server_ports = self._extract_setup_info(lines)
                                if session_id:
                                    self.session_id = session_id
                                    logger.info(f"SETUP (缓存认证)成功，会话ID: {session_id}, 服务器端口: {server_ports}")
                                    return {
                                        "success": True,
                                        "session_id": session_id,
                                        "server_ports": server_ports,
                                        "client_ports": (client_port_rtp, client_port_rtcp),
                                        "cached_auth": True
                                    }
                        except Exception as e:
                            logger.debug(f"缓存认证失败，尝试重新认证: {e}")
                            # 继续执行正常的认证流程
            
            # 第一次请求，可能包含认证信息（如果之前已经建立）
            response = self._send_request("SETUP", full_uri, headers)
            
            # 解析响应
            lines = response.split('\r\n')
            status_line = lines[0]
            
            if "200 OK" in status_line:
                # 提取会话ID和传输信息
                session_id, server_ports = self._extract_setup_info(lines)
                if session_id:
                    self.session_id = session_id
                    logger.info(f"SETUP成功，会话ID: {session_id}, 服务器端口: {server_ports}")
                    return {
                        "success": True,
                        "session_id": session_id,
                        "server_ports": server_ports,
                        "client_ports": (client_port_rtp, client_port_rtcp)
                    }
                else:
                    return {"success": False, "error": "未找到会话ID"}
            elif "401 Unauthorized" in status_line:
                # 需要认证，查找WWW-Authenticate头
                auth_header = None
                for line in lines:
                    if line.lower().startswith('www-authenticate:'):
                        auth_header = line.split(':', 1)[1].strip()
                        break
                
                if auth_header and self.username and self.password:
                    logger.info(f"SETUP收到401认证挑战，开始Digest认证: {auth_header}")
                    
                    # 生成Digest认证响应，使用完整URI
                    auth_response = self._generate_digest_auth(auth_header, "SETUP", full_uri)
                    if not auth_response:
                        return {"success": False, "error": "生成Digest认证失败"}
                    
                    # 重试请求，包含认证信息
                    auth_headers = {**headers, "Authorization": auth_response}
                    retry_response = self._send_request("SETUP", full_uri, auth_headers)
                    
                    # 解析重试响应
                    retry_lines = retry_response.split('\r\n')
                    retry_status_line = retry_lines[0]
                    
                    if "200 OK" in retry_status_line:
                        # 提取会话ID和传输信息
                        session_id, server_ports = self._extract_setup_info(retry_lines)
                        if session_id:
                            self.session_id = session_id
                            logger.info(f"SETUP (Digest认证)成功，会话ID: {session_id}, 服务器端口: {server_ports}")
                            return {
                                "success": True,
                                "session_id": session_id,
                                "server_ports": server_ports,
                                "client_ports": (client_port_rtp, client_port_rtcp)
                            }
                        else:
                            return {"success": False, "error": "Digest认证后未找到会话ID"}
                    else:
                        return {"success": False, "error": f"Digest认证后SETUP失败: {retry_status_line}"}
                else:
                    if not auth_header:
                        return {"success": False, "error": "401 Unauthorized但缺少WWW-Authenticate头"}
                    else:
                        return {"success": False, "error": "需要认证但未提供用户名和密码"}
            else:
                return {"success": False, "error": f"SETUP失败: {status_line}"}
                
        except Exception as e:
            logger.error(f"SETUP命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_setup_info(self, lines: list) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
        """从SETUP响应中提取会话ID和服务器端口信息"""
        session_id = None
        server_ports = None
        
        for line in lines:
            if line.startswith("Session:"):
                session_id = line.split(":")[1].split(";")[0].strip()
            elif line.startswith("Transport:"):
                # 解析服务器端口
                transport_line = line.split(":")[1]
                server_port_match = re.search(r'server_port=(\d+)-(\d+)', transport_line)
                if server_port_match:
                    server_ports = (int(server_port_match.group(1)), int(server_port_match.group(2)))
        
        return session_id, server_ports
    
    def play(self, channel: int = 1, subtype: int = 0) -> Dict[str, Any]:
        """发送PLAY命令开始播放"""
        try:
            # 构建相对路径URI（用于RTSP请求行）
            request_uri = f"/cam/realmonitor?channel={channel}&subtype={subtype}/"
            # 构建完整URL（用于Digest认证）
            full_uri = f"rtsp://{self.ip_address}:{self.port}{request_uri}"
            
            headers = {
                "Range": "npt=0.000-"
            }
            
            # 检查是否有缓存的认证信息可以直接使用
            if self.username and self.password:
                # 尝试使用缓存的认证信息
                for cache_key, cache_data in self.nonce_cache.items():
                    if cache_data["expiry_time"] > time.time():
                        # 使用缓存的认证信息
                        auth_headers = {**headers, "Authorization": cache_data["auth_response"]}
                        try:
                            response = self._send_request("PLAY", full_uri, auth_headers)
                            lines = response.split('\r\n')
                            status_line = lines[0]
                            
                            if "200 OK" in status_line:
                                logger.info("PLAY (缓存认证)命令成功，开始接收RTP流")
                                return {"success": True, "response": response, "cached_auth": True}
                        except Exception as e:
                            logger.debug(f"缓存认证失败，尝试重新认证: {e}")
                            # 继续执行正常的认证流程
            
            response = self._send_request("PLAY", full_uri, headers)
            
            # 解析响应
            lines = response.split('\r\n')
            status_line = lines[0]
            
            if "200 OK" in status_line:
                logger.info("PLAY命令成功，开始接收RTP流")
                return {"success": True, "response": response}
            elif "401 Unauthorized" in status_line:
                # 需要认证，查找WWW-Authenticate头
                auth_header = None
                for line in lines:
                    if line.lower().startswith('www-authenticate:'):
                        auth_header = line.split(':', 1)[1].strip()
                        break
                
                if auth_header and self.username and self.password:
                    logger.info(f"PLAY收到401认证挑战，开始Digest认证: {auth_header}")
                    
                    # 生成Digest认证响应，使用完整URI
                    auth_response = self._generate_digest_auth(auth_header, "PLAY", full_uri)
                    if not auth_response:
                        return {"success": False, "error": "生成Digest认证失败"}
                    
                    # 重试请求，包含认证信息
                    auth_headers = {**headers, "Authorization": auth_response}
                    retry_response = self._send_request("PLAY", full_uri, auth_headers)
                    
                    # 解析重试响应
                    retry_lines = retry_response.split('\r\n')
                    retry_status_line = retry_lines[0]
                    
                    if "200 OK" in retry_status_line:
                        logger.info("PLAY (Digest认证)命令成功，开始接收RTP流")
                        return {"success": True, "response": retry_response}
                    else:
                        return {"success": False, "error": f"Digest认证后PLAY失败: {retry_status_line}"}
                else:
                    if not auth_header:
                        return {"success": False, "error": "401 Unauthorized但缺少WWW-Authenticate头"}
                    else:
                        return {"success": False, "error": "需要认证但未提供用户名和密码"}
            else:
                return {"success": False, "error": f"PLAY失败: {status_line}"}
                
        except Exception as e:
            logger.error(f"PLAY命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    def pause(self, channel: int = 1, subtype: int = 0) -> Dict[str, Any]:
        """发送PAUSE命令暂停播放"""
        try:
            # 构建相对路径URI（用于RTSP请求行）
            request_uri = f"/cam/realmonitor?channel={channel}&subtype={subtype}/"
            # 构建完整URL（用于Digest认证）
            full_uri = f"rtsp://{self.ip_address}:{self.port}{request_uri}"
            
            # 检查是否有缓存的认证信息可以直接使用
            if self.username and self.password:
                # 尝试使用缓存的认证信息
                for cache_key, cache_data in self.nonce_cache.items():
                    if cache_data["expiry_time"] > time.time():
                        # 使用缓存的认证信息
                        auth_headers = {"Authorization": cache_data["auth_response"]}
                        try:
                            response = self._send_request("PAUSE", full_uri, auth_headers)
                            lines = response.split('\r\n')
                            status_line = lines[0]
                            
                            if "200 OK" in status_line:
                                logger.info("PAUSE (缓存认证)命令成功")
                                return {"success": True, "response": response, "cached_auth": True}
                        except Exception as e:
                            logger.debug(f"缓存认证失败，尝试重新认证: {e}")
                            # 继续执行正常的认证流程
            
            response = self._send_request("PAUSE", full_uri)
            
            lines = response.split('\r\n')
            status_line = lines[0]
            
            if "200 OK" in status_line:
                logger.info("PAUSE命令成功")
                return {"success": True, "response": response}
            elif "401 Unauthorized" in status_line:
                # 需要认证，查找WWW-Authenticate头
                auth_header = None
                for line in lines:
                    if line.lower().startswith('www-authenticate:'):
                        auth_header = line.split(':', 1)[1].strip()
                        break
                
                if auth_header and self.username and self.password:
                    logger.info(f"PAUSE收到401认证挑战，开始Digest认证: {auth_header}")
                    
                    # 生成Digest认证响应，使用完整URI
                    auth_response = self._generate_digest_auth(auth_header, "PAUSE", full_uri)
                    if not auth_response:
                        return {"success": False, "error": "生成Digest认证失败"}
                    
                    # 重试请求，包含认证信息
                    headers = {"Authorization": auth_response}
                    retry_response = self._send_request("PAUSE", full_uri, headers)
                    
                    # 解析重试响应
                    retry_lines = retry_response.split('\r\n')
                    retry_status_line = retry_lines[0]
                    
                    if "200 OK" in retry_status_line:
                        logger.info("PAUSE (Digest认证)命令成功")
                        return {"success": True, "response": retry_response}
                    else:
                        return {"success": False, "error": f"Digest认证后PAUSE失败: {retry_status_line}"}
                else:
                    if not auth_header:
                        return {"success": False, "error": "401 Unauthorized但缺少WWW-Authenticate头"}
                    else:
                        return {"success": False, "error": "需要认证但未提供用户名和密码"}
            else:
                return {"success": False, "error": f"PAUSE失败: {status_line}"}
                
        except Exception as e:
            logger.error(f"PAUSE命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    def teardown(self, channel: int = 1, subtype: int = 0) -> Dict[str, Any]:
        """发送TEARDOWN命令停止播放"""
        try:
            # 构建相对路径URI（用于RTSP请求行）
            request_uri = f"/cam/realmonitor?channel={channel}&subtype={subtype}/"
            # 构建完整URL（用于Digest认证）
            full_uri = f"rtsp://{self.ip_address}:{self.port}{request_uri}"
            
            # 检查是否有缓存的认证信息可以直接使用
            if self.username and self.password:
                # 尝试使用缓存的认证信息
                for cache_key, cache_data in self.nonce_cache.items():
                    if cache_data["expiry_time"] > time.time():
                        # 使用缓存的认证信息
                        auth_headers = {"Authorization": cache_data["auth_response"]}
                        try:
                            response = self._send_request("TEARDOWN", full_uri, auth_headers)
                            lines = response.split('\r\n')
                            status_line = lines[0]
                            
                            if "200 OK" in status_line:
                                logger.info("TEARDOWN (缓存认证)命令成功")
                                return {"success": True, "response": response, "cached_auth": True}
                        except Exception as e:
                            logger.debug(f"缓存认证失败，尝试重新认证: {e}")
                            # 继续执行正常的认证流程
            
            response = self._send_request("TEARDOWN", full_uri)
            
            lines = response.split('\r\n')
            status_line = lines[0]
            
            if "200 OK" in status_line:
                logger.info("TEARDOWN命令成功")
                return {"success": True, "response": response}
            elif "401 Unauthorized" in status_line:
                # 需要认证，查找WWW-Authenticate头
                auth_header = None
                for line in lines:
                    if line.lower().startswith('www-authenticate:'):
                        auth_header = line.split(':', 1)[1].strip()
                        break
                
                if auth_header and self.username and self.password:
                    logger.info(f"TEARDOWN收到401认证挑战，开始Digest认证: {auth_header}")
                    
                    # 生成Digest认证响应，使用完整URI
                    auth_response = self._generate_digest_auth(auth_header, "TEARDOWN", full_uri)
                    if not auth_response:
                        return {"success": False, "error": "生成Digest认证失败"}
                    
                    # 重试请求，包含认证信息
                    headers = {"Authorization": auth_response}
                    retry_response = self._send_request("TEARDOWN", full_uri, headers)
                    
                    # 解析重试响应
                    retry_lines = retry_response.split('\r\n')
                    retry_status_line = retry_lines[0]
                    
                    if "200 OK" in retry_status_line:
                        logger.info("TEARDOWN (Digest认证)命令成功")
                        return {"success": True, "response": retry_response}
                    else:
                        return {"success": False, "error": f"Digest认证后TEARDOWN失败: {retry_status_line}"}
                else:
                    if not auth_header:
                        return {"success": False, "error": "401 Unauthorized但缺少WWW-Authenticate头"}
                    else:
                        return {"success": False, "error": "需要认证但未提供用户名和密码"}
            else:
                return {"success": False, "error": f"TEARDOWN失败: {status_line}"}
                
        except Exception as e:
            logger.error(f"TEARDOWN命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    def start_stream(self, channel: int = 1, subtype: int = 0, client_port_start: int = 63088) -> Dict[str, Any]:
        """启动完整的RTSP流流程"""
        try:
            logger.info(f"开始RTSP流流程: {self.ip_address}:{self.port}, 通道: {channel}, 码流: {subtype}")
            
            # 1. 建立连接
            if not self.connect():
                return {"success": False, "error": "连接失败"}
            
            # 2. DESCRIBE
            describe_result = self.describe(channel, subtype)
            if not describe_result["success"]:
                self.disconnect()
                return describe_result
            
            # 3. SETUP
            setup_result = self.setup(channel, subtype, client_port_start)
            if not setup_result["success"]:
                self.disconnect()
                return setup_result
            
            # 4. PLAY
            play_result = self.play(channel, subtype)
            if not play_result["success"]:
                self.disconnect()
                return play_result
            
            logger.info("RTSP流启动成功")
            return {
                "success": True,
                "session_id": self.session_id,
                "client_ports": setup_result["client_ports"],
                "server_ports": setup_result["server_ports"],
                "media_info": describe_result["media_info"]
            }
            
        except Exception as e:
            logger.error(f"启动RTSP流失败: {e}")
            self.disconnect()
            return {"success": False, "error": str(e)}
    
    def stop_stream(self) -> Dict[str, Any]:
        """停止RTSP流"""
        try:
            if self.session_id:
                # 发送TEARDOWN命令
                teardown_result = self.teardown()
                if not teardown_result["success"]:
                    logger.warning(f"TEARDOWN失败: {teardown_result['error']}")
            
            # 断开连接
            self.disconnect()
            logger.info("RTSP流已停止")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"停止RTSP流失败: {e}")
            return {"success": False, "error": str(e)}

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取nonce缓存统计信息"""
        total_cached = len(self.nonce_cache)
        expired_count = 0
        valid_count = 0
        current_time = time.time()
        
        for cache_key, cache_data in self.nonce_cache.items():
            if cache_data["expiry_time"] > current_time:
                valid_count += 1
            else:
                expired_count += 1
        
        return {
            "total_cached": total_cached,
            "valid_count": valid_count,
            "expired_count": expired_count,
            "cache_hit_rate": valid_count / max(total_cached, 1) * 100 if total_cached > 0 else 0
        }

# RTSP流管理类
class RTSPStreamManager:
    """管理多个RTSP流连接"""
    
    def __init__(self):
        self.active_streams: Dict[str, RTSPClient] = {}
        self.stream_info: Dict[str, Dict[str, Any]] = {}
    
    def start_stream(self, stream_id: str, ip_address: str, port: int = 554, 
                    username: str = "", password: str = "", channel: int = 1, 
                    subtype: int = 0, client_port_start: int = 63088) -> Dict[str, Any]:
        """启动新的RTSP流"""
        try:
            # 检查是否已存在
            if stream_id in self.active_streams:
                return {"success": False, "error": "流ID已存在"}
            
            # 创建RTSP客户端
            client = RTSPClient(ip_address, port, username, password)
            
            # 启动流
            result = client.start_stream(channel, subtype, client_port_start)
            
            if result["success"]:
                self.active_streams[stream_id] = client
                self.stream_info[stream_id] = {
                    "ip_address": ip_address,
                    "port": port,
                    "channel": channel,
                    "subtype": subtype,
                    "session_id": result["session_id"],
                    "client_ports": result["client_ports"],
                    "server_ports": result["server_ports"],
                    "media_info": result["media_info"],
                    "start_time": time.time()
                }
                
                logger.info(f"RTSP流启动成功: {stream_id}")
                return {"success": True, "stream_id": stream_id, **result}
            else:
                return result
                
        except Exception as e:
            logger.error(f"启动RTSP流失败: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_stream(self, stream_id: str) -> Dict[str, Any]:
        """停止指定的RTSP流"""
        try:
            if stream_id not in self.active_streams:
                return {"success": False, "error": "流ID不存在"}
            
            client = self.active_streams[stream_id]
            result = client.stop_stream()
            
            if result["success"]:
                del self.active_streams[stream_id]
                del self.stream_info[stream_id]
                logger.info(f"RTSP流已停止: {stream_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"停止RTSP流失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_stream_info(self, stream_id: str) -> Dict[str, Any]:
        """获取流信息"""
        if stream_id in self.stream_info:
            return {"success": True, "info": self.stream_info[stream_id]}
        else:
            return {"success": False, "error": "流ID不存在"}
    
    def get_all_streams(self) -> Dict[str, Any]:
        """获取所有活跃流信息"""
        return {
            "success": True,
            "streams": list(self.stream_info.keys()),
            "count": len(self.active_streams)
        }
    
    def stop_all_streams(self) -> Dict[str, Any]:
        """停止所有RTSP流"""
        try:
            stopped_count = 0
            for stream_id in list(self.active_streams.keys()):
                result = self.stop_stream(stream_id)
                if result["success"]:
                    stopped_count += 1
            
            logger.info(f"已停止所有RTSP流，共 {stopped_count} 个")
            return {"success": True, "stopped_count": stopped_count}
            
        except Exception as e:
            logger.error(f"停止所有RTSP流失败: {e}")
            return {"success": False, "error": str(e)}

# 创建全局RTSP流管理器实例
rtsp_stream_manager = RTSPStreamManager()

# 定义请求模型
from pydantic import BaseModel

class StartStreamRequest(BaseModel):
    stream_id: str
    ip_address: str
    port: int = 554
    username: str = ""
    password: str = ""
    channel: int = 1
    subtype: int = 0
    client_port_start: int = 63088

class StopStreamRequest(BaseModel):
    stream_id: str

class TestConnectionRequest(BaseModel):
    ip_address: str
    port: int = 554
    username: str = ""
    password: str = ""
    channel: int = 1
    subtype: int = 0

# RTSP流管理API端点
@router.post("/start-stream", tags=["RTSP流管理"])
async def start_rtsp_stream(request: StartStreamRequest):
    """启动RTSP流"""
    try:
        result = rtsp_stream_manager.start_stream(
            request.stream_id, request.ip_address, request.port, 
            request.username, request.password, 
            request.channel, request.subtype, request.client_port_start
        )
        
        if result["success"]:
            return {"success": True, "data": result}
        else:
            return {"success": False, "error": result["error"]}
            
    except Exception as e:
        logger.error(f"启动RTSP流API失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/stop-stream", tags=["RTSP流管理"])
async def stop_rtsp_stream(request: StopStreamRequest):
    """停止RTSP流"""
    try:
        result = rtsp_stream_manager.stop_stream(request.stream_id)
        return result
        
    except Exception as e:
        logger.error(f"停止RTSP流API失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stream-info/{stream_id}", tags=["RTSP流管理"])
async def get_rtsp_stream_info(stream_id: str):
    """获取RTSP流信息"""
    try:
        result = rtsp_stream_manager.get_stream_info(stream_id)
        return result
        
    except Exception as e:
        logger.error(f"获取RTSP流信息API失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/all-streams", tags=["RTSP流管理"])
async def get_all_rtsp_streams():
    """获取所有RTSP流信息"""
    try:
        result = rtsp_stream_manager.get_all_streams()
        return result
        
    except Exception as e:
        logger.error(f"获取所有RTSP流信息API失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/stop-all-streams", tags=["RTSP流管理"])
async def stop_all_rtsp_streams():
    """停止所有RTSP流"""
    try:
        result = rtsp_stream_manager.stop_all_streams()
        return result
        
    except Exception as e:
        logger.error(f"停止所有RTSP流API失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/test-rtsp-connection", tags=["RTSP流管理"])
async def test_rtsp_connection(request: TestConnectionRequest):
    """测试RTSP连接"""
    try:
        # 创建临时客户端进行测试
        client = RTSPClient(request.ip_address, request.port, request.username, request.password)
        
        # 测试连接
        if not client.connect():
            return {"success": False, "error": "连接失败"}
        
        # 测试DESCRIBE
        describe_result = client.describe(request.channel, request.subtype)
        
        # 断开连接
        client.disconnect()
        
        if describe_result["success"]:
            return {
                "success": True,
                "message": "RTSP连接测试成功",
                "media_info": describe_result["media_info"]
            }
        else:
            return {
                "success": False,
                "error": f"DESCRIBE失败: {describe_result['error']}"
            }
            
    except Exception as e:
        logger.error(f"RTSP连接测试失败: {e}")
        return {"success": False, "error": str(e)}

@router.get("/cache-stats", tags=["RTSP流管理"])
async def get_rtsp_cache_stats():
    """获取RTSP nonce缓存统计信息"""
    try:
        # 获取所有活跃流的缓存统计
        all_stats = {}
        total_stats = {
            "total_cached": 0,
            "valid_count": 0,
            "expired_count": 0,
            "cache_hit_rate": 0.0
        }
        
        for stream_id, client in rtsp_stream_manager.active_streams.items():
            if hasattr(client, 'get_cache_stats'):
                stats = client.get_cache_stats()
                all_stats[stream_id] = stats
                
                # 累计总统计
                total_stats["total_cached"] += stats["total_cached"]
                total_stats["valid_count"] += stats["valid_count"]
                total_stats["expired_count"] += stats["expired_count"]
        
        # 计算总体缓存命中率
        if total_stats["total_cached"] > 0:
            total_stats["cache_hit_rate"] = total_stats["valid_count"] / total_stats["total_cached"] * 100
        
        return {
            "success": True,
            "stream_cache_stats": all_stats,
            "total_cache_stats": total_stats
        }
        
    except Exception as e:
        logger.error(f"获取RTSP缓存统计信息失败: {e}")
        return {"success": False, "error": str(e)}
