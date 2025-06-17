import { DATA_SOURCE_TYPES, DASHBOARD_MODULES } from '@/utils/dataBinding.js'

// 大屏模块配置
export const dashboardModulesConfig = {
  // 园区概况模块
  [DASHBOARD_MODULES.FACTORY_OVERVIEW]: {
    name: '园区概况',
    description: '显示任务数量、监控设备、检测事件等统计信息',
    dataSources: [
      {
        name: 'dashboard_data',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/overview-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      },
    ],
    transform: {
      custom: (data) => {        
        return {
          factoryCount: parseInt(data[0].detection_config_count) || 0,
          areaCount: parseInt(data[0].device_count) || 0,
          staffCount: parseInt(data[0].detection_event_count) || 0,
          cameraCount: parseInt(data[0].crowd_analysis_job_count) || 0,
          deviceCount: parseInt(data[0].edge_server_count) || 0,
          eventCount: parseInt(data[0].external_event_count) || 0
        }
      }
    },
    fallbackData: {
      factoryCount: 5,
      areaCount: 230,
      staffCount: 3458,
      cameraCount: 14,
      deviceCount: 12,
      eventCount: 3732
    }
  },

  // 告警数据模块
  [DASHBOARD_MODULES.ALERT_DATA]: {
    name: '检测告警数据',
    description: '异常事件类别统计',
    dataSources: [
      {
        name: 'detectionEvents',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/detection-event-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (events) => {
        
        if (!Array.isArray(events)) return []
        events = events[0]
        
        return events.map(event => ({
          engine_name: event.engine_name,
          detection_count: event.detection_count
        }))
      }
    },
    fallbackData: [
      { engine_name: '未戴安全帽',detection_count: 1},
      { engine_name: '玩手机',detection_count: 11},
      { engine_name: '区域入侵',detection_count: 38},
      { engine_name: '烟雾监测',detection_count: 1},
      { engine_name: '异常事件',detection_count: 64}
    ]
  },

  // 游客分布模块
  [DASHBOARD_MODULES.STAFF_DISTRIBUTION]: {
    name: '游客分布',
    description: '人群分析中各任务的游客数量',
    dataSources: [
      {
        name: 'crowdAnalysisData',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/crowd-analysis-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (crowdJobs) => {

        crowdJobs = crowdJobs[0]
        
        // 计算最大人数用于百分比计算
        const maxCount = Math.max(...crowdJobs.map(job => job.people_count || 0), 1)
        
        // 转换为前端显示格式，最多显示6个区域
        return crowdJobs.slice(0, 6).map(job => ({
          area: job.job_name || '未知区域',
          count: job.people_count || 0,
          percentage: Math.round((job.people_count || 0) / maxCount * 100),
          lastUpdate: job.last_update || null
        }))
      }
    },
    fallbackData: [
      { area: 'A车间', count: 749, percentage: 85 },
      { area: 'B车间', count: 631, percentage: 70 },
      { area: 'C车间', count: 525, percentage: 60 },
      { area: 'D车间', count: 444, percentage: 50 },
      { area: 'E车间', count: 375, percentage: 42 },
      { area: 'F车间', count: 350, percentage: 40 }
    ]
  },

  // 监测点位模块
  [DASHBOARD_MODULES.MONITORING_POINTS]: {
    name: '园区人数热力图',
    description: '监测设备在地图上的分布和状态',
    dataSources: [
      {
        name: 'cameras',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/devices/',
        params: { device_type: 'camera' },
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (devices) => {
        if (!Array.isArray(devices)) return []
        
        return devices.map((device, index) => ({
          x: 20 + (index % 4) * 20,
          y: 30 + Math.floor(index / 4) * 15,
          status: device.status ? 'active' : 'danger',
          deviceId: device.device_id,
          deviceName: device.device_name
        }))
      }
    },
    fallbackData: [
      { x: 25, y: 30, status: 'active' },
      { x: 45, y: 45, status: 'active' },
      { x: 65, y: 35, status: 'warning' },
      { x: 75, y: 55, status: 'active' },
      { x: 85, y: 40, status: 'active' },
      { x: 35, y: 65, status: 'danger' },
      { x: 55, y: 70, status: 'active' }
    ]
  },

  // 告警历史模块
  [DASHBOARD_MODULES.ALERT_HISTORY]: {
    name: '事件告警信息',
    description: '数据事件列表中的异常事件',
    dataSources: [
      {
        name: 'recentEvents',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/alert-history-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (events) => {
        if (!Array.isArray(events)) return []
        events = events[0]
        return events.map(event => ({
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
    },
    fallbackData: [
      { id: 1, type: '未戴安全帽', device: '摄像头001', time: '13:25:32', status: 'danger', statusText: '未处理', isNew: true, detection_count: 1, confidence: 0.9 },
      { id: 2, type: '玩手机', device: '摄像头003', time: '13:20:15', status: 'warning', statusText: '处理中', isNew: false, detection_count: 2, confidence: 0.8 },
      { id: 3, type: '区域入侵', device: '摄像头005', time: '13:15:48', status: 'success', statusText: '已处理', isNew: false, detection_count: 3, confidence: 0.7 }
    ]
  },

  // 行为统计模块
  [DASHBOARD_MODULES.BEHAVIOR_STATS]: {
    name: '检测各类型分析',
    description: '检测类型/算法引擎的分类统计',
    dataSources: [
      {
        name: 'detectionTypes',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/detection-type-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (events) => {
        if (!Array.isArray(events)) return []
        events = events[0]
        // console.log('检测类型分析原始数据:', events)
        
        return events.map((event,index) => ({
          type: index+1,
          name: event.engine_name,
          value: event.count,
          trend: event.count_yesterday_rate,
          icon: index === 0 ? 'production-icon' : index === 1 ? 'storage-icon' : index === 2 ? 'operation-icon' : index === 3 ? 'maintenance-icon' : index === 4 ? 'environment-icon' : 'safety-icon'
        }))
      }
    },
    fallbackData: [
      { type: 'production', name: '生产设备', value: 2014, trend: 5.2, icon: 'production-icon' },
      { type: 'storage', name: '存储区域', value: 3804, trend: -2.1, icon: 'storage-icon' },
      { type: 'operation', name: '作业监测', value: 2024, trend: 8.3, icon: 'operation-icon' },
      { type: 'maintenance', name: '车辆监测', value: 2048, trend: 3.7, icon: 'maintenance-icon' },
      { type: 'environment', name: '环境监测', value: 2011, trend: -1.5, icon: 'environment-icon' },
      { type: 'safety', name: '安全环保', value: 2324, trend: 12.8, icon: 'safety-icon' }
    ]
  },

  // 实时监控模块
  [DASHBOARD_MODULES.LIVE_MONITORS]: {
    name: '最新报警推送',
    description: '数据事件列表中的最新报警推送',
    dataSources: [
      {
        name: 'unhandledEvents',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/alert-history-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (events) => {
        if (!Array.isArray(events)) return []
        events = events[0].slice(0, 4)
        return events.map((event, index) => ({
          id: event.event_id,
          name: event.location || `监控点${index + 1}`,
          image: event.normalized_data?.processed_images?.pic_data?.original_path,
          status: event.status === 'new' ? 'danger' : 'success',
          statusText: event.status === 'new' ? '告警' : '正常'
        }))
      }
    },
    fallbackData: [
      { id: 1, name: '入口大门', status: 'active', statusText: '正常' },
      { id: 2, name: 'A车间', status: 'warning', statusText: '告警' },
      { id: 3, name: 'B车间', status: 'active', statusText: '正常' },
      { id: 4, name: '仓储区', status: 'active', statusText: '正常' }
    ]
  },

  // 项目排队时长模块
  [DASHBOARD_MODULES.PROJECT_QUEUE]: {
    name: '项目排队时长',
    description: '各区域的项目排队时长统计',
    dataSources: [
      {
        name: 'queueData',
        type: DATA_SOURCE_TYPES.COMPUTED,
        computation: async () => {
          // 可以从多个数据源计算得出
          return [
            { area: 'A区', time: 100 },
            { area: 'B区', time: 80 },
            { area: 'C区', time: 70 },
            { area: 'D区', time: 60 },
            { area: 'E区', time: 50 }
          ]
        },
        fallbackData: []
      }
    ],
    transform: {
      mapping: {
        areas: 'area',
        times: 'time'
      }
    },
    fallbackData: [
      { area: 'A区', time: 100 },
      { area: 'B区', time: 80 },
      { area: 'C区', time: 70 },
      { area: 'D区', time: 60 },
      { area: 'E区', time: 50 }
    ]
  },

  // 历史数据事件模块
  [DASHBOARD_MODULES.HISTORICAL_STATS]: {
    name: '历史数据事件',
    description: '数据事件列表中的历史事件统计',
    dataSources: [
      {
        name: 'historicalEvents',
        type: DATA_SOURCE_TYPES.API,
        endpoint: '/dashboard/historical-stats-data',
        params: {},
        dataPath: 'data.data',
        fallbackData: []
      }
    ],
    transform: {
      custom: (events) => {
        // console.log('历史统计数据:', events)
        
        if (!Array.isArray(events)) return []
        events = events[0]

        // 后端已经返回了格式化的数据
        return events.map(item => ({
          date: item.date,
          value: item.count || 0
        }))
      }
    },
    fallbackData: [
      { date: '2022-02-24', value: 85 },
      { date: '2022-02-25', value: 90 },
      { date: '2022-02-26', value: 95 }
    ]
  }
}

// 导出模块配置
export default dashboardModulesConfig 