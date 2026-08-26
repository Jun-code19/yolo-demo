import axios from 'axios'
import { ElMessage } from 'element-plus'

const apiClient = axios.create({
  baseURL: '/api/v2/vlm-inspection',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000
})

apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      ElMessage.error('登录已过期，请重新登录')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const vlmInspectionApi = {
  getJobs(params = { page: 1, page_size: 20 }) {
    return apiClient.get('/jobs', { params })
  },
  getJob(jobId) {
    return apiClient.get(`/jobs/${jobId}`)
  },
  createJob(data) {
    return apiClient.post('/jobs', data)
  },
  updateJob(jobId, data) {
    return apiClient.put(`/jobs/${jobId}`, data)
  },
  deleteJob(jobId) {
    return apiClient.delete(`/jobs/${jobId}/delete`)
  },
  pauseJob(jobId) {
    return apiClient.post(`/jobs/${jobId}/pause`)
  },
  resumeJob(jobId) {
    return apiClient.post(`/jobs/${jobId}/resume`)
  },
  runJobNow(jobId) {
    return apiClient.post(`/jobs/${jobId}/run`)
  },
  getFindings(jobId, params = {}) {
    return apiClient.get(`/jobs/${jobId}/findings`, { params })
  },
  getRuns(jobId, params = {}) {
    return apiClient.get(`/jobs/${jobId}/runs`, { params })
  },
  getAvailableDevices() {
    return apiClient.get('/available-devices')
  },
  getAvailableVlmModels() {
    return apiClient.get('/available-vlm-models')
  },
  getPrompts() {
    return apiClient.get('/prompts')
  },
  bootstrapQwenModel(apiKey) {
    return apiClient.post('/bootstrap-qwen-model', apiKey ? { api_key: apiKey } : {})
  },
  updateVlmCredentials(modelId, apiKey) {
    return apiClient.put(`/vlm-models/${modelId}/credentials`, { api_key: apiKey })
  },
  getVlmCredentialsStatus(modelId) {
    return apiClient.get(`/vlm-models/${modelId}/credentials-status`)
  },
  getVlmProviders() {
    return apiClient.get('/vlm-providers')
  },
  listVlmModels() {
    return apiClient.get('/vlm-models')
  },
  createVlmModel(data) {
    return apiClient.post('/vlm-models', data)
  },
  updateVlmModel(modelId, data) {
    return apiClient.put(`/vlm-models/${modelId}`, data)
  },
  deleteVlmModel(modelId) {
    return apiClient.delete(`/vlm-models/${modelId}`)
  },
  testInspection(formData) {
    return apiClient.post('/test', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000
    })
  }
}

export default vlmInspectionApi
