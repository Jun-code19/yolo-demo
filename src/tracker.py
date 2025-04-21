import cv2
import numpy as np
from collections import defaultdict
import colorsys

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
        
        # 在这里判断是否拌线
        # if self.area_coordinates and self.area_coordinates['subtype'] == 'directional':
        #     # 获取当前轨迹点
        #     current_trajectory = self.trackers[track_id]['trajectory']
        #     # 获取当前轨迹点的前一个点
        #     prev_trajectory = current_trajectory[-2]
            

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
        """绘制平滑的跟踪轨迹"""
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
                
                # 绘制平滑的轨迹
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
        
        return frame
