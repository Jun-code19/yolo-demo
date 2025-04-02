import win32gui
import win32ui
import win32con
import win32process
import psutil
import numpy as np
import cv2
import logging
from typing import Tuple, Optional, List, Dict
from ctypes import windll, byref, c_ubyte, Structure, c_void_p, POINTER, sizeof, c_int
from ctypes.wintypes import RECT, DWORD, HWND, HDC, HBITMAP, BOOL

logger = logging.getLogger(__name__)

# 添加 DWMWINDOWATTRIBUTE 枚举
class DWMWINDOWATTRIBUTE:
    DWMWA_NCRENDERING_ENABLED = 1
    DWMWA_CLOAKED = 14

class WindowCapture:
    def __init__(self):
        self.hwnd = None
        self.window_rect = None
        self.border_pixels = 8
        self.titlebar_pixels = 30
        self.running = False
        self.gdiplusToken = c_void_p()
        self._initialize_gdi()
        # 添加特殊进程列表
        self.special_processes = ['msedge.exe', 'chrome.exe', 'firefox.exe', 'bilibili.exe']

    def _initialize_gdi(self):
        """初始化GDI+"""
        try:
            class GdiplusStartupInput(Structure):
                _fields_ = [
                    ("GdiplusVersion", c_void_p),
                    ("DebugEventCallback", c_void_p),
                    ("SuppressBackgroundThread", c_void_p),
                    ("SuppressExternalCodecs", c_void_p)
                ]
            startup_input = GdiplusStartupInput()
            startup_input.GdiplusVersion = 1
            windll.gdiplus.GdiplusStartup(byref(self.gdiplusToken), byref(startup_input), None)
        except Exception as e:
            logger.error(f"GDI+初始化失败: {str(e)}")

    def _is_window_cloaked(self, hwnd) -> bool:
        """检查窗口是否被隐藏"""
        try:
            cloaked = c_int(0)
            windll.dwmapi.DwmGetWindowAttribute(
                hwnd,
                DWMWINDOWATTRIBUTE.DWMWA_CLOAKED,
                byref(cloaked),
                sizeof(c_int)
            )
            return bool(cloaked.value)
        except:
            return False

    def list_processes(self) -> List[Dict]:
        """获取所有运行中的进程信息"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                def callback(hwnd, hwnds):
                    if win32gui.IsWindowVisible(hwnd):
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid == proc.pid:
                            title = win32gui.GetWindowText(hwnd)
                            if title:  # 只添加有窗口标题的进程
                                hwnds.append({
                                    'pid': pid,
                                    'name': proc.name(),
                                    'title': title,
                                    'hwnd': hwnd
                                })
                    return True

                hwnds = []
                win32gui.EnumWindows(callback, hwnds)
                processes.extend(hwnds)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return sorted(processes, key=lambda x: x['name'].lower())

    def find_window_by_pid_and_title(self, pid: int, title: str) -> bool:
        """通过PID和窗口标题查找窗口"""
        try:
            def callback(hwnd, target):
                if win32gui.IsWindowVisible(hwnd):
                    _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
                    w_title = win32gui.GetWindowText(hwnd)
                    if w_pid == pid and w_title == title:
                        target['hwnd'] = hwnd
                return True

            target = {'hwnd': None}
            win32gui.EnumWindows(callback, target)
            
            if target['hwnd']:
                self.hwnd = target['hwnd']
                self.window_rect = win32gui.GetWindowRect(self.hwnd)
                return True
            return False
            
        except Exception as e:
            logger.error(f"查找窗口时出错: {str(e)}")
            return False

    def capture(self) -> Optional[np.ndarray]:
        """捕获窗口画面"""
        try:
            if not self.hwnd:
                return None

            # 获取进程名
            _, pid = win32process.GetWindowThreadProcessId(self.hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name().lower()
            except:
                process_name = ""

            # 获取窗口尺寸
            rect = win32gui.GetWindowRect(self.hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            if width <= 0 or height <= 0:
                return None

            # 创建设备上下文
            hwndDC = win32gui.GetWindowDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # 创建位图
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 根据进程类型选择不同的捕获方法
            if process_name in self.special_processes or self._is_window_cloaked(self.hwnd):
                # 使用 PrintWindow 的特殊模式
                result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT = 3
            else:
                # 尝试使用 BitBlt
                try:
                    saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                    result = 1
                except:
                    # 如果 BitBlt 失败，回退到 PrintWindow
                    result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 3)

            if result == 0:
                # 如果第一次尝试失败，使用备用方法
                result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 2)  # PW_CLIENTONLY = 2
                if result == 0:
                    logger.warning("All capture methods failed")
                    return None

            # 获取位图信息
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            # 转换为numpy数组
            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img.shape = (height, width, 4)

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)

            # 转换为RGB格式
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

            # 检查图像是否全黑
            if np.mean(img) < 1.0:
                logger.warning("Captured image appears to be black")
                # 尝试备用捕获方法
                return self._fallback_capture()

            return img

        except Exception as e:
            logger.error(f"捕获窗口画面时出错: {str(e)}")
            return None

    def _fallback_capture(self) -> Optional[np.ndarray]:
        """备用捕获方法"""
        try:
            if not self.hwnd:
                return None

            # 获取窗口尺寸
            rect = win32gui.GetWindowRect(self.hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # 使用 BITBLT 和 PrintWindow 的组合方法
            hwndDC = win32gui.GetWindowDC(self.hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 尝试不同的 PrintWindow 标志
            flags = [3, 2, 0]  # PW_RENDERFULLCONTENT = 3, PW_CLIENTONLY = 2, 0 = 默认
            success = False

            for flag in flags:
                result = windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), flag)
                if result != 0:
                    success = True
                    break

            if not success:
                return None

            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype=np.uint8)
            img.shape = (height, width, 4)

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwndDC)

            # 转换为RGB格式
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

            return img

        except Exception as e:
            logger.error(f"备用捕获方法失败: {str(e)}")
            return None

    def get_window_info(self) -> dict:
        """获取窗口信息"""
        if not self.hwnd:
            return {}
            
        try:
            _, pid = win32process.GetWindowThreadProcessId(self.hwnd)
            rect = win32gui.GetWindowRect(self.hwnd)
            title = win32gui.GetWindowText(self.hwnd)
            
            return {
                'pid': pid,
                'title': title,
                'position': (rect[0], rect[1]),
                'size': (rect[2] - rect[0], rect[3] - rect[1])
            }
        except Exception as e:
            logger.error(f"获取窗口信息时出错: {str(e)}")
            return {}

    def __del__(self):
        """清理GDI+资源"""
        if self.gdiplusToken:
            try:
                windll.gdiplus.GdiplusShutdown(self.gdiplusToken)
            except:
                pass
