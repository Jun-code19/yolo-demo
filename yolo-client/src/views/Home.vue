<template>
  <div class="home-container">
    <!-- 主要统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#409EFF">
                <VideoCameraFilled />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.summary?.total_devices || 0 }}</div>
              <div class="stat-label">设备总数</div>
              <div class="stat-detail">
                <span class="online">{{ comprehensiveData.summary?.online_devices || 0 }} 在线</span>
                <span class="offline">{{ comprehensiveData.summary?.offline_devices || 0 }} 离线</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#67C23A">
                <DataLine />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.events?.detection_events?.total || 0 }}</div>
              <div class="stat-label">检测事件总数</div>
              <div class="stat-detail">
                <span class="total">{{ comprehensiveData.events?.detection_events?.today || 0 }} 今日事件</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#E6A23C">
                <Warning />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.events?.scheme_events?.total || 0 }}</div>
              <div class="stat-label">订阅事件总数</div>
              <div class="stat-detail">
                <span class="total">{{ comprehensiveData.events?.scheme_events?.today || 0 }} 今日事件</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#F56C6C">
                <Timer />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.performance?.accuracy || 0 }}%</div>
              <div class="stat-label">检测准确率</div>
              <div class="stat-detail">
                <span class="time">{{ comprehensiveData.performance?.avg_detection_time?.toFixed(3) || 0 }}s 平均耗时</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模块统计卡片 -->
    <el-row :gutter="20">
      <el-col :lg="6" :md="12" :sm="12" :xs="24" class="module-col">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>检测与模型</span>
              <el-tag type="success">{{ comprehensiveData.summary?.active_models || 0 }}/{{
                comprehensiveData.summary?.total_models || 0 }}</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">活跃 YOLO 模型</span>
              <span class="value">{{ comprehensiveData.summary?.active_models || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">检测配置</span>
              <span class="value">{{ comprehensiveData.summary?.active_detection_configs || 0 }}/{{
                comprehensiveData.summary?.total_detection_configs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">人群分析</span>
              <span class="value">{{ comprehensiveData.summary?.active_crowd_jobs || 0 }}/{{
                comprehensiveData.summary?.total_crowd_jobs || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :lg="6" :md="12" :sm="12" :xs="24" class="module-col">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>VLM 能力</span>
              <el-tag type="warning">{{ comprehensiveData.summary?.today_vlm_inspection_alerts || 0 }} 今日告警</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">VLM 推理配置</span>
              <span class="value">{{ comprehensiveData.summary?.active_vlm_pipeline_configs || 0 }}/{{
                comprehensiveData.summary?.vlm_pipeline_configs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">VLM 模型</span>
              <span class="value">{{ comprehensiveData.summary?.active_vlm_models || 0 }}/{{
                comprehensiveData.summary?.total_vlm_models || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">VLM 巡检</span>
              <span class="value">{{ comprehensiveData.summary?.active_vlm_inspection_jobs || 0 }}/{{
                comprehensiveData.summary?.total_vlm_inspection_jobs || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :lg="6" :md="12" :sm="12" :xs="24" class="module-col">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>数据推送</span>
              <el-tag type="success">{{ comprehensiveData.summary?.active_push_configs || 0 }}/{{
                comprehensiveData.summary?.total_push_configs || 0 }}</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">推送配置</span>
              <span class="value">{{ comprehensiveData.summary?.active_push_configs || 0 }}/{{
                comprehensiveData.summary?.total_push_configs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">数据监听</span>
              <span class="value">{{ comprehensiveData.summary?.active_listeners || 0 }}/{{
                comprehensiveData.summary?.total_listeners || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">边缘设备</span>
              <span class="value">{{ comprehensiveData.summary?.online_edge_servers || 0 }}/{{
                comprehensiveData.summary?.total_edge_servers || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :lg="6" :md="12" :sm="12" :xs="24" class="module-col">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>系统管理</span>
              <el-tag type="info">{{ comprehensiveData.summary?.total_users || 0 }} 用户</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">系统用户</span>
              <span class="value">{{ comprehensiveData.summary?.total_users || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">系统日志</span>
              <span class="value">{{ comprehensiveData.summary?.total_system_logs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">检测日志</span>
              <span class="value">{{ comprehensiveData.summary?.total_detection_logs || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表和活动区域 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :md="16" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>数据趋势分析</span>
              <div class="chart-legend">
                <span class="legend-item">
                  <span class="legend-color detection"></span>
                  检测事件
                </span>
                <span class="legend-item">
                  <span class="legend-color external"></span>
                  外部事件
                </span>
                <span class="legend-item">
                  <span class="legend-color scheme"></span>
                  订阅事件
                </span>
              </div>
            </div>
          </template>
          <div class="chart-container">
            <div ref="chartRef" class="chart"></div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="8" :sm="24">
        <el-card class="activity-card">
          <template #header>
            <div class="card-header">
              <span>最近活动</span>
              <el-button type="primary" link @click="viewMoreEvents">
                查看更多
              </el-button>
            </div>
          </template>
          <div class="activity-container" ref="activityContainer">
            <div class="activity-list" :style="{ transform: `translateY(${scrollOffset}px)` }">
              <div v-for="activity in comprehensiveData.recent_activities" :key="activity.event_id"
                class="activity-item">
                <div class="activity-content">
                  <div class="activity-text">{{ activity.content }}</div>
                  <div class="activity-meta">
                    <span class="activity-time">{{ activity.timestamp }}</span>
                    <el-tag size="small" :type="getActivityTagType(activity)">
                      {{ getActivitySourceLabel(activity) }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分布统计（单行 4 卡，每卡可切换维度） -->
    <el-row :gutter="16" class="distribution-row pie-panel-row">
      <el-col
        v-for="panel in piePanels"
        :key="panel.key"
        :lg="6"
        :md="12"
        :sm="12"
        :xs="24"
        class="pie-panel-col"
      >
        <el-card class="pie-panel-card">
          <template #header>
            <div class="pie-panel-header">
              <span class="pie-panel-title">{{ panel.title }}</span>
              <el-radio-group
                v-model="pieViewMode[panel.key]"
                size="small"
                @change="() => renderSwitchablePie(panel.key)"
              >
                <el-radio-button
                  v-for="view in panel.views"
                  :key="view.value"
                  :value="view.value"
                >
                  {{ view.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div class="distribution-chart distribution-chart-compact">
            <div :ref="(el) => bindPieChartRef(panel.key, el)" class="chart"></div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 订阅事件与人群分析 -->
    <el-row :gutter="20" class="distribution-row">
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>订阅事件统计</span>
              <span class="section-hint">按订阅方案 Top 20</span>
            </div>
          </template>
          <div class="distribution-chart distribution-chart-bar">
            <div ref="schemeEventChartRef" class="chart"></div>
          </div>
        </el-card>
      </el-col>

      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>人群分析趋势</span>
              <span class="section-hint">各任务平均 / 峰值人数</span>
            </div>
          </template>
          <div class="distribution-chart distribution-chart-bar">
            <div ref="crowdTrendChartRef" class="chart"></div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, watch, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  VideoCameraFilled,
  Warning,
  DataLine,
  Timer
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import deviceApi from '@/api/device'

const router = useRouter()
const chartRef = ref(null)
const schemeEventChartRef = ref(null)
const crowdTrendChartRef = ref(null)
const activityContainer = ref(null)

const piePanels = [
  {
    key: 'detection',
    title: '检测事件',
    views: [
      { value: 'type', label: '类型' },
      { value: 'status', label: '状态' }
    ]
  },
  {
    key: 'modelPipeline',
    title: '模型与推理',
    views: [
      { value: 'modelType', label: '模型' },
      { value: 'pipeline', label: '推理' }
    ]
  },
  {
    key: 'vlm',
    title: 'VLM 巡检',
    views: [
      { value: 'jobStatus', label: '任务' },
      { value: 'alertJob', label: '告警' }
    ]
  },
  {
    key: 'external',
    title: '外部事件',
    views: [
      { value: 'status', label: '状态' },
      { value: 'engine', label: '引擎' }
    ]
  }
]

const pieViewMode = reactive({
  detection: 'type',
  modelPipeline: 'modelType',
  vlm: 'jobStatus',
  external: 'status'
})

const pieChartRefMap = {}
const pieChartInstanceMap = {}

const bindPieChartRef = (key, el) => {
  if (el) {
    pieChartRefMap[key] = el
  }
}

let chart = null
let schemeEventChart = null
let crowdTrendChart = null

const PIE_COLORS = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#626AEF', '#909399', '#36CFC9', '#B37FEB']

const comprehensiveData = reactive({
  summary: {},
  events: {},
  distributions: {},
  inference_pipeline: {},
  users: {},
  performance: {},
  trends: {},
  recent_activities: [],
  crowd_analysis: {},
  vlm_inspection: {}
})

const loading = ref(false)
const scrollOffset = ref(0)
let scrollInterval = null

// 获取完整仪表盘数据
const fetchComprehensiveData = async () => {
  loading.value = true
  try {
    const response = await deviceApi.getComprehensiveDashboardOverview()
    if (response.status === 200) {
      Object.assign(comprehensiveData, response.data)
      // 更新图表
      renderCharts()
      // 启动活动滚动
      startActivityScroll()
    }
  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
    ElMessage.error('获取仪表盘数据失败')
  } finally {
    loading.value = false
  }
}

// 启动活动滚动
const startActivityScroll = () => {
  if (scrollInterval) {
    clearInterval(scrollInterval)
  }

  if (comprehensiveData.recent_activities && comprehensiveData.recent_activities.length > 0) {
    scrollInterval = setInterval(() => {
      scrollOffset.value -= 1
      // 当滚动到底部时，重置到顶部
      if (scrollOffset.value <= -comprehensiveData.recent_activities.length * 60) {
        scrollOffset.value = 0
      }
    }, 50)
  }
}

// 渲染所有图表
const renderCharts = () => {
  renderTrendChart()
  renderAllSwitchablePies()
  renderSchemeEventChart()
  renderCrowdTrendChart()
}

const initChartInstance = (chartInstance, chartRef) => {
  if (!chartRef.value) return chartInstance
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  return chartInstance
}

const setEmptyBarChart = (chartInstance, chartRef, emptyText = '暂无数据') => {
  const instance = initChartInstance(chartInstance, chartRef)
  if (!instance) return chartInstance
  instance.setOption({
    title: {
      text: emptyText,
      left: 'center',
      top: 'middle',
      textStyle: { color: '#909399', fontSize: 14, fontWeight: 'normal' }
    },
    grid: { show: false },
    xAxis: { show: false },
    yAxis: { show: false },
    series: []
  }, true)
  return instance
}

const truncateAxisLabel = (value, maxLen = 10) => {
  const text = String(value || '')
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text
}

const getSwitchablePieData = (key, mode) => {
  if (key === 'detection') {
    if (mode === 'type') {
      const typeDistribution = comprehensiveData.events?.detection_events?.type_distribution || {}
      return {
        seriesName: '检测事件类型',
        items: Object.entries(typeDistribution).map(([type, count]) => ({
          name: getEventTypeName(type),
          value: count
        }))
      }
    }
    const statusDistribution = comprehensiveData.events?.detection_events?.status_distribution || {}
    return {
      seriesName: '检测事件状态',
      items: Object.entries(statusDistribution).map(([status, count]) => ({
        name: getStatusLabel(status),
        value: count
      }))
    }
  }

  if (key === 'modelPipeline') {
    if (mode === 'pipeline') {
      const modeDistribution = comprehensiveData.inference_pipeline?.mode_distribution || {}
      return {
        seriesName: '推理模式',
        items: Object.entries(modeDistribution).map(([pipelineMode, count]) => ({
          name: getPipelineModeName(pipelineMode),
          value: count
        }))
      }
    }
    const typeDistribution = comprehensiveData.distributions?.model_types || {}
    return {
      seriesName: '模型类型',
      items: Object.entries(typeDistribution).map(([type, count]) => ({
        name: getModelTypeName(type),
        value: count
      }))
    }
  }

  if (key === 'vlm') {
    if (mode === 'alertJob') {
      const jobDistribution = comprehensiveData.vlm_inspection?.job_alert_distribution || []
      return {
        seriesName: '巡检告警任务',
        items: jobDistribution.map((job) => ({
          name: job.job_name,
          value: job.count
        }))
      }
    }
    const statusDistribution = comprehensiveData.vlm_inspection?.job_status_distribution || {}
    return {
      seriesName: '巡检任务状态',
      items: [
        { name: '运行中', value: statusDistribution.active || 0 },
        { name: '已暂停', value: statusDistribution.inactive || 0 }
      ]
    }
  }

  if (mode === 'engine') {
    const engineDistribution = comprehensiveData.events?.external_events?.engine_distribution || {}
    return {
      seriesName: '外部事件引擎',
      items: Object.entries(engineDistribution).map(([engine, count]) => ({
        name: engine || '未知引擎',
        value: count
      }))
    }
  }

  const statusDistribution = comprehensiveData.events?.external_events?.status_distribution || {}
  return {
    seriesName: '外部事件状态',
    items: Object.entries(statusDistribution).map(([status, count]) => ({
      name: getStatusLabel(status),
      value: count
    }))
  }
}

const renderSwitchablePie = (key) => {
  const chartEl = pieChartRefMap[key]
  if (!chartEl) return

  const { seriesName, items } = getSwitchablePieData(key, pieViewMode[key])
  pieChartInstanceMap[key] = renderPieChart(
    pieChartInstanceMap[key],
    { value: chartEl },
    seriesName,
    items,
    { compact: true }
  )
}

const renderAllSwitchablePies = () => {
  nextTick(() => {
    piePanels.forEach((panel) => renderSwitchablePie(panel.key))
  })
}

const renderPieChart = (chartInstance, chartRef, seriesName, items, { compact = false } = {}) => {
  if (!chartRef.value) return chartInstance

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const data = (items || []).filter((item) => item.value > 0)
  if (!data.length) {
    chartInstance.setOption({
      title: {
        text: '暂无数据',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#909399', fontSize: 14, fontWeight: 'normal' }
      },
      series: []
    }, true)
    return chartInstance
  }

  chartInstance.setOption({
    color: PIE_COLORS,
    title: { show: false },
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/>{c} ({d}%)'
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: compact ? 10 : 11 }
    },
    series: [
      {
        name: seriesName,
        type: 'pie',
        radius: compact ? ['34%', '56%'] : ['40%', '65%'],
        center: compact ? ['50%', '48%'] : ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: (params) => (params.percent >= (compact ? 10 : 8) ? `${params.name}\n${params.percent.toFixed(0)}%` : ''),
          fontSize: compact ? 10 : 11
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 6
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.15)'
          }
        },
        data
      }
    ]
  }, true)

  return chartInstance
}

// 渲染趋势图表
const renderTrendChart = () => {
  if (!chartRef.value) return

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const trends = comprehensiveData.trends?.daily || []
  const dates = trends.map(item => item.date)
  const detectionData = trends.map(item => item.detection_events)
  const externalData = trends.map(item => item.external_events)
  const schemeData = trends.map(item => item.scheme_events)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: ['检测事件', '外部事件', '订阅事件']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: 30
      }
    },
    yAxis: {
      type: 'value',
      name: '数量'
    },
    series: [
      {
        name: '检测事件',
        type: 'line',
        data: detectionData,
        itemStyle: {
          color: '#409EFF'
        },
        smooth: true
      },
      {
        name: '外部事件',
        type: 'line',
        data: externalData,
        itemStyle: {
          color: '#67C23A'
        },
        smooth: true
      },
      {
        name: '订阅事件',
        type: 'line',
        data: schemeData,
        itemStyle: {
          color: '#F56C6C'
        },
        smooth: true
      }
    ]
  }

  chart.setOption(option)
}

// 获取模型类型名称
const getModelTypeName = (type) => {
  const typeMap = {
    object_detection: '目标检测',
    vlm: 'VLM 模型',
    smart_behavior: '智能行为',
    smart_person: '人员场景',
    smart_counting: '智能人数统计',
    segmentation: '图像分割',
    keypoint: '关键点检测',
    pose: '姿态估计',
    face: '人脸识别',
    other: '其他类型'
  }
  return typeMap[type] || type
}

const getPipelineModeName = (mode) => {
  const modeMap = {
    yolo_only: '仅 YOLO',
    yolo_then_verify: 'YOLO + VLM 复检',
    yolo_then_analyze: 'YOLO + VLM 分析'
  }
  return modeMap[mode] || mode
}

const getEventTypeName = (eventType) => {
  const typeMap = {
    'object_detection': '目标检测',
    'yolo_verify': 'VLM 复检',
    'yolo_analyze': 'VLM 行为分析',
    'smart_behavior': '智能行为',
    'smart_person': '人员场景',
    'smart_counting': '智能人数统计',
    'segmentation': '图像分割',
    'keypoint': '关键点检测',
    'pose': '姿态估计',
    'face': '人脸识别',
    'other': '其他类型'
  }
  return typeMap[eventType] || eventType
}

const getActivitySourceLabel = (activity) => {
  const content = activity?.content || ''
  if (content.includes('[VLM推理]')) return 'VLM 推理'
  if (activity?.source === 'external') return '外部事件'
  return '本地检测'
}

const getActivityTagType = (activity) => {
  const content = activity?.content || ''
  if (content.includes('[VLM推理]')) return 'warning'
  if (activity?.source === 'external') return 'success'
  return 'primary'
}

// 获取状态标签
const getStatusLabel = (status) => {
  const map = {
    'new': '新事件',
    'viewed': '已查看',
    'flagged': '已标记',
    'archived': '已归档'
  };
  return map[status] || status;
};

// 渲染订阅事件条形图
const renderSchemeEventChart = () => {
  const distribution = comprehensiveData.events?.scheme_events?.scheme_distribution || []
  if (!distribution.length) {
    schemeEventChart = setEmptyBarChart(schemeEventChart, schemeEventChartRef)
    return
  }

  schemeEventChart = initChartInstance(schemeEventChart, schemeEventChartRef)
  if (!schemeEventChart) return

  const sorted = [...distribution].sort((a, b) => b.count - a.count)
  const names = sorted.map((item) => item.scheme_name)
  const counts = sorted.map((item) => item.count)

  schemeEventChart.setOption({
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const item = sorted[params[0]?.dataIndex]
        if (!item) return ''
        return [
          item.scheme_name,
          `事件数：${item.count}`,
          item.device_name ? `设备：${item.device_name}` : ''
        ].filter(Boolean).join('<br/>')
      }
    },
    grid: {
      left: 12,
      right: 12,
      top: 32,
      bottom: 56,
      containLabel: true
    },
    dataZoom: sorted.length > 10 ? [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: 0,
        end: Math.min(100, Math.round(10 / sorted.length * 100))
      },
      {
        type: 'slider',
        xAxisIndex: 0,
        height: 18,
        bottom: 4,
        start: 0,
        end: Math.min(100, Math.round(10 / sorted.length * 100)),
        borderColor: '#ebeef5',
        fillerColor: 'rgba(245, 108, 108, 0.15)',
        handleSize: '80%'
      }
    ] : undefined,
    xAxis: {
      type: 'category',
      data: names,
      axisTick: { alignWithLabel: true },
      axisLine: { lineStyle: { color: '#ebeef5' } },
      axisLabel: {
        color: '#606266',
        interval: 0,
        rotate: 35,
        fontSize: 11,
        formatter: (value) => truncateAxisLabel(value, 8)
      }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: {
        lineStyle: { type: 'dashed', color: '#ebeef5' }
      }
    },
    series: [
      {
        name: '订阅事件',
        type: 'bar',
        data: counts,
        barMaxWidth: 28,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#f56c6c' },
            { offset: 1, color: '#fab6b6' }
          ])
        },
        label: {
          show: true,
          position: 'top',
          color: '#606266',
          fontSize: 11
        }
      }
    ]
  }, true)
}

// 渲染人群分析趋势图表
const renderCrowdTrendChart = () => {
  const jobDistribution = comprehensiveData.crowd_analysis?.job_distribution || []
  if (!jobDistribution.length) {
    crowdTrendChart = setEmptyBarChart(crowdTrendChart, crowdTrendChartRef)
    return
  }

  crowdTrendChart = initChartInstance(crowdTrendChart, crowdTrendChartRef)
  if (!crowdTrendChart) return

  const sorted = [...jobDistribution].sort((a, b) => b.max_count - a.max_count)
  const jobNames = sorted.map((job) => job.job_name)
  const avgCounts = sorted.map((job) => Number(job.avg_count || 0))
  const maxCounts = sorted.map((job) => Number(job.max_count || 0))
  const sampleCounts = sorted.map((job) => Number(job.count || 0))

  crowdTrendChart.setOption({
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const index = params[0]?.dataIndex ?? 0
        const job = sorted[index]
        if (!job) return ''
        return [
          job.job_name,
          `采样次数：${sampleCounts[index]}`,
          ...params.map((item) => `${item.marker}${item.seriesName}：${item.value}`)
        ].join('<br/>')
      }
    },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { fontSize: 12, color: '#606266' }
    },
    grid: {
      left: 12,
      right: 20,
      top: 36,
      bottom: 8,
      containLabel: true
    },
    xAxis: {
      type: 'value',
      minInterval: 1,
      name: '人数',
      nameTextStyle: { color: '#909399', fontSize: 12 },
      splitLine: {
        lineStyle: { type: 'dashed', color: '#ebeef5' }
      }
    },
    yAxis: {
      type: 'category',
      data: jobNames,
      inverse: true,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: '#606266',
        formatter: (value) => truncateAxisLabel(value, 12)
      }
    },
    series: [
      {
        name: '平均人数',
        type: 'bar',
        data: avgCounts,
        barMaxWidth: 14,
        barGap: '20%',
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#79bbff' },
            { offset: 1, color: '#409eff' }
          ])
        }
      },
      {
        name: '峰值人数',
        type: 'bar',
        data: maxCounts,
        barMaxWidth: 14,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#95d475' },
            { offset: 1, color: '#67c23a' }
          ])
        },
        label: {
          show: true,
          position: 'right',
          color: '#606266',
          fontSize: 11,
          formatter: ({ value }) => (value > 0 ? value : '')
        }
      }
    ]
  }, true)
}

// 查看更多事件
const viewMoreEvents = () => {
  router.push('/detection/events')
}

// 窗口大小变化时调整图表大小
const handleResize = () => {
  if (chart) chart.resize()
  Object.values(pieChartInstanceMap).forEach((instance) => instance?.resize())
  if (schemeEventChart) schemeEventChart.resize()
  if (crowdTrendChart) crowdTrendChart.resize()
}

// 页面加载时获取数据
onMounted(() => {
  fetchComprehensiveData()
  window.addEventListener('resize', handleResize)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (scrollInterval) {
    clearInterval(scrollInterval)
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
  Object.keys(pieChartInstanceMap).forEach((key) => {
    pieChartInstanceMap[key]?.dispose()
    delete pieChartInstanceMap[key]
  })
  if (schemeEventChart) {
    schemeEventChart.dispose()
    schemeEventChart = null
  }
  if (crowdTrendChart) {
    crowdTrendChart.dispose()
    crowdTrendChart = null
  }
})

// 监听数据变化，更新图表
watch(comprehensiveData, () => {
  renderCharts()
}, { deep: true })
</script>

<style scoped>
.home-container {
  height: 100%;
  min-width: 0;
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
  text-align: center;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  color: #303133;
}

.page-header p {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  height: 120px;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-icon .el-icon {
  font-size: 24px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.stat-detail {
  font-size: 12px;
}

.stat-detail .online {
  color: #67C23A;
  margin-right: 8px;
}

.stat-detail .offline {
  color: #F56C6C;
}

.stat-detail .total {
  color: #409EFF;
}

.stat-detail .time {
  color: #E6A23C;
}

.module-col {
  display: flex;
  margin-bottom: 20px;
}

.module-card {
  flex: 1;
  width: 100%;
}

.module-card :deep(.el-card__body) {
  min-height: 132px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.module-item .label {
  color: #606266;
  font-size: 13px;
  flex: 1;
  min-width: 0;
}

.module-item .value {
  color: #303133;
  font-weight: 500;
  font-size: 13px;
  flex-shrink: 0;
  white-space: nowrap;
}

.chart-row {
  margin-bottom: 24px;
}

.chart-legend {
  display: flex;
  gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #606266;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 4px;
}

.legend-color.detection {
  background-color: #409EFF;
}

.legend-color.external {
  background-color: #67C23A;
}

.legend-color.scheme {
  background-color: #F56C6C;
}

.legend-color.logs {
  background-color: #E6A23C;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.chart {
  height: 100%;
  width: 100%;
}

.activity-card {
  height: 100%;
}

.activity-container {
  height: 350px;
  overflow: hidden;
  position: relative;
}

.activity-list {
  transition: transform 0.5s ease;
}

.activity-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.activity-text {
  font-size: 13px;
  line-height: 1.4;
  color: #303133;
}

.activity-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.activity-time {
  font-size: 12px;
  color: #909399;
}

.distribution-row {
  margin-bottom: 20px;
}

.pie-panel-row {
  margin-bottom: 20px;
}

.pie-panel-col {
  margin-bottom: 16px;
}

.pie-panel-card {
  height: 100%;
}

.pie-panel-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.pie-panel-card :deep(.el-card__body) {
  padding: 8px 12px 12px;
}

.pie-panel-header {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}

.pie-panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}

.distribution-chart-compact {
  height: 280px;
}

.distribution-chart-bar {
  height: 340px;
}

.section-hint {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

@media (min-width: 1200px) {
  .pie-panel-header {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .pie-panel-header .el-radio-group {
    flex-shrink: 0;
  }
}

.distribution-chart {
  height: 300px;
  width: 100%;
}

.dual-chart-container {
  display: flex;
  gap: 20px;
  height: 380px;
}

.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-title {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  text-align: center;
  margin-bottom: 10px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.dual-chart-container .distribution-chart {
  flex: 1;
  height: auto;
  min-height: 250px;
}

@media screen and (max-width: 1200px) {
  .el-col {
    margin-bottom: 20px;
  }
}

@media screen and (max-width: 768px) {
  .el-card {
    margin-bottom: 16px;
  }

  .chart-container {
    height: 250px;
  }

  .distribution-chart {
    height: 200px;
  }

  .distribution-chart-compact {
    height: 240px;
  }

  .distribution-chart-bar {
    height: 280px;
  }

  .chart-legend {
    flex-direction: column;
    gap: 8px;
  }

  .dual-chart-container {
    flex-direction: column;
    height: auto;
    gap: 10px;
  }

  .dual-chart-container .distribution-chart {
    min-height: 200px;
  }
}
</style>