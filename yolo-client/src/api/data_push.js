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

// 数据推送相关 API
export const dataPushApi = {
    // 获取推送配置列表
    getPushConfigs(configId = null) {
      return apiClient.get('/push/list', { 
        params: configId ? { config_id: configId } : {}
      });
    },
    
    // 创建推送配置
    createPushConfig(configData) {
      return apiClient.post('/push/create', configData);
    },
    
    // 更新推送配置
    updatePushConfig(pushId, configData) {
      return apiClient.put(`/push/${pushId}`, configData);
    },
    
    // 删除推送配置
    deletePushConfig(pushId) {
      return apiClient.delete(`/push/${pushId}`);
    },
    
    // 测试推送配置
    testPushConfig(pushId) {
      return apiClient.post(`/push/test/${pushId}`);
    },
    
    // 获取推送统计信息
    getPushStats() {
      return apiClient.get('/push/stats');
    },
    
    // 重新加载推送配置
    reloadPushConfig(pushId) {
      return apiClient.post(`/push/reload/${pushId}`);
    }
  }; 