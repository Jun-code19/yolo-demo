import axios from 'axios';
import { ElMessage } from 'element-plus';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: '/api/v2',
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
    // 处理401错误（未授权，token过期）
    if (error.response && error.response.status === 401) {
      // 清除token和用户信息
      localStorage.removeItem('token');
      localStorage.removeItem('userInfo');
      
      // 显示提示信息
      ElMessage.error('登录已过期，请重新登录');
      
      // 重定向到登录页面
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const smartSchemeApi = {
  // 事件订阅管理
  createScheme: (data) => apiClient.post('/smart-schemes/manager', data),
  getSchemes: (params) => apiClient.get('/smart-schemes/manager', { params }),
  getScheme: (schemeId) => apiClient.get(`/smart-schemes/manager/${schemeId}`),
  updateScheme: (schemeId, data) => apiClient.put(`/smart-schemes/manager/${schemeId}`, data),
  deleteScheme: (schemeId) => apiClient.delete(`/smart-schemes/manager/${schemeId}`),

  // 事件订阅控制
  startScheme: (schemeId) => apiClient.post(`/smart-schemes/manager/${schemeId}/start`),
  stopScheme: (schemeId) => apiClient.post(`/smart-schemes/manager/${schemeId}/stop`),
  restartScheme: (schemeId) => apiClient.post(`/smart-schemes/manager/${schemeId}/restart`),

  // 状态监控
  getAllStatus: () => apiClient.get('/smart-schemes/status'),
  getSchemeStatus: (schemeId) => apiClient.get(`/smart-schemes/${schemeId}/status`),
  getSystemStatus: () => apiClient.get('/smart-schemes/system/status'),

  // 事件查询
  getSmartEvents: (params) => apiClient.get('/smart-schemes/events', { params }),
  getSmartEvent: (eventId) => apiClient.get(`/smart-schemes/events/${eventId}`),
  
  // 事件删除
  deleteSmartEvent: (eventId) => apiClient.delete(`/smart-schemes/events/${eventId}`),
  batchDeleteSmartEvents: (eventIds) => apiClient.post('/smart-schemes/events/batch-delete', { event_ids: eventIds }),
  
  // 批量事件操作
  batchProcessSmartEvents: (eventIds) => apiClient.post('/smart-schemes/events/batch-process', { event_ids: eventIds }),
  batchIgnoreSmartEvents: (eventIds) => apiClient.post('/smart-schemes/events/batch-ignore', { event_ids: eventIds }),

  // 统计信息
  getStats: () => apiClient.get('/smart-schemes/stats/summary'),
  getEventsStatsOverview: () => apiClient.get('/smart-schemes/stats/overview'),

  // 更新事件
  updateSmartEvent: (eventId, updateData) => apiClient.put(`/smart-schemes/events/${eventId}`, updateData),

  // 获取摄像头列表
  getCameras: () => apiClient.get('/smart-schemes/cameras'),
  
  // 获取事件类型列表
  getEventTypes: () => apiClient.get('/smart-schemes/event-types'),

  // 导出事件
  exportEvents: (params) => apiClient.get('/smart-schemes/events/export', { 
    params,
    responseType: 'blob'
  }),

  // 获取事件订阅日志
  getSchemeLogs: (schemeId, params) => apiClient.get(`/smart-schemes/${schemeId}/logs`, { params })
}

export default smartSchemeApi 