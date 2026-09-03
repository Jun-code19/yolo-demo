import { reactive, computed } from 'vue'
import { apiClient_v1, getWaitTimeData, DEFAULT_DASHBOARD_SCREEN_NAME } from '@/api/dashboard.js'

const EVENT_STATUS_MAP = {
  new: { status: 'danger', statusText: '未处理' },
  viewed: { status: 'success', statusText: '已查看' },
  flagged: { status: 'warning', statusText: '已标记' },
  archived: { status: 'success', statusText: '已归档' },
}

const STATUS_CHART_COLORS = {
  new: '#ff6b6b',
  viewed: '#4a90e2',
  flagged: '#ffbf00',
  archived: '#67c23a',
}

function mapEventRow(event) {
  const statusInfo = EVENT_STATUS_MAP[event.status] || { status: 'info', statusText: event.status || '未知' }
  const ts = event.timestamp ? new Date(event.timestamp) : null
  return {
    id: event.event_id,
    device: event.device_name || '未知设备',
    type: event.event_type || '未知类型',
    name: event.description || '-',
    rawStatus: event.status || 'new',
    detection_count: event.detection_count ?? 0,
    confidence: event.confidence != null ? `${event.confidence}%` : '--',
    time: ts
      ? ts.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
      : '--',
    status: statusInfo.status,
    statusText: statusInfo.statusText,
    isNew: ts ? Date.now() - ts.getTime() < 300000 : false,
    image: event.thumbnail_path,
  }
}

