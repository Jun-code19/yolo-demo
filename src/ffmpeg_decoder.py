import ffmpeg
import numpy as np
import threading
import time
import logging
import psutil
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from typing import Optional, Tuple, Dict, Any
import subprocess
import os

logger = logging.getLogger(__name__)

class FFmpegDecoder:
    """FFmpeg视频解码器"""
    
    def __init__(self, rtsp_url: str, max_workers: int = 4, buffer_size: int = 2):
        self.rtsp_url = rtsp_url
        self.max_workers = max_workers
        self.buffer_size = buffer_size
        
        # 状态变量
        self.is_running = False
        self.process = None
        self.read_thread = None
        
        # 帧缓冲
        self.frame_buffer = deque(maxlen=1)
        self.lock = threading.Lock()
        
        # 统计信息
        self.frame_count = 0
        self.last_frame_time = 0
        self.decode_times = []
        self.cpu_usage_history = []
        
        # 连接参数
        self.connection_retries = 3
        self.retry_delay = 2
        self.width = None
        self.height = None
        self.frame_size = None
        
        # 解码线程池
        self.decoder_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # 调试信息
        self.debug_mode = True
        self.last_error = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10
        
        # 自适应缓冲区
        self.adaptive_buffer = True
        self.buffer_adjustment_interval = 10  # 每10秒调整一次
        self.last_buffer_adjustment = time.time()
        self.read_failure_rate = 0.0
        self.read_attempts = 0
        self.read_successes = 0

    def _create_ffmpeg_process(self) -> Optional[Any]:
        """创建FFmpeg进程"""
        try:
            # 使用简化的FFmpeg参数，避免兼容性问题
            process = (
                ffmpeg
                .input(
                    self.rtsp_url,
                    rtsp_transport='tcp',      # 使用TCP避免UDP丢包
                    timeout=5000000            # 5秒超时
                )
                .output(
                    'pipe:',
                    format='rawvideo',
                    pix_fmt='bgr24',           # OpenCV兼容的像素格式
                    r=25,                      # 固定帧率25fps
                    acodec='none'              # 不处理音频
                )
                .run_async(pipe_stdout=True, pipe_stderr=True, quiet=False)
            )
            return process
        except Exception as e:
            logger.error(f"创建FFmpeg进程失败: {e}")
            return None

    def _decode_frame_worker(self, frame_data: bytes, width: int, height: int) -> Optional[np.ndarray]:
        """解码帧的工作函数"""
        try:
            start_time = time.time()
            
            # 将字节数据转换为numpy数组
            frame = np.frombuffer(frame_data, dtype=np.uint8)
            frame = frame.reshape((height, width, 3))
            
            decode_time = time.time() - start_time
            self.decode_times.append(decode_time)

            return frame
        except Exception as e:
            logger.error(f"解码帧失败: {e}")
            return None

    def _read_frame_data(self, process: Any, width: int, height: int) -> Optional[np.ndarray]:
        """读取一帧数据"""
        try:
            # 计算一帧的字节数 (BGR24格式: width * height * 3)
            frame_size = width * height * 3
            
            # 检查进程状态
            if process.poll() is not None:
                logger.warning("FFmpeg进程已退出")
                return None
            
            # 直接读取帧数据（Windows兼容）
            frame_data = process.stdout.read(frame_size)
            if not frame_data:
                print("---获取帧数据失败:frame_data is None---")
                return None
            
            if len(frame_data) != frame_size:
                if self.debug_mode:
                    logger.debug(f"帧数据大小不匹配: 期望{frame_size}, 实际{len(frame_data)}")
                return None
            
            # 直接解码，不使用线程池避免复杂性
            frame = self._decode_frame_worker(frame_data, width, height)
            return frame
            
        except Exception as e:
            logger.error(f"读取帧数据失败: {e}")
            self.last_error = str(e)
            return None

    def _get_stream_info(self, process: Any = None) -> Tuple[Optional[int], Optional[int]]:
        """获取流信息（宽度和高度）"""
        try:
            # 使用ffprobe获取流信息
            probe = ffmpeg.probe(self.rtsp_url)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')  
            width = int(video_info['width'])
            height = int(video_info['height'])
            return width, height
        except Exception as e:
            logger.error(f"获取流信息失败: {e}")
            # 使用默认分辨率
            return 1920, 1080

    def start(self) -> bool:
        """启动解码器"""
        if self.is_running:
            return True
            
        for attempt in range(self.connection_retries):
            try:               
                # 先获取流信息
                width, height = self._get_stream_info(None)
                if not width or not height:
                    logger.error("无法获取流信息")
                    continue
                
                self.width = width
                self.height = height
                self.frame_size = width * height * 3
                
                # 创建FFmpeg进程
                self.process = self._create_ffmpeg_process()
                if not self.process:
                    logger.error("创建FFmpeg进程失败")
                    continue
                
                # 启动读取线程
                self.is_running = True
                self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
                self.read_thread.start()
                
                # 启动自动重连线程
                self.reconnect_thread = threading.Thread(target=self._auto_reconnect_loop, daemon=True)
                self.reconnect_thread.start()
                
                return True
                
            except Exception as e:
                logger.error(f"启动解码器失败 (第{attempt + 1}次): {e}")
                if self.process:
                    self.process.terminate()
                    self.process = None
                
                if attempt < self.connection_retries - 1:
                    time.sleep(self.retry_delay)
        
        logger.error("FFmpeg解码器启动失败，已达到最大重试次数")
        return False

    def _auto_reconnect_loop(self):
        """自动重连循环"""
        while self.is_running:
            try:
                # 每5秒检查一次，但每0.5秒检查一次停止信号
                for _ in range(10):  # 10 * 0.5 = 5秒
                    if not self.is_running:
                        logger.debug("自动重连循环收到停止信号，退出")
                        return
                    time.sleep(0.5)
                
                # 检查读取线程是否还在运行
                if self.is_running and self.read_thread and not self.read_thread.is_alive():
                    logger.warning("读取线程已停止，尝试重新启动解码器")
                    if self.is_running:  # 再次检查，避免在停止过程中重启
                        self._restart_decoder()
                    
            except Exception as e:
                logger.error(f"自动重连循环出错: {e}")
                if not self.is_running:
                    break
                time.sleep(1)
        
        logger.debug("自动重连循环已退出")

    def _restart_decoder(self):
        """重启解码器"""
        try:
            # 检查是否已经停止
            if not self.is_running:
                logger.debug("解码器已停止，跳过重启")
                return
            
            logger.info("重启FFmpeg解码器...")
            
            # 停止当前进程
            if self.process:
                self.process.terminate()
                self.process = None
            
            # 重置状态
            self.is_running = False
            time.sleep(1)
            
            # 检查是否应该继续重启
            if not self.is_running:
                logger.debug("解码器已停止，取消重启")
                return
            
            # 重新启动
            if self.start():
                logger.info("FFmpeg解码器重启成功")
            else:
                logger.error("FFmpeg解码器重启失败")
                
        except Exception as e:
            logger.error(f"重启解码器失败: {e}")

    def _read_loop(self):
        """读取循环"""
        consecutive_empty_reads = 0
        max_empty_reads = 50  # 增加最大连续空读取次数
        last_success_time = time.time()
        frame_interval = 1.0 / 25  # 25fps的目标间隔
        restart_count = 0
        max_restarts = 3
                
        while self.is_running and self.process:
            try:
                loop_start = time.time()
                
                # 检查是否已停止
                if not self.is_running:
                    logger.debug("读取循环收到停止信号，退出")
                    break
                
                frame = self._read_frame_data(self.process, self.width, self.height)

                if frame is not None:
                    with self.lock:
                        # 如果缓冲区满了，移除最旧的帧
                        # if len(self.frame_buffer) >= self.buffer_size:
                        #     self.frame_buffer.popleft()
                        self.frame_buffer.append(frame)
                        self.frame_count += 1
                        self.last_frame_time = time.time()
                        self.consecutive_failures = 0  # 重置失败计数
                    
                    consecutive_empty_reads = 0  # 重置空读取计数
                    last_success_time = time.time()
                    restart_count = 0  # 重置重启计数
                        
                else:
                    consecutive_empty_reads += 1
                    self.consecutive_failures += 1
                    
                    # 检查进程是否还在运行
                    if self.process and self.process.poll() is not None:
                        logger.warning("FFmpeg进程已退出，尝试重新连接")
                        break
                    
                    # 检查是否长时间没有成功读取帧
                    if time.time() - last_success_time > 10:  # 增加到10秒
                        if restart_count < max_restarts and self.is_running:
                            logger.warning(f"长时间未读取到帧，尝试重启解码器 (第{restart_count + 1}次)")
                            restart_count += 1
                            if self.is_running:
                                self._quick_restart()
                            last_success_time = time.time()  # 重置时间
                            continue
                        else:
                            logger.error("达到最大重启次数，停止解码器")
                            break
                    
                    # 如果连续失败次数过多，尝试重启
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        if restart_count < max_restarts and self.is_running:
                            logger.warning(f"连续失败{self.consecutive_failures}次，尝试重启解码器 (第{restart_count + 1}次)")
                            restart_count += 1
                            if self.is_running:
                                self._quick_restart()
                            continue
                        else:
                            logger.error("达到最大重启次数，停止解码器")
                            break
                
                # 控制循环频率，确保稳定的帧率
                loop_time = time.time() - loop_start
                if loop_time < frame_interval:
                    time.sleep(frame_interval - loop_time)
                    
            except Exception as e:
                logger.error(f"读取循环出错: {e}")
                self.consecutive_failures += 1
                if not self.is_running:
                    break
                time.sleep(0.05)  # 增加出错时的休眠时间
        
        logger.debug("读取循环已退出")
        self.is_running = False

    def _quick_restart(self):
        """快速重启解码器"""
        try:
            # 检查是否已经停止
            if not self.is_running:
                logger.debug("解码器已停止，跳过快速重启")
                return False
            
            logger.info("快速重启FFmpeg解码器...")
            
            # 停止当前进程
            if self.process:
                self.process.terminate()
                self.process = None
            
            # 短暂等待
            time.sleep(0.5)
            
            # 检查是否应该继续重启
            if not self.is_running:
                logger.debug("解码器已停止，取消快速重启")
                return False
            
            # 重新创建进程
            if self.is_running:
                self.process = self._create_ffmpeg_process()
                if not self.process:
                    logger.error("快速重启失败：无法创建FFmpeg进程")
                    return False
                
                # 重置失败计数
                self.consecutive_failures = 0
                
                logger.info("快速重启成功")
                return True
            else:
                logger.debug("解码器已停止，取消快速重启")
                return False
            
        except Exception as e:
            logger.error(f"快速重启失败: {e}")
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """读取一帧（兼容OpenCV的read方法）"""
        if not self.is_running:
            return False, None
        
        # 尝试多次获取帧，提高成功率
        max_attempts = 5  # 减少重试次数，提高实时性
        success = False
        frame = None
        
        for attempt in range(max_attempts):
            with self.lock:
                if self.frame_buffer:
                    frame = self.frame_buffer.popleft()
                    success = True
                    break
            
            # 如果缓冲区为空，等待更短时间
            if attempt < max_attempts - 1:
                if attempt < 2:
                    time.sleep(0.005)  # 前2次快速重试（5ms）
                elif attempt < 4:
                    time.sleep(0.02)   # 中间2次中等等待（20ms）
                else:
                    time.sleep(0.05)   # 最后1次较长等待（50ms）
        
        # 更新统计信息
        self.read_attempts += 1
        if success:
            self.read_successes += 1
        
        # 计算失败率
        if self.read_attempts > 0:
            self.read_failure_rate = 1.0 - (self.read_successes / self.read_attempts)
        
        # 自适应缓冲区调整
        if self.adaptive_buffer and time.time() - self.last_buffer_adjustment > self.buffer_adjustment_interval:
            self._adjust_buffer_size()
            self.last_buffer_adjustment = time.time()
        
        return success, frame

    def _adjust_buffer_size(self):
        """自适应调整缓冲区大小"""
        try:
            current_buffer_size = len(self.frame_buffer)
            
            if self.read_failure_rate > 0.3:  # 失败率超过30%
                # 增加缓冲区大小
                new_buffer_size = min(self.buffer_size + 1, 10)  # 最大10帧
                if new_buffer_size > self.buffer_size:
                    self.buffer_size = new_buffer_size
                    self.frame_buffer = deque(self.frame_buffer, maxlen=new_buffer_size)
                    logger.info(f"增加缓冲区大小到 {new_buffer_size} (失败率: {self.read_failure_rate:.2f})")
                    
            elif self.read_failure_rate < 0.1 and current_buffer_size > 2:  # 失败率低于10%且缓冲区较大
                # 减少缓冲区大小
                new_buffer_size = max(self.buffer_size - 1, 2)  # 最小2帧
                if new_buffer_size < self.buffer_size:
                    self.buffer_size = new_buffer_size
                    self.frame_buffer = deque(self.frame_buffer, maxlen=new_buffer_size)
                    logger.info(f"减少缓冲区大小到 {new_buffer_size} (失败率: {self.read_failure_rate:.2f})")
                    
        except Exception as e:
            logger.error(f"调整缓冲区大小失败: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        with self.lock:
            avg_decode_time = np.mean(self.decode_times) if self.decode_times else 0
            avg_cpu_usage = np.mean(self.cpu_usage_history) if self.cpu_usage_history else 0
            
            return {
                'frame_count': self.frame_count,
                'buffer_size': len(self.frame_buffer),
                'avg_decode_time_ms': avg_decode_time * 1000,
                'avg_cpu_usage': avg_cpu_usage,
                'is_running': self.is_running,
                'thread_pool_size': self.max_workers,
                'consecutive_failures': self.consecutive_failures,
                'last_error': self.last_error
            }

    def stop(self):
        """停止解码器"""
        logger.info("正在停止FFmpeg解码器...")
        
        # 设置停止标志
        self.is_running = False
        
        # 停止FFmpeg进程
        if self.process:
            try:
                logger.debug("终止FFmpeg进程...")
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"终止FFmpeg进程失败: {e}")
                try:
                    self.process.kill()
                except:
                    pass
            finally:
                self.process = None
        
        # 等待读取线程结束
        if self.read_thread and self.read_thread.is_alive():
            logger.debug("等待读取线程结束...")
            try:
                self.read_thread.join(timeout=5)
                if self.read_thread.is_alive():
                    logger.warning("读取线程未能在5秒内结束")
            except Exception as e:
                logger.warning(f"等待读取线程结束失败: {e}")
        
        # 等待自动重连线程结束
        if hasattr(self, 'reconnect_thread') and self.reconnect_thread and self.reconnect_thread.is_alive():
            logger.debug("等待自动重连线程结束...")
            try:
                self.reconnect_thread.join(timeout=5)
                if self.reconnect_thread.is_alive():
                    logger.warning("自动重连线程未能在5秒内结束")
            except Exception as e:
                logger.warning(f"等待自动重连线程结束失败: {e}")
        
        # 清空缓冲区
        with self.lock:
            self.frame_buffer.clear()
        
        # 关闭解码线程池
        if self.decoder_pool:
            self.decoder_pool.shutdown(wait=True)
        
        logger.info("FFmpeg解码器已停止")