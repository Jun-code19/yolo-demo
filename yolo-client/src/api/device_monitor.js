import axios from 'axios'

const apiClientV1 = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
})

const apiClientV2 = axios.create({
  baseURL: '/api/v2',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
})

const attachAuth = (client) => {
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
}

attachAuth(apiClientV1)
attachAuth(apiClientV2)

export const deviceMonitorApi = {
  getConfig: () => apiClientV1.get('/settings/device-monitor'),
  saveConfig: (data) => apiClientV1.put('/settings/device-monitor', data),
  getPushTags: () => apiClientV1.get('/settings/device-monitor/push-tags'),
  getRuntime: () => apiClientV2.get('/settings/device-monitor/runtime'),
  reloadScheduler: () => apiClientV2.post('/settings/device-monitor/reload')
}

export const COMMON_PUSH_TAGS = [
  'device_online_status',
  // 'detection',
  // 'alarm',
  // 'system',
  // 'statistics',
  // 'crowd_analysis',
  // 'vlm_inspection',
  // 'external_event'
]

export const PROBE_METHOD_OPTIONS = [
  { value: 'rtsp', label: 'RTSP 拉流', desc: '通道级探测，适合摄像头/NVR' },
  { value: 'tcp', label: 'TCP 端口', desc: '主机级连通' },
  { value: 'http_dahua', label: 'HTTP（大华）', desc: '新大华设备 API' },
  { value: 'ping', label: 'Ping', desc: '需启用且容器有 ping 命令' }
]

export const DEVICE_TYPE_LABELS = {
  camera: '摄像头',
  nvr: 'NVR 通道',
  edge_server: '边缘服务器',
  storage_node: '存储节点',
  default: '默认（其他类型）'
}
