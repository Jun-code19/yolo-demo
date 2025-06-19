import asyncio
import json
import logging
import queue
import threading
from typing import Dict, Any, List
from datetime import datetime
import uuid

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

from src.data_listener_manager import BaseListener, UnifiedEvent
from src.database import ListenerType, ExternalEventType

logger = logging.getLogger(__name__)

class MQTTListener(BaseListener):
    """MQTT监听器实现"""
    
    def __init__(self, config):
        super().__init__(config)
        
        if not MQTT_AVAILABLE:
            raise ImportError("paho-mqtt 库未安装，请运行: pip install paho-mqtt")
        
        self.client = None
        self.connected = False
        
        # MQTT配置
        self.broker_host = self.connection_config.get('host', 'localhost')
        self.broker_port = self.connection_config.get('port', 1883)
        self.username = self.connection_config.get('username')
        self.password = self.connection_config.get('password')
        self.client_id = self.connection_config.get('client_id', f'listener_{self.config_id}')
        
        # 订阅配置
        self.topics = self.connection_config.get('topics', ['#'])  # 默认订阅所有主题
        self.qos = self.connection_config.get('qos', 0)
        
        # 连接配置
        self.keepalive = self.connection_config.get('keepalive', 60)
        self.clean_session = self.connection_config.get('clean_session', True)
        self.reconnect_delay = self.connection_config.get('reconnect_delay', 5)
        
        # TLS/SSL配置
        self.use_tls = self.connection_config.get('use_tls', False)
        self.ca_cert = self.connection_config.get('ca_cert')
        self.certfile = self.connection_config.get('certfile')
        self.keyfile = self.connection_config.get('keyfile')
        
        # 消息队列（用于异步处理）
        self.message_queue = None
        self.loop = None
        # 线程安全的消息缓冲队列
        self.thread_safe_queue = queue.Queue(maxsize=1000)
    
    async def connect(self) -> bool:
        """建立MQTT连接"""
        try:
            self.client = mqtt.Client(
                client_id=self.client_id,
                clean_session=self.clean_session
            )
            
            # 设置回调函数
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.on_subscribe = self._on_subscribe
            self.client.on_log = self._on_log
            
            # 设置认证信息
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            # 配置TLS/SSL
            if self.use_tls:
                if self.ca_cert:
                    self.client.tls_set(
                        ca_certs=self.ca_cert,
                        certfile=self.certfile,
                        keyfile=self.keyfile
                    )
                else:
                    self.client.tls_set()
            
            # 连接到MQTT代理
            logger.info(f"正在连接MQTT代理: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, self.keepalive)
            
            # 启动网络循环
            self.client.loop_start()
            
            # 等待连接确认
            for _ in range(30):  # 最多等待30秒
                if self.connected:
                    break
                await asyncio.sleep(1)
            
            if self.connected:
                logger.info(f"MQTT连接成功: {self.broker_host}:{self.broker_port}")
                return True
            else:
                logger.error("MQTT连接超时")
                return False
                
        except Exception as e:
            logger.error(f"MQTT连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开MQTT连接"""
        try:
            self.connected = False
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.client = None
                logger.info("MQTT连接已断开")
            
            # 清理队列和循环引用
            self.message_queue = None
            self.loop = None
        except Exception as e:
            logger.error(f"断开MQTT连接失败: {e}")
    
    async def listen(self):
        """开始监听MQTT消息"""
        # 初始化队列和事件循环引用
        self.loop = asyncio.get_running_loop()
        self.message_queue = asyncio.Queue()
        
        # 订阅主题
        await self._subscribe_topics()
        
        # 处理消息队列
        while self.running:
            try:
                # 首先检查线程安全队列
                try:
                    message_data = self.thread_safe_queue.get_nowait()
                    await self._process_message(message_data)
                    continue
                except queue.Empty:
                    pass
                
                # 然后检查异步队列
                try:
                    message_data = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=0.1
                    )
                    await self._process_message(message_data)
                except asyncio.TimeoutError:
                    # 短暂睡眠以避免忙等待
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"处理MQTT消息失败: {e}")
                await asyncio.sleep(0.1)
    
    async def _subscribe_topics(self):
        """订阅MQTT主题"""
        if not self.connected or not self.client:
            return
        
        for topic in self.topics:
            try:
                result, mid = self.client.subscribe(topic, self.qos)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"已订阅MQTT主题: {topic} (QoS: {self.qos})")
                else:
                    logger.error(f"订阅MQTT主题失败: {topic}, 错误码: {result}")
            except Exception as e:
                logger.error(f"订阅主题 {topic} 失败: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            self.connected = True
            logger.info("MQTT连接成功")
        else:
            self.connected = False
            logger.error(f"MQTT连接失败，返回码: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        self.connected = False
        if rc != 0:
            logger.warning(f"MQTT意外断开连接，返回码: {rc}")
        else:
            logger.info("MQTT正常断开连接")
    
    def _on_message(self, client, userdata, msg):
        """MQTT消息回调"""
        try:
            # 解码消息负载
            payload = msg.payload.decode('utf-8', errors='ignore')
            
            # 构造消息数据
            message_data = {
                'topic': msg.topic,
                'payload': payload,
                'qos': msg.qos,
                'retain': msg.retain,
                'timestamp': datetime.now().isoformat(),
                'raw_payload': msg.payload.hex() if isinstance(msg.payload, bytes) else None
            }
            
            # 尝试解析JSON负载
            try:
                json_payload = json.loads(payload)
                message_data['json_payload'] = json_payload
            except json.JSONDecodeError:
                # 不是JSON格式，保持原始字符串
                pass
            
            # 使用线程安全队列作为主要方式
            try:
                self.thread_safe_queue.put_nowait(message_data)
            except queue.Full:
                logger.warning("线程安全队列已满，丢弃消息")
                # 如果线程安全队列满了，尝试使用异步队列
                if self.loop and self.message_queue:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.message_queue.put(message_data),
                            self.loop
                        )
                    except RuntimeError as e:
                        logger.warning(f"无法将消息放入异步队列: {e}")
                else:
                    logger.warning("消息队列或事件循环未初始化，消息丢失")
            
        except Exception as e:
            logger.error(f"处理MQTT消息回调失败: {e}")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """MQTT订阅回调"""
        logger.debug(f"MQTT订阅确认，消息ID: {mid}, 授权QoS: {granted_qos}")
    
    def _on_log(self, client, userdata, level, buf):
        """MQTT日志回调"""
        if level <= mqtt.MQTT_LOG_WARNING:
            logger.debug(f"MQTT: {buf}")
    
    async def _process_message(self, message_data: Dict[str, Any]):
        """处理MQTT消息"""
        try:
            # 增强消息数据
            enhanced_data = self._enhance_message_data(message_data)
            
            # 标准化数据格式
            event = self.normalize_data(enhanced_data)

            if event and event.event_type != ExternalEventType.heartbeat:
                # 触发事件处理
                await self.emit_event(event)
            
        except Exception as e:
            logger.error(f"处理MQTT消息失败: {e}")
    
    def _enhance_message_data(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强消息数据，添加更多上下文信息"""
        enhanced = message_data.copy()

        # 如果有JSON负载，将其作为主要数据
        if 'json_payload' in message_data:
            enhanced = message_data['json_payload']
        
        # 添加MQTT特定信息
        enhanced['mqtt_topic'] = message_data['topic']
        enhanced['mqtt_qos'] = message_data['qos']
        enhanced['mqtt_retain'] = message_data['retain']
        
        # 从主题提取设备信息（如果遵循约定格式）
        topic_parts = message_data['topic'].split('/')
        if len(topic_parts) >= 2:
            enhanced['device_from_topic'] = topic_parts[1]  # 假设格式为 /device_id/...
        
        # 添加消息类型推断
        if 'type' not in enhanced:
            enhanced['type'] = self._infer_message_type(message_data['topic'], enhanced)
        
        return enhanced
    
    def _infer_message_type(self, topic: str, data: Dict) -> str:
        """根据主题和数据推断消息类型"""
        topic_lower = topic.lower()
        
        # 常见主题模式匹配
        if 'alarm' in topic_lower or 'alert' in topic_lower:
            return 'alarm'
        elif 'detect' in topic_lower or 'detection' in topic_lower:
            return 'detection'
        elif 'status' in topic_lower or 'heartbeat' in topic_lower:
            return 'status'
        elif 'command' in topic_lower or 'cmd' in topic_lower:
            return 'command'
        else:
            return 'other'
    