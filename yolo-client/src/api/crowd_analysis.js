import axios from 'axios';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: '/api/v2/crowd-analysis',
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

// 人群分析相关 API
export const crowdAnalysisApi = {
  // 获取分析任务列表（分页）
  getAnalysisJobs(params = { page: 1, page_size: 10 }) {
    return apiClient.get('/jobs', { params });
  },
  
  // 获取特定分析任务详情
  getAnalysisJob(jobId) {
    return apiClient.get(`/jobs/${jobId}`);
  },
  
  // 创建新的分析任务
  createAnalysisJob(jobData) {
    return apiClient.post('/jobs', jobData);
  },
  
  // 删除分析任务
  deleteAnalysisJob(jobId) {
    return apiClient.delete(`/jobs/${jobId}/delete`);
  },
  
  // 立即执行分析任务
  runAnalysisJobNow(jobId) {
    return apiClient.post(`/jobs/${jobId}/run`);
  },

  // 暂停分析任务
  pauseAnalysisJob(jobId) {
    return apiClient.post(`/jobs/${jobId}/pause`);
  },

  // 恢复分析任务
  resumeAnalysisJob(jobId) {
    return apiClient.post(`/jobs/${jobId}/resume`);
  },

  // 导出分析结果数据
  exportAnalysisResults(jobId, days = 7) {
    return apiClient.get(`/jobs/${jobId}/export`, { params: { days } });
  },

  // 获取可用于人群分析的设备
  getAvailableDevices() {
    return apiClient.get('/available-devices');
  },
  
  // 获取可用于人群分析的模型
  getAvailableModels() {
    return apiClient.get('/available-models');
  },
  
  // 获取设备详情信息
  getDevicesDetails(device_ids) {
    // 将数组转换为逗号分隔的字符串
    const deviceIdsParam = Array.isArray(device_ids) ? device_ids.join(',') : device_ids;
    return apiClient.get('/info-devices', { params: { device_ids: deviceIdsParam }});
  },

  // 获取历史分析数据，用于趋势图
  getAnalysisHistory(jobId, startDate, endDate) {
    const params = {};
    if (startDate) {
      params.start_date = startDate.toISOString();
    }
    if (endDate) {
      params.end_date = endDate.toISOString();
    }
    return apiClient.get(`/jobs/${jobId}/history`, { params });
  },

  updateAnalysisJob(jobId, data) {
    return apiClient.put(`/jobs/${jobId}`, data);
  },

  getModelClasses(modelId) {
    return apiClient.get(`/model-classes/${modelId}`);
  }
};

export default crowdAnalysisApi; 