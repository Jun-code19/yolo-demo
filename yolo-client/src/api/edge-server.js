import axios from 'axios';
import { ElMessage } from 'element-plus';

// 边缘服务器API服务类
class EdgeServerAPI {
  constructor(serverIP, serverPort = 80) {
    this.baseURL = `http://${serverIP}:${serverPort}`;
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      }
    });

    // 添加响应拦截器处理错误
    this.client.interceptors.response.use(
      response => response,
      error => {
        console.error('边缘服务器请求错误:', error);
        if (error.code === 'ECONNABORTED') {
          ElMessage.error('连接超时，请检查服务器地址和网络连接');
        } else if (error.response) {
          ElMessage.error(`请求失败: ${error.response.status} ${error.response.statusText}`);
        } else {
          ElMessage.error('网络连接失败，请检查服务器地址');
        }
        return Promise.reject(error);
      }
    );
  }

  // 1. 获取算法引擎详情
  async getAlgorithmEngines(engineId = '') {
    const response = await this.client.get('/api/v1/algorithm/engine', {
      params: { id: engineId }
    });
    return response.data;
  }

  // 2. 获取视频通道详情
  async getVideoChannels() {
    const response = await this.client.get('/api/v1/system/channels/mag');
    return response.data;
  }

  // 3. 获取通道截图
  getChannelImage(imagePath) {
    return `${this.baseURL}/${imagePath}`;
  }

  // 4. 获取事件类型
  async getEventTypes() {
    const response = await this.client.get('/api/v1/system/eventTypes');
    return response.data;
  }

  // 5. 获取历史事件
  async getHistoryEvents(params = {}) {
    const defaultParams = {
      chNo: '',
      eventType: '',
      startTime: 0,
      endTime: 0,
      limit: 20,
      pageNo: 1
    };
    const finalParams = { ...defaultParams, ...params };
    
    const response = await this.client.get('/api/v1/system/channels/pics', {
      params: finalParams
    });
    return response.data;
  }

  // 6. 获取历史事件截图
  getEventImage(imagePath) {
    return `${this.baseURL}/${imagePath}`;
  }

  // 7. 获取系统版本信息
  async getSystemVersion() {
    const response = await this.client.get('/api/v1/system/version');
    return response.data;
  }

  // 8. 获取系统内存/磁盘/flash信息
  async getSystemFlash() {
    const response = await this.client.get('/api/v1/system/flash');
    return response.data;
  }

  // 9. 获取系统序列号信息
  async getDeviceInfo() {
    const response = await this.client.get('/api/v1/system/deviceInfo');
    return response.data;
  }

  // 10. 获取系统CPU和内存使用情况
  async getCPUStatic() {
    const timestamp = Date.now();
    const response = await this.client.get(`/api/v1/system/cpustatic?${timestamp}`);
    return response.data;
  }

  // 11. 测试服务器连接
  async testConnection() {
    try {
      const result = await this.getSystemVersion();
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // 12. 获取服务器基本信息（综合信息）
  async getServerInfo() {
    try {
      const [version, flash, deviceInfo] = await Promise.all([
        this.getSystemVersion(),
        this.getSystemFlash(),
        this.getDeviceInfo()
      ]);

      return {
        success: true,
        data: {
          version: version.result,
          system: flash.result,
          device: deviceInfo.result
        }
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }
}

// 后端API客户端
const backendAPI = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  }
});

// 添加请求拦截器，自动添加认证token
backendAPI.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// 添加响应拦截器处理错误
backendAPI.interceptors.response.use(
  response => response,
  error => {
    console.error('后端API请求错误:', error);
    if (error.response?.status === 401) {
      ElMessage.error('认证失败，请重新登录');
      // 可以在这里触发登出逻辑
    } else if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail);
    } else {
      ElMessage.error('请求失败，请稍后重试');
    }
    return Promise.reject(error);
  }
);

// 边缘服务器管理服务
export default {
  // 创建边缘服务器API实例
  createServerAPI(serverIP, serverPort = 80) {
    return new EdgeServerAPI(serverIP, serverPort);
  },

  // 获取服务器列表
  async getServerList(params = {}) {
    try {
      const response = await backendAPI.get('/edge-servers', { params });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 添加服务器
  async addServer(serverData) {
    try {
      const response = await backendAPI.post('/edge-servers', {
        name: serverData.name,
        ip_address: serverData.ip,
        port: serverData.port || 80,
        description: serverData.description || '',
        is_active: true
      });
      ElMessage.success('服务器添加成功');
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 更新服务器
  async updateServer(serverId, serverData) {
    try {
      const updateData = {};
      if (serverData.name) updateData.name = serverData.name;
      if (serverData.ip) updateData.ip_address = serverData.ip;
      if (serverData.port) updateData.port = serverData.port;
      if (serverData.description !== undefined) updateData.description = serverData.description;
      if (serverData.is_active !== undefined) updateData.is_active = serverData.is_active;

      const response = await backendAPI.put(`/edge-servers/${serverId}`, updateData);
      ElMessage.success('服务器更新成功');
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 删除服务器
  async removeServer(serverId) {
    try {
      await backendAPI.delete(`/edge-servers/${serverId}`);
      ElMessage.success('服务器删除成功');
      return true;
    } catch (error) {
      throw error;
    }
  },

  // 获取单个服务器信息
  async getServer(serverId) {
    try {
      const response = await backendAPI.get(`/edge-servers/${serverId}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 更新服务器状态
  async updateServerStatus(serverId, statusData) {
    try {
      const response = await backendAPI.patch(`/edge-servers/${serverId}/status`, statusData);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 获取在线服务器
  async getOnlineServers() {
    try {
      const response = await backendAPI.get('/edge-servers/online/list');
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 根据状态获取服务器
  async getServersByStatus(status) {
    try {
      const response = await backendAPI.get(`/edge-servers/status/${status}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 测试服务器连接并更新状态
  async testAndUpdateServerStatus(serverId, serverIP, serverPort = 80) {
    try {
      const serverAPI = this.createServerAPI(serverIP, serverPort);
      const connectionResult = await serverAPI.testConnection();
      
      if (connectionResult.success) {
        // 获取服务器详细信息
        const serverInfo = await serverAPI.getServerInfo();
        
        const statusData = {
          status: 'online',
          system_info: serverInfo.data?.system || null,
          version_info: serverInfo.data?.version || null,
          device_info: serverInfo.data?.device || null
        };
        
        await this.updateServerStatus(serverId, statusData);
        return { success: true, status: 'online' };
      } else {
        await this.updateServerStatus(serverId, { status: 'offline' });
        return { success: false, status: 'offline', error: connectionResult.error };
      }
    } catch (error) {
      await this.updateServerStatus(serverId, { status: 'offline' });
      return { success: false, status: 'offline', error: error.message };
    }
  }
}; 