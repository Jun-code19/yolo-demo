import cv2
import numpy as np
from collections import defaultdict
import colorsys
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

class ObjectTracker:
    def __init__(self, max_age=30, min_hits=3, iou_threshold=0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = {}
        self.frame_count = 0
        self.colors = {}
        self.class_colors = {}
        self.next_id = 0
        self.active_tracks = set()  # 添加活跃轨迹集合
        self.trajectory_buffer = {}  # 添加轨迹缓冲区
        self.interpolation_threshold = 50  # 插值阈值
        
        # 智能分析相关
        self.area_coordinates = None
        self.current_count = 0  # 区域内当前人数
        self.today_in_count = 0  # 今日进入总数
        self.today_out_count = 0  # 今日离开总数
        self.triggered_events = {}  # 已触发的事件，避免重复触发
        self.line_crossed_tracks = {}  # 记录已过线的轨迹
        self.date = datetime.now().strftime("%Y-%m-%d")  # 记录当前日期

        # 尝试加载中文字体，如果失败则使用默认字体
        try:
            # Windows系统中文字体路径
            self.font_path = "C:/Windows/Fonts/simhei.ttf"  # 黑体
            self.font = ImageFont.truetype(self.font_path, 30)
            self.font_small = ImageFont.truetype(self.font_path, 24)
        except:
            try:
                # 尝试其他常见中文字体
                self.font_path = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"  # 微软雅黑
                self.font = ImageFont.truetype(self.font_path, 30)
                self.font_small = ImageFont.truetype(self.font_path, 24)
            except:
                # 如果都找不到，使用默认字体
                self.font = ImageFont.load_default()
                self.font_small = ImageFont.load_default()

    def _generate_colors(self, num_classes):
        hsv_tuples = [(x / num_classes, 1., 1.) for x in range(num_classes)]
        colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), colors))
        return colors

    def _assign_color(self, class_id):
        if class_id not in self.class_colors:
            if not self.class_colors:
                colors = self._generate_colors(100)  # 假设最多100个类别
                self.class_colors = {i: color for i, color in enumerate(colors)}
            else:
                self.class_colors[class_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.class_colors[class_id]
    
    def set_area_coordinates(self, area_coordinates, frame_shape):
        """设置区域坐标"""
        self.area_coordinates = area_coordinates
        self.frame_shape = frame_shape
        
        # 将归一化坐标转换为像素坐标
        if area_coordinates and area_coordinates.get('points'):
            h, w = frame_shape[:2]
            self.area_points = [(int(p['x'] * w), int(p['y'] * h)) for p in area_coordinates['points']]
        else:
            self.area_points = None
    
    def _point_in_polygon(self, point, polygon):
        """判断点是否在多边形内（Ray casting算法）"""
        if not polygon or len(polygon) < 3:
            return False
            
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _line_intersection(self, line1, line2):
        """计算两条线段的交点"""
        (x1, y1), (x2, y2) = line1
        (x3, y3), (x4, y4) = line2
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None  # 平行线
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        
        if 0 <= t <= 1 and 0 <= u <= 1:
            ix = x1 + t * (x2 - x1)
            iy = y1 + t * (y2 - y1)
            return (ix, iy)
        
        return None
    
    def _crossed_line(self, track_id, current_point, previous_point):
        """检测是否穿越了拌线"""
        if not self.area_points or len(self.area_points) < 2:
            return False, None
        
        # 构建拌线段
        for i in range(len(self.area_points) - 1):
            line_segment = (self.area_points[i], self.area_points[i + 1])
            trajectory_segment = (previous_point, current_point)
            
            intersection = self._line_intersection(line_segment, trajectory_segment)
            if intersection:
                return True, intersection
        
        return False, None
    
    def _analyze_behavior(self, track_id, current_center, prev_center):
        """分析行为逻辑"""
        analysis_type = self.area_coordinates.get('analysisType')
        
        if analysis_type == 'behavior':
            self._analyze_behavior_detection(track_id, current_center, prev_center)
        elif analysis_type == 'counting':
            self._analyze_counting(track_id, current_center, prev_center)
    
    def _analyze_behavior_detection(self, track_id, current_center, prev_center):
        """通用行为分析"""
        behavior_type = self.area_coordinates.get('behaviorType')
        behavior_subtype = self.area_coordinates.get('behaviorSubtype', 'simple')
        behavior_direction = self.area_coordinates.get('behaviorDirection', 'in')
        
        if behavior_type == 'area':
            # 区域检测
            current_in_area = self._point_in_polygon(current_center, self.area_points)
            prev_in_area = self._point_in_polygon(prev_center, self.area_points)
            
            if behavior_subtype == 'simple':
                # 普通检测：只要进入区域就触发
                if current_in_area and not prev_in_area:
                    self._trigger_behavior_event(track_id, 'area_enter', current_center)
                elif not current_in_area and prev_in_area:
                    self._trigger_behavior_event(track_id, 'area_exit', current_center)
            elif behavior_subtype == 'directional':
                # 方向检测：只检测指定方向
                if behavior_direction == 'in' and current_in_area and not prev_in_area:
                    self._trigger_behavior_event(track_id, 'area_enter', current_center)
                elif behavior_direction == 'out' and not current_in_area and prev_in_area:
                    self._trigger_behavior_event(track_id, 'area_exit', current_center)
        
        elif behavior_type == 'line':
            # 拌线检测
            crossed, intersection = self._crossed_line(track_id, current_center, prev_center)
            
            if crossed:
                if behavior_subtype == 'simple':
                    # 普通检测：穿越拌线就触发
                    self._trigger_behavior_event(track_id, 'line_cross', intersection or current_center)
                elif behavior_subtype == 'directional':
                    # 方向检测：需要判断穿越方向
                    direction = self._get_crossing_direction(prev_center, current_center)
                    if (behavior_direction == 'in' and direction == 'in') or \
                       (behavior_direction == 'out' and direction == 'out'):
                        self._trigger_behavior_event(track_id, f'line_cross_{direction}', intersection or current_center)
    
    def _analyze_counting(self, track_id, current_center, prev_center):
        """人数统计分析"""
        counting_type = self.area_coordinates.get('countingType')
        
        if counting_type == 'occupancy':
            # 区域内人数统计 - 每帧重新统计区域内的实际人数
            # 不需要依赖进出事件，直接统计当前帧中所有在区域内的目标
            pass  # 实际统计在update方法中进行
        
        elif counting_type == 'flow':
            
            # 如果日期发生变化，重置今日计数
            if self.date != datetime.now().strftime("%Y-%m-%d"):
                self.today_in_count = 0
                self.today_out_count = 0
                self.date = datetime.now().strftime("%Y-%m-%d")

            # 人流统计
            crossed, intersection = self._crossed_line(track_id, current_center, prev_center)
            
            if crossed and track_id not in self.line_crossed_tracks:
                direction = self._get_crossing_direction(prev_center, current_center)
                flow_direction = self.area_coordinates.get('flowDirection', 'bidirectional')
                
                # 根据流向设置判断是否计数
                should_count = False
                if flow_direction == 'bidirectional':
                    should_count = True
                elif flow_direction == 'in' and direction == 'in':
                    should_count = True
                elif flow_direction == 'out' and direction == 'out':
                    should_count = True
                
                if should_count:
                    if direction == 'in':
                        self.today_in_count += 1
                    else:
                        self.today_out_count += 1
                    
                    self.line_crossed_tracks[track_id] = direction
                    self._trigger_counting_event(track_id, f'line_cross_{direction}', intersection or current_center)
    
    def _get_crossing_direction(self, prev_point, current_point):
        """判断穿越方向（简化版本，可根据实际需求优化）"""
        # 这里使用简单的Y坐标判断，实际应用中可能需要更复杂的算法
        if current_point[1] > prev_point[1]:
            return 'in'  # 向下为进入
        else:
            return 'out'  # 向上为离开
    
    def _trigger_behavior_event(self, track_id, event_type, position):
        """触发行为事件"""
        event_key = f"{track_id}_{event_type}"
        if event_key not in self.triggered_events:
            self.triggered_events[event_key] = {
                'track_id': track_id,
                'event_type': event_type,
                'position': position,
                'timestamp': self.frame_count
            }
            # 这里可以添加回调函数来处理事件
            # print(f"行为事件触发: {event_type}, 轨迹ID: {track_id}, 位置: {position}")
    
    def _trigger_counting_event(self, track_id, event_type, position):
        """触发计数事件"""
        event_key = f"{track_id}_{event_type}"
        if event_key not in self.triggered_events:
            self.triggered_events[event_key] = {
                'track_id': track_id,
                'event_type': event_type,
                'position': position,
                'current_count': self.current_count,
                'today_in_count': self.today_in_count,
                'today_out_count': self.today_out_count,
                'timestamp': self.frame_count
            }
            # 这里可以添加回调函数来处理事件
            # print(f"计数事件: {event_type}, 当前人数: {self.current_count}, 今日进入: {self.today_in_count}, 今日离开: {self.today_out_count}")

    def _calculate_iou(self, bbox1, bbox2):
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2
        
        xi1, yi1 = max(x1, x3), max(y1, y3)
        xi2, yi2 = min(x2, x4), min(y2, y4)
        
        intersection_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        
        bbox1_area = (x2 - x1) * (y2 - y1)
        bbox2_area = (x4 - x3) * (y4 - y3)
        
        union_area = bbox1_area + bbox2_area - intersection_area
        
        iou = intersection_area / union_area if union_area > 0 else 0
        return iou

    def _get_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def update(self, detections):
        self.frame_count += 1
        current_active_tracks = set()  # 用于存储当前帧的活跃轨迹
        
        # 如果没有检测结果，清空所有跟踪器
        if not detections:
            # 保持短暂的轨迹持续性
            for track_id in list(self.active_tracks):
                if self.frame_count - self.trackers[track_id].get('last_update', 0) > 5:
                    self.trackers.pop(track_id)
            return
        
        # 如果是第一帧或没有现有跟踪器
        if not self.trackers:
            for det in detections:
                track_id = self._init_new_tracker(det)
                current_active_tracks.add(track_id)
            self.active_tracks = current_active_tracks
            return

        # 构建代价矩阵
        cost_matrix = np.zeros((len(detections), len(self.trackers)))
        detection_indices = []
        tracker_indices = []

        for i, det in enumerate(detections):
            for j, (track_id, tracker) in enumerate(self.trackers.items()):
                iou = self._calculate_iou(tracker['box'], det['bbox'])
                cost_matrix[i, j] = 1 - iou  # 转换为代价（1 - IOU）
                detection_indices.append(i)
                tracker_indices.append(track_id)

        # 使用匈牙利算法进行匹配
        matched_detections = set()
        matched_trackers = set()

        # 对每个检测结果找到最佳匹配
        for det_idx, det in enumerate(detections):
            best_iou = 0
            best_track_id = None
            
            for track_id, tracker in self.trackers.items():
                if track_id in matched_trackers:
                    continue
                    
                iou = self._calculate_iou(tracker['box'], det['bbox'])
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_track_id = track_id
            
            if best_track_id is not None:
                self._update_tracker(best_track_id, det)
                matched_detections.add(det_idx)
                matched_trackers.add(best_track_id)
                current_active_tracks.add(best_track_id)

        # 处理未匹配的检测结果
        for det_idx, det in enumerate(detections):
            if det_idx not in matched_detections:
                track_id = self._init_new_tracker(det)
                current_active_tracks.add(track_id)

        # 立即移除未匹配的跟踪器
        self.trackers = {k: v for k, v in self.trackers.items() if k in current_active_tracks}
        self.active_tracks = current_active_tracks

        # 更新区域内人数统计
        self._update_area_occupancy_count()

    def _init_new_tracker(self, detection):
        """初始化新的跟踪器并返回track_id"""
        track_id = self.next_id
        center = self._get_center(detection['bbox'])
        self.trackers[track_id] = {
            'box': detection['bbox'],
            'center': center,
            'hits': 1,
            'age': 0,
            'class': detection['class_id'],
            'trajectory': [center],
            'confidence': detection['confidence'] if len(detection) > 5 else 1.0,
            'last_update': self.frame_count
        }
        self.next_id += 1
        return track_id

    def _update_tracker(self, track_id, detection):
        """更新现有跟踪器，包含轨迹平滑和插值"""
        current_center = self._get_center(detection['bbox'])
        prev_center = self.trackers[track_id]['center']
        
        # 计算与上一个点的距离
        distance = np.sqrt((current_center[0] - prev_center[0])**2 + 
                         (current_center[1] - prev_center[1])**2)
        
        # 如果距离过大且有足够的历史轨迹点，进行插值
        if distance > self.interpolation_threshold and len(self.trackers[track_id]['trajectory']) > 0:
            interpolated_points = self._interpolate_points(prev_center, current_center)
            self.trackers[track_id]['trajectory'].extend(interpolated_points)

        # 智能分析逻辑
        if self.area_coordinates and self.area_points:
            self._analyze_behavior(track_id, current_center, prev_center)

        # 更新轨迹
        self.trackers[track_id]['trajectory'].append(current_center)
        
        # 使用卡尔曼滤波平滑轨迹
        if len(self.trackers[track_id]['trajectory']) >= 3:
            self._smooth_trajectory(track_id)
        
        self.trackers[track_id].update({
            'box': detection['bbox'],
            'center': current_center,
            'hits': self.trackers[track_id]['hits'] + 1,
            'age': 0,
            'class': detection['class_id'],
            'confidence': detection['confidence'] if len(detection) > 5 else 1.0,
            'last_update': self.frame_count
        })

    def _interpolate_points(self, start_point, end_point):
        """在两点之间进行线性插值"""
        num_points = int(np.sqrt(
            (end_point[0] - start_point[0])**2 + 
            (end_point[1] - start_point[1])**2
        ) / 10)  # 每10像素插入一个点
        
        if num_points < 2:
            return []
            
        x = np.linspace(start_point[0], end_point[0], num_points)
        y = np.linspace(start_point[1], end_point[1], num_points)
        
        return list(zip(x, y))[1:-1]  # 不包括起点和终点

    def _smooth_trajectory(self, track_id):
        """使用简单的移动平均平滑轨迹"""
        trajectory = np.array(self.trackers[track_id]['trajectory'])
        window_size = 3
        
        if len(trajectory) >= window_size:
            smoothed = []
            for i in range(len(trajectory)):
                start_idx = max(0, i - window_size // 2)
                end_idx = min(len(trajectory), i + window_size // 2 + 1)
                window = trajectory[start_idx:end_idx]
                smoothed.append(np.mean(window, axis=0))
            
            self.trackers[track_id]['trajectory'] = smoothed

    def draw_tracks(self, frame, max_trajectory_length=30, show_boxes=True):
        """绘制平滑的跟踪轨迹和智能分析信息"""
        # 绘制轨迹
        for track_id, track in self.trackers.items():
            if track_id in self.active_tracks and track['hits'] >= self.min_hits:
                color = self._assign_color(track['class'])
                
                # 只在show_boxes为True时绘制边界框和ID
                if show_boxes:
                    x1, y1, x2, y2 = map(int, track['box'])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    conf_text = f"ID:{track_id} {track['confidence']:.2f}"
                    cv2.putText(frame, conf_text, (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # 绘制轨迹（人流统计时显示更明显的轨迹）
                show_trajectory = True
                if self.area_coordinates:
                    analysis_type = self.area_coordinates.get('analysisType')
                    counting_type = self.area_coordinates.get('countingType')
                    # 人流统计时显示轨迹
                    if analysis_type == 'counting' and counting_type == 'flow':
                        show_trajectory = True
                    # 区域人数统计时不显示轨迹
                    elif analysis_type == 'counting' and counting_type == 'occupancy':
                        show_trajectory = False
                
                if show_trajectory:
                    trajectory = track['trajectory'][-max_trajectory_length:]
                    if len(trajectory) > 1:
                        points = np.array(trajectory, dtype=np.float32)
                        points = np.round(points).astype(np.int32)
                        
                        for i in range(len(points) - 1):
                            pt1 = tuple(points[i])
                            pt2 = tuple(points[i + 1])
                            cv2.line(frame, pt1, pt2, color, 2, cv2.LINE_AA)
                
                # 绘制当前位置点
                cv2.circle(frame, (int(track['center'][0]), int(track['center'][1])), 
                          4, color, -1, cv2.LINE_AA)
        
        # 绘制智能分析信息
        self._draw_analysis_info(frame)
        
        return frame
    
    def _draw_chinese_text(self, frame, text, position, font_size=24, color=(255, 255, 255)):
        """使用PIL绘制中文文字到OpenCV图像上"""
        # 将OpenCV图像转换为PIL图像
        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(frame_pil)
        # 选择字体大小
        if font_size <= 24:
            current_font = self.font_small
        else:
            current_font = self.font
        # 绘制文字（PIL的颜色是RGB格式）
        pil_color = (color[2], color[1], color[0])  # BGR转RGB

        try:
            draw.text(position, text, font=current_font, fill=pil_color)
        except Exception as e:
            print(f"绘制文字失败: {e}")

        # 将PIL图像转换回OpenCV图像
        frame_cv = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
        frame[:] = frame_cv[:]

    def _draw_analysis_info(self, frame):
        """绘制智能分析信息"""
        if not self.area_coordinates:
            return
        
        analysis_type = self.area_coordinates.get('analysisType')
        
        if analysis_type == 'counting':
            counting_type = self.area_coordinates.get('countingType')
            
            if counting_type == 'occupancy':
                # 区域人数统计 - 显示当前人数
                info_text = f"当前人数: {self.current_count}"
                self._draw_chinese_text(frame, info_text, (10, 10), 30, (0, 255, 0))
                
                # 显示今日统计
                # today_text = f"今日进入: {self.today_in_count} | 今日离开: {self.today_out_count}"
                # self._draw_chinese_text(frame, today_text, (10, 40), 18, (255, 255, 255))
                
            elif counting_type == 'flow':
                # 人流统计 - 显示进出统计
                flow_direction = self.area_coordinates.get('flowDirection', 'bidirectional')
                
                if flow_direction == 'bidirectional':
                    info_text = f"今日进入: {self.today_in_count} | 今日离开: {self.today_out_count}"
                elif flow_direction == 'in':
                    info_text = f"今日进入: {self.today_in_count}"
                elif flow_direction == 'out':
                    info_text = f"今日离开: {self.today_out_count}"
                else:
                    info_text = f"总通过: {self.today_in_count + self.today_out_count}"
                
                self._draw_chinese_text(frame, info_text, (10, 10), 30, (0, 255, 255))
                
        elif analysis_type == 'behavior':
            # 行为分析 - 显示检测模式
            behavior_type = self.area_coordinates.get('behaviorType')
            behavior_subtype = self.area_coordinates.get('behaviorSubtype', 'simple')
            behavior_direction = self.area_coordinates.get('behaviorDirection', '')
            
            type_text = '区域检测' if behavior_type == 'area' else '拌线检测'
            mode_text = '方向检测' if behavior_subtype == 'directional' else '普通检测'
            
            info_text = f"{type_text} - {mode_text}"
            if behavior_subtype == 'directional':
                direction_text = '进入' if behavior_direction == 'in' else '离开'
                info_text += f" ({direction_text})"
            
            self._draw_chinese_text(frame, info_text, (10, 10), 30, (255, 165, 0))
    
    def get_counting_stats(self):
        """获取计数统计信息"""
        return {
            'current_count': self.current_count,
            'today_in_count': self.today_in_count,
            'today_out_count': self.today_out_count,
            'total_today': self.today_in_count + self.today_out_count
        }

    def _update_area_occupancy_count(self):
        """更新区域内人数统计"""
        if not self.area_coordinates or self.area_coordinates.get('countingType') != 'occupancy':
            return
        
        # 统计当前帧中所有在区域内的活跃目标
        current_count_in_area = 0
        for track_id in self.active_tracks:
            if track_id in self.trackers:
                tracker = self.trackers[track_id]
                center = tracker['center']
                if self._point_in_polygon(center, self.area_points):
                    current_count_in_area += 1
        
        # 检查人数是否发生变化
        if current_count_in_area != self.current_count:
            old_count = self.current_count
            self.current_count = current_count_in_area
            
            # 触发人数变化事件（使用帧数作为事件key的一部分避免重复）
            change_type = 'increase' if current_count_in_area > old_count else 'decrease'
            change_amount = abs(current_count_in_area - old_count)
            
            # 使用帧数和变化量创建唯一的事件key
            event_key = f"occupancy_{self.frame_count}_{change_type}_{change_amount}"
            if event_key not in self.triggered_events:
                self.triggered_events[event_key] = {
                    'track_id': 0,  # 区域统计事件不关联特定track
                    'event_type': f'occupancy_change_{change_type}',
                    'position': None,
                    'old_count': old_count,
                    'new_count': current_count_in_area,
                    'change_amount': change_amount,
                    'current_count': self.current_count,
                    'today_in_count': self.today_in_count,
                    'today_out_count': self.today_out_count,
                    'timestamp': self.frame_count
                }
                
                # 输出事件信息
                change_text = '增加' if current_count_in_area > old_count else '减少'
                # print(f"区域人数{change_text} {change_amount}人: {old_count} -> {current_count_in_area}, 今日累计进入: {self.today_in_count}, 今日累计离开: {self.today_out_count}")
            
            # 更新今日统计（基于变化量）
            change_amount = current_count_in_area - old_count
            if change_amount > 0:
                self.today_in_count += change_amount
            else:
                self.today_out_count += abs(change_amount)

