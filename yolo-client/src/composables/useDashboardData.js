import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiClient_v1 } from '@/api/dashboard.js'

export function useDashboardData() {
  // 数据状态
  const data = reactive({
    factoryData: {},
    alertData: [],
    staffDistribution: [],
    alertHistory: [],
    behaviorStats: [],
    liveMonitors: [],
    historicalStats: []
  })

  // 加载状态
  const loading = reactive({
    factoryData: false,
    alertData: false,
    staffDistribution: false,
    alertHistory: false,
    behaviorStats: false,
    liveMonitors: false,
    historicalStats: false
  })

  // 错误状态
  const errors = reactive({
    factoryData: null,
    alertData: null,
    staffDistribution: null,
    alertHistory: null,
    behaviorStats: null,
    liveMonitors: null,
    historicalStats: null
  })

  // 定时器
  let refreshTimer = null

  // 简化的API请求函数
  const apiRequest = async (endpoint, fallbackData = null) => {
    try {
      const response = await apiClient_v1.get(endpoint)
      return response.data?.data || fallbackData
    } catch (error) {
      console.error(`API请求失败 (${endpoint}):`, error)
      return fallbackData
    }
  }

  // 加载园区概况数据
  const loadFactoryData = async () => {
    loading.factoryData = true
    errors.factoryData = null
    
    try {
      const rawData = await apiRequest('/dashboard/overview-data')
      if (rawData) {
        const item = rawData
        data.factoryData = {
          factoryCount: parseInt(item.detection_config_count) || 0,
          areaCount: parseInt(item.device_count) || 0,
          staffCount: parseInt(item.detection_event_count) || 0,
          cameraCount: parseInt(item.crowd_analysis_job_count) || 0,
          deviceCount: parseInt(item.edge_server_count) || 0,
          eventCount: parseInt(item.external_event_count) || 0
        }
      }
    } catch (error) {
      errors.factoryData = error
      console.error('加载园区概况数据失败:', error)
    } finally {
      loading.factoryData = false
    }
  }

  // 加载告警数据
  const loadAlertData = async () => {
    loading.alertData = true
    errors.alertData = null
    
    try {
      const rawData = await apiRequest('/dashboard/detection-event-data')

      if (rawData && Array.isArray(rawData)) {
        data.alertData = rawData.map(event => ({
          engine_name: event.engine_name,
          detection_count: event.detection_count
        }))
      }
    } catch (error) {
      errors.alertData = error
      console.error('加载告警数据失败:', error)
    } finally {
      loading.alertData = false
    }
  }

  // 加载游客分布数据
  const loadStaffDistribution = async () => {
    loading.staffDistribution = true
    errors.staffDistribution = null
    
    try {
      const rawData = await apiRequest('/dashboard/crowd-analysis-data')

      if (rawData && Array.isArray(rawData)) {
        const crowdJobs = rawData
        const maxCount = Math.max(...crowdJobs.map(job => job.people_count || 0), 1)
        
        data.staffDistribution = crowdJobs.slice(0, 6).map(job => ({
          area: job.job_name || '未知区域',
          count: job.people_count || 0,
          percentage: Math.round((job.people_count || 0) / maxCount * 100),
          lastUpdate: job.last_update || null
        }))
      }
    } catch (error) {
      errors.staffDistribution = error
      console.error('加载游客分布数据失败:', error)
    } finally {
      loading.staffDistribution = false
    }
  }

  // 加载告警历史数据
  const loadAlertHistory = async () => {
    loading.alertHistory = true
    errors.alertHistory = null
    
    try {
      const rawData = await apiRequest('/dashboard/alert-history-data')

      if (rawData && Array.isArray(rawData)) {
        data.alertHistory = rawData.map(event => ({
          id: event.event_id,
          device: event.device_name || '未知设备',
          type: event.engine_name || '未知算法',
          name: event.location || '未知名称',
          detection_count: event.normalized_data?.targets?.length || 0,
          confidence: (event.confidence || 0).toFixed(2),
          time: new Date(event.timestamp).toLocaleTimeString(),
          status: event.status === 'new' ? 'danger' : 'success',
          statusText: event.status === 'new' ? '未处理' : '已处理',
          isNew: (new Date() - new Date(event.timestamp)) < 300000
        }))
      }
    } catch (error) {
      errors.alertHistory = error
      console.error('加载告警历史数据失败:', error)
    } finally {
      loading.alertHistory = false
    }
  }

  // 加载行为统计数据
  const loadBehaviorStats = async () => {
    loading.behaviorStats = true
    errors.behaviorStats = null
    
    try {
      const rawData = await apiRequest('/dashboard/detection-type-data')

      if (rawData && Array.isArray(rawData)) {
        data.behaviorStats = rawData.map((event, index) => ({
          type: index + 1,
          name: event.engine_name,
          value: event.count,
          trend: event.count_yesterday_rate,
          icon: ['production-icon', 'storage-icon', 'operation-icon', 'maintenance-icon', 'environment-icon', 'safety-icon'][index] || 'safety-icon'
        }))
      }
    } catch (error) {
      errors.behaviorStats = error
      console.error('加载行为统计数据失败:', error)
    } finally {
      loading.behaviorStats = false
    }
  }

  // 加载实时监控数据
  const loadLiveMonitors = async () => {
    loading.liveMonitors = true
    errors.liveMonitors = null
    
    try {
      const rawData = await apiRequest('/dashboard/alert-history-data')

      if (rawData && Array.isArray(rawData)) {
        data.liveMonitors = rawData.slice(0, 4).map((event, index) => ({
          id: event.event_id,
          name: event.location || `监控点${index + 1}`,
          image: event.normalized_data?.processed_images?.pic_data?.original_path,
          status: event.status === 'new' ? 'danger' : 'success',
          statusText: event.status === 'new' ? '告警' : '正常'
        }))
      }
    } catch (error) {
      errors.liveMonitors = error
      console.error('加载实时监控数据失败:', error)
    } finally {
      loading.liveMonitors = false
    }
  }

  // 加载历史统计数据
  const loadHistoricalStats = async () => {
    loading.historicalStats = true
    errors.historicalStats = null
    
    try {
      const rawData = await apiRequest('/dashboard/historical-stats-data')

      if (rawData && Array.isArray(rawData)) {
        data.historicalStats = rawData.map(item => ({
          date: item.date,
          value: item.count || 0
        }))
      }
    } catch (error) {
      errors.historicalStats = error
      console.error('加载历史统计数据失败:', error)
    } finally {
      loading.historicalStats = false
    }
  }

  // 加载所有数据
  const loadAllData = async () => {
    await Promise.allSettled([
      loadFactoryData(),
      loadAlertData(),
      loadStaffDistribution(),
      loadAlertHistory(),
      loadBehaviorStats(),
      loadLiveMonitors(),
      loadHistoricalStats()
    ])
  }

  // 刷新数据
  const refreshData = async () => {
    await loadAllData()
  }

  // 启动自动刷新
  const startAutoRefresh = (interval = 30000) => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
    }
    refreshTimer = setInterval(loadAllData, interval)
  }

  // 停止自动刷新
  const stopAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  // 计算属性：总体加载状态
  const isLoading = computed(() => {
    return Object.values(loading).some(loading => loading)
  })

  // 计算属性：是否有错误
  const hasErrors = computed(() => {
    return Object.values(errors).some(error => error !== null)
  })

  // 生命周期
  onMounted(() => {
    loadAllData()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    // 数据
    data,
    
    // 状态
    loading,
    errors,
    isLoading,
    hasErrors,
    
    // 方法
    loadAllData,
    refreshData,
    startAutoRefresh,
    stopAutoRefresh,
    
    // 单独加载方法
    loadFactoryData,
    loadAlertData,
    loadStaffDistribution,
    loadAlertHistory,
    loadBehaviorStats,
    loadLiveMonitors,
    loadHistoricalStats
  }
} 