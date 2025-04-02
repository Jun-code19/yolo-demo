from PyQt5.QtCore import QThread, pyqtSignal
import time
import logging
from .window_capture import WindowCapture

logger = logging.getLogger(__name__)

class WindowCaptureThread(QThread):
    frame_captured = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.capturer = WindowCapture()
        self._running = False
        self.fps = 30
        self.frame_time = 1.0 / self.fps

    def set_target_window(self, title: str) -> bool:
        """设置要捕获的目标窗口"""
        return self.capturer.find_window_by_title(title)

    def get_window_list(self) -> list:
        """获取可用窗口列表"""
        return self.capturer.list_windows()

    def run(self):
        """运行捕获线程"""
        self._running = True
        logger.info("Window capture thread started")
        
        while self._running:
            try:
                start_time = time.time()
                
                # 捕获画面
                frame = self.capturer.capture()
                if frame is not None and frame.size > 0:
                    # 确保帧数据有效
                    if len(frame.shape) == 3 and frame.shape[2] >= 3:
                        self.frame_captured.emit(frame)
                        logger.debug(f"Captured frame shape: {frame.shape}")
                    else:
                        logger.warning(f"Invalid frame shape: {frame.shape}")
                else:
                    logger.warning("Captured frame is None or empty")
                
                # 控制帧率
                elapsed = time.time() - start_time
                if elapsed < self.frame_time:
                    time.sleep(self.frame_time - elapsed)
                    
            except Exception as e:
                logger.error(f"Error in capture thread: {str(e)}")
                time.sleep(0.1)
                
        logger.info("Window capture thread stopped")

    def stop(self):
        """停止捕获线程"""
        logger.info("Stopping window capture thread...")
        self._running = False
        self.wait()  # 等待线程结束
        logger.info("Window capture thread stopped successfully")

    def set_fps(self, fps: int):
        """设置捕获帧率"""
        self.fps = max(1, min(fps, 60))
        self.frame_time = 1.0 / self.fps

    def get_window_info(self) -> dict:
        """获取当前窗口信息"""
        return self.capturer.get_window_info()
