"""
事件订阅管理模块 - 管理监听摄像头主动上报的不同类型数据事件订阅配置
基于NetSDK开发包实现真实的设备连接和事件订阅
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import uuid
import os

# NetSDK相关导入
try:
    from NetSDK.NetSDK import NetClient
    from NetSDK.SDK_Struct import *
    from NetSDK.SDK_Enum import *
    from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect, fMessCallBackEx1, fVideoStatSumCallBack, CB_FUNCTYPE
    # from ctypes import cast, POINTER, c_char, c_long, c_llong, c_dword, c_ldword
    NETSDK_AVAILABLE = True
except ImportError:
    NETSDK_AVAILABLE = False
    logging.warning("NetSDK包未安装，请检查NetSDK包是否正确安装")

from sqlalchemy.orm import Session
from src.database import (
    SessionLocal, Device, SmartScheme, SmartEvent, 
    EventStatus, get_db
)

logger = logging.getLogger(__name__)


@dataclass
class DeviceConnection:
    """设备连接信息"""
    device_id: str  # 存储设备ID而不是Device对象
    device_name: str  # 存储设备名称
    ip_address: str  # 存储设备IP
    port: int  # 存储设备端口
    username: str  # 存储用户名
    password: str  # 存储密码
    login_id: int = 0 # 登录ID
    attach_id: int = 0 # 视频统计摘要ID
    is_connected: bool = False # 是否连接
    schemes: List[str] = None  # 该设备上的订阅ID列表
    alarm_interval: int = 0  # 报警间隔时间
    last_heartbeat: Optional[datetime] = None # 上次心跳时间
    last_alarm_time: Optional[datetime] = None  # 上次报警时间，用于控制报警间隔
    push_tags: List[str] = None  # 推送标签
    event_types: List[str] = None  # 事件类型

    def __post_init__(self):
        if self.schemes is None:
            self.schemes = []


class SmartSchemer:
    """事件订阅管理器"""
    
    def __init__(self):
        self.device_connections: Dict[str, DeviceConnection] = {}  # device_id -> DeviceConnection
        self.scheme_connections: Dict[str, str] = {}  # scheme_id -> device_id
        self.running = False
        self._lock = threading.Lock()
        
        if NETSDK_AVAILABLE:
            # NetSDK用到的相关变量和回调
            self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
            self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)
            self.m_MessCallBackEx1 = fMessCallBackEx1(self.MessCallBackEx1)
            self.m_VideoStatSumCallBack = fVideoStatSumCallBack(self.VideoStatSumCallBack)
            # 获取NetSDK对象并初始化
            self.sdk = NetClient()
            self.sdk.InitEx(self.m_DisConnectCallBack)
            self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)
            # 设置报警回调函数
            self.sdk.SetDVRMessCallBackEx1(self.m_MessCallBackEx1, 0)
        else:
            self.sdk = None
    
    async def initialize(self):
        """初始化管理器"""
        try:
            # 从数据库加载所有启用的订阅配置
            await self._load_schemes()
            
            # 启动监控线程
            self.running = True
            asyncio.create_task(self._monitor_loop())
            
        except Exception as e:
            raise
    
    async def _load_schemes(self):
        """从数据库加载订阅配置"""
        try:
            db = SessionLocal()
            try:
                # 获取所有运行中的订阅
                schemes = db.query(SmartScheme).filter(SmartScheme.status == 'running').all()
                
                for scheme in schemes:
                    await self._start_scheme_internal(scheme, db)
                    
                logger.info(f"加载了 {len(schemes)} 个运行中的订阅")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"加载订阅配置失败: {e}")
    
    async def _start_scheme_internal(self, scheme: SmartScheme, db: Session):
        """内部启动订阅"""
        try:
            device = db.query(Device).filter(Device.device_id == scheme.camera_id).first()
            if not device:
                logger.error(f"设备不存在: {scheme.camera_id}")
                return False
            
            # 检查设备连接
            if scheme.camera_id not in self.device_connections:
                # 创建新的设备连接
                device_conn = DeviceConnection(
                    device_id=device.device_id,
                    device_name=device.device_name,
                    ip_address=device.ip_address,
                    port=scheme.camera_port,
                    username=device.username,
                    password=device.password,
                    alarm_interval=scheme.alarm_interval,
                    push_tags=scheme.push_tags.split(','),
                    event_types=scheme.event_types
                )
                self.device_connections[scheme.camera_id] = device_conn
                
                # 登录设备
                if not await self._login_device(device_conn):
                    logger.error(f"设备登录失败: {device.device_name}")
                    return False

            device_conn = self.device_connections[scheme.camera_id]
            
            # 检查订阅是否已经存在，避免重复添加
            if scheme.id not in device_conn.schemes:
                # 根据事件类型启动相应的订阅
                for event_type in scheme.event_types:
                    if event_type == 'alarm':
                        await self._start_alarm_listen(device_conn, scheme)
                    elif event_type == 'smart':
                        await self._start_smart_listen(device_conn, scheme)
                
                # 记录订阅关系 
                device_conn.schemes.append(scheme.id)
                self.scheme_connections[scheme.id] = scheme.camera_id
            else:
                logger.info(f"订阅 {scheme.id} 已存在，跳过重复启动")
          
            # 更新数据库状态
            scheme.started_at = datetime.now()
            scheme.updated_at = datetime.now()
            db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"启动订阅失败: {scheme.id}, 错误: {e}")
            return False
    
    async def _login_device(self, device_conn: DeviceConnection) -> bool:
        """登录设备"""
        try:
            stuInParam = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
            stuInParam.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
            stuInParam.szIP = device_conn.ip_address.encode()
            stuInParam.nPort = device_conn.port
            stuInParam.szUserName = device_conn.username.encode()
            stuInParam.szPassword = device_conn.password.encode()
            stuInParam.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
            stuInParam.pCapParam = None

            stuOutParam = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
            stuOutParam.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)
            
            loginID, device_info, error_msg = self.sdk.LoginWithHighLevelSecurity(stuInParam, stuOutParam)
            
            if loginID != 0:
                device_conn.login_id = loginID
                device_conn.is_connected = True
                device_conn.last_heartbeat = datetime.now()
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"设备登录异常: {device_conn.device.device_name}, 错误: {e}")
            return False
    
    async def _start_alarm_listen(self, device_conn: DeviceConnection, scheme: SmartScheme):
        """启动报警事件订阅"""      
        try:
            result = self.sdk.StartListenEx(device_conn.login_id)
            if result:
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"启动报警事件订阅异常: {scheme.id}, 错误: {e}")
            return False
    
    async def _start_smart_listen(self, device_conn: DeviceConnection, scheme: SmartScheme):
        """启动智能事件订阅"""       
        try:
            # 启动视频统计摘要订阅
            inParam = NET_IN_ATTACH_VIDEOSTAT_SUM()
            inParam.dwSize = sizeof(NET_IN_ATTACH_VIDEOSTAT_SUM)
            inParam.nChannel = 0  # 默认通道
            inParam.cbVideoStatSum = self.m_VideoStatSumCallBack
            outParam = NET_OUT_ATTACH_VIDEOSTAT_SUM()
            outParam.dwSize = sizeof(NET_OUT_ATTACH_VIDEOSTAT_SUM)
            
            attachID = self.sdk.AttachVideoStatSummary(device_conn.login_id, inParam, outParam, 5000)
            if attachID != 0:
                device_conn.attach_id = attachID
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"启动智能事件订阅异常: {scheme.id}, 错误: {e}")
            return False
    
    async def start_scheme(self, scheme_id: str) -> bool:
        """启动订阅"""
        try:
            db = SessionLocal()
            try:
                scheme = db.query(SmartScheme).filter(SmartScheme.id == scheme_id).first()
                if not scheme:
                    return False
                
                if scheme.status == 'running':
                    return True
                
                success = await self._start_scheme_internal(scheme, db)
                if success:
                    scheme.status = 'running'
                    db.commit()
                else:
                    scheme.status = 'error'
                    db.commit()
                
                return success
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"启动订阅异常: {scheme_id}, 错误: {e}")
            return False
    
    async def stop_scheme(self, scheme_id: str) -> bool:
        """停止订阅"""
        try:
            db = SessionLocal()
            try:
                scheme = db.query(SmartScheme).filter(SmartScheme.id == scheme_id).first()
                if not scheme:
                    logger.error(f"订阅不存在: {scheme_id}")
                    return False
                
                # 从连接管理中移除
                device_id = self.scheme_connections.pop(scheme_id, None)
                if device_id and device_id in self.device_connections:
                    device_conn = self.device_connections[device_id]
                    if scheme_id in device_conn.schemes:
                        device_conn.schemes.remove(scheme_id)
                    
                    # 如果设备没有其他订阅，则登出设备
                    if not device_conn.schemes:
                        await self._logout_device(device_conn)
                        del self.device_connections[device_id]
                
                # 更新数据库状态
                scheme.status = 'stopped'
                scheme.stopped_at = datetime.now()
                scheme.updated_at = datetime.now()
                db.commit()
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"停止订阅异常: {scheme_id}, 错误: {e}")
            return False
    
    async def _logout_device(self, device_conn: DeviceConnection):
        """登出设备"""       
        try:
            if device_conn.login_id > 0:
                # 停止事件订阅
                if device_conn.attach_id > 0:
                    self.sdk.DetachVideoStatSummary(device_conn.attach_id)
                self.sdk.StopListen(device_conn.login_id)
                # 登出
                result = self.sdk.Logout(device_conn.login_id)
                if result:
                    pass
                else:
                    pass
                
                device_conn.is_connected = False
                device_conn.login_id = 0
                device_conn.attach_id = 0
                
        except Exception as e:
            logger.error(f"设备登出异常: {device_conn.device_name}, 错误: {e}")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                await self._check_connections()
                await self._update_heartbeats()
                await asyncio.sleep(30)  # 每30秒检查一次
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(60)  # 异常时等待更长时间
    
    async def _check_connections(self):
        """检查连接状态"""
        for device_id, device_conn in list(self.device_connections.items()):
            if not device_conn.is_connected:
                # logger.warning(f"设备连接断开: {device_conn.device_name}")
                # 尝试重新连接
                await self._reconnect_device(device_conn)
    
    async def _reconnect_device(self, device_conn: DeviceConnection):
        """重新连接设备"""
        try:         
            # 重新登录
            if await self._login_device(device_conn):
                # logger.info(f"重新启动该设备上的所有订阅: {device_conn.schemes}")
                
                # 重新启动该设备上的所有订阅的事件监听
                db = SessionLocal()
                try:
                    for scheme_id in device_conn.schemes:
                        scheme = db.query(SmartScheme).filter(SmartScheme.id == scheme_id).first()
                        if scheme and scheme.status == 'running':
                            # 只重新启动事件监听，不重新创建订阅关系
                            await self._restart_event_listeners(device_conn, scheme)
                finally:
                    db.close()
                
                # logger.info(f"设备重新连接成功: {device_conn.device_name}")
            else:
                logger.error(f"设备重新连接失败: {device_conn.device_name}")
                
        except Exception as e:
            logger.error(f"重新连接设备异常: {device_conn.device_name}, 错误: {e}")
    
    async def _restart_event_listeners(self, device_conn: DeviceConnection, scheme: SmartScheme):
        """重新启动事件监听（不重新创建订阅关系）"""
        try:
            # logger.info(f"重新启动事件监听: 设备={device_conn.device_name}, 订阅={scheme.id}")
            
            # 确保订阅关系映射正确
            if scheme.id not in self.scheme_connections:
                self.scheme_connections[scheme.id] = device_conn.device_id
            
            # 根据事件类型重新启动相应的订阅
            for event_type in scheme.event_types:
                if event_type == 'alarm':
                    await self._start_alarm_listen(device_conn, scheme)
                elif event_type == 'smart':
                    await self._start_smart_listen(device_conn, scheme)
            
            # logger.info(f"事件监听重新启动成功: 订阅={scheme.id}")
            return True
            
        except Exception as e:
            logger.error(f"重新启动事件监听失败: {scheme.id}, 错误: {e}")
            return False
    
    async def _update_heartbeats(self):
        """更新心跳时间"""
        for device_conn in self.device_connections.values():
            if device_conn.is_connected:
                device_conn.last_heartbeat = datetime.now()
    
    def _create_smart_event(self, scheme_id: str, event_type: str, title: str, 
                           description: str = None, priority: str = 'normal', 
                           event_data: Dict = None):
        """创建智能事件记录"""
        try:
            db = SessionLocal()
            try:
                event = SmartEvent(
                    scheme_id=scheme_id,
                    event_type=event_type,
                    title=title,
                    description=description,
                    priority=priority,
                    event_data=event_data,
                    status='pending',
                    timestamp=datetime.now()
                )
                
                db.add(event)
                db.commit()
                db.refresh(event)
                
                return event
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"创建智能事件失败: {e}")
            return None
    
    # NetSDK回调函数
    def VideoStatSumCallBack(self, lAttachHandle, pBuf, dwBufLen, dwUser):
        """视频统计摘要回调函数"""
        try:            
            # 查找对应的订阅
            for device_conn in self.device_connections.values():
                if device_conn.attach_id == lAttachHandle:  # 根据attach_id查找对应的订阅
                    for scheme_id in device_conn.schemes:
                        # 正确转换结构体指针
                        info = cast(pBuf, POINTER(NET_VIDEOSTAT_SUMMARY)).contents
                        
                        # 检查报警间隔时间
                        if info.nInsidePeopleNum > 0 and device_conn.alarm_interval > 0:
                            # 检查间隔时间
                            if device_conn.last_alarm_time is None:
                                # 第一次报警，允许通过，并记录当前时间
                                device_conn.last_alarm_time = datetime.now()
                            else:
                                time_diff = datetime.now() - device_conn.last_alarm_time
                                if time_diff.total_seconds() < device_conn.alarm_interval:
                                    return
                                else:
                                    device_conn.last_alarm_time = datetime.now()                                      
                        
                        event_data={
                                'cameraInfo': device_conn.device_name + ":" + device_conn.ip_address,
                                'deviceId': device_conn.device_id,
                                'enteredCount': info.stuEnteredSubtotal.nToday,
                                'exitedCount': info.stuExitedSubtotal.nToday,
                                'stayingCount': info.nInsidePeopleNum,
                                'passedCount': info.stuPassedSubtotal.nToday,
                                'recordTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'event_description': f'区域内人数={info.nInsidePeopleNum}, 今日进入={info.stuEnteredSubtotal.nToday}, 今日离开={info.stuExitedSubtotal.nToday}, 今日通过={info.stuPassedSubtotal.nToday}'
                            }

                        # 调用现有的数据推送功能
                        try:
                            from src.data_pusher import data_pusher
                            data_pusher.push_data(
                                data=event_data,
                                tags=device_conn.push_tags
                            )
                        except Exception as push_error:
                            logger.error(f"数据推送失败: {push_error}")
                        
                        # 创建智能事件
                        self._create_smart_event(
                            scheme_id=scheme_id,
                            event_type='smart',
                            title=f'客流统计(区域人数)' if info.nInsidePeopleNum > 0 else f'客流统计(人流统计)',
                            description=f'区域内人数={info.nInsidePeopleNum}, 今日进入={info.stuEnteredSubtotal.nToday}, 今日离开={info.stuExitedSubtotal.nToday}',
                            priority='normal',
                            event_data=event_data
                        )
                    break
                    
        except Exception as e:
            logger.error(f"处理视频统计摘要回调异常: {e}")

    def MessCallBackEx1(self, lCommand, lLoginID, pBuf, dwBufLen, pchDVRIP, nDVRPort, bAlarmAckFlag, nEventID, dwUser):
        """消息回调函数"""
        try:       
            # 报警类型转换
            try:
                alarm_type = SDK_ALARM_TYPE(lCommand) # 报警类型
                
            except (ValueError, TypeError):
                return

            # if alarm_type == SDK_ALARM_TYPE.VIDEOLOST_ALARM_EX:  # 视频丢失报警
            #     info = cast(pBuf, POINTER(NET_A_ALARM_VIDEO_LOSS_INFO)).contents
            #     if info.nAction == 1:
            #         logger.info(f"视频丢失报警开始: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            #     elif info.nAction == 2:
            #         logger.info(f"视频丢失报警结束: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            #     else:
            #         return
            # elif alarm_type == SDK_ALARM_TYPE.SHELTER_ALARM_EX:  # 视频遮挡报警
            #     info = cast(pBuf, POINTER(NET_A_DEV_EVENT_ALARM_VIDEOBLIND)).contents
            #     logger.info(f"视频遮挡报警{info.szName}: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            # elif alarm_type == SDK_ALARM_TYPE.EVENT_MOTIONDETECT:  # 视频移动侦测事件
            #     info = cast(pBuf, POINTER(ALARM_MOTIONDETECT_INFO)).contents
            #     if info.nEventAction == 1:
            #         logger.info(f"视频移动侦测事件开始: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            #     elif info.nEventAction == 2:
            #         logger.info(f"视频移动侦测事件结束: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            #     else:
            #         return
            
            if alarm_type == SDK_ALARM_TYPE.EVENT_CROSSREGION_DETECTION:  # 警戒区事件                
                info = cast(pBuf, POINTER(DEV_EVENT_CROSSREGION_INFO)).contents
                if info.bEventAction == 0 or info.bEventAction == 1 or info.bEventAction == 2:
                    pass
                else:
                    return
                #     logger.info(f"警戒区事件开始{info.szName}: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                #     logger.info(f"入侵方向:{info.bDirection},检测动作类型:{info.bActionType}，累计触发次数:{info.nOccurrenceCount},{info.nObjetcHumansNum}人")
                # elif info.bEventAction == 2:
                #     logger.info(f"警戒区事件结束{info.szName}: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                #     logger.info(f"入侵方向:{info.bDirection},检测动作类型:{info.bActionType}，累计触发次数:{info.nOccurrenceCount},{info.nObjetcHumansNum}人")
                # else:
                #     return
            elif alarm_type == SDK_ALARM_TYPE.EVENT_CROSSLINE_DETECTION:  # 警戒线事件
                info = cast(pBuf, POINTER(DEV_EVENT_CROSSLINE_INFO)).contents
                if info.bEventAction == 0 or info.bEventAction == 1 or info.bEventAction == 2:
                    pass
                else:
                    return
                #     logger.info(f"警戒线事件开始{info.szName}: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                #     logger.info(f"入侵方向:{info.bDirection}，累计触发次数:{info.nOccurrenceCount},{info.nObjetcHumansNum}人")
                # elif info.bEventAction == 2:
                #     logger.info(f"警戒线事件结束{info.szName}: LoginID={lLoginID},通道={info.nChannelID},当前时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                #     logger.info(f"入侵方向:{info.bDirection}，累计触发次数:{info.nOccurrenceCount},{info.nObjetcHumansNum}人")
                # else:
                #     return
            else:
                return
            
            # 查找对应的订阅
            for device_conn in self.device_connections.values():
                if device_conn.login_id == lLoginID:
                    for scheme_id in device_conn.schemes:
                        event_data={}
                        if alarm_type == SDK_ALARM_TYPE.EVENT_CROSSREGION_DETECTION:  # 警戒区事件
                            info = cast(pBuf, POINTER(DEV_EVENT_CROSSREGION_INFO)).contents
                            if info.bEventAction == 0 or info.bEventAction == 1:
                                event_data={
                                    'cameraInfo': device_conn.device_name + ":" + device_conn.ip_address,
                                    'deviceId': device_conn.device_id,
                                    'direction': '0:进入' if info.bDirection == 0 else '1:离开' if info.bDirection == 1 else '2:出现' if info.bDirection == 2 else '3:消失',
                                    'actionType': '0:出现' if info.bActionType == 0 else '1:消失' if info.bActionType == 1 else '2:在区域内' if info.bActionType == 2 else '3:穿越区域',
                                    'occurrenceCount': f'累计触发{info.nOccurrenceCount}次',
                                    'recordTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'event_description': f'设备 {device_conn.device_name} + {device_conn.ip_address} 触发区域入侵事件',
                                    'bEventAction': info.bEventAction
                                }
                        if alarm_type == SDK_ALARM_TYPE.EVENT_CROSSLINE_DETECTION:  # 警戒线事件
                            info = cast(pBuf, POINTER(DEV_EVENT_CROSSLINE_INFO)).contents
                            if info.bEventAction == 0 or info.bEventAction == 1:
                                event_data={
                                    'cameraInfo': device_conn.device_name + ":" + device_conn.ip_address,
                                    'deviceId': device_conn.device_id,
                                    'direction': '0:进入' if info.bDirection == 0 else '1:离开' if info.bDirection == 1 else '2:出现' if info.bDirection == 2 else '3:消失',
                                    'occurrenceCount': f'累计触发{info.nOccurrenceCount}次',
                                    'recordTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'event_description': f'设备 {device_conn.device_name} + {device_conn.ip_address} 触发绊线入侵事件',
                                    'bEventAction': info.bEventAction
                                }
                        # 推送事件
                        
                        try:
                            from src.data_pusher import data_pusher
                            data_pusher.push_data(
                                data=event_data,
                                tags=device_conn.push_tags
                            )
                        except Exception as push_error:
                            logger.error(f"数据推送失败: {push_error}")
                        
                        # 创建报警事件
                        self._create_smart_event(
                            scheme_id=scheme_id,
                            event_type='alarm',
                            title=f'报警事件(区域入侵)'if alarm_type == SDK_ALARM_TYPE.EVENT_CROSSREGION_DETECTION else f'报警事件(绊线入侵)',
                            description=f'设备 {device_conn.device_name}:{device_conn.ip_address} 触发(区域入侵)'if alarm_type == SDK_ALARM_TYPE.EVENT_CROSSREGION_DETECTION else f'设备 {device_conn.device_name}:{device_conn.ip_address} 触发(绊线入侵)',
                            priority='high',
                            event_data=event_data
                        )
                    break
                    
        except Exception as e:
            logger.error(f"处理报警回调异常: {e}")
    
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        """断开连接回调函数"""
        try:  
            # 查找对应的设备
            for device_conn in self.device_connections.values():
                if device_conn.login_id == lLoginID:
                    device_conn.is_connected = False
                    
                    if device_conn.event_types is not None and 'system_log' in device_conn.event_types:
                
                        # 为所有相关订阅创建系统日志事件
                        for scheme_id in device_conn.schemes:
                            self._create_smart_event(
                                scheme_id=scheme_id,
                                event_type='system_log',
                                title='设备断开连接',
                                description=f'设备 {device_conn.device_name} + {device_conn.ip_address} 连接断开',
                                priority='high',
                                event_data={
                                    'cameraInfo': device_conn.device_name + ":" + device_conn.ip_address,
                                    'deviceId': device_conn.device_id,
                                    'recordTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'event_description': f'设备 {device_conn.device_name} + {device_conn.ip_address} 连接断开'
                                }
                            )
                        break
                    
        except Exception as e:
            logger.error(f"处理断开连接回调异常: {e}")
    
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        """重新连接回调函数"""
        try:  
            # 查找对应的设备
            for device_conn in self.device_connections.values():
                if device_conn.login_id == lLoginID:
                    # device_conn.is_connected = True
                    # device_conn.last_heartbeat = datetime.now()
                    
                    # 重新启动该设备上的所有订阅
                    # db = SessionLocal()
                    # try:
                    #     for scheme_id in device_conn.schemes:
                    #         scheme = db.query(SmartScheme).filter(SmartScheme.id == scheme_id).first()
                    #         if scheme and scheme.status == 'running':
                    #             await self._restart_event_listeners(device_conn, scheme)
                    # finally:
                    #     db.close()

                    if device_conn.event_types is not None and 'system_log' in device_conn.event_types:
                        # 为所有相关订阅创建系统日志事件
                        for scheme_id in device_conn.schemes:
                            self._create_smart_event(
                                scheme_id=scheme_id,
                                event_type='system_log',
                                title='设备重新连接',
                                description=f'设备 {device_conn.device_name} + {device_conn.ip_address} 重新连接成功',
                                priority='normal',
                                event_data={
                                    'cameraInfo': device_conn.device_name + ":" + device_conn.ip_address,
                                    'deviceId': device_conn.device_id,
                                    'recordTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'event_description': f'设备 {device_conn.device_name} + {device_conn.ip_address} 重新连接成功'
                                }
                            )
                        break
                    
        except Exception as e:
            logger.error(f"处理重新连接回调异常: {e}")

    async def shutdown(self):
        """关闭管理器"""
        try:
            logger.info("正在关闭事件订阅管理器...")
            
            self.running = False
            
            # 停止所有订阅
            for device_conn in list(self.device_connections.values()):
                await self._logout_device(device_conn)
            
            # 清理NetSDK
            if NETSDK_AVAILABLE and self.sdk:
                self.sdk.Cleanup()
            
            logger.info("事件订阅管理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭事件订阅管理器失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        status = {
            'running': self.running,
            'device_connections': len(self.device_connections),
            'scheme_connections': len(self.scheme_connections),
            'devices': []
        }
        
        for device_id, device_conn in self.device_connections.items():
            status['devices'].append({
                'device_id': device_id,
                'device_name': device_conn.device_name,
                'is_connected': device_conn.is_connected,
                'login_id': device_conn.login_id,
                'scheme_count': len(device_conn.schemes),
                'last_heartbeat': device_conn.last_heartbeat.isoformat() if device_conn.last_heartbeat else None
            })
        
        return status
      
# 全局实例
smart_schemer = SmartSchemer()
