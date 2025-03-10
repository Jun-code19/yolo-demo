import axios from 'axios';

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

// 设备相关 API
export default {
  // 认证相关
  login(username, password) {
    // 使用URLSearchParams格式化表单数据
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    
    console.log("发送登录请求:", params.toString());
    
    // 直接使用axios.post，完整控制Headers
    return axios.post('/api/v1/token', params, {
      baseURL: 'http://localhost:8000',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
  },
  
  getCurrentUser() {
    return apiClient.get('/me');
  },
  
  // 系统初始化相关
  checkSystemInitialized() {
    return apiClient.get('/system/init-check');
  },
  
  initializeSystem(adminData) {
    return apiClient.post('/system/init', adminData);
  },
  
  // 获取所有设备
  getDevices(params = { skip: 0, limit: 100 }) {
    return apiClient.get('/devices/', { params });
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
  updateDeviceStatus(deviceId, deviceName, status) {
    return apiClient.put(`/devices/${deviceId}/status?device_name=${deviceName}&status=${status}`);
  },
  
  // 删除设备 (这个接口在后端可能需要添加)
  deleteDevice(deviceId) {
    return apiClient.delete(`/devices/${deviceId}`);
  },
  
  // 系统日志
  getSyslogs(params) {
    return apiClient.get('/syslogs/', { params });
  }
}; 