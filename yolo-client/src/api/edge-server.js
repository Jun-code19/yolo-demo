import axios from 'axios';
import { ElMessage } from 'element-plus';

export const PLATFORM_TYPES = {
  maisi: { label: '迈思智能盒子', defaultPort: 80 },
  // 裸机 nginx 入口为 80（反代本机 8080）；直连 serve_unified 时再改成 8080
  edgebox: { label: 'Edge AI Box', defaultPort: 80 },
  nodered: { label: 'Node-RED', defaultPort: 1880 },
  custom: { label: '自定义节点', defaultPort: 80 },
};

export function getPlatformLabel(platformType) {
  return PLATFORM_TYPES[platformType]?.label || platformType || '未知';
}

export function getDefaultPort(platformType) {
  return PLATFORM_TYPES[platformType]?.defaultPort ?? 80;
}

export function buildBaseUrl(server) {
  const host = server.ip_address;
  const port = Number(server.port ?? getDefaultPort(server.platform_type));
  // 标准 HTTP 80 不写端口，避免跳到 :80 的怪异地址
  if (!port || port === 80) {
    return `http://${host}`;
  }
  return `http://${host}:${port}`;
}

export function getAdminUrl(server) {
  if (server.admin_url) return server.admin_url;
  return buildBaseUrl(server);
}

export function getDashboardUrl(server) {
  if (server.dashboard_url) return server.dashboard_url;
  if (server.platform_type === 'nodered') {
    return `${buildBaseUrl(server)}/ui`;
  }
  return null;
}

export function getHealthCheckUrl(server) {
  if (server.health_check_url) return server.health_check_url;
  if (server.platform_type === 'maisi' || !server.platform_type) {
    return null;
  }
  if (server.platform_type === 'edgebox') {
    return `${buildBaseUrl(server)}/api/v1/system/status?detail=1`;
  }
  return buildBaseUrl(server);
}

export function isMaisiPlatform(server) {
  return !server?.platform_type || server.platform_type === 'maisi';
}

export function isEdgeBoxPlatform(server) {
  return server?.platform_type === 'edgebox';
}

