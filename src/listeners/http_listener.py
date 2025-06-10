import asyncio
import json
import logging
import aiohttp
from aiohttp import web
from typing import Dict, Any, Optional
from datetime import datetime
import threading
import uuid

from src.data_listener_manager import BaseListener, UnifiedEvent
from src.database import ListenerType, ExternalEventType

logger = logging.getLogger(__name__)

class HTTPListener(BaseListener):
    """HTTP监听器实现（支持Webhook和轮询模式）"""
    
    def __init__(self, config):
        super().__init__(config)
        
        # HTTP配置
        self.mode = self.connection_config.get('mode', 'webhook')  # webhook or polling
        
        # Webhook模式配置
        self.host = self.connection_config.get('host', '0.0.0.0')
        self.port = self.connection_config.get('port', 8080)
        self.path = self.connection_config.get('path', '/webhook')
        self.methods = self.connection_config.get('methods', ['POST'])
        self.auth_token = self.connection_config.get('auth_token')
        self.auth_header = self.connection_config.get('auth_header', 'Authorization')
        
        # 轮询模式配置
        self.poll_url = self.connection_config.get('poll_url')
        self.poll_interval = self.connection_config.get('poll_interval', 30)  # 秒
        self.poll_method = self.connection_config.get('poll_method', 'GET')
        self.poll_headers = self.connection_config.get('poll_headers', {})
        self.poll_params = self.connection_config.get('poll_params', {})
        self.poll_timeout = self.connection_config.get('poll_timeout', 30)
        
        # 通用HTTP配置
        self.max_content_length = self.connection_config.get('max_content_length', 10 * 1024 * 1024)  # 10MB
        self.ssl_verify = self.connection_config.get('ssl_verify', True)
        
        # 内部状态
        self.app = None
        self.runner = None
        self.site = None
        self.session = None
        self.message_queue = None  # 将在connect时创建
        self.stop_event = threading.Event()
    
    async def connect(self) -> bool:
        """建立HTTP连接"""
        try:
            # 在当前事件循环中创建队列
            self.message_queue = asyncio.Queue()
            
            if self.mode == 'webhook':
                return await self._start_webhook_server()
            elif self.mode == 'polling':
                return await self._setup_polling()
            else:
                logger.error(f"不支持的HTTP模式: {self.mode}")
                return False
        except Exception as e:
            logger.error(f"HTTP连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开HTTP连接"""
        try:
            self.stop_event.set()  # 设置停止标志
            
            if self.mode == 'webhook':
                await self._stop_webhook_server()
            elif self.mode == 'polling':
                await self._cleanup_polling()
                
            logger.info(f"HTTP监听器已断开: {self.mode}模式")
            
        except Exception as e:
            logger.error(f"断开HTTP连接失败: {e}")
    
    async def listen(self):
        """开始监听HTTP数据"""
        try:
            if self.mode == 'webhook':
                await self._listen_webhook()
            elif self.mode == 'polling':
                await self._listen_polling()
        except Exception as e:
            logger.error(f"HTTP监听异常: {e}")
            raise
    
    async def _start_webhook_server(self) -> bool:
        """启动Webhook服务器"""
        try:
            self.app = web.Application()
            
            # 设置路由
            for method in self.methods:
                self.app.router.add_route(method, self.path, self._handle_webhook)
            
            # 添加健康检查端点
            self.app.router.add_get('/health', self._handle_health)
            
            # 启动服务器
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"HTTP Webhook服务器已启动: {self.host}:{self.port}{self.path}")
            return True
            
        except Exception as e:
            logger.error(f"启动Webhook服务器失败: {e}")
            return False
    
    async def _stop_webhook_server(self):
        """停止Webhook服务器"""
        try:
            if self.site:
                await self.site.stop()
                self.site = None
            
            if self.runner:
                await self.runner.cleanup()
                self.runner = None
            
            self.app = None
            logger.info("HTTP Webhook服务器已停止")
            
        except Exception as e:
            logger.error(f"停止Webhook服务器失败: {e}")
    
    async def _setup_polling(self) -> bool:
        """设置HTTP轮询"""
        try:
            if not self.poll_url:
                logger.error("轮询模式需要配置poll_url")
                return False
            
            # 在当前事件循环中创建HTTP会话
            connector = aiohttp.TCPConnector(ssl=self.ssl_verify)
            timeout = aiohttp.ClientTimeout(total=self.poll_timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.poll_headers
            )
            
            logger.info(f"HTTP轮询已设置: {self.poll_url}")
            return True
            
        except Exception as e:
            logger.error(f"设置HTTP轮询失败: {e}")
            return False
    
    async def _cleanup_polling(self):
        """清理HTTP轮询"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            logger.info("HTTP轮询已清理")
        except Exception as e:
            logger.error(f"清理HTTP轮询失败: {e}")
    
    async def _listen_webhook(self):
        """监听Webhook消息"""
        # 确保message_queue已创建
        if not self.message_queue:
            logger.error("Webhook消息队列未初始化")
            return
            
        # Webhook模式下，消息通过HTTP请求处理，这里只需要处理队列中的消息
        while self.running and not self.stop_event.is_set():
            try:
                # 使用更短的超时时间，频繁检查停止标志
                message_data = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=0.5
                )
                await self._process_message(message_data)
            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                logger.error(f"处理Webhook消息失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _listen_polling(self):
        """监听轮询数据"""
        retry_count = 0
        max_retries = 5
        
        while self.running and not self.stop_event.is_set():
            try:
                await self._poll_data()
                retry_count = 0  # 成功后重置重试计数
                
                # 检查停止标志的同时等待
                for _ in range(int(self.poll_interval)):
                    if not self.running or self.stop_event.is_set():
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"HTTP轮询失败 (第{retry_count}次): {e}")
                
                if retry_count >= max_retries:
                    logger.error(f"HTTP轮询连续失败{max_retries}次，延长等待时间")
                    wait_time = min(self.poll_interval * 2, 300)  # 最大5分钟
                else:
                    wait_time = self.poll_interval
                
                # 检查停止标志的同时等待
                for _ in range(int(wait_time)):
                    if not self.running or self.stop_event.is_set():
                        break
                    await asyncio.sleep(1)
    
    async def _handle_webhook(self, request: web.Request) -> web.Response:
        """处理Webhook请求"""
        try:
            # 验证认证
            if self.auth_token:
                auth_value = request.headers.get(self.auth_header)
                if not auth_value or auth_value != f"Bearer {self.auth_token}":
                    return web.Response(status=401, text="Unauthorized")
            
            # 获取请求数据
            content_type = request.content_type
            
            if content_type == 'application/json':
                data = await request.json()
            elif content_type == 'application/x-www-form-urlencoded':
                data = dict(await request.post())
            elif content_type.startswith('text/'):
                text = await request.text()
                data = {"message": text, "content_type": content_type}
            else:
                # 二进制数据
                raw_data = await request.read()
                data = {
                    "data": raw_data.hex(),
                    "content_type": content_type,
                    "size": len(raw_data)
                }
            
            # 添加请求元数据
            data.update({
                "http_method": request.method,
                "http_path": request.path,
                "http_headers": dict(request.headers),
                "http_query": dict(request.query),
                "client_ip": request.remote,
                "timestamp": datetime.now().isoformat()
            })
            
            # 放入处理队列
            if self.message_queue:
                await self.message_queue.put(data)
            else:
                logger.warning("消息队列未初始化，直接处理消息")
                await self._process_message(data)
            
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"处理Webhook请求失败: {e}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def _handle_health(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({
            "status": "healthy",
            "listener_id": self.config_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _poll_data(self):
        """轮询数据"""
        if not self.session or self.session.closed:
            logger.warning("HTTP会话未就绪或已关闭，跳过本次轮询")
            return
            
        try:
            # 确保在正确的事件循环中执行
            async with self.session.request(
                self.poll_method,
                self.poll_url,
                params=self.poll_params
            ) as response:
                
                if response.status == 200:
                    content_type = response.content_type
                    
                    if content_type == 'application/json':
                        data = await response.json()
                    elif content_type.startswith('text/'):
                        text = await response.text()
                        data = {"message": text, "content_type": content_type}
                    else:
                        raw_data = await response.read()
                        data = {
                            "data": raw_data.hex(),
                            "content_type": content_type,
                            "size": len(raw_data)
                        }
                    
                    # 添加轮询元数据
                    data.update({
                        "http_method": self.poll_method,
                        "http_url": self.poll_url,
                        "http_status": response.status,
                        "http_headers": dict(response.headers),
                        "timestamp": datetime.now().isoformat(),
                        "poll_mode": True
                    })
                    
                    # 处理数据
                    await self._process_message(data)
                    
                else:
                    logger.warning(f"HTTP轮询响应异常: {response.status} - {self.poll_url}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP轮询客户端错误: {e}")
            raise
        except asyncio.TimeoutError:
            logger.warning(f"HTTP轮询超时: {self.poll_url}")
            raise
        except Exception as e:
            logger.error(f"HTTP轮询请求失败: {e}")
            raise
    
    async def _process_message(self, data: Dict[str, Any]):
        """处理HTTP消息"""
        try:
            # 增强消息数据
            enhanced_data = self._enhance_message_data(data)
            
            # 标准化数据格式
            event = self.normalize_data(enhanced_data)
            
            # 触发事件处理
            await self.emit_event(event)
            
        except Exception as e:
            logger.error(f"处理HTTP消息失败: {e}")
    
    def _enhance_message_data(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强消息数据"""
        enhanced = message_data.copy()
        
        # 添加HTTP特定信息
        enhanced['http_mode'] = self.mode
        
        # 推断消息类型
        if 'type' not in enhanced:
            enhanced['type'] = self._infer_message_type(enhanced)
        
        # 从路径或URL提取设备信息
        if 'device_id' not in enhanced:
            device_id = self._extract_device_from_http(enhanced)
            if device_id:
                enhanced['device_id'] = device_id
        
        return enhanced
    
    def _infer_message_type(self, data: Dict) -> str:
        """推断HTTP消息类型"""
        # 从路径推断
        path = data.get('http_path', '').lower()
        if 'alarm' in path or 'alert' in path:
            return 'alarm'
        elif 'detect' in path or 'detection' in path:
            return 'detection'
        elif 'status' in path or 'heartbeat' in path:
            return 'status'
        elif 'command' in path or 'cmd' in path:
            return 'command'
        
        # 从数据内容推断
        if 'alarm' in str(data).lower():
            return 'alarm'
        elif 'detect' in str(data).lower():
            return 'detection'
        
        return 'other'
    
    def _extract_device_from_http(self, data: Dict) -> Optional[str]:
        """从HTTP信息中提取设备ID"""
        # 从路径中提取
        path = data.get('http_path', '')
        path_parts = path.strip('/').split('/')
        
        # 常见模式：/webhook/device_id/event
        if len(path_parts) >= 2:
            potential_device = path_parts[1]
            if potential_device and potential_device != 'webhook':
                return potential_device
        
        # 从查询参数中提取
        query = data.get('http_query', {})
        device_id = query.get('device_id') or query.get('deviceId') or query.get('device')
        if device_id:
            return device_id
        
        # 从头部中提取
        headers = data.get('http_headers', {})
        device_id = headers.get('X-Device-ID') or headers.get('Device-ID')
        if device_id:
            return device_id
        
        return None
    
    def normalize_data(self, raw_data: Dict) -> UnifiedEvent:
        """重写标准化方法，针对HTTP优化"""
        try:
            # 基础字段
            event_id = raw_data.get('id') or raw_data.get('event_id') or str(uuid.uuid4())
            timestamp = self._parse_timestamp(raw_data.get('timestamp') or datetime.now())
            
            # 应用数据映射规则
            mapping = self.data_mapping
            
            # 事件类型映射
            event_type = ExternalEventType.other
            if 'event_type_mapping' in mapping:
                raw_type = raw_data.get(mapping.get('event_type_field', 'type'), 'other')
                event_type = ExternalEventType(mapping['event_type_mapping'].get(raw_type, 'other'))
            else:
                # 使用推断的类型
                inferred_type = raw_data.get('type', 'other')
                try:
                    event_type = ExternalEventType(inferred_type)
                except ValueError:
                    event_type = ExternalEventType.other
            
            # 设备ID
            device_id = None
            if 'device_id_field' in mapping:
                device_id = raw_data.get(mapping['device_id_field'])
            else:
                device_id = (raw_data.get('device_id') or 
                           raw_data.get('deviceId') or 
                           raw_data.get('device'))
            
            # 位置信息
            location = None
            if 'location_field' in mapping:
                location = raw_data.get(mapping['location_field'])
            else:
                location = raw_data.get('location') or raw_data.get('position')
            
            # 置信度
            confidence = None
            if 'confidence_field' in mapping:
                confidence = raw_data.get(mapping['confidence_field'])
            else:
                confidence = raw_data.get('confidence') or raw_data.get('score')
                if confidence is not None:
                    confidence = float(confidence)
            
            # 描述
            description = None
            if 'description_field' in mapping:
                description = raw_data.get(mapping['description_field'])
            else:
                description = (raw_data.get('description') or 
                             raw_data.get('message') or
                             raw_data.get('text'))
            
            # 提取目标信息
            targets = None
            if 'targets_field' in mapping:
                targets_data = raw_data.get(mapping['targets_field'])
                if targets_data:
                    targets = self._extract_targets(targets_data)
            else:
                targets_data = raw_data.get('targets') or raw_data.get('objects')
                if targets_data:
                    targets = self._extract_targets(targets_data)
            
            # 标签
            tags = ['http', self.mode]  # 默认添加http和模式标签
            if 'tags_field' in mapping:
                custom_tags = raw_data.get(mapping['tags_field'])
                if custom_tags:
                    if isinstance(custom_tags, str):
                        tags.append(custom_tags)
                    elif isinstance(custom_tags, list):
                        tags.extend(custom_tags)
            
            # 添加HTTP方法作为标签
            if 'http_method' in raw_data:
                tags.append(f"method:{raw_data['http_method']}")
            
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
                                value = float(value) if '.' in str(value) else int(value)
                            elif field_type == 'boolean':
                                value = bool(value) if isinstance(value, bool) else str(value).lower() in ['true', '1', 'yes']
                            elif field_type == 'json':
                                if isinstance(value, str):
                                    import json
                                    value = json.loads(value)
                            elif field_type == 'image':
                                # 图片字段暂时保持原值，后续单独处理
                                pass
                            # 'string' 类型保持原值
                            
                            custom_data[target_field] = value
                        except Exception as e:
                            logger.warning(f"转换自定义字段 {source_field} 失败: {e}")
                            custom_data[target_field] = value
            
            # 处理图片字段
            processed_images = {}
            if 'image_fields' in mapping:
                processed_images = self._process_image_fields(raw_data, mapping['image_fields'])
            
            return UnifiedEvent(
                event_id=event_id,
                event_type=event_type,
                timestamp=timestamp,
                source_type=self.listener_type,
                device_id=device_id,
                location=location,
                confidence=confidence,
                description=description,
                targets=targets,
                tags=tags,
                metadata={
                    'source_config': self.config_id,
                    'http_mode': raw_data.get('http_mode'),
                    'http_method': raw_data.get('http_method'),
                    'http_path': raw_data.get('http_path'),
                    'client_ip': raw_data.get('client_ip'),
                    'custom_data': custom_data,
                    'processed_images': processed_images
                },
                original_data=raw_data
            )
            
        except Exception as e:
            logger.error(f"HTTP数据标准化失败: {e}")
            # 返回最小化的事件对象
            return UnifiedEvent(
                event_id=str(uuid.uuid4()),
                event_type=ExternalEventType.other,
                timestamp=datetime.now(),
                source_type=self.listener_type,
                tags=['http'],
                original_data=raw_data
            ) 