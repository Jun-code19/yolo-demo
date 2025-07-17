import axios from 'axios';

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
    // 对于token端点的请求，不修改Content-Type
    if (config.url === '/token') {
      return config;
    }
    
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

export const dataListenerApi = {
  // 配置管理
  createConfig: (data) => apiClient.post('/data-listeners/configs', data),
  getConfigs: (params) => apiClient.get('/data-listeners/configs', { params }),
  getConfig: (configId) => apiClient.get(`/data-listeners/configs/${configId}`),
  updateConfig: (configId, data) => apiClient.put(`/data-listeners/configs/${configId}`, data),
  deleteConfig: (configId) => apiClient.delete(`/data-listeners/configs/${configId}`),

  // 监听器控制
  startListener: (configId) => apiClient.post(`/data-listeners/configs/${configId}/start`),
  stopListener: (configId) => apiClient.post(`/data-listeners/configs/${configId}/stop`),
  restartListener: (configId) => apiClient.post(`/data-listeners/configs/${configId}/restart`),

  // 状态监控
  getAllStatus: () => apiClient.get('/data-listeners/status'),
  getListenerStatus: (configId) => apiClient.get(`/data-listeners/configs/${configId}/status`),

  // 事件查询
  getEvents: (params) => apiClient.get('/data-listeners/events', { params }),
  getEvent: (eventId) => apiClient.get(`/data-listeners/events/${eventId}`),
  
  // 事件删除
  deleteEvent: (eventId) => apiClient.delete(`/data-listeners/events/${eventId}`),
  batchDeleteEvents: (eventIds) => apiClient.post('/data-listeners/events/batch-delete', { event_ids: eventIds }),

  // 统计信息
  getStats: () => apiClient.get('/data-listeners/stats/summary'),

  // 获取外部事件统计概览
  getEventsStatsOverview: () => apiClient.get('/data-listeners/stats/overview'),

  // 更新外部事件
  updateEvent: (eventId, updateData) => apiClient.put(`/data-listeners/events/${eventId}`, updateData),

  // 批量操作
  batchStart: (configIds) => apiClient.post('/data-listeners/batch/start', configIds),
  batchStop: (configIds) => apiClient.post('/data-listeners/batch/stop', configIds),

  // 获取设备和引擎名称映射
  getDeviceEngineNameMappings: () => apiClient.get('/data-listeners/device_engine_name_mappings')
}

export default dataListenerApi 