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
  getDashboardData: () => apiClient_v1.get('/heatmap/dashboard/data'),
}


// 导出API和客户端
export { apiClient_v1,apiClient_v2 }