// 边缘服务器API服务类（迈思智能盒子专用）
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

    this.client.interceptors.response.use(
      response => response,
      error => {
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

  async getAlgorithmEngines(engineId = '') {
    const response = await this.client.get('/api/v1/algorithm/engine', {
      params: { id: engineId }
    });
    return response.data;
  }

  async getVideoChannels() {
    const response = await this.client.get('/api/v1/system/channels/mag');
    return response.data;
  }

  getChannelImage(imagePath) {
    return `${this.baseURL}/${imagePath}`;
  }

  async getEventTypes() {
    const response = await this.client.get('/api/v1/system/eventTypes');
    return response.data;
  }

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

  getEventImage(imagePath) {
    return `${this.baseURL}/${imagePath}`;
  }

  async getSystemVersion() {
    const response = await this.client.get('/api/v1/system/version');
    return response.data;
  }

  async getSystemFlash() {
    const response = await this.client.get('/api/v1/system/flash');
    return response.data;
  }

  async getDeviceInfo() {
    const response = await this.client.get('/api/v1/system/deviceInfo');
    return response.data;
  }

  async getCPUStatic() {
    const timestamp = Date.now();
    const response = await this.client.get(`/api/v1/system/cpustatic?${timestamp}`);
    return response.data;
  }

  async testConnection() {
    try {
      const result = await this.getSystemVersion();
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

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

async function testGenericConnection(url) {
  try {
    const response = await axios.get(url, { timeout: 10000, validateStatus: () => true });
    const ok = response.status >= 200 && response.status < 500;
    return { success: ok, status: response.status };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/** 探活 Edge AI Box：解析无鉴权 /api/v1/system/status?detail=1 */
async function probeEdgeBoxStatus(url) {
  try {
    let probeUrl = url;
    try {
      const u = new URL(url);
      if (!u.searchParams.has('detail')) u.searchParams.set('detail', '1');
      probeUrl = u.toString();
    } catch (_) {
      probeUrl = url.includes('?') ? `${url}&detail=1` : `${url}?detail=1`;
    }
    const response = await axios.get(probeUrl, { timeout: 12000, validateStatus: () => true });
    if (response.status !== 200) {
      return { success: false, status: response.status, error: `HTTP ${response.status}` };
    }
    const data = response.data;
    if (!data || typeof data !== 'object' || !data.system) {
      return { success: false, error: '无效的 status 响应（缺少 system 字段）' };
    }
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// 后端API客户端
const backendAPI = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  }
});

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

backendAPI.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      ElMessage.error('认证失败，请重新登录');
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
  PLATFORM_TYPES,
  getPlatformLabel,
  getDefaultPort,
  buildBaseUrl,
  getAdminUrl,
  getDashboardUrl,
  getHealthCheckUrl,
  isMaisiPlatform,

  createServerAPI(serverIP, serverPort = 80) {
    return new EdgeServerAPI(serverIP, serverPort);
  },

  async getServerList(params = {}) {
    const response = await backendAPI.get('/edge-servers', { params });
    return response.data;
  },

  async addServer(serverData) {
    const response = await backendAPI.post('/edge-servers', {
      name: serverData.name,
      ip_address: serverData.ip,
      port: serverData.port || getDefaultPort(serverData.platform_type),
      description: serverData.description || '',
      platform_type: serverData.platform_type || 'maisi',
      admin_url: serverData.admin_url || null,
      dashboard_url: serverData.dashboard_url || null,
      health_check_url: serverData.health_check_url || null,
      is_active: true
    });
    ElMessage.success('节点添加成功');
    return response.data;
  },

  async updateServer(serverId, serverData) {
    const updateData = {};
    if (serverData.name) updateData.name = serverData.name;
    if (serverData.ip) updateData.ip_address = serverData.ip;
    if (serverData.port) updateData.port = serverData.port;
    if (serverData.description !== undefined) updateData.description = serverData.description;
    if (serverData.platform_type) updateData.platform_type = serverData.platform_type;
    if (serverData.admin_url !== undefined) updateData.admin_url = serverData.admin_url || null;
    if (serverData.dashboard_url !== undefined) updateData.dashboard_url = serverData.dashboard_url || null;
    if (serverData.health_check_url !== undefined) updateData.health_check_url = serverData.health_check_url || null;
    if (serverData.is_active !== undefined) updateData.is_active = serverData.is_active;

    const response = await backendAPI.put(`/edge-servers/${serverId}`, updateData);
    ElMessage.success('节点更新成功');
    return response.data;
  },

  async removeServer(serverId) {
    await backendAPI.delete(`/edge-servers/${serverId}`);
    ElMessage.success('节点删除成功');
    return true;
  },

  async getServer(serverId) {
    const response = await backendAPI.get(`/edge-servers/${serverId}`);
    return response.data;
  },

  async updateServerStatus(serverId, statusData) {
    const response = await backendAPI.patch(`/edge-servers/${serverId}/status`, statusData);
    return response.data;
  },

  async getOnlineServers() {
    const response = await backendAPI.get('/edge-servers/online/list');
    return response.data;
  },

  async getServersByStatus(status) {
    const response = await backendAPI.get(`/edge-servers/status/${status}`);
    return response.data;
  },

  async testConnectionForServer(server) {
    if (isMaisiPlatform(server)) {
      const serverAPI = this.createServerAPI(server.ip_address, server.port);
      return serverAPI.testConnection();
    }
    if (isEdgeBoxPlatform(server)) {
      return probeEdgeBoxStatus(getHealthCheckUrl(server));
    }
    const url = getHealthCheckUrl(server);
    return testGenericConnection(url);
  },

  async testAndUpdateServerStatus(serverId, server) {
    if (!server || typeof server !== 'object') {
      throw new Error('testAndUpdateServerStatus 需要传入完整 server 对象');
    }

    try {
      if (isMaisiPlatform(server)) {
        const serverAPI = this.createServerAPI(server.ip_address, server.port);
        const connectionResult = await serverAPI.testConnection();

        if (connectionResult.success) {
          const serverInfo = await serverAPI.getServerInfo();
          await this.updateServerStatus(serverId, {
            status: 'online',
            system_info: serverInfo.data?.system || null,
            version_info: serverInfo.data?.version || null,
            device_info: serverInfo.data?.device || null
          });
          return { success: true, status: 'online' };
        }

        await this.updateServerStatus(serverId, { status: 'offline' });
        return { success: false, status: 'offline', error: connectionResult.error };
      }

      if (isEdgeBoxPlatform(server)) {
        const url = getHealthCheckUrl(server);
        const probe = await probeEdgeBoxStatus(url);
        if (probe.success) {
          const payload = probe.data;
          await this.updateServerStatus(serverId, {
            status: 'online',
            system_info: payload,
            version_info: {
              app_name: payload.system?.app_name,
              app_version: payload.system?.app_version,
              edge_inference: payload.system?.edge_inference,
              hostname: payload.system?.hostname
            },
            device_info: {
              npu: payload.npu || null,
              detection: payload.detection || null,
              models: payload.models || null
            }
          });
          return { success: true, status: 'online', data: payload };
        }
        await this.updateServerStatus(serverId, { status: 'offline' });
        return {
          success: false,
          status: 'offline',
          error: probe.error || `HTTP ${probe.status}`
        };
      }

      const url = getHealthCheckUrl(server);
      const connectionResult = await testGenericConnection(url);

      if (connectionResult.success) {
        await this.updateServerStatus(serverId, { status: 'online' });
        return { success: true, status: 'online' };
      }

      await this.updateServerStatus(serverId, { status: 'offline' });
      return {
        success: false,
        status: 'offline',
        error: connectionResult.error || `HTTP ${connectionResult.status}`
      };
    } catch (error) {
      await this.updateServerStatus(serverId, { status: 'offline' });
      return { success: false, status: 'offline', error: error.message };
    }
  }
};
