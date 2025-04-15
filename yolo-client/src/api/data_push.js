import axios from 'axios';

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: 'http://localhost:8003/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000
});

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