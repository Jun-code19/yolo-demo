import axios from 'axios'
import { ElMessage } from 'element-plus'

const apiClient = axios.create({
  baseURL: '/api/v1/person-search',
  timeout: 180000
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

export function getPersonSearchStats() {
  return apiClient.get('/stats')
}

export function getPersonReidModelInfo() {
  return apiClient.get('/model-info')
}

export function getPersonGallery(params = {}) {
  return apiClient.get('/gallery', { params })
}

export function getPersonGalleryDetail(galleryId) {
  return apiClient.get(`/gallery/${galleryId}`)
}

export function getPersonTrackDetail(trackId) {
  return apiClient.get(`/tracks/${trackId}`)
}

export function searchPersonByImage(formData, params = {}) {
  return apiClient.post('/search', formData, {
    params,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function indexPersonEvent(eventId) {
  return apiClient.post(`/index-event/${eventId}`)
}

export function batchIndexPersonEvents(limit = 50) {
  return apiClient.post('/batch-index', { limit })
}

export function rebuildPersonGalleryEmbeddings(limit = 5000, force = true) {
  return apiClient.post('/rebuild-embeddings', { limit, force }, { timeout: 60000 })
}

export function getPersonRebuildEmbeddingsStatus() {
  return apiClient.get('/rebuild-embeddings/status', { timeout: 15000 })
}

export default {
  getPersonSearchStats,
  getPersonReidModelInfo,
  getPersonGallery,
  getPersonGalleryDetail,
  getPersonTrackDetail,
  searchPersonByImage,
  indexPersonEvent,
  batchIndexPersonEvents,
  rebuildPersonGalleryEmbeddings,
  getPersonRebuildEmbeddingsStatus
}
