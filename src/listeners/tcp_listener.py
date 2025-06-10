import asyncio
import json
import socket
import logging
from typing import Dict, Any
from datetime import datetime

from src.data_listener_manager import BaseListener, UnifiedEvent
from src.database import ListenerType, ExternalEventType

logger = logging.getLogger(__name__)

class TCPListener(BaseListener):
    """TCP监听器实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.server = None
        self.clients = set()
        
        # TCP配置
        self.host = self.connection_config.get('host', '0.0.0.0')
        self.port = self.connection_config.get('port', 8080)
        self.buffer_size = self.connection_config.get('buffer_size', 4096)
        self.encoding = self.connection_config.get('encoding', 'utf-8')
        self.mode = self.connection_config.get('mode', 'server')  # server or client
        
        # 客户端模式配置
        self.remote_host = self.connection_config.get('host', 'localhost')
        self.remote_port = self.connection_config.get('port', 8080)
        self.reconnect_interval = self.connection_config.get('reconnect_interval', 5)
        
        # 数据解析配置
        self.data_format = self.connection_config.get('data_format', 'json')  # json, line, binary
        self.delimiter = self.connection_config.get('delimiter', '\n')
    
    async def connect(self) -> bool:
        """建立TCP连接"""
        try:
            if self.mode == 'server':
                return await self._start_server()
            else:
                return await self._connect_client()
        except Exception as e:
            logger.error(f"TCP连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开TCP连接"""
        try:
            if self.mode == 'server' and self.server:
                self.server.close()
                await self.server.wait_closed()
                self.server = None
                logger.info(f"TCP服务器已关闭: {self.host}:{self.port}")
            
            # 关闭所有客户端连接
            for client in list(self.clients):
                try:
                    client.close()
                    await client.wait_closed()
                except:
                    pass
            self.clients.clear()
            
        except Exception as e:
            logger.error(f"断开TCP连接失败: {e}")
    
    async def listen(self):
        """开始监听TCP数据"""
        try:
            if self.mode == 'server':
                await self._listen_server()
            else:
                await self._listen_client()
        except Exception as e:
            logger.error(f"TCP监听异常: {e}")
            raise
    
    async def _start_server(self) -> bool:
        """启动TCP服务器"""
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port
            )
            
            logger.info(f"TCP服务器已启动: {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"启动TCP服务器失败: {e}")
            return False
    
    async def _connect_client(self) -> bool:
        """连接到TCP服务器"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.remote_host, self.remote_port),
                timeout=10  # 10秒超时
            )
            
            self.clients.add(writer)
            logger.info(f"已连接到TCP服务器: {self.remote_host}:{self.remote_port}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"连接TCP服务器超时: {self.remote_host}:{self.remote_port}")
            return False
        except Exception as e:
            logger.error(f"连接TCP服务器失败: {e}")
            return False
    
    async def _listen_server(self):
        """服务器模式监听"""
        if self.server:
            # 使用当前事件循环，避免创建新的Future
            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP服务器开始监听: {addr}")
            
            try:
                # 直接等待停止信号，而不是使用serve_forever
                while self.running and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"TCP服务器监听异常: {e}")
            finally:
                self.server.close()
                await self.server.wait_closed()
                logger.info("TCP服务器已关闭")
    
    async def _listen_client(self):
        """客户端模式监听"""
        retry_count = 0
        max_retries = 10
        
        while self.running and not self.stop_event.is_set():
            try:
                # 尝试连接
                if retry_count >= max_retries:
                    logger.error(f"TCP客户端重试次数超限({max_retries})，停止尝试连接")
                    break
                
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self.remote_host, self.remote_port),
                        timeout=10
                    )
                    
                    logger.info(f"已连接到TCP服务器: {self.remote_host}:{self.remote_port}")
                    retry_count = 0  # 连接成功，重置重试计数
                    
                    # 处理连接数据
                    try:
                        await self._handle_client_data(reader, writer)
                    finally:
                        writer.close()
                        await writer.wait_closed()
                        logger.info(f"与TCP服务器断开连接: {self.remote_host}:{self.remote_port}")
                    
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
                    retry_count += 1
                    wait_time = min(self.reconnect_interval * retry_count, 60)
                    logger.warning(f"连接TCP服务器失败 (第{retry_count}次): {e}")
                    logger.info(f"{wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                        
            except Exception as e:
                logger.error(f"TCP客户端监听异常: {e}")
                await asyncio.sleep(self.reconnect_interval)
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"新客户端连接: {client_addr}")
        
        self.clients.add(writer)
        
        try:
            await self._handle_client_data(reader, writer)
        except Exception as e:
            logger.error(f"处理客户端 {client_addr} 数据失败: {e}")
        finally:
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            logger.info(f"客户端断开连接: {client_addr}")
    
    async def _handle_client_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端数据"""
        buffer = b''
        
        while self.running and not self.stop_event.is_set():
            try:
                # 设置读取超时，避免长时间阻塞
                data = await asyncio.wait_for(reader.read(self.buffer_size), timeout=1.0)
                if not data:
                    logger.info("连接已关闭，无更多数据")
                    break
                
                buffer += data
                
                # 根据数据格式解析
                if self.data_format == 'json':
                    messages = await self._parse_json_messages(buffer)
                    for message in messages:
                        buffer = buffer[len(message['raw_bytes']):]
                        await self._process_message(message['data'])
                
                elif self.data_format == 'line':
                    messages = await self._parse_line_messages(buffer)
                    for message in messages:
                        buffer = buffer[len(message['raw_bytes']):]
                        await self._process_message(message['data'])
                
                elif self.data_format == 'binary':
                    # 二进制数据处理
                    await self._process_binary_data(buffer)
                    buffer = b''
                
            except asyncio.TimeoutError:
                # 读取超时，继续循环检查停止标志
                continue
            except Exception as e:
                logger.error(f"处理数据失败: {e}")
                break
    
    async def _parse_json_messages(self, buffer: bytes) -> list:
        """解析JSON消息"""
        messages = []
        text = buffer.decode(self.encoding, errors='ignore')
        
        # 尝试解析JSON对象
        start = 0
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # 找到完整的JSON对象
                        json_str = text[start:i+1]
                        try:
                            data = json.loads(json_str)
                            raw_bytes = json_str.encode(self.encoding)
                            messages.append({
                                'data': data,
                                'raw_bytes': raw_bytes
                            })
                            start = i + 1
                        except json.JSONDecodeError:
                            # JSON解析失败，跳过
                            start = i + 1
                        brace_count = 0
        
        return messages
    
    async def _parse_line_messages(self, buffer: bytes) -> list:
        """解析行分隔消息"""
        messages = []
        text = buffer.decode(self.encoding, errors='ignore')
        lines = text.split(self.delimiter)
        
        # 最后一行可能不完整，保留在缓冲区
        for line in lines[:-1]:
            if line.strip():
                try:
                    # 尝试JSON解析
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # 如果不是JSON，作为文本处理
                    data = {"message": line.strip(), "timestamp": datetime.now().isoformat()}
                
                raw_bytes = (line + self.delimiter).encode(self.encoding)
                messages.append({
                    'data': data,
                    'raw_bytes': raw_bytes
                })
        
        return messages
    
    async def _process_binary_data(self, data: bytes):
        """处理二进制数据"""
        # 二进制数据处理逻辑，这里简单转换为十六进制字符串
        hex_data = data.hex()
        message_data = {
            "type": "binary",
            "data": hex_data,
            "size": len(data),
            "timestamp": datetime.now().isoformat()
        }
        await self._process_message(message_data)
    
    async def _process_message(self, data: Dict[str, Any]):
        """处理解析后的消息"""
        try:
            # 标准化数据格式
            event = self.normalize_data(data)
            
            # 触发事件处理
            await self.emit_event(event)
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")

# TCP客户端监听器（主动连接模式）
class TCPClientListener(TCPListener):
    """TCP客户端监听器"""
    
    def __init__(self, config):
        super().__init__(config)
        self.mode = 'client'  # 强制设置为客户端模式 