import axios from 'axios';
import { ElMessage } from 'element-plus';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000
});

// 添加请求拦截器，自动附加认证token
apiClient.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 添加响应拦截器，处理token过期情况
apiClient.interceptors.response.use(
  response => {
    return response;
  },
  error => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('userInfo');
      ElMessage.error('登录已过期，请重新登录');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 检测配置相关 API
export const detectionConfigApi = {
  // 获取检测配置列表
  getConfigs(params = { skip: 0, limit: 100 }) {
    return apiClient.get('/detection/configs', { params });
  },
  
  // 获取单个检测配置
  getConfig(configId) {
    return apiClient.get(`/detection/configs/${configId}`);
  },
  
  // 创建检测配置
  createConfig(configData) {
    return apiClient.post('/detection/configs', configData);
  },
  
  // 更新检测配置
  updateConfig(configId, configData) {
    return apiClient.put(`/detection/configs/${configId}`, configData);
  },
  
  // 删除检测配置
  deleteConfig(configId) {
    return apiClient.delete(`/detection/configs/${configId}`);
  },
  
  // 切换配置启用状态
  toggleConfig(configId, enabled) {
    return apiClient.put(`/detection/configs/${configId}/toggle?enabled=${enabled}`);
  }
};

// 检测事件相关 API
export const detectionEventApi = {
  // 获取检测事件列表
  getEvents(params = { skip: 0, limit: 100 }) {
    return apiClient.get('/detection/events', { params });
  },
  
  // 获取单个检测事件
  getEvent(eventId) {
    return apiClient.get(`/detection/events/${eventId}`);
  },
  
  // 更新事件状态
  updateEventStatus(eventId, status) {
    return apiClient.put(`/detection/events/${eventId}`, { status });
  },
  
  // 更新事件备注
  updateEventNotes(eventId, notes) {
    return apiClient.put(`/detection/events/${eventId}`, { notes });
  },
  
  // 删除检测事件
  deleteEvent(eventId) {
    return apiClient.delete(`/detection/events/${eventId}`);
  },
  
  // 批量更新事件状态
  batchUpdateStatus(eventIds, status) {
    return apiClient.put('/detection/events/batch-update', {
      event_ids: eventIds,
      status: status
    });
  },
  
  // 获取事件统计信息
  getEventStats(params = {}) {
    return apiClient.get('/detection/events/stats', { params });
  }
};

// 检测服务相关 API
export const detectionServiceApi = {
  // 启动设备检测
  startDetection(deviceId, configId = null) {
    return apiClient.post('/detection/start', {
      device_id: deviceId,
      config_id: configId
    });
  },
  
  // 停止设备检测
  stopDetection(deviceId) {
    return apiClient.post('/detection/stop', {
      device_id: deviceId
    });
  },
  
  // 获取活跃检测设备列表
  getActiveDetections() {
    return apiClient.get('/detection/active');
  },
  
  // 检查设备检测状态
  checkDetectionStatus(deviceId) {
    return apiClient.get(`/detection/status/${deviceId}`);
  }
}; 