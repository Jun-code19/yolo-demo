import axios from 'axios'

const API_BASE_URL_v1 = '/api/v1'
const API_BASE_URL_v2 = '/api/v2'

const apiClient_v1 = axios.create({
  baseURL: API_BASE_URL_v1,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const apiClient_v2 = axios.create({
  baseURL: API_BASE_URL_v2,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 添加请求拦截器，自动添加认证token
apiClient_v1.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)
// 添加请求拦截器，自动添加认证token
apiClient_v2.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

export const DEFAULT_DASHBOARD_SCREEN_NAME = '园区 AI 视觉监测大屏'

/** preview 已废弃，统一归并为 mini */
export const normalizeHeatmapDisplayMode = (mode) => (mode === 'full' ? 'full' : 'mini')

/** block=普通模式着色，fusion=伪热力融合 */
export const normalizeHeatmapRenderStyle = (style) => (style === 'fusion' ? 'fusion' : 'block')

/** off | smart(TopN+悬停) | hover | all */
export const normalizeLabelMode = (mode, legacyShowLabels) => {
  if (mode === 'off' || mode === 'smart' || mode === 'all' || mode === 'hover') return mode
  if (legacyShowLabels === false) return 'off'
  return 'smart'
}

export const DEFAULT_FUSION_CONFIG = {
  blur: 32,
  opacity: 0.95,
  intensityBoost: 1.42,
  sharpLayer: 0.42,
  pointRadius: 80,
  showLabels: true,
  showBorders: false,
}

export const dashboardMapApi = {
  uploadDashboardMap: (data) => apiClient_v1.post('/heatmap/maps', data, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  }),
  getDashboardMaps: () => apiClient_v1.get('/heatmap/maps'),
  getDashboardMapImage: (mapId) => apiClient_v1.get(`/heatmap/maps/${mapId}/image`),
  getDashboardMapAreas: (mapId) => apiClient_v1.get(`/heatmap/maps/${mapId}/areas`),
  createDashboardMapArea: (data) => apiClient_v1.post('/heatmap/areas', data),
  updateDashboardMapArea: (areaId, data) => apiClient_v1.put(`/heatmap/areas/${areaId}`, data),
  deleteDashboardMapArea: (areaId) => apiClient_v1.delete(`/heatmap/areas/${areaId}`),
  createDashboardMapBinding: (data) => apiClient_v1.post('/heatmap/bindings', data),
  deleteDashboardMapAreaBindings: (areaId) => apiClient_v1.delete(`/heatmap/areas/${areaId}/bindings`),
  deleteDashboardMap: (mapId) => apiClient_v1.delete(`/heatmap/maps/${mapId}`),
  getDashboardConfig: () => apiClient_v1.get('/heatmap/dashboard/config'),
  saveDashboardConfig: (data) => apiClient_v1.post('/heatmap/dashboard/config', data),
  saveDashboardScreenName: (screenName) => apiClient_v1.put('/heatmap/dashboard/screen-name', { screen_name: screenName }),
  getDashboardData: () => apiClient_v1.get('/heatmap/dashboard/data'),
}

export const dashboardIntegrationApi = {
  getConfig: () => apiClient_v1.get('/settings/dashboard-integrations'),
  saveConfig: (data) => apiClient_v1.put('/settings/dashboard-integrations', data),
  testWaitTime: (data) => apiClient_v1.post('/settings/dashboard-integrations/test-wait-time', data),
}

export const getWaitTimeData = async (timeoutMs = 70000) => {
  try {
    const response = await apiClient_v1.get('/dashboard/wait-time', { timeout: timeoutMs });
    return response.data?.data ?? response.data;
  } catch (error) {
    console.error('Error fetching wait time data:', error);
    throw error;
  }
};

export const getWeatherData = async (lat, lon) => {
  try {
    const response = await apiClient_v1.get('/dashboard/weather', {
      params: { lat, lon },
    });
    return response.data?.data ?? response.data;
  } catch (error) {
    console.error('Error fetching weather data:', error);
    throw error;
  }
};

// 导出API和客户端
export { apiClient_v1,apiClient_v2 }