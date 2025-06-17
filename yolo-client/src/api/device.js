import axios from 'axios';
import { ElMessage } from 'element-plus';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: '/api/v1',
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

// 设备相关 API
export default {
  // 认证相关
  login(username, password) {
    // 使用URLSearchParams格式化表单数据
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    
    // console.log("发送登录请求:", params.toString());
    
    // 直接使用axios.post，完整控制Headers
    return axios.post('/api/v1/token', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
  },
  
  getCurrentUser() {
    return apiClient.get('/me');
  },
  
  // Token验证
  validateToken() {
    return apiClient.get('/token/validate');
  },
  
  // 用户管理相关
  updateUserProfile(userData) {
    return apiClient.put('/users/profile', userData);
  },
  
  updatePassword(passwordData) {
    return apiClient.put('/users/password', passwordData);
  },
  
  // 系统初始化相关
  checkSystemInitialized() {
    return apiClient.get('/system/init-check');
  },
  
  initializeSystem(adminData) {
    return apiClient.post('/system/init', adminData);
  },
  
  // 获取所有设备
  getDevices(params = { skip: 0, limit: 200 }) {
    // 过滤掉空值参数
    const filteredParams = Object.fromEntries(
      Object.entries(params).filter(([_, value]) => value !== null && value !== undefined && value !== '')
    );
    return apiClient.get('/devices/', { params: filteredParams });
  },
  
  // 获取筛选后的设备列表
  getFilteredDevices(filterParams = {}, paginationParams = { skip: 0, limit: 100 }) {
    const params = { ...paginationParams, ...filterParams };
    // 过滤掉空值参数
    const filteredParams = Object.fromEntries(
      Object.entries(params).filter(([_, value]) => value !== null && value !== undefined && value !== '')
    );
    return apiClient.get('/devices/', { params: filteredParams });
  },
  
  // 获取设备在线状态
  getDevicesStatus() {
    return apiClient.get('/alldevices/status');
  },

  // 获取单个设备详情
  getDevice(deviceId) {
    return apiClient.get(`/devices/${deviceId}`);
  },
  
  // 创建新设备
  createDevice(deviceData) {
    return apiClient.post('/devices/', deviceData);
  },
  
  // 更新设备状态
  updateDevice(deviceId, deviceData) {
    return apiClient.put(`/devices/${deviceId}`,deviceData);
  },
  
  // 删除设备 (这个接口在后端可能需要添加)
  deleteDevice(deviceId) {
    return apiClient.delete(`/devices/${deviceId}`);
  },
  
  // 模型管理相关API
  getModels() {
    return apiClient.get('/models/');
  },
  
  getModel(modelId) {
    return apiClient.get(`/models/${modelId}`);
  },
  
  uploadModel(formData) {
    return apiClient.post('/models/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },
  
  deleteModel(modelId) {
    return apiClient.delete(`/models/${modelId}`);
  },
  
  toggleModelActive(modelId, active) {
    return apiClient.put(`/models/${modelId}/toggle?active=${active}`);
  },
  
  // 获取首页仪表盘数据
  getDashboardOverview() {
    return apiClient.get('/dashboard/overview');
  },

  // 导出设备数据模板
  exportDeviceTemplate() {
    return apiClient.get('/devices/export/template', {
      responseType: 'blob' // 使用blob响应类型来处理文件下载
    });
  },
  
  // 导出设备数据
  exportDevices() {
    return apiClient.get('/devices/export/data', {
      responseType: 'blob' // 使用blob响应类型来处理文件下载
    });
  },
  
  // 导入设备数据
  importDevices(formData) {
    return apiClient.post('/devices/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },
}; 