import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiClient_v1, getWaitTimeData } from '@/api/dashboard.js'

export function useDashboardData() {
  // 数据状态
  const data = reactive({
    overviewData: {},
    alertData: [],
    staffDistribution: [],
    alertHistory: [],
    behaviorStats: [],
    liveMonitors: [],
    historicalStats: [],
    systemStatus: {
      status: 'normal',
      cpu: { percent: 0, total: 0, used: 0 },
      memory: { percent: 0, total: 0, used: 0 },
      disk: { percent: 0, total: 0, used: 0 },
      gpu: { percent: 0, total: 0, used: 0 }
    },
    waitTimeData: [] // 新增排队时长数据
  })

  // 加载状态
  const loading = reactive({
    overviewData: false,
    alertData: false,
    staffDistribution: false,
    alertHistory: false,
    behaviorStats: false,
    liveMonitors: false,
    historicalStats: false,
    systemStatus: false,
    waitTimeData: false // 新增排队时长加载状态
  })

  // 错误状态
  const errors = reactive({
    overviewData: null,
    alertData: null,
    staffDistribution: null,
    alertHistory: null,
    behaviorStats: null,
    liveMonitors: null,
    historicalStats: null,
    systemStatus: null,
    waitTimeData: null // 新增排队时长错误状态
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

  const get_dashboard_overview_data = async () => {
    loading.overviewData = true
    errors.overviewData = null
    
    try {
      const rawData = await apiRequest('/dashboard/overview-smart-data')
      if (rawData) {
        const item = rawData
        data.overviewData = {
          deviceCount: parseInt(item.device_count) || 0,
          detectionConfigCount: parseInt(item.detection_config_count) || 0,
          crowdAnalysisJobCount: parseInt(item.crowd_analysis_job_count) || 0,
          smartSchemeCount: parseInt(item.smart_scheme_count) || 0,
          smartEventCount: parseInt(item.smart_event_count) || 0,
          detectionSmartEventCount: parseInt(item.detection_event_count) || 0
        }
        if (Array.isArray(rawData.detection_events)) {
          data.alertHistory = rawData.detection_events.map(event => ({
            id: event.event_id,
            device: event.device_name || '未知设备',
            type: event.event_type || '未知类型',
            name: event.meta_data?.event_description,
            detection_count: event.bounding_box?.length || 0,
            confidence: (event.confidence || 0).toFixed(2),
            time: new Date(event.timestamp).toLocaleTimeString(),
            status: event.status === 'new' ? 'danger' : 'success',
            statusText: event.status === 'new' ? '未处理' : '已处理',
            isNew: (new Date() - new Date(event.timestamp)) < 300000
          }))
        }
      }
      if (Array.isArray(rawData.detection_lasted_events)) {
        data.liveMonitors = rawData.detection_lasted_events.map((event, index) => ({
          id: event.event_id,
          name: event.device_name || '未知设备',
          image: event.thumbnail_path,
          status: event.status === 'new' ? 'danger' : 'success',
          statusText: event.status === 'new' ? '告警' : '正常'
        }))
      }
    } catch (error) {
      errors.overviewData = error
      console.error('加载园区概况数据失败:', error)
    } finally {
      loading.overviewData = false
    }
  }
  
  const get_dashboard_type_data= async () => {
    loading.behaviorStats = true
    errors.behaviorStats = null
    
    try {
      const rawData = await apiRequest('/dashboard/type-smart-data')
      if (rawData && Array.isArray(rawData)) {
        data.behaviorStats = rawData.map((event, index) => ({
          type: index + 1,
          event_type: event.category,
          event_count: event.event_total,
          total_count: event.today_total,
          growth_rate: event.growth_rate,
          icon: ['production-icon', 'storage-icon', 'operation-icon', 'maintenance-icon', 'environment-icon', 'safety-icon'][index] || 'safety-icon'
        }));
          data.alertData = rawData.map(event => ({
          event_type: event.category,
          event_count: event.event_total
        }))
      }
    } catch (error) {
      errors.behaviorStats = error
      console.error('加载行为统计数据失败:', error)
    } finally {
      loading.behaviorStats = false
    }
  }

  const get_dashboard_historical_data = async () => {
    loading.historicalStats = true
    errors.historicalStats = null
    
    try {
      const rawData = await apiRequest('/dashboard/historical-smart-data')
      if (rawData && Array.isArray(rawData)) {
        data.historicalStats = rawData.map(item => ({
          date: item.date,
          detection_value: item.detection_event_count || 0,
          external_value: item.external_event_count || 0,
          smart_value: item.smart_event_count || 0,
        }))
      }
    } catch (error) {
      errors.historicalStats = error
      console.error('加载历史统计数据失败:', error)
    } finally {
      loading.historicalStats = false
    }
  }

  const get_system_status = async () => {
    loading.systemStatus = true
    errors.systemStatus = null
    try {
      const rawData = await apiRequest('/dashboard/system-status')
      if (rawData) {
        data.systemStatus = rawData
      }
    } catch (error) {
      errors.systemStatus = error
      console.error('加载系统资源数据失败:', error)
    } finally {
      loading.systemStatus = false
    }
  }

  const get_wait_time = async () => {
    loading.waitTimeData = true;
    errors.waitTimeData = null;
    try {
      const response = await getWaitTimeData();
      data.waitTimeData = response;
    } catch (error) {
      errors.waitTimeData = error;
      console.error('加载排队时长数据失败:', error);
    } finally {
      loading.waitTimeData = false;
    }
  };

  // 加载所有数据
  const loadAllData = async () => {
    await Promise.allSettled([
      get_dashboard_overview_data(),
      get_dashboard_type_data(),
      loadStaffDistribution(),
      get_dashboard_historical_data(),
      get_system_status(), // 添加系统资源数据加载
      get_wait_time() // 添加排队时长数据加载
    ])
  }

  // 刷新数据
  const refreshData = async () => {
    // await loadAllData()
  }

  // 启动自动刷新
  const startAutoRefresh = (interval = 60000) => {
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
    stopAutoRefresh
  }
} 