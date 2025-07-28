import asyncio
import json
import uuid
import threading
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from sqlalchemy.orm import Session

from src.database import (
    SessionLocal, ListenerConfig, ExternalEvent, ListenerStatus, 
    ListenerType, ExternalEventType, EventStatus
)

logger = logging.getLogger(__name__)

@dataclass
class UnifiedEvent:
    """统一事件数据格式"""
    event_id: str
    event_type: ExternalEventType
    timestamp: datetime
    source_type: ListenerType
    device_id: Optional[str] = None
    location: Optional[str] = None
    confidence: Optional[float] = None
    description: Optional[str] = None
    targets: Optional[List[Dict]] = None
    metadata: Optional[Dict] = None
    tags: Optional[List[str]] = None
    original_data: Optional[Dict] = None

class BaseListener(ABC):
    """基础监听器抽象类"""
    
    def __init__(self, config: ListenerConfig):
        self.config = config
        self.config_id = config.config_id
        self.name = config.name
        self.listener_type = config.listener_type
        self.connection_config = config.connection_config
        self.data_mapping = config.data_mapping or {}
        self.filter_rules = config.filter_rules or {}
        
        # 新增：算法字段映射配置
        self.edge_device_mappings = getattr(config, 'edge_device_mappings', [])
        self.algorithm_field_mappings = getattr(config, 'algorithm_field_mappings', {})
        self.algorithm_specific_fields = getattr(config, 'algorithm_specific_fields', {})
        
        # 新增：设备和引擎名称映射
        self.device_name_mappings = getattr(config, 'device_name_mappings', {})
        self.engine_name_mappings = getattr(config, 'engine_name_mappings', {})
        
        # 推送配置
        self.push_enabled = getattr(config, 'push_enabled', False)
        self.push_config = getattr(config, 'push_config', {})
        
        self.running = False
        self.thread = None
        self.event_handlers: List[Callable] = []
        self.stop_event = threading.Event()
        
        # 统计信息
        self.events_received = 0
        self.events_processed = 0
        self.last_event_time = None
        self.error_count = 0
        self.last_error = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    async def listen(self):
        """开始监听数据"""
        pass
    
    def add_event_handler(self, handler: Callable[[UnifiedEvent], None]):
        """添加事件处理器"""
        self.event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable[[UnifiedEvent], None]):
        """移除事件处理器"""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
    
    async def emit_event(self, event: UnifiedEvent):
        """触发事件处理"""
        self.events_received += 1
        self.last_event_time = datetime.now()
        
        try:
            # 调用所有事件处理器
            for handler in self.event_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"事件处理器错误: {e}")
            
            self.events_processed += 1
            
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"处理事件失败: {e}")
    
    def normalize_data(self, raw_data: Dict) -> UnifiedEvent:
        """将原始数据标准化为统一格式"""
        try:
            # 基础映射
            event_id = raw_data.get('id') or str(uuid.uuid4())
            timestamp = self._parse_timestamp(raw_data.get('timestamp') or datetime.now())
            
            # 应用数据映射规则
            mapping = self.data_mapping
            
            # 事件类型推断（基于内容自动推断）
            event_type = self._infer_event_type(raw_data)
            
            # 通用基础字段映射
            device_sn = None
            if 'sn_field' in mapping:
                device_sn = raw_data.get(mapping['sn_field'])
            
            channel_id = None
            if 'channel_field' in mapping:
                channel_id = raw_data.get(mapping['channel_field'])
            
            engine_id = None
            if 'engine_field' in mapping:
                engine_id = raw_data.get(mapping['engine_field'])
            
            location = None
            if 'location_field' in mapping:
                location = raw_data.get(mapping['location_field'])
            
            # 时间戳字段
            if 'timestamp_field' in mapping:
                ts_value = raw_data.get(mapping['timestamp_field'])
                if ts_value:
                    timestamp = self._parse_timestamp(ts_value)
            
            description = None
            if 'description_field' in mapping:
                description = raw_data.get(mapping['description_field'])
            
            # 判断校验，如果engine_id不为空，则判断该引擎id，是否在algorithm_field_mappings中。数据格式{"1": [17, 1, 16, 18]}，如果engine_id为17，则判断17是否在[17, 1, 16, 18]中
            if engine_id:
                engine_found = False
                for device_id, engine_list in self.algorithm_field_mappings.items():
                    if engine_id in engine_list:
                        engine_found = True
                        break
                
                if not engine_found:
                    logger.warning(f"引擎id {engine_id} 不存在算法字段映射中")
                    return None

            # 处理算法特定字段
            algorithm_data = self._process_algorithm_fields(raw_data, device_sn, engine_id)
            
            # 提取检测结果和置信度
            confidence, targets = self._extract_detection_results(raw_data, algorithm_data)
            
            # 处理自定义字段映射
            custom_data = {}
            if 'custom_fields' in mapping:
                for source_field, field_config in mapping['custom_fields'].items():
                    if source_field in raw_data:
                        target_field = field_config.get('target_field', source_field)
                        field_type = field_config.get('field_type', 'string')
                        value = raw_data[source_field]
                        
                        # 根据字段类型进行转换
                        try:
                            if field_type == 'number':
                                value = float(value) if value is not None else None
                            elif field_type == 'boolean':
                                value = bool(value) if value is not None else None
                            elif field_type == 'json':
                                if isinstance(value, str):
                                    value = json.loads(value)
                            # string 类型保持原样
                            
                            custom_data[target_field] = value
                        except (ValueError, json.JSONDecodeError) as e:
                            logger.warning(f"字段类型转换失败 {source_field}: {e}")
                            custom_data[target_field] = str(value) if value is not None else None
            
            # 处理图片字段
            processed_images = {}
            if 'image_fields' in mapping:
                processed_images = self._process_image_fields(raw_data, mapping['image_fields'])
                # 清除原始图片字段
                for field_name in mapping['image_fields']:
                    if field_name in raw_data:
                        del raw_data[field_name]
            
            # 构建设备映射信息
            device_mapping = self._build_device_mapping(device_sn, channel_id, engine_id)
            
            # 创建扩展的元数据
            extended_metadata = {
                'source_config': self.config_id,
                'device_sn': device_sn,
                'channel_id': channel_id,
                'engine_id': engine_id,
                'device_mapping': device_mapping,
                'algorithm_data': algorithm_data,
                'custom_data': custom_data,
                'processed_images': processed_images
            }
            
            return UnifiedEvent(
                event_id=event_id,
                event_type=event_type,
                timestamp=timestamp,
                source_type=self.listener_type,
                device_id=str(device_sn) + '_' + str(channel_id),  # 使用设备SN作为device_id
                location=location,
                confidence=confidence,
                description=description,
                targets=targets,
                metadata=extended_metadata,
                original_data=raw_data
            )
            
        except Exception as e:
            logger.error(f"数据标准化失败: {e}")
            # 返回最小化的事件对象
            return UnifiedEvent(
                event_id=str(uuid.uuid4()),
                event_type=ExternalEventType.other,
                timestamp=datetime.now(),
                source_type=self.listener_type,
                original_data=raw_data
            )
    
    def _parse_timestamp(self, timestamp_data) -> datetime:
        """解析时间戳"""
        if isinstance(timestamp_data, datetime):
            return timestamp_data
        elif isinstance(timestamp_data, (int, float)):
            return datetime.fromtimestamp(timestamp_data)
        elif isinstance(timestamp_data, str):
            try:
                # 尝试多种时间格式
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                    try:
                        return datetime.strptime(timestamp_data, fmt)
                    except ValueError:
                        continue
                # 如果都失败，返回当前时间
                return datetime.now()
            except:
                return datetime.now()
        else:
            return datetime.now()
    
    def _infer_event_type(self, raw_data: Dict) -> ExternalEventType:
        """根据数据内容推断事件类型"""
        try:
            # 检查是否有检测结果
            if 'nn_output' in raw_data or 'detections' in raw_data or 'targets' in raw_data:
                return ExternalEventType.detection
            
            # 检查是否有报警相关字段
            if any(key in raw_data for key in ['alarm', 'alert', 'warning']):
                return ExternalEventType.alarm
            
            # 检查是否是状态数据
            if any(key in raw_data for key in ['status', 'state', 'health']):
                return ExternalEventType.status
            
            # 检查是否是心跳数据
            if any(key in raw_data for key in ['heartbeat', 'ping', 'keepalive']):
                return ExternalEventType.heartbeat
            
            return ExternalEventType.other
            
        except Exception:
            return ExternalEventType.other
    
    def _process_algorithm_fields(self, raw_data: Dict, device_sn: str, engine_id: str) -> Dict:
        """处理算法特定字段"""
        algorithm_data = {}
        
        try:
            # 获取配置中的算法字段映射
            algorithm_mappings = getattr(self, 'algorithm_field_mappings', {})
            algorithm_fields = getattr(self, 'algorithm_specific_fields', {})
            
            # 根据设备SN和引擎ID查找对应的字段配置
            if device_sn and engine_id:
                for device_id, engine_list in algorithm_mappings.items():
                    if engine_id in engine_list:
                        device_fields_config = algorithm_fields.get(device_id, {})
                        fields_list = device_fields_config.get(str(engine_id), [])
                        
                        # 支持数组格式的字段配置
                        if isinstance(fields_list, list):
                            for field_mapping in fields_list:
                                source_field = field_mapping.get('source_field')
                                target_field = field_mapping.get('target_field')
                                field_type = field_mapping.get('field_type', 'string')
                                
                                if source_field and target_field and source_field in raw_data:
                                    value = raw_data[source_field]
                                    
                                    # 根据字段类型进行转换
                                    try:
                                        if field_type == 'number':
                                            value = float(value) if value is not None else None
                                        elif field_type == 'boolean':
                                            value = bool(value) if value is not None else None
                                        elif field_type == 'array' and isinstance(value, str):
                                            import json
                                            value = json.loads(value)
                                        elif field_type == 'object' and isinstance(value, str):
                                            import json
                                            value = json.loads(value)
                                        # string 类型保持原样
                                        
                                        algorithm_data[target_field] = value
                                    except (ValueError, json.JSONDecodeError) as e:
                                        logger.warning(f"算法字段类型转换失败 {source_field}: {e}")
                                        algorithm_data[target_field] = str(value) if value is not None else None
                        
                        break
            
            return algorithm_data
            
        except Exception as e:
            logger.warning(f"处理算法字段失败: {e}")
            return {}
    
    def _extract_detection_results(self, raw_data: Dict, algorithm_data: Dict) -> tuple:
        """提取检测结果和置信度"""
        confidence = None
        targets = []
        
        try:
            # 从算法数据中提取检测结果
            detections = algorithm_data.get('detections')
            if detections and isinstance(detections, list):
                targets = []
                confidences = []
                
                for detection in detections:
                    target = {}
                    
                    # 提取目标类型和置信度
                    if isinstance(detection, dict):
                        if 'class_name' in detection:
                            target['class_name'] = detection['class_name']
                        if 'gcid' in detection:
                            target['class_id'] = detection['gcid']
                        if 'conf' in detection:
                            target['confidence'] = float(detection['conf'])
                            confidences.append(target['confidence'])
                        
                        # 提取边界框信息
                        if all(key in detection for key in ['x1', 'y1', 'x2', 'y2']):
                            target['bbox'] = {
                                'x1': detection['x1'],
                                'y1': detection['y1'],
                                'x2': detection['x2'],
                                'y2': detection['y2']
                            }
                    
                    if target:
                        targets.append(target)
                
                # 计算平均置信度
                if confidences:
                    confidence = sum(confidences) / len(confidences)
            
            # 如果没有从算法数据中提取到，尝试从原始数据直接提取
            if confidence is None:
                # 尝试常见的置信度字段名
                for conf_field in ['confidence', 'conf', 'score']:
                    if conf_field in raw_data:
                        try:
                            confidence = float(raw_data[conf_field])
                            break
                        except (ValueError, TypeError):
                            continue
            
            return confidence, targets
            
        except Exception as e:
            logger.warning(f"提取检测结果失败: {e}")
            return None, []
    
    def _build_device_mapping(self, device_sn: str, channel_id: str, engine_id: str) -> Dict:
        """构建设备映射信息"""
        mapping = {}
        
        try:
            # 获取配置中的设备和引擎名称映射
            device_name_mappings = getattr(self, 'device_name_mappings', {})
            engine_name_mappings = getattr(self, 'engine_name_mappings', {})
            
            if device_sn:
                mapping['device_sn'] = device_sn
                # 尝试从映射中获取设备名称
                device_name = None
                
                # 首先尝试直接通过SN查找
                if device_sn in device_name_mappings:
                    device_name = device_name_mappings[device_sn]
                else:
                    # 如果没有SN映射，尝试通过设备ID查找
                    # 这里需要根据实际的设备关联逻辑来调整
                    edge_device_mappings = getattr(self, 'edge_device_mappings', [])
                    for device_id in edge_device_mappings:
                        if device_id in device_name_mappings:
                            device_name = device_name_mappings[device_id]
                            break
                
                if device_name:
                    mapping['device_name'] = device_name
            
            if channel_id:
                mapping['channel_id'] = channel_id
                # TODO: 可以添加通道名称映射
            
            if engine_id:
                mapping['engine_id'] = engine_id
                # 从映射中获取引擎名称
                if str(engine_id) in engine_name_mappings:
                    mapping['engine_name'] = engine_name_mappings[str(engine_id)]
            
            return mapping
            
        except Exception as e:
            logger.warning(f"构建设备映射信息失败: {e}")
            return {}
    
    async def start(self) -> bool:
        """启动监听器"""
        if self.running:
            logger.warning(f"监听器 {self.config_id} 已在运行")
            return True
        
        try:
            if await self.connect():
                self.running = True
                self.stop_event.clear()
                
                # 在单独线程中运行监听逻辑
                self.thread = threading.Thread(target=self._run_listen_loop)
                self.thread.daemon = True
                self.thread.start()
                
                logger.info(f"监听器 {self.config_id} 已启动")
                return True
            else:
                logger.error(f"监听器 {self.config_id} 连接失败")
                return False
                
        except Exception as e:
            logger.error(f"启动监听器 {self.config_id} 失败: {e}")
            self.last_error = str(e)
            return False
    
    def _run_listen_loop(self):
        """在单独线程中运行监听循环"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行监听任务
            loop.run_until_complete(self.listen())
            
        except Exception as e:
            logger.error(f"监听循环异常: {e}")
            self.last_error = str(e)
        finally:
            loop.close()
    
    async def stop(self):
        """停止监听器"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        try:
            await self.disconnect()
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
                
            logger.info(f"监听器 {self.config_id} 已停止")
            
        except Exception as e:
            logger.error(f"停止监听器 {self.config_id} 失败: {e}")

    def _process_image_fields(self, raw_data: Dict, image_config: Dict) -> Dict:
        """处理图片字段"""
        processed_images = {}
        
        for field_name, config in image_config.items():
            if field_name not in raw_data:
                continue
                
            try:
                image_data = raw_data[field_name]
                encoding = config.get('encoding', 'base64')
                save_path_prefix = config.get('save_path', 'images/events')
                generate_thumbnail = config.get('generate_thumbnail', False)
                
                # 根据编码类型处理图片
                if encoding == 'base64':
                    saved_paths = self._save_base64_image(
                        image_data, save_path_prefix, generate_thumbnail
                    )
                elif encoding == 'url':
                    saved_paths = self._download_and_save_image(
                        image_data, save_path_prefix, generate_thumbnail
                    )
                elif encoding == 'binary':
                    saved_paths = self._save_binary_image(
                        image_data, save_path_prefix, generate_thumbnail
                    )
                else:
                    logger.warning(f"不支持的图片编码类型: {encoding}")
                    continue
                
                processed_images[field_name] = {
                    'original_field': field_name,
                    'encoding': encoding,
                    **saved_paths
                }
                
            except Exception as e:
                logger.error(f"处理图片字段 {field_name} 失败: {e}")
                processed_images[field_name] = {
                    'error': str(e),
                    'original_field': field_name
                }
        
        return processed_images
    
    def _save_base64_image(self, base64_data: str, save_path_prefix: str, generate_thumbnail: bool) -> Dict:
        """保存base64编码的图片"""
        import base64
        import os
        from pathlib import Path
        from PIL import Image
        import io
        
        try:
            # 去除base64前缀（如果有的话）
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            # 解码图片数据
            image_bytes = base64.b64decode(base64_data)
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.config_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            
            # 创建保存目录
            save_dir = Path(save_path_prefix)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存原图
            original_path = save_dir / filename
            with open(original_path, 'wb') as f:
                f.write(image_bytes)
            
            result = {
                'original_path': str(original_path),
                'file_size': len(image_bytes)
            }
            
            # 生成缩略图
            if generate_thumbnail:
                try:
                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_path = save_dir / thumbnail_filename
                    
                    image = Image.open(io.BytesIO(image_bytes))
                    image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    image.save(thumbnail_path, 'JPEG', quality=85)
                    
                    result['thumbnail_path'] = str(thumbnail_path)
                    result['thumbnail_size'] = thumbnail_path.stat().st_size
                    
                except Exception as e:
                    logger.warning(f"生成缩略图失败: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"保存base64图片失败: {e}")
            raise
    
    def _download_and_save_image(self, image_url: str, save_path_prefix: str, generate_thumbnail: bool) -> Dict:
        """下载并保存网络图片"""
        import aiohttp
        import asyncio
        from pathlib import Path
        from PIL import Image
        
        async def download_image():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                            return image_bytes
                        else:
                            raise ValueError(f"HTTP {response.status}: 下载图片失败")
            except Exception as e:
                logger.error(f"下载图片失败: {e}")
                raise
        
        try:
            # 在事件循环中下载图片
            loop = asyncio.get_event_loop()
            image_bytes = loop.run_until_complete(download_image())
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.config_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            
            # 创建保存目录
            save_dir = Path(save_path_prefix)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存原图
            original_path = save_dir / filename
            with open(original_path, 'wb') as f:
                f.write(image_bytes)
            
            result = {
                'original_path': str(original_path),
                'file_size': len(image_bytes),
                'source_url': image_url
            }
            
            # 生成缩略图
            if generate_thumbnail:
                try:
                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_path = save_dir / thumbnail_filename
                    
                    image = Image.open(io.BytesIO(image_bytes))
                    image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    image.save(thumbnail_path, 'JPEG', quality=85)
                    
                    result['thumbnail_path'] = str(thumbnail_path)
                    result['thumbnail_size'] = thumbnail_path.stat().st_size
                    
                except Exception as e:
                    logger.warning(f"生成缩略图失败: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"下载并保存图片失败: {e}")
            raise
    
    def _save_binary_image(self, binary_data: bytes, save_path_prefix: str, generate_thumbnail: bool) -> Dict:
        """保存二进制图片数据"""
        from pathlib import Path
        from PIL import Image
        import io
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.config_id}_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            
            # 创建保存目录
            save_dir = Path(save_path_prefix)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存原图
            original_path = save_dir / filename
            with open(original_path, 'wb') as f:
                f.write(binary_data)
            
            result = {
                'original_path': str(original_path),
                'file_size': len(binary_data)
            }
            
            # 生成缩略图
            if generate_thumbnail:
                try:
                    thumbnail_filename = f"thumb_{filename}"
                    thumbnail_path = save_dir / thumbnail_filename
                    
                    image = Image.open(io.BytesIO(binary_data))
                    image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    image.save(thumbnail_path, 'JPEG', quality=85)
                    
                    result['thumbnail_path'] = str(thumbnail_path)
                    result['thumbnail_size'] = thumbnail_path.stat().st_size
                    
                except Exception as e:
                    logger.warning(f"生成缩略图失败: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"保存二进制图片失败: {e}")
            raise

class DataListenerManager:
    """数据监听管理器"""
    
    def __init__(self):
        self.listeners: Dict[str, BaseListener] = {}
        self.event_handlers: List[Callable] = []
        self.running = False
        
        # 统计信息
        self.total_events = 0
        self.total_listeners = 0
    
    def register_listener_type(self, listener_type: ListenerType, listener_class):
        """注册监听器类型"""
        if not hasattr(self, '_listener_classes'):
            self._listener_classes = {}
        self._listener_classes[listener_type] = listener_class
    
    def add_global_event_handler(self, handler: Callable[[UnifiedEvent], None]):
        """添加全局事件处理器"""
        self.event_handlers.append(handler)
    
    def remove_global_event_handler(self, handler: Callable[[UnifiedEvent], None]):
        """移除全局事件处理器"""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
    
    async def create_listener(self, config: ListenerConfig) -> bool:
        """创建监听器"""
        if config.config_id in self.listeners:
            logger.warning(f"监听器 {config.config_id} 已存在")
            return False
        
        try:
            # 根据类型创建监听器
            listener_class = getattr(self, '_listener_classes', {}).get(config.listener_type)
            if not listener_class:
                logger.error(f"不支持的监听器类型: {config.listener_type}")
                return False
            
            listener = listener_class(config)
            
            # 添加全局事件处理器
            for handler in self.event_handlers:
                listener.add_event_handler(handler)
            
            # 添加专用事件处理器
            listener.add_event_handler(self._handle_event)
            
            self.listeners[config.config_id] = listener
            self.total_listeners += 1
            
            logger.info(f"监听器 {config.config_id} 已创建")
            return True
            
        except Exception as e:
            logger.error(f"创建监听器 {config.config_id} 失败: {e}")
            return False
    
    async def start_listener(self, config_id: str) -> bool:
        """启动监听器"""
        if config_id not in self.listeners:
            logger.error(f"监听器 {config_id} 不存在")
            return False
        
        result = await self.listeners[config_id].start()
        
        # 更新状态
        self._update_listener_status(config_id)
        
        return result
    
    async def stop_listener(self, config_id: str) -> bool:
        """停止监听器"""
        if config_id not in self.listeners:
            logger.error(f"监听器 {config_id} 不存在")
            return False
        
        await self.listeners[config_id].stop()
        
        # 停止后移除监听器，避免重复创建问题
        del self.listeners[config_id]
        self.total_listeners -= 1
        
        # 更新状态
        self._update_listener_status(config_id)
        
        return True
    
    async def remove_listener(self, config_id: str) -> bool:
        """移除监听器"""
        if config_id in self.listeners:
            await self.stop_listener(config_id)
            del self.listeners[config_id]
            self.total_listeners -= 1
            logger.info(f"监听器 {config_id} 已移除")
            return True
        return False
    
    async def start_all_enabled(self, db: Session):
        """启动所有已启用的监听器"""
        enabled_configs = db.query(ListenerConfig).filter(ListenerConfig.enabled.is_(True)).all()
        
        started_count = 0
        for config in enabled_configs:
            try:
                if await self.create_listener(config):
                    if await self.start_listener(config.config_id):
                        started_count += 1
            except Exception as e:
                logger.error(f"启动监听器 {config.config_id} 失败: {e}")
        
        logger.info(f"已启动 {started_count} 个数据监听器")
        return started_count
    
    async def stop_all(self):
        """停止所有监听器"""
        for config_id in list(self.listeners.keys()):
            await self.stop_listener(config_id)
    
    def get_listener_status(self, config_id: str) -> Dict:
        """获取监听器状态"""
        if config_id not in self.listeners:
            return {"status": "not_found"}
        
        listener = self.listeners[config_id]
        return {
            "status": "running" if listener.running else "stopped",
            "events_received": listener.events_received,
            "events_processed": listener.events_processed,
            "last_event_time": listener.last_event_time,
            "error_count": listener.error_count,
            "last_error": listener.last_error
        }
    
    def get_all_status(self) -> Dict:
        """获取所有监听器状态"""
        status = {}
        for config_id, listener in self.listeners.items():
            status[config_id] = self.get_listener_status(config_id)
        
        return {
            "listeners": status,
            "total_listeners": self.total_listeners,
            "total_events": self.total_events,
            "running_count": len([l for l in self.listeners.values() if l.running])
        }
    
    async def _handle_event(self, event: UnifiedEvent):
        """处理接收到的事件"""
        self.total_events += 1
        
        try:
            # 保存到数据库
            await self.save_event_to_db(event)
            
            # 数据推送处理
            await self._handle_push_data(event)
            
            logger.debug(f"处理事件: {event.event_id}, 类型: {event.event_type}")
            
        except Exception as e:
            logger.error(f"处理事件失败: {e}")
    
    async def _handle_push_data(self, event: UnifiedEvent):
        """处理数据推送"""
        try:
            # 检查是否有启用推送的监听器
            for listener in self.listeners.values():
                if (listener.push_enabled and 
                    hasattr(listener, 'config') and 
                    event.metadata and 
                    event.metadata.get('source_config') == listener.config_id):
                    
                    push_config = listener.push_config or {}
                    tags = push_config.get('tags', [])
                    template = push_config.get('template', '')
                    
                    if tags:  # 只有设置了推送标签才进行推送
                        # 构建推送数据
                        push_data = self._build_push_data(event, template)
                        
                        # 调用现有的数据推送功能
                        try:
                            from src.data_pusher import data_pusher
                            data_pusher.push_data(
                                data=push_data,
                                tags=tags
                            )
                            logger.info(f"数据推送成功: 事件{event.event_id}, 标签{tags}")
                        except Exception as push_error:
                            logger.error(f"数据推送失败: {push_error}")
                        
                    break
                    
        except Exception as e:
            logger.error(f"处理数据推送失败: {e}")
    
    def _build_push_data(self, event: UnifiedEvent, template: str) -> Dict:
        """构建推送数据"""
        try:
            # 基础推送数据
            push_data = {
                'event_id': event.event_id,
                'event_type': event.event_type.value,
                'timestamp': event.timestamp.isoformat(),
                'device_sn': event.device_id,
                'location': event.location,
                'confidence': event.confidence,
                'description': event.description,
                'targets': event.targets or [],
                'metadata': event.metadata or {}
            }
            
            # 如果有推送模板，使用模板格式化数据
            if template:
                try:
                    # 简单的模板变量替换
                    formatted_template = template.format(
                        device_sn=event.device_id or '',
                        location=event.location or '',
                        timestamp=event.timestamp.isoformat(),
                        event_type=event.event_type.value,
                        confidence=event.confidence or 0,
                        description=event.description or ''
                    )
                    push_data['formatted_message'] = formatted_template
                except Exception as template_error:
                    logger.warning(f"模板格式化失败: {template_error}")
                    push_data['template_error'] = str(template_error)
            
            return push_data
            
        except Exception as e:
            logger.error(f"构建推送数据失败: {e}")
            return {
                'event_id': event.event_id,
                'error': str(e)
            }
    
    async def save_event_to_db(self, event: UnifiedEvent):
        """保存事件到数据库"""
        try:
            from src.database import SessionLocal, ExternalEvent
            
            db = SessionLocal()
            
            # 提取元数据
            metadata = event.metadata or {}
            
            # 创建事件记录
            db_event = ExternalEvent(
                event_id=event.event_id,
                config_id=metadata.get('source_config'),
                source_type=event.source_type,
                event_type=event.event_type,
                device_id=event.device_id,  # 现在存储设备SN
                device_sn=metadata.get('device_sn'),
                device_name=metadata.get('device_mapping', {}).get('device_name'),  # 设备名称
                channel_id=metadata.get('channel_id'),
                engine_id=metadata.get('engine_id'),
                engine_name=metadata.get('device_mapping', {}).get('engine_name'),  # 引擎名称
                location=event.location,
                confidence=event.confidence,
                original_data=event.original_data,
                normalized_data={
                    "description": event.description,
                    "targets": event.targets,
                    "custom_data": metadata.get('custom_data', {}),
                    "processed_images": metadata.get('processed_images', {}),
                    "device_mapping": metadata.get('device_mapping', {})
                },
                algorithm_data=metadata.get('algorithm_data', {}),
                event_metadata=metadata,
                timestamp=event.timestamp
            )
            
            db.add(db_event)
            db.commit()
            db.close()
            
            logger.info(f"事件已保存到数据库: {event.event_id}")
            
        except Exception as e:
            logger.error(f"保存事件到数据库失败: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    def _update_listener_status(self, config_id: str):
        """更新监听器状态到数据库"""
        if config_id not in self.listeners:
            return
        
        listener = self.listeners[config_id]
        db = SessionLocal()
        try:
            status = db.query(ListenerStatus).filter(ListenerStatus.config_id == config_id).first()
            if not status:
                status = ListenerStatus(config_id=config_id)
                db.add(status)
            
            status.status = "running" if listener.running else "stopped"
            status.last_event_time = listener.last_event_time
            status.events_count = listener.events_processed
            status.error_count = listener.error_count
            status.last_error = listener.last_error
            status.started_at = datetime.now() if listener.running else None
            status.updated_at = datetime.now()
            
            db.commit()
            
        except Exception as e:
            logger.error(f"更新监听器状态失败: {e}")
            db.rollback()
        finally:
            db.close()

# 创建全局监听器管理器实例
data_listener_manager = DataListenerManager() 