function formatFeedTime(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function normalizeWaitTimeItem(raw) {
  if (!raw || typeof raw !== 'object') return null
  const src = raw.activeData || raw.systemData || raw
  const name = raw.projectName ?? src.projectName ?? raw.ProjectName ?? raw.name ?? raw.project_name ?? raw.title
  const wait = src.waitingMinutes ?? raw.waitingMinutes ?? raw.WaitingMinutes ?? raw.waitTime ?? raw.wait_time ?? raw.waitMinutes
  const people = src.peopleCount ?? raw.peopleCount ?? raw.PeopleCount ?? raw.people_count ?? raw.queueCount ?? raw.QueueCount
  const interval = src.projectInterval ?? raw.projectInterval ?? raw.ProjectInterval ?? raw.project_interval ?? raw.interval
  if (name == null && wait == null && people == null && interval == null) return null
  return {
    projectName: String(name ?? '未知项目'),
    waitingMinutes: Number(wait ?? 0),
    peopleCount: Number(people ?? 0),
    projectInterval: Number(interval ?? 0),
  }
}

function parseWaitTimeResponse(payload) {
  if (payload == null) return []
  let list = null
  if (Array.isArray(payload)) list = payload
  else if (Array.isArray(payload.data)) list = payload.data
  else if (Array.isArray(payload.Data)) list = payload.Data
  else if (Array.isArray(payload.items)) list = payload.items
  else if (Array.isArray(payload.Items)) list = payload.Items
  else if (Array.isArray(payload.result)) list = payload.result
  else if (Array.isArray(payload.Result)) list = payload.Result
  else if (Array.isArray(payload.records)) list = payload.records
  else if (Array.isArray(payload.Records)) list = payload.Records
  if (!list) return []
  return list.map(normalizeWaitTimeItem).filter(Boolean)
}

function applyWaitTimeToData(data, payload) {
  const items = parseWaitTimeResponse(payload)
  if (items.length > 0) {
    data.waitTimeData = items
    data.useWaitTimeChart = true
  } else {
    data.waitTimeData = []
    data.useWaitTimeChart = false
  }
}

function buildKpiList(overview, statsScope) {
  const o = overview || {}
  const useToday = statsScope === 'today' && (o.detection_event_today || 0) > 0
  return [
    { key: 'device', value: `${o.device_online || 0}/${o.device_total || 0}`, label: '设备在线', sub: `${o.device_offline || 0} 离线` },
    { key: 'pending', value: o.detection_event_new || 0, label: '待处理事件', sub: `累计 ${o.detection_event_total || 0} 条`, highlight: (o.detection_event_new || 0) > 0 },
    { key: 'events', value: useToday ? (o.detection_event_today || 0) : (o.detection_event_total || 0), label: useToday ? '今日检测' : '累计检测', sub: useToday ? `累计 ${o.detection_event_total || 0}` : '历史总量' },
    { key: 'config', value: `${o.detection_config_enabled || 0}/${o.detection_config_total || 0}`, label: '检测任务', sub: '启用 / 总数' },
    { key: 'perf', value: o.avg_detection_time_ms > 0 ? `${o.avg_detection_time_ms}ms` : '--', label: '近7天均耗', sub: '检测性能' },
    { key: 'conf', value: o.avg_confidence > 0 ? `${o.avg_confidence}%` : '--', label: '平均置信度', sub: '近7天' },
  ]
}

function buildKpiExtended(overview) {
  const o = overview || {}
  return [
    { key: 'vlm', value: o.vlm_alert_today || 0, label: '今日 VLM 告警', sub: `累计 ${o.vlm_alert_total || 0}` },
    { key: 'composite', value: o.composite_alert_today || 0, label: '今日复合告警', sub: `规则 ${o.alert_rule_enabled || 0} 条启用`, highlight: (o.composite_alert_today || 0) > 0 },
    { key: 'smart', value: o.smart_event_today || 0, label: '今日订阅事件', sub: `方案 ${o.smart_scheme_running || 0} 运行中` },
    { key: 'alertRule', value: o.composite_alert_total || 0, label: '规则', sub: `今日 ${o.composite_alert_today || 0} · 启用 ${o.alert_rule_enabled || 0} 条`, highlight: (o.composite_alert_today || 0) > 0 },
    { key: 'push', value: o.push_success_today || 0, label: '今日推送成功', sub: `失败 ${o.push_failure_today || 0} · 配置 ${o.push_config_enabled || 0}`, highlight: (o.push_failure_today || 0) > 0 },
    { key: 'model', value: `${o.active_models || 0}/${o.total_models || 0}`, label: 'YOLO 模型', sub: `监听异常 ${o.listener_error || 0}`, highlight: (o.listener_error || 0) > 0 },
  ]
}

export function useDashboardData() {
  const data = reactive({
    kpiList: [],
    kpiExtended: [],
    overviewSummary: {},
    statsScope: 'total',
    deviceRankScope: 'total',
    typeStats: [],
    deviceRanking: [],
    alertRuleStats: [],
    eventStatusStats: [],
    hourlyStats: [],
    behaviorStats: [],
    alertFeed: [],
    pushFailures: [],
    heatmapAreas: [],
    listenerSummary: [],
    offlineDevices: [],
    crowdDistribution: [],
    alertHistory: [],
    liveMonitors: [],
    historicalStats: [],
    performanceTrend: [],
    waitTimeData: [],
    useWaitTimeChart: false,
    systemStatus: {
      status: 'normal',
      cpu: { percent: 0, total: 0, used: 0 },
      memory: { percent: 0, total: 0, used: 0 },
      disk: { percent: 0, total: 0, used: 0 },
      gpu: { percent: 0, total: 0, used: 0 },
    },
    lastUpdated: '',
    screenName: DEFAULT_DASHBOARD_SCREEN_NAME,
  })

  const loading = reactive({ board: false, systemStatus: false, waitTime: false })
  const errors = reactive({ board: null, systemStatus: null, waitTime: null })
  let refreshTimer = null

  const apiRequest = async (endpoint, fallback = null) => {
    try {
      const response = await apiClient_v1.get(endpoint)
      return response.data?.data ?? fallback
    } catch (error) {
      console.error(`API请求失败 (${endpoint}):`, error)
      return fallback
    }
  }

  const loadBoardData = async () => {
    loading.board = true
    errors.board = null
    try {
      const board = await apiRequest('/dashboard/board-data')
      if (!board) return

      const overview = board.overview || {}
      data.overviewSummary = overview
      data.statsScope = board.stats_scope || 'total'
      data.deviceRankScope = board.device_rank_scope || 'total'
      data.kpiList = buildKpiList(overview, data.statsScope)
      data.kpiExtended = buildKpiExtended(overview)
      data.lastUpdated = board.query_time
        ? new Date(board.query_time).toLocaleTimeString('zh-CN')
        : new Date().toLocaleTimeString('zh-CN')
      data.screenName = board.screen_name || DEFAULT_DASHBOARD_SCREEN_NAME

      data.typeStats = (board.detection_type_stats || []).map((item) => ({
        name: item.category,
        value: item.display_count ?? item.total_count ?? 0,
      }))

      data.deviceRanking = (board.device_ranking || []).map((item) => ({
        name: item.device_name,
        value: item.today_count ?? 0,
      }))

      data.alertRuleStats = (board.alert_rule_stats || board.external_engine_stats || []).map((item) => ({
        name: item.name,
        value: item.value ?? 0,
      }))

      data.eventStatusStats = (board.event_status_distribution || []).map((item) => ({
        name: item.label,
        value: item.count ?? 0,
        status: item.status,
        color: STATUS_CHART_COLORS[item.status] || '#909399',
      }))

      data.hourlyStats = board.hourly_distribution || []

      data.behaviorStats = (board.behavior_stats || []).map((item) => ({
        name: item.category,
        value: item.display_count ?? 0,
        growth: item.growth_rate ?? 0,
      }))

      const composite = (board.recent_composite_alerts || []).map((item) => ({
        id: `c-${item.id}`,
        source: 'composite',
        sourceLabel: '规则',
        title: item.title,
        device: item.device_name,
        time: formatFeedTime(item.timestamp),
        ts: item.timestamp ? new Date(item.timestamp).getTime() : 0,
      }))
      const vlm = (board.recent_vlm_alerts || []).map((item) => ({
        id: `v-${item.id}`,
        source: 'vlm',
        sourceLabel: 'VLM',
        title: item.title,
        device: item.device_name,
        time: formatFeedTime(item.timestamp),
        ts: item.timestamp ? new Date(item.timestamp).getTime() : 0,
      }))
      const smart = (board.recent_smart_events || []).map((item) => ({
        id: `s-${item.id}`,
        source: 'smart',
        sourceLabel: '订阅',
        title: item.title,
        device: item.event_type || '',
        time: formatFeedTime(item.timestamp),
        ts: item.timestamp ? new Date(item.timestamp).getTime() : 0,
      }))
      data.alertFeed = [...composite, ...vlm, ...smart]
        .sort((a, b) => b.ts - a.ts)
        .slice(0, 16)

      data.pushFailures = board.push_failures || []
      data.heatmapAreas = board.heatmap_area_stats || []
      data.listenerSummary = board.listener_status_summary || []

      data.offlineDevices = board.offline_devices || []
      data.crowdDistribution = board.crowd_distribution || []

      data.historicalStats = (board.historical_trend || []).map((item) => ({
        date: item.date,
        detection: item.detection_event_count || 0,
        alertRule: item.alert_rule_count ?? item.external_event_count ?? 0,
        smart: item.smart_event_count || 0,
      }))

      data.performanceTrend = board.performance_trend || []
      data.alertHistory = (board.recent_events || []).slice(0, 20).map(mapEventRow)
      data.liveMonitors = (board.latest_snapshots || []).slice(0, 6).map((event) => ({
        id: event.event_id,
        name: event.device_name || '未知设备',
        type: event.event_type || '',
        image: event.thumbnail_path,
        status: event.status === 'new' ? 'warning' : 'active',
        statusText: event.status === 'new' ? '新告警' : '已处理',
      }))

      applyWaitTimeToData(data, null)
    } finally {
      loading.board = false
    }
  }

  const loadWaitTime = async () => {
    loading.waitTime = true
    errors.waitTime = null
    try {
      const raw = await getWaitTimeData(70000)
      applyWaitTimeToData(data, raw)
    } catch (error) {
      data.waitTimeData = []
      data.useWaitTimeChart = false
      errors.waitTime = error
    } finally {
      loading.waitTime = false
    }
  }

  const loadSystemStatus = async () => {
    loading.systemStatus = true
    try {
      const raw = await apiRequest('/dashboard/system-status')
      if (raw) data.systemStatus = raw
    } catch (error) {
      errors.systemStatus = error
    } finally {
      loading.systemStatus = false
    }
  }

  const loadAllData = async () => {
    await loadBoardData()
    loadSystemStatus()
    loadWaitTime()
  }

  const refreshData = async () => { await loadAllData() }

  const startAutoRefresh = (interval = 60000) => {
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = setInterval(loadAllData, interval)
  }

  const stopAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  const typeChartTitle = computed(() =>
    data.statsScope === 'today' ? '今日检测类型' : '累计检测类型 Top'
  )
  const deviceChartTitle = computed(() =>
    data.deviceRankScope === 'today' ? '今日设备告警 Top' : '累计设备告警 Top'
  )
  const thirdPanelTitle = computed(() =>
    data.useWaitTimeChart ? '项目排队时长' : '系统资源'
  )
  const isLoading = computed(() => Object.values(loading).some(Boolean))
  const hasErrors = computed(() => Object.values(errors).some(Boolean))

  return {
    data,
    loading,
    errors,
    isLoading,
    hasErrors,
    typeChartTitle,
    deviceChartTitle,
    thirdPanelTitle,
    loadAllData,
    refreshData,
    startAutoRefresh,
    stopAutoRefresh,
  }
}
