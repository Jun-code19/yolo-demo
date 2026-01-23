<template>
  <div class="dashboard-container">
    <!-- 顶部标题栏 -->
    <div class="dashboard-header">
      <div class="header-left">
        <div class="time-display">{{ currentTime }}</div>
      </div>
      <div class="header-center">
        <h1 class="main-title">园区AI视觉监测数据大屏</h1>
      </div>
      <div class="header-right">
        <div class="dashboard-controls">
          <div class="weather-info">
            <span>{{ weatherData.city }}</span>
            <span>{{ weatherData.temperature }}</span>
            <span>{{ weatherData.text }}</span>
          </div>
        </div>

      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="dashboard-main">
      <!-- 左侧面板 -->
      <div class="dashboard-left">
        <!-- 园区概况 -->
        <div class="panel factory-overview">
          <h3 class="panel-title">园区概况</h3>
          <div class="overview-grid">
            <div class="overview-item">
              <div class="overview-icon factory-icon">
              </div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.detectionConfigCount }}</div>
                <div class="overview-label">任务数量</div>
                <!-- 任务总数为检测配置任务列表中所有任务数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon area-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.deviceCount }}</div>
                <div class="overview-label">监控设备</div>
                <!-- 监控设备为设备列表中所有监控数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon staff-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.detectionSmartEventCount }}</div>
                <div class="overview-label">检测事件</div>
                <!-- 检测事件为检测事件列表中所有检测事件数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon camera-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.crowdAnalysisJobCount }}</div>
                <div class="overview-label">项目数量</div>
                <!-- 项目数量为人群分析中所有项目数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon device-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.smartSchemeCount }}</div>
                <div class="overview-label">订阅设备</div>
                <!-- 订阅设备为边缘设备列表中所有订阅设备数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon event-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ overviewData.smartEventCount }}</div>
                <div class="overview-label">订阅事件</div>
                <!-- 订阅事件为数据事件列表中所有订阅事件数量 -->
              </div>
            </div>
          </div>
        </div>

        <!-- 项目排队时长 -->
        <!-- 暂定 -->
        <div class="panel safety-chart">
          <h3 class="panel-title">项目排队时长</h3>
          <div class="chart-container">
            <div ref="waitTimeChartRef" class="chart"></div>
          </div>
        </div>

        <!-- 游客分布 -->
        <!-- 游客分布为人群分析中各任务的游客数量 -->
        <div class="panel staff-distribution">
          <h3 class="panel-title">项目人数分布</h3>
          <div class="chart-container">
            <div ref="staffDistributionChartRef" class="chart"></div>
          </div>
        </div>
        <!-- 系统资源监听 -->
        <div class="panel system-chart">
          <h3 class="panel-title">系统资源</h3>
          <div class="chart-container">
            <div ref="systemChartRef" class="chart"></div>
          </div>
        </div>
      </div>

      <!-- 中间面板 -->
      <div class="dashboard-center">
        <!-- 检测告警数据 -->
        <!-- 检测告警数据为数据事件列表中的异常事件类别统计 -->
        <div class="panel alert-data">
          <h3 class="panel-title">检测类型统计</h3>
          <div class="alert-stats">
            <div class="alert-item" v-for="(item, index) in displayedAlertData" :key="item.event_type">
              <div class="alert-value"
                :class="index === displayedAlertData.length - 1 ? 'danger' : index % 4 === 0 ? 'warning' : index % 4 === 1 ? 'info' : index % 4 === 2 ? 'success' : 'danger'">
                {{ item.event_count }}</div>
              <div class="alert-label">{{ item.event_type }}</div>
            </div>
          </div>
        </div>

        <!-- 人数热力图 -->
        <div class="panel heatmap-panel">
          <h3 class="panel-title">
            人数分布图
          </h3>
          <div class="heatmap-container">
            <DashboardHeatMap @open-map-zoom="handleOpenMapZoom" />
          </div>
        </div>

        <!-- 事件告警信息 -->
        <!-- 事件告警信息为数据事件列表中的异常事件 -->
        <div class="panel alert-history">
          <h3 class="panel-title">检测事件信息</h3>
          <div class="alert-table">
            <div class="table-header">
              <div class="col">检测类型</div>
              <div class="col">设备名称</div>
              <div class="col col-detail">详情</div>
              <div class="col">数量</div>
              <div class="col">置信度</div>
              <div class="col">时间</div>
              <div class="col">状态</div>
            </div>
            <div class="table-body" ref="alertTableBodyRef">
              <transition-group name="alert-fade" tag="div" class="table-rows-container">
                <div v-for="alert in alertHistory" :key="alert.id" class="table-row"
                  :class="{ 'highlight': alert.isNew }">
                  <div class="col">{{ alert.type }}</div>
                  <div class="col">{{ alert.device }}</div>
                  <div class="col col-detail">{{ alert.name }}</div>
                  <div class="col">{{ alert.detection_count }}</div>
                  <div class="col">{{ alert.confidence }}</div>
                  <div class="col">{{ alert.time }}</div>
                  <div class="col">
                    <span class="status-badge" :class="alert.status">
                      {{ alert.statusText }}
                    </span>
                  </div>
                </div>
              </transition-group>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="dashboard-right">
        <!-- 检测各类型分析 -->
        <!-- 检测各类型分析为检测类型/算法引擎的分类统计 -->
        <div class="panel behavior-analysis">
          <h3 class="panel-title">今日检测分析</h3>
          <div class="behavior-stats">
            <div class="behavior-item" v-for="item in displayedBehaviorStats" :key="item.type">
              <div class="behavior-icon" :class="item.icon"></div>
              <div class="behavior-content">
                <div class="behavior-name">{{ item.event_type }}</div>
                <div class="behavior-value">{{ item.event_count }}:{{ item.total_count }}</div>
                <div class="behavior-trend" :class="item.growth_rate > 0 ? 'up' : item.growth_rate < 0 ? 'down' : 'equal'">
                  {{ item.growth_rate > 0 ? '↑' : item.growth_rate < 0 ? '↓' : '-' }} {{ Math.abs(item.growth_rate) }}% </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 历史数据事件 -->
          <!-- 历史数据事件为数据事件列表中的历史事件统计 -->
          <div class="panel compliance-chart">
            <h3 class="panel-title">历史检测统计</h3>
            <div class="chart-container">
              <div ref="complianceChartRef" class="chart"></div>
            </div>
          </div>

          <!-- 最新报警推送 -->
          <!-- 最新报警推送为数据事件列表中的最新报警推送 -->
          <div class="panel live-monitor">
            <h3 class="panel-title">最新检测记录</h3>
            <div class="monitor-grid">
              <div class="monitor-item" v-for="monitor in displayedLiveMonitors" :key="monitor.id">
                <div class="monitor-screen">
                  <img :src="getImageUrl(monitor.image)" :alt="monitor.name" @error="handleImageError" />
                  <div class="monitor-overlay">
                    <div class="monitor-name">{{ monitor.name }}</div>
                    <div class="monitor-status" :class="monitor.status">
                      {{ monitor.statusText }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 检测占比分类 -->
          <!-- 检测占比分类为检测各类型分析对应的风险占比分类 -->
          <div class="panel risk-distribution">
            <h3 class="panel-title">检测占比分类</h3>
            <div class="chart-container">
              <div ref="riskChartRef" class="chart"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 地图缩放对话框 -->
      <el-dialog v-model="showMapZoomDialog" title="地图预览" width="85%" :top="'3vh'" class="dashboard-map-dialog"
        :show-close="false">
        <template #header>
          <div class="dialog-header-custom">
            <div class="dialog-title-custom">
              <span class="title-icon">🗺️</span>
              <span class="title-text">地图预览</span>
            </div>
            <div class="dialog-controls">
              <div class="zoom-info">
                缩放: {{ Math.round(zoomState.scale * 100) }}%
              </div>
              <button @click="showMapZoomDialog = false" class="close-btn-custom">
                <span class="btn-icon">✕</span>
                <span>关闭</span>
              </button>
            </div>
          </div>
        </template>

        <div class="map-zoom-container">
          <canvas ref="zoomCanvas" class="zoom-canvas" @wheel="handleZoomWheel" @mousedown="handleZoomMouseDown"
            @mousemove="handleZoomMouseMove" @mouseup="handleZoomMouseUp" @mouseleave="handleZoomMouseUp"
            @dblclick="resetZoom"></canvas>
          <div class="zoom-tips">
            <div class="tip-item">🖱️ 滚轮缩放</div>
            <div class="tip-item">✋ 拖拽移动</div>
            <div class="tip-item">🔄 双击重置</div>
          </div>
        </div>

        <template #footer>
          <div class="dialog-footer-custom">
            <button @click="goToHeatMapManagement" class="footer-btn primary">
              <span class="btn-icon">⚙️</span>
              <span>管理设置</span>
            </button>
          </div>
        </template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import DashboardHeatMap from '@/components/DashboardHeatMap.vue'
import { getWeatherData } from '@/api/dashboard.js' // 新增：导入 getWeatherData

const router = useRouter()

// 响应式数据
const currentTime = ref('')
const waitTimeChartRef = ref(null)
const complianceChartRef = ref(null)
const riskChartRef = ref(null)
const systemChartRef = ref(null)
const staffDistributionChartRef = ref(null) // 新增：项目人数分布图表ref

// 实时监控轮播相关
const liveMonitorStartIndex = ref(0)
let liveMonitorCarouselInterval = null

// 检测事件信息滚动相关
let alertHistoryScrollInterval = null
const alertTableBodyRef = ref(null); // 新增：获取表格body的引用

// 地图缩放功能相关
const showMapZoomDialog = ref(false)
const zoomCanvas = ref(null)
const mapZoomData = ref({
  mapImage: null,
  areas: [],
  config: {}
})

// 缩放相关状态
const zoomState = reactive({
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  isDragging: false,
  lastMouseX: 0,
  lastMouseY: 0
})

// 天气数据
const weatherData = reactive({
  city: '未知',
  temperature: '--',
  text: '--' // 新增天气描述字段
});

// 检测类型统计轮播相关
const alertCarouselStartIndex = ref(0)
let alertCarouselInterval = null

// 今日检测分析轮播相关
const behaviorCarouselStartIndex = ref(0)

// 使用简化的数据管理
import { useDashboardData } from '@/composables/useDashboardData.js'

const {
  data,
  isLoading,
  hasErrors,
  refreshData,
  stopAutoRefresh
} = useDashboardData()

// 获取排队时长数据
const waitTimeData = computed(() => data.waitTimeData);

// 获取图片URL
const getImageUrl = (imagePath) => {
  // 使用后端提供的图片服务API
  if (imagePath) {
    return `/api/v1/data-listeners/images/${encodeURIComponent(imagePath)}`
  }
}

// 处理图片加载错误
const handleImageError = (event) => {
  event.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjRjVGNUY1Ii8+CjxwYXRoIGQ9Ik0yMCAzMEMyNS41MjI5IDMwIDMwIDI1LjUyMjkgMzAgMjBDMzAgMTQuNDc3MSAyNS41MjI5IDEwIDIwIDEwQzE0LjQ3NzEgMTAgMTAgMTQuNDc3MSAxMCAyMEMxMCAyNS41MjI5IDE0LjQ3NzEgMzAgMjAgMzBaIiBmaWxsPSIjQ0NDQ0NDIi8+CjxwYXRoIGQ9Ik0yMCAyMi41QzIxLjM4MDcgMjIuNSAyMi41IDIxLjM4MDcgMjIuNSAyMEMyMi41IDE4LjYxOTMgMjEuMzgwNyAxNy41IDIwIDE3LjVDMTguNjE5MyAxNy41IDE3LjUgMTguNjE5MyAxNy41IDIwQzE3LjUgMjEuMzgwNyAxOC42MTkzIDIyLjUgMjAgMjIuNVoiIGZpbGw9IiNGRkZGRkYiLz4KPC9zdmc+'
  event.target.style.opacity = '0.5'
}

// 简化的数据访问
const overviewData = computed(() => data.overviewData)
const alertData = computed(() => data.alertData)
const staffDistribution = computed(() => data.staffDistribution)
const alertHistory = computed(() => data.alertHistory)
const behaviorStats = computed(() => data.behaviorStats)
const liveMonitors = computed(() => data.liveMonitors)
const historicalStats = computed(() => data.historicalStats)
const systemStatus = computed(() => data.systemStatus)

// 计算属性：当前显示在轮播中的 liveMonitors
const displayedLiveMonitors = computed(() => {
  const monitors = liveMonitors.value
  const startIndex = liveMonitorStartIndex.value
  const endIndex = startIndex + 4
  
  if (monitors.length <= 4) {
    return monitors
  } else if (endIndex <= monitors.length) {
    return monitors.slice(startIndex, endIndex)
  } else {
    // 循环显示：从末尾截取一部分，再从开头截取一部分
    return monitors.slice(startIndex).concat(monitors.slice(0, endIndex % monitors.length))
  }
})

// 计算属性：当前显示在轮播中的 alertData
const displayedAlertData = computed(() => {
  const data = alertData.value
  const displayCount = 5 // 每次显示6个
  if (data.length <= displayCount) {
    return data
  }
  const startIndex = alertCarouselStartIndex.value
  const endIndex = startIndex + displayCount
  if (endIndex <= data.length) {
    return data.slice(startIndex, endIndex)
  } else {
    // 从末尾截取一部分，再从开头截取一部分补齐
    const firstPart = data.slice(startIndex)
    const secondPart = data.slice(0, endIndex % data.length)
    return firstPart.concat(secondPart)
  }
})

// 计算属性：当前显示在轮播中的 behaviorStats
const displayedBehaviorStats = computed(() => {
  const data = behaviorStats.value
  const displayCount = 5 // 每次显示5个
  if (data.length <= displayCount) {
    return data
  }
  const startIndex = behaviorCarouselStartIndex.value
  const endIndex = startIndex + displayCount
  if (endIndex <= data.length) {
    return data.slice(startIndex, endIndex)
  } else {
    // 从末尾截取一部分，再从开头截取一部分补齐
    const firstPart = data.slice(startIndex)
    const secondPart = data.slice(0, endIndex % data.length)
    return firstPart.concat(secondPart)
  }
})

let timeInterval = null

// 图表实例存储
let waitTimeChart = null
let complianceChart = null
let riskChart = null
let systemChart = null
let staffDistributionChart = null // 新增：项目人数分布图表实例

// 初始化图表
const initCharts = () => {
  // 安全作业合格率图表
  waitTimeChart = echarts.init(waitTimeChartRef.value)
  updatewaitTimeChart()

  // 历史数据事件图表
  complianceChart = echarts.init(complianceChartRef.value)
  updateComplianceChart()

  // 风险占比分类图表
  riskChart = echarts.init(riskChartRef.value)
  updateRiskChart()

  systemChart = echarts.init(systemChartRef.value)
  updateSystemChart()

  // 初始化项目人数分布图表
  staffDistributionChart = echarts.init(staffDistributionChartRef.value)
  updateStaffDistributionChart()

  // 响应式处理
  window.addEventListener('resize', () => {
    waitTimeChart?.resize()
    complianceChart?.resize()
    riskChart?.resize()
    systemChart?.resize()
    staffDistributionChart?.resize() // 新增：项目人数分布图表响应式处理
  })
}

// 更新安全作业合格率图表
const updatewaitTimeChart = () => {
  if (!waitTimeChart) return

  const projectNames = waitTimeData.value.map(item => item.systemData.projectName);
  const waitingMinutes = waitTimeData.value.map(item => item.systemData.waitingMinutes);
  const peopleCount = waitTimeData.value.map(item => item.systemData.peopleCount);
  const projectInterval = waitTimeData.value.map(item => item.systemData.projectInterval);

  waitTimeChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '8%',
      right: '8%',
      top: '20%',
      bottom: '5%',
      containLabel: true
    },
    legend: {
      data: ['排队时长', '排队人数', '项目时间'],
      textStyle: { color: '#ffffff', fontSize: 10},
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(30, 60, 114, 0.9)',
      borderColor: '#ff8a65',
      borderWidth: 2,
      textStyle: { color: '#ffffff' },
      formatter: function (params) {
        let res = `<b>${params[0].name}</b><br/>`;
        params.forEach(item => {
          res += `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${item.color};"></span>`;
          res += `${item.seriesName}: ${item.value}<br/>`;
        });
        return res;
      }
    },
    xAxis: {
      type: 'category',
      data: projectNames,
      axisLabel: {
        color: '#ffffff',
        fontSize: 10,
        fontWeight: 'bold',
      },
      axisLine: {
        lineStyle: { color: '#ff8a65', width: 2 }
      },
      axisTick: {
        show: false
      },
      splitLine: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#ffffff',
        fontSize: 10,
        fontWeight: 'bold',
        formatter: '{value}'
      },
      axisLine: {
        lineStyle: { color: '#ff8a65', width: 2 }
      },
      splitLine: {
        lineStyle: { color: 'rgba(255, 138, 101, 0.3)', type: 'dashed' }
      }
    },
    series: [
      {
        name: '排队时长',
        type: 'bar',
        data: waitingMinutes,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [ // 纵向渐变
            { offset: 0, color: '#ff8a65' },
            { offset: 1, color: '#ff6b6b' }
          ]),
          borderColor: '#ff8a65',
          borderWidth: 1,
          borderRadius: [5, 5, 0, 0], // 圆角
          shadowBlur: 10,
          shadowColor: 'rgba(255, 138, 101, 0.5)'
        },
        barWidth: '20%',
        animationDelay: (idx) => idx * 100,
        animationDuration: 1000
      },
      {
        name: '排队人数',
        type: 'bar',
        data: peopleCount,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#4a90e2' },
            { offset: 1, color: '#1e3c72' }
          ]),
          borderColor: '#4a90e2',
          borderWidth: 1,
          borderRadius: [5, 5, 0, 0],
          shadowBlur: 10,
          shadowColor: 'rgba(74, 144, 226, 0.5)'
        },
        barWidth: '20%',
        animationDelay: (idx) => idx * 100 + 150,
        animationDuration: 1000
      },
      {
        name: '项目时间',
        type: 'bar',
        data: projectInterval,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2ec7cd' },
            { offset: 1, color: '#1fdac5' }
          ]),
          borderColor: '#2ec7cd',
          borderWidth: 1,
          borderRadius: [5, 5, 0, 0],
          shadowBlur: 10,
          shadowColor: 'rgba(46, 199, 205, 0.5)'
        },
        barWidth: '20%',
        animationDelay: (idx) => idx * 100 + 300,
        animationDuration: 1000
      }
    ]
  })
}

// 更新历史数据事件图表
const updateComplianceChart = () => {
  if (!complianceChart) return

  // 确保有数据
  const chartData = historicalStats.value || []

  // 动态计算Y轴最大值，考虑所有三个事件类型
  const maxDetection = Math.max(...chartData.map(item => item.detection_value || 0), 0)
  const maxExternal = Math.max(...chartData.map(item => item.external_value || 0), 0)
  const maxSmart = Math.max(...chartData.map(item => item.smart_value || 0), 0)
  const overallMaxValue = Math.max(maxDetection, maxExternal, maxSmart)

  const yAxisMax = Math.ceil(overallMaxValue * 1.2) // 增加20%的缓冲

  complianceChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '15%',
      right: '10%',
      top: '20%',
      bottom: '25%'
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 60, 114, 0.9)',
      borderColor: '#ff8a65',
      borderWidth: 2,
      textStyle: {
        color: '#ffffff'
      },
      formatter: function (params) {
        let res = params[0].name + '<br/>';
        params.forEach(item => {
          res += '<span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:' + item.color + ';"></span>'
            + item.seriesName + ': ' + item.value + '<br/>';
        });
        return res;
      }
    },
    xAxis: {
      type: 'category',
      data: chartData.map(item => {
        // 格式化日期显示
        const date = new Date(item.date)
        // 月和日保留两位数
        // return `${date.getMonth() + 1}/${date.getDate()}`
        return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
      }),
      axisLabel: {
        color: '#ffffff',
        fontSize: 10,
        fontWeight: 'bold',
        rotate: chartData.length > 6 ? 45 : 0, // 数据点多时旋转标签
        interval: 0 // 显示所有标签
      },
      axisLine: {
        lineStyle: {
          color: '#ff8a65',
          width: 2
        }
      },
      axisTick: {
        lineStyle: { color: '#ff8a65' }
      }
    },
    yAxis: {
      type: 'value',
      max: yAxisMax,
      axisLabel: {
        color: '#ffffff',
        fontSize: 12,
        fontWeight: 'bold'
      },
      axisLine: {
        lineStyle: {
          color: '#ff8a65',
          width: 2
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(255, 138, 101, 0.3)',
          type: 'dashed'
        }
      }
    },
    series: [
      {
        name: '检测事件',
        data: chartData.map(item => item.detection_value || 0),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        itemStyle: {
          color: '#4a90e2',
          borderColor: '#ffffff',
          borderWidth: 3,
          shadowBlur: 15,
          shadowColor: 'rgba(74, 144, 226, 0.8)'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(74, 144, 226, 0.4)' },
            { offset: 0.5, color: 'rgba(74, 144, 226, 0.2)' },
            { offset: 1, color: 'rgba(74, 144, 226, 0.1)' }
          ])
        },
        animationDuration: 2000
      },
      {
        name: '外部事件',
        data: chartData.map(item => item.external_value || 0),
        type: 'line',
        smooth: true,
        symbol: 'rect',
        symbolSize: 5,
        itemStyle: {
          color: '#ffbf00',
          borderColor: '#ffffff',
          borderWidth: 3,
          shadowBlur: 15,
          shadowColor: 'rgba(255, 191, 0, 0.8)'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255, 191, 0, 0.4)' },
            { offset: 0.5, color: 'rgba(255, 191, 0, 0.2)' },
            { offset: 1, color: 'rgba(255, 191, 0, 0.1)' }
          ])
        },
        animationDuration: 2000
      },
      {
        name: '订阅事件',
        data: chartData.map(item => item.smart_value || 0),
        type: 'line',
        smooth: true,
        symbol: 'triangle',
        symbolSize: 5,
        itemStyle: {
          color: '#ff8a65',
          borderColor: '#ffffff',
          borderWidth: 3,
          shadowBlur: 15,
          shadowColor: 'rgba(255, 138, 101, 0.8)'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255, 138, 101, 0.4)' },
            { offset: 0.5, color: 'rgba(255, 138, 101, 0.2)' },
            { offset: 1, color: 'rgba(255, 138, 101, 0.1)' }
          ])
        },
        animationDuration: 2000
      }
    ]
  })
}

// 更新检测类型占比分类图表
const updateRiskChart = () => {
  if (!riskChart) return

  // 计算总值
  const total = behaviorStats.value.reduce((sum, item) => sum + item.event_count, 0)
  // 定义一组默认颜色
  const defaultColors = [
    ['#83bff6', '#188df0'], // 蓝色渐变
    ['#2ec7cd', '#1fdac5'], // 青色渐变
    ['#b6a2de', '#8a7fd5'], // 紫色渐变
    ['#ffbf00', '#ff8a65'], // 橙色渐变
    ['#c23531', '#a61b18'], // 红色渐变
    ['#d48265', '#bb505d'], // 棕色渐变
    ['#91c7ae', '#749f83'], // 绿色渐变
    ['#749f83', '#ca8622'], // 橄榄色渐变
    ['#6e7074', '#546570'], // 灰色渐变
    ['#c4ccd3', '#97a0a8']  // 浅灰色渐变
  ];

  // 使用 behaviorStats 数据，并计算百分比
  const chartData = behaviorStats.value.map((item, index) => ({
    value: total > 0 ? Number(((item.event_count / total) * 100).toFixed(1)) : 0,
    name: item.event_type,
    itemStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
        { offset: 0, color: defaultColors[index % defaultColors.length][0] },
        { offset: 1, color: defaultColors[index % defaultColors.length][1] }
      ]),
      shadowBlur: 15,
      shadowColor: `rgba(${parseInt(defaultColors[index % defaultColors.length][0].slice(1, 3), 16)}, ${parseInt(defaultColors[index % defaultColors.length][0].slice(3, 5), 16)}, ${parseInt(defaultColors[index % defaultColors.length][0].slice(5, 7), 16)}, 0.5)`
    }
  }))

  riskChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}% ({d}%)'
    },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '50%'],
      data: chartData,
      label: {
        show: true,
        color: '#ffffff',
        fontSize: 13,
        // fontWeight: 'bold',
        formatter: '{b}: {c}%',
        textShadowBlur: 10,
        textShadowColor: 'rgba(255, 138, 101, 0.8)'
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 20,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

//更新系统资源信息
const updateSystemChart = () =>{
  if (!systemChart) return

  const resources = [];

  // 添加GPU数据 (仅当百分比大于0时)
  if (systemStatus.value.gpu && systemStatus.value.gpu.percent > 0) {
    resources.push({ name: 'GPU', value: systemStatus.value.gpu.percent, used: systemStatus.value.gpu.used, total: systemStatus.value.gpu.total, color: ['#1fdac5', '#2ec7cd'] });
  }

  // 添加磁盘数据
  if (systemStatus.value.disk) {
    resources.push({ name: '磁盘', value: systemStatus.value.disk.percent, used: systemStatus.value.disk.used, total: systemStatus.value.disk.total, color: ['#ffbf00', '#ff8a65'] });
  }

  // 添加内存数据
  if (systemStatus.value.memory) {
    resources.push({ name: '内存', value: systemStatus.value.memory.percent, used: systemStatus.value.memory.used, total: systemStatus.value.memory.total, color: ['#4a90e2', '#1e3c72'] });
  }

  // 添加CPU数据
  if (systemStatus.value.cpu) {
    resources.push({ name: 'CPU', value: systemStatus.value.cpu.percent, used: systemStatus.value.cpu.used, total: systemStatus.value.cpu.total, color: ['#ff8a65', '#ff6b6b'] });
  }

  systemChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '10%',
      right: '15%',
      top: '15%',
      bottom: '15%',
      containLabel: true // 确保标签显示完全
    },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        formatter: '{value}%',
        color: '#ffffff',
        fontSize: 12
      },
      axisLine: {
        lineStyle: {
          color: '#ff8a65',
          width: 2
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(255, 138, 101, 0.3)',
          type: 'dashed'
        }
      }
    },
    yAxis: {
      type: 'category',
      data: resources.map(r => r.name),
      axisLabel: {
        color: '#ffffff',
        fontSize: 12,
        // fontWeight: 'bold'
      },
      axisLine: {
        lineStyle: {
          color: '#ff8a65',
          width: 2
        }
      },
      axisTick: {
        show: false
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      backgroundColor: 'rgba(30, 60, 114, 0.9)',
      borderColor: '#ff8a65',
      borderWidth: 2,
      textStyle: {
        color: '#ffffff'
      },
      formatter: function (params) {
        const data = params[0].data;
        // 直接从data中获取resourceData
        const resource = data.resourceData;
        if (!resource) return '';
        
        let unit = 'GB'; // 默认单位
        if (resource.name === 'CPU' || resource.name === 'GPU') {
          unit = ''; // CPU和GPU没有单位
        }

        return `<b>${resource.name}</b><br/>` +
               `使用率: ${resource.value.toFixed(1)}%<br/>` +
               (resource.total > 0 ? `已用: ${resource.used.toFixed(1)}${unit} / 总量: ${resource.total.toFixed(1)}${unit}` : '');
      }
    },
    series: [
      {
        name: '使用率',
        type: 'bar',
        barWidth: '60%',
        data: resources.map(resource => ({
          value: resource.value,
          name: resource.name,
          itemStyle: {
            borderRadius: [0, 10, 10, 0], // 圆角
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [ // 水平渐变
              { offset: 0, color: resource.color[0] },
              { offset: 1, color: resource.color[1] }
            ]),
            shadowColor: 'rgba(0, 0, 0, 0.5)',
            shadowBlur: 10
          },
          // 将原始资源数据存储在data中，以便tooltip访问
          resourceData: resource
        })),
        label: {
          show: true,
          position: 'right',
          formatter: '{c}%',
          color: '#ffffff',
          fontSize: 12,
          fontWeight: 'bold',
          textShadowColor: 'rgba(0, 0, 0, 0.5)',
          textShadowBlur: 5
        }
      }
    ]
  });
}

// 更新时间
const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).replace(/\//g, '-')
}

// 启动实时监控轮播
const startLiveMonitorCarousel = () => {
  if (liveMonitorCarouselInterval) {
    clearInterval(liveMonitorCarouselInterval)
  }
  liveMonitorCarouselInterval = setInterval(() => {
    const monitors = liveMonitors.value
    if (monitors.length > 4) {
      liveMonitorStartIndex.value = (liveMonitorStartIndex.value + 4) % monitors.length
    }
  }, 10000) // 每10秒切换一次
}

// 启动检测事件信息滚动
const startAlertHistoryScroll = () => {
  if (alertHistoryScrollInterval) {
    clearInterval(alertHistoryScrollInterval);
  }
  const tableBody = alertTableBodyRef.value;
  if (!tableBody) return;

  const scrollStep = 1; // 每次滚动的像素值
  const scrollIntervalTime = 50; // 滚动间隔时间（毫秒）

  alertHistoryScrollInterval = setInterval(() => {
    tableBody.scrollTop += scrollStep;

    // 如果滚动到底部，则重置滚动位置
    if (tableBody.scrollTop + tableBody.clientHeight >= tableBody.scrollHeight) {
      tableBody.scrollTop = 0;
    }
  }, scrollIntervalTime);
}

// 启动检测类型统计轮播
const startAlertDataCarousel = () => {
  if (alertCarouselInterval) {
    clearInterval(alertCarouselInterval)
  }
    alertCarouselInterval = setInterval(() => {
      if (alertData.value.length > 5) { // 超过5个才启动切换
        alertCarouselStartIndex.value = (alertCarouselStartIndex.value + 1) % alertData.value.length
        behaviorCarouselStartIndex.value = (behaviorCarouselStartIndex.value + 1) % behaviorStats.value.length
      }
    }, 2500) // 每3秒切换一次
}

// 简化的刷新方法
const handleRefreshData = async () => {
  await refreshData()
  // 延迟更新图表，确保数据已经更新
  setTimeout(() => {
    updateComplianceChart()
  }, 100)
}

onMounted(async () => {
  updateTime()
  fetchWeather(); // 调用新的天气获取函数
  timeInterval = setInterval(updateTime, 1000)
  // 延迟初始化图表，确保DOM已渲染
  setTimeout(() => {
    initCharts()
  }, 100)
  startLiveMonitorCarousel() // 启动实时监控轮播
  startAlertHistoryScroll() // 启动检测事件信息滚动
  startAlertDataCarousel() // 启动检测类型统计轮播
})

// 新的天气获取函数
const fetchWeather = () => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
  
        try {
          const data = await getWeatherData(lat, lon);
          if (data.results && data.results.length > 0) {
            weatherData.city = data.results[0].location.name || '未知城市';
            weatherData.temperature = `${data.results[0].now.temperature}°C`;
            weatherData.text = data.results[0].now.text || '--';
          } else {
            console.error('心知天气API未返回有效数据');
            weatherData.city = '获取失败';
            weatherData.temperature = '--';
            weatherData.text = '--';
          }
        } catch (error) {
          console.error('获取天气数据失败:', error);
          weatherData.city = '获取失败';
          weatherData.temperature = '--';
          weatherData.text = '--';
        }
      },
      async (error) => {
        console.error('获取地理位置失败:', error);
        // 如果获取地理位置失败，则使用默认城市（例如北京）的经纬度来获取天气
        const defaultLat = 39.9042;
        const defaultLon = 116.4074;
        try {
          const data = await getWeatherData(defaultLat, defaultLon);
          if (data.results && data.results.length > 0) {
            weatherData.city = data.results[0].location.name || '未知城市';
            weatherData.temperature = `${data.results[0].now.temperature}°C`;
            weatherData.text = data.results[0].now.text || '--';
          } else {
            console.error('心知天气API未返回有效数据 (默认城市)');
            weatherData.city = '获取失败';
            weatherData.temperature = '--';
            weatherData.text = '--';
          }
        } catch (defaultError) {
          console.error('获取默认城市天气数据失败:', defaultError);
          weatherData.city = '获取失败';
          weatherData.temperature = '--';
          weatherData.text = '--';
        }
      },
      { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
    );
  } else {
    console.error('浏览器不支持地理位置功能。');
    weatherData.city = '不支持地理位置';
    weatherData.temperature = '--';
    weatherData.text = '--';
  }
};

// 监听历史统计数据变化，自动更新图表
watch(historicalStats, (newData) => {
  // console.log('historicalStats 数据变化:', newData)
  if (complianceChart && newData) {
    updateComplianceChart()
  }
}, { deep: true })

// 监听 behaviorStats 数据变化
watch(behaviorStats, (newData) => {
  if (riskChart && newData) {
    updateRiskChart()
  }
}, { deep: true })

// 监听 systemStatus 数据变化
watch(systemStatus, (newData) => {
  if (systemChart && newData) {
    updateSystemChart()
  }
}, { deep: true })

// 监听 waitTimeData 变化，自动更新图表
watch(waitTimeData, (newData) => {
  if (waitTimeChart && newData) {
    updatewaitTimeChart();
  }
}, { deep: true });

// 监听 staffDistribution 数据变化，自动更新图表
watch(staffDistribution, (newData) => {
  if (staffDistributionChart && newData) {
    updateStaffDistributionChart();
  }
}, { deep: true });

// 地图缩放功能方法
const handleOpenMapZoom = (data) => {
  mapZoomData.value = data
  showMapZoomDialog.value = true
  nextTick(() => {
    resetZoom()
    drawZoomCanvas()
  })
}

const drawZoomCanvas = () => {
  if (!zoomCanvas.value || !mapZoomData.value.mapImage) return

  const canvas = zoomCanvas.value
  const ctx = canvas.getContext('2d')

  // 设置canvas尺寸
  const container = canvas.parentElement
  const rect = container.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height

  // 清除画布
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 计算绘制参数
  const scale = Math.min(canvas.width / mapZoomData.value.mapImage.width, canvas.height / mapZoomData.value.mapImage.height) * zoomState.scale
  const mapWidth = mapZoomData.value.mapImage.width * scale
  const mapHeight = mapZoomData.value.mapImage.height * scale
  const x = (canvas.width - mapWidth) / 2 + zoomState.offsetX
  const y = (canvas.height - mapHeight) / 2 + zoomState.offsetY

  // 绘制地图
  ctx.drawImage(mapZoomData.value.mapImage, x, y, mapWidth, mapHeight)

  // 绘制区域
  mapZoomData.value.areas.forEach(area => {
    if (area.points && area.points.length >= 3) {
      drawAreaOnZoomCanvas(ctx, area, { x, y, scale })
    }
  })
}

const drawAreaOnZoomCanvas = (ctx, area, transform) => {
  if (!area.points || area.points.length < 3) return

  const { x: offsetX, y: offsetY, scale } = transform

  ctx.beginPath()
  const firstPoint = area.points[0]
  ctx.moveTo(firstPoint.x * scale + offsetX, firstPoint.y * scale + offsetY)

  area.points.forEach(point => {
    ctx.lineTo(point.x * scale + offsetX, point.y * scale + offsetY)
  })
  ctx.closePath()

  // 填充颜色
  const areaColor = area.color ? area.color.replace(/[\d\.]+\)$/g, '0.4)') : 'rgba(74, 144, 226, 0.4)'
  ctx.fillStyle = areaColor
  ctx.fill()

  // 绘制边框
  const borderColor = area.color ? area.color.replace(/rgba?/, 'rgb').replace(/,\s*[\d\.]+\)/, ')') : '#4a90e2'
  ctx.strokeStyle = borderColor
  ctx.lineWidth = Math.max(2, scale * 2)
  ctx.stroke()

  // 绘制标签
  const center = calculateAreaCenter(area)
  const centerX = center.x * scale + offsetX
  const centerY = center.y * scale + offsetY

  const fontSize = Math.max(12, Math.min(24, scale * 16))

  ctx.fillStyle = '#333'
  ctx.font = `bold ${fontSize}px Arial`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  // 添加文字阴影效果
  ctx.shadowColor = 'rgba(255, 255, 255, 0.8)'
  ctx.shadowBlur = 3
  ctx.shadowOffsetX = 1
  ctx.shadowOffsetY = 1

  ctx.fillText(area.name, centerX, centerY - fontSize * 0.6)
  ctx.fillText(`${area.currentCount || 0}人`, centerX, centerY + fontSize * 0.6)

  // 重置阴影
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0
  ctx.shadowOffsetX = 0
  ctx.shadowOffsetY = 0
}

const calculateAreaCenter = (area) => {
  if (!area.points || area.points.length === 0) return { x: 0, y: 0 }

  const sumX = area.points.reduce((sum, point) => sum + point.x, 0)
  const sumY = area.points.reduce((sum, point) => sum + point.y, 0)

  return {
    x: sumX / area.points.length,
    y: sumY / area.points.length
  }
}

const handleZoomWheel = (event) => {
  event.preventDefault()
  const delta = event.deltaY > 0 ? 0.9 : 1.1
  const newScale = Math.max(0.5, Math.min(5, zoomState.scale * delta))

  // 计算鼠标在canvas上的位置
  const rect = event.target.getBoundingClientRect()
  const mouseX = event.clientX - rect.left
  const mouseY = event.clientY - rect.top

  // 计算当前图像的实际显示位置和尺寸
  const currentImageScale = Math.min(rect.width / mapZoomData.value.mapImage.width, rect.height / mapZoomData.value.mapImage.height) * zoomState.scale
  const currentImageWidth = mapZoomData.value.mapImage.width * currentImageScale
  const currentImageHeight = mapZoomData.value.mapImage.height * currentImageScale
  const currentImageX = (rect.width - currentImageWidth) / 2 + zoomState.offsetX
  const currentImageY = (rect.height - currentImageHeight) / 2 + zoomState.offsetY

  // 计算鼠标相对于图像的位置比例
  const relativeX = (mouseX - currentImageX) / currentImageWidth
  const relativeY = (mouseY - currentImageY) / currentImageHeight

  // 计算新的图像尺寸
  const newImageScale = Math.min(rect.width / mapZoomData.value.mapImage.width, rect.height / mapZoomData.value.mapImage.height) * newScale
  const newImageWidth = mapZoomData.value.mapImage.width * newImageScale
  const newImageHeight = mapZoomData.value.mapImage.height * newImageScale

  // 计算新的偏移量，使鼠标位置在图像上的相对位置保持不变
  const newImageX = mouseX - relativeX * newImageWidth
  const newImageY = mouseY - relativeY * newImageHeight

  // 更新偏移量和缩放比例
  zoomState.offsetX = newImageX - (rect.width - newImageWidth) / 2
  zoomState.offsetY = newImageY - (rect.height - newImageHeight) / 2
  zoomState.scale = newScale

  drawZoomCanvas()
}

const handleZoomMouseDown = (event) => {
  zoomState.isDragging = true
  zoomState.lastMouseX = event.clientX
  zoomState.lastMouseY = event.clientY
  event.target.style.cursor = 'grabbing'
}

const handleZoomMouseMove = (event) => {
  if (zoomState.isDragging) {
    const deltaX = event.clientX - zoomState.lastMouseX
    const deltaY = event.clientY - zoomState.lastMouseY

    zoomState.offsetX += deltaX
    zoomState.offsetY += deltaY
    zoomState.lastMouseX = event.clientX
    zoomState.lastMouseY = event.clientY

    drawZoomCanvas()
  }
}

const handleZoomMouseUp = () => {
  zoomState.isDragging = false
  if (zoomCanvas.value) {
    zoomCanvas.value.style.cursor = 'grab'
  }
}

const resetZoom = () => {
  zoomState.scale = 1
  zoomState.offsetX = 0
  zoomState.offsetY = 0
  if (zoomCanvas.value) {
    drawZoomCanvas()
  }
}

const goToHeatMapManagement = () => {
  router.push('/heatmap-management')
}

// 暴露方法给父组件或调试使用
defineExpose({
  refreshData: handleRefreshData,
  isLoading,
  hasErrors,
  data
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  // 停止自动刷新
  stopAutoRefresh()
  if (liveMonitorCarouselInterval) clearInterval(liveMonitorCarouselInterval) // 停止实时监控轮播
  if (alertHistoryScrollInterval) clearInterval(alertHistoryScrollInterval) // 停止检测事件信息滚动
  if (alertCarouselInterval) clearInterval(alertCarouselInterval) // 停止检测类型统计轮播
  if (staffDistributionChart) staffDistributionChart.dispose(); // 新增：销毁图表实例
})

// 更新项目人数分布图表
const updateStaffDistributionChart = () => {
  if (!staffDistributionChart) return;

  const chartData = staffDistribution.value.map(item => ({
    name: item.area,
    value: item.count
  }));

  staffDistributionChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '10%',
      right: '10%',
      top: '20%',
      bottom: '5%', // 调整底部间距以容纳图例
      containLabel: true
    },
    legend: {
      data: ['人数 (柱状图)', '人数 (折线图)'],
      textStyle: { color: '#ffffff' }
    },
    xAxis: {
      type: 'category',
      data: chartData.map(item => item.name),
      axisLabel: {
        color: '#ffffff',
        fontSize: 10,
      },
      axisLine: {
        lineStyle: { color: '#ff8a65', width: 2 }
      },
      axisTick: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#ffffff',
        fontSize: 10
      },
      axisLine: {
        lineStyle: { color: '#ff8a65', width: 2 }
      },
      splitLine: {
        lineStyle: { color: 'rgba(255, 138, 101, 0.3)', type: 'dashed' }
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(30, 60, 114, 0.9)',
      borderColor: '#ff8a65',
      borderWidth: 2,
      textStyle: { color: '#ffffff' }
    },
    series: [
      {
        name: '人数 (柱状图)',
        type: 'bar',
        data: chartData.map(item => item.value),
        barWidth: '15%', // 调整柱子宽度
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2ec7cd' },
            { offset: 1, color: '#1fdac5' }
          ]),
          borderColor: '#2ec7cd',
          borderWidth: 1,
          borderRadius: [5, 5, 0, 0],
          shadowBlur: 10,
          shadowColor: 'rgba(46, 199, 205, 0.5)'
        },
        animationDelay: (idx) => idx * 100,
        animationDuration: 1000
      },
      {
        name: '人数 (折线图)',
        type: 'line',
        data: chartData.map(item => item.value),
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: {
          color: '#ff8a65',
          width: 3,
          shadowBlur: 10,
          shadowColor: 'rgba(255, 138, 101, 0.5)'
        },
        itemStyle: {
          color: '#ff8a65',
          borderColor: '#fff',
          borderWidth: 2
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(255, 138, 101, 0.3)' },
            { offset: 1, color: 'rgba(255, 138, 101, 0)' }
          ])
        },
        animationDelay: (idx) => idx * 100 + 50,
        animationDuration: 1000
      }
    ]
  });
};

</script>

<style scoped>
.dashboard-container {
  width: 100%;
  height: 100vh;
  background:
    radial-gradient(ellipse at top, rgba(30, 60, 114, 0.4) 0%, transparent 50%),
    radial-gradient(ellipse at bottom, rgba(255, 138, 101, 0.3) 0%, transparent 50%),
    linear-gradient(135deg, #0f1a2e 0%, #1e3c72 30%, #2a4d7a 70%, #4a90e2 100%);
  color: #ffffff;
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  overflow: hidden;
  position: relative;
}

.dashboard-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image:
    linear-gradient(rgba(74, 144, 226, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 138, 101, 0.05) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none;
  z-index: 1;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 70px;
  padding: 0 40px;
  background: linear-gradient(90deg,
      rgba(30, 60, 114, 0.8) 0%,
      rgba(74, 144, 226, 0.6) 50%,
      rgba(255, 138, 101, 0.8) 100%);
  border-bottom: 2px solid #ff8a65;
  box-shadow:
    0 2px 20px rgba(255, 138, 101, 0.4),
    0 1px 0 rgba(255, 255, 255, 0.1);
  position: relative;
  z-index: 10;
  backdrop-filter: blur(15px);
}

.dashboard-header::before {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #4a90e2, #ff8a65, transparent);
  animation: headerGlow 3s ease-in-out infinite alternate;
}

@keyframes headerGlow {
  0% {
    opacity: 0.5;
    transform: scaleX(0.8);
  }

  100% {
    opacity: 1;
    transform: scaleX(1);
  }
}

.time-display {
  font-size: 18px;
  color: #ffffff;
  font-weight: 500;
  letter-spacing: 1px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.main-title {
  font-size: 34px;
  font-weight: bold;
  background: linear-gradient(45deg, #ffffff, #ffe0b5, #ff8a65);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 30px rgba(255, 138, 101, 0.6);
  margin: 0;
  letter-spacing: 2px;
  animation: titleGlow 4s ease-in-out infinite alternate;
}

@keyframes titleGlow {
  0% {
    filter: drop-shadow(0 0 20px rgba(255, 138, 101, 0.4));
  }

  100% {
    filter: drop-shadow(0 0 30px rgba(255, 138, 101, 0.8));
  }
}

.dashboard-controls {
  display: flex;
  gap: 10px;
  margin-right: 20px;
}

.control-btn {
  background: linear-gradient(135deg, rgba(74, 144, 226, 0.8), rgba(255, 138, 101, 0.8));
  border: 1px solid rgba(255, 138, 101, 0.6);
  color: #ffffff;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 10px rgba(255, 138, 101, 0.3);
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 100px;
  justify-content: center;
}

.control-btn:hover {
  background: linear-gradient(135deg, rgba(255, 138, 101, 0.9), rgba(74, 144, 226, 0.9));
  border-color: #ff8a65;
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.5);
  transform: translateY(-1px);
}

.control-btn:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(255, 138, 101, 0.4);
}

.control-btn:disabled {
  background: linear-gradient(135deg, rgba(108, 117, 125, 0.8), rgba(108, 117, 125, 0.6));
  border-color: rgba(108, 117, 125, 0.6);
  cursor: not-allowed;
  transform: none;
  box-shadow: 0 2px 10px rgba(108, 117, 125, 0.3);
}

.btn-icon {
  display: inline-block;
  transition: transform 0.5s ease;
}

.refresh-btn:hover .btn-icon {
  transform: rotate(180deg);
}

.config-btn {
  background: linear-gradient(135deg, rgba(111, 66, 193, 0.8), rgba(255, 138, 101, 0.8));
}

.config-btn:hover {
  background: linear-gradient(135deg, rgba(255, 138, 101, 0.9), rgba(111, 66, 193, 0.9));
}

.weather-info {
  font-size: 16px;
  color: #ffffff;
  font-weight: 500;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  display: flex; /* 新增：使子元素横向排列 */
  gap: 15px; /* 新增：增加子元素之间的间距 */
}

.dashboard-main {
  display: flex;
  height: calc(100vh - 80px);
  padding: 10px;
  gap: 10px;
  position: relative;
  z-index: 5;
}

.dashboard-left,
.dashboard-center,
.dashboard-right {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dashboard-left {
  flex: 0 0 25vw;
  overflow-y: auto;
  height: calc(100vh - 90px);
}

.dashboard-center {
  flex: 1;
  overflow-y: auto;
  height: calc(100vh - 90px);
}

.dashboard-right {
  flex: 0 0 25vw;
  overflow-y: auto;
  height: calc(100vh - 90px);
}

.panel {
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.7) 0%,
      rgba(15, 26, 46, 0.8) 50%,
      rgba(42, 77, 122, 0.7) 100%);
  border: 1px solid rgba(255, 138, 101, 0.4);
  border-radius: 12px;
  padding: 10px;
  backdrop-filter: blur(15px);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.1),
    0 0 20px rgba(255, 138, 101, 0.2);
  position: relative;
  overflow: hidden;
}

.panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg,
      transparent,
      #ff8a65,
      #4a90e2,
      #ff8a65,
      transparent);
  border-radius: 12px 12px 0 0;
  animation: panelGlow 4s ease-in-out infinite alternate;
}

@keyframes panelGlow {
  0% {
    opacity: 0.5;
  }

  100% {
    opacity: 1;
  }
}

.panel-title {
  font-size: 16px;
  font-weight: bold;
  background: linear-gradient(135deg, #ffffff, #ffe0b5);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0 0 16px 0;
  text-align: center;
  position: relative;
  letter-spacing: 1px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.panel-title::after {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #ff8a65, transparent);
}

/* 工厂概况样式 */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.overview-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.15) 0%,
      rgba(255, 138, 101, 0.1) 100%);
  border-radius: 8px;
  border: 1px solid rgba(255, 138, 101, 0.3);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.overview-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 138, 101, 0.2), transparent);
  transition: left 0.5s ease;
}

.overview-item:hover {
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.25) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  border-color: #ff8a65;
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.3);
}

.overview-item:hover::before {
  left: 100%;
}

.overview-icon {

  /* 如果页面宽度大于1200px，小于1600px，则不显示icon */
  /* display: none; */
  @media (max-width: 1600px) and (min-width: 1200px) {
    display: none;
    /* display: block; */
  }

  width: 30px;
  height: 30px;
  margin-right: 12px;
  border-radius: 50%;
  background-size: 20px;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.factory-icon {
  background: linear-gradient(135deg, #ff8a65, #ff6b6b) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M12 2l3.09 6.26L22 9l-5 4.87L18.18 21 12 17.27 5.82 21 7 13.87 2 9l6.91-.74L12 2z"/></svg>') center/50% no-repeat;
}

.area-icon {
  background: linear-gradient(135deg, #4a90e2, #1e3c72) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>') center/50% no-repeat;
}

.staff-icon {
  background: linear-gradient(135deg, #ff8a65, #4a90e2) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M16 4c0-1.11.89-2 2-2s2 .89 2 2-.89 2-2 2-2-.89-2-2zm4 18v-6h2.5l-2.54-7.63A1.5 1.5 0 0 0 18.53 7h-.53c-.8 0-1.53.5-1.83 1.25L14.5 12.5l1.5 1.5L17 11h1l1.5 4.5H21V22h-1z"/></svg>') center/50% no-repeat;
}

.camera-icon {
  background: linear-gradient(135deg, #4a90e2, #ff8a65) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>') center/50% no-repeat;
}

.device-icon {
  background: linear-gradient(135deg, #ff8a65, #4a90e2) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11C5.84 5 5.28 5.42 5.08 6.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99z"/></svg>') center/50% no-repeat;
}

.event-icon {
  background: linear-gradient(135deg, #ff6b6b, #ff8a65) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>') center/50% no-repeat;
}

.overview-content {
  flex: 1;
}

.overview-value {
  font-size: 24px;
  font-weight: bold;
  color: #ffffff;
  line-height: 1;
  text-shadow: 0 0 15px rgba(255, 138, 101, 0.8);
}

.overview-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 4px;
}

/* 告警数据样式 */
.alert-stats {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.alert-item {
  text-align: center;
  flex: 1;
  position: relative;
}

.alert-value {
  font-size: 50px;
  font-weight: bold;
  margin-bottom: 8px;
  text-shadow: 0 0 25px currentColor;
  font-family: 'Courier New', monospace;
}

.alert-value.danger {
  color: #ff6b6b;
}

.alert-value.warning {
  color: #ff8a65;
}

.alert-value.info {
  color: #4a90e2;
}

.alert-value.success {
  color: #4CAF50;
}

.alert-value.primary {
  color: #1e3c72;
}

.alert-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
}

/* 地图样式 - 撑满父容器 */
.map-container {
  position: relative;
  flex: 1;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid rgba(255, 138, 101, 0.6);
  box-shadow:
    0 0 20px rgba(255, 138, 101, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.map-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.monitoring-points {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.monitoring-point {
  position: absolute;
  width: 20px;
  height: 20px;
}

.point-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
}

.point-ripple {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: ripple 2s infinite;
}

.monitoring-point.active .point-dot {
  background: #4a90e2;
  box-shadow: 0 0 15px #4a90e2;
}

.monitoring-point.active .point-ripple {
  border: 2px solid #4a90e2;
}

.monitoring-point.warning .point-dot {
  background: #ff8a65;
  box-shadow: 0 0 15px #ff8a65;
}

.monitoring-point.warning .point-ripple {
  border: 2px solid #ff8a65;
}

.monitoring-point.danger .point-dot {
  background: #ff6b6b;
  box-shadow: 0 0 15px #ff6b6b;
}

.monitoring-point.danger .point-ripple {
  border: 2px solid #ff6b6b;
}

@keyframes ripple {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 1;
  }

  100% {
    transform: translate(-50%, -50%) scale(2.5);
    opacity: 0;
  }
}

/* 告警历史样式 - 撑满父容器 */
.alert-table {
  flex: 1;
  overflow-y: auto; /* 隐藏滚动条，实现平滑滚动 */
  height: 200px; /* 设定固定高度，根据实际显示行数调整 */
  font-size:small;
}

.table-header {
  display: flex;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.3) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  padding: 8px;
  /* font-weight: bold; */
  color: #ffffff;
  border-radius: 6px;
  margin-bottom: 10px;
  border: 1px solid rgba(255, 138, 101, 0.4);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.table-body {
  flex: 1;
  overflow-y: auto;
  max-height: 149px;
  font-size:small;
}

.table-row {
  display: flex;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 138, 101, 0.3);
  transition: all 0.3s ease;
}

.table-row.highlight {
  background: linear-gradient(135deg,
      rgba(255, 107, 107, 0.3) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  animation: highlight 3s ease;
}

.table-row:hover {
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.2) 0%,
      rgba(255, 138, 101, 0.15) 100%);
}

.col {
  flex: 1;
  padding: 0 8px;
  color: rgba(255, 255, 255, 0.9);
}

.col-detail {
  flex: 2; /* 详情列占据双倍宽度 */
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.status-badge.danger {
  background: linear-gradient(135deg, rgba(255, 107, 107, 0.3), rgba(255, 107, 107, 0.2));
  color: #ff6b6b;
  border: 1px solid #ff6b6b;
}

.status-badge.warning {
  background: linear-gradient(135deg, rgba(255, 138, 101, 0.3), rgba(255, 138, 101, 0.2));
  color: #ff8a65;
  border: 1px solid #ff8a65;
}

.status-badge.success {
  background: linear-gradient(135deg, rgba(76, 175, 80, 0.3), rgba(76, 175, 80, 0.2));
  color: #4CAF50;
  border: 1px solid #4CAF50;
}

/* 行为统计样式 */
.behavior-stats {
  display: grid;
  grid-template-columns: repeat(v-bind('behaviorStats.length > 5 ? 5:behaviorStats.length'), 1fr);
  gap: 8px;
}

.behavior-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.15) 0%,
      rgba(255, 138, 101, 0.1) 100%);
  border-radius: 8px;
  border: 1px solid rgba(255, 138, 101, 0.3);
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
  min-height: 120px;
}

.behavior-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 138, 101, 0.2), transparent);
  transition: left 0.5s ease;
}

.behavior-item:hover {
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.25) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  border-color: #ff8a65;
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.3);
}

.behavior-item:hover::before {
  left: 100%;
}

.behavior-icon {
  width: 32px;
  height: 32px;
  margin-bottom: 8px;
  border-radius: 6px;
  background-size: 16px;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.production-icon {
  background: linear-gradient(135deg, #ff8a65, #ff6b6b);
}

.storage-icon {
  background: linear-gradient(135deg, #4a90e2, #1e3c72);
}

.operation-icon {
  background: linear-gradient(135deg, #ff8a65, #4a90e2);
}

.maintenance-icon {
  background: linear-gradient(135deg, #4a90e2, #ff8a65);
}

.environment-icon {
  background: linear-gradient(135deg, #ff8a65, #ff6b6b);
}

.safety-icon {
  background: linear-gradient(135deg, #ff6b6b, #ff8a65);
}

.behavior-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.behavior-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.2em; /* 明确设置行高 */
  height: 2.4em; /* 两行的高度 (2 * 1.2em) */
  overflow: hidden; /* 隐藏超出部分 */
  display: -webkit-box; /* 启用弹性盒子 */
  -webkit-line-clamp: 2; /* 限制显示两行 */
  line-clamp: 2; /* 标准属性 */
  -webkit-box-orient: vertical; /* 垂直方向排列 */
  margin-bottom: 4px;
  text-align: center;
}

.behavior-value {
  font-size: 15px;
  font-weight: bold;
  color: #ffffff;
  text-shadow: 0 0 10px rgba(255, 138, 101, 0.8);
  margin-bottom: 2px;
}

.behavior-trend {
  font-size: 10px;
  text-align: center;
}

.behavior-trend.up {
  color: #4CAF50;
}

.behavior-trend.down {
  color: #ff6b6b;
}

.behavior-trend.equal {
  color: #4a90e2;
}

/* 员工分布列表 - 内部滚动 */
.staff-distribution .distribution-list {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
}

.distribution-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px;
  border-radius: 6px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.1) 0%,
      rgba(255, 138, 101, 0.05) 100%);
  border: 1px solid rgba(255, 138, 101, 0.2);
  transition: all 0.3s ease;
}

.distribution-item:hover {
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.2) 0%,
      rgba(255, 138, 101, 0.1) 100%);
  border-color: #ff8a65;
}

.area-name {
  width: 60px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.3) 0%,
      rgba(15, 26, 46, 0.4) 100%);
  border-radius: 4px;
  margin: 0 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 138, 101, 0.3);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4a90e2, #ff8a65);
  border-radius: 4px;
  transition: width 0.5s ease;
  box-shadow: 0 0 10px rgba(255, 138, 101, 0.5);
}

.area-count {
  width: 40px;
  text-align: right;
  font-size: 14px;
  color: #ffffff;
  font-weight: bold;
  text-shadow: 0 0 8px rgba(255, 138, 101, 0.6);
}

/* 实时监控样式 */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.monitor-item {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 138, 101, 0.4);
  transition: all 0.3s ease;
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.3) 0%,
      rgba(15, 26, 46, 0.4) 100%);
}

.monitor-item:hover {
  border-color: #ff8a65;
  box-shadow: 0 0 15px rgba(255, 138, 101, 0.4);
  transform: translateY(-2px);
}

.monitor-screen {
  position: relative;
  height: 100px;
  background: #000;
}

.monitor-screen img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.monitor-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent,
      rgba(30, 60, 114, 0.9) 40%,
      rgba(15, 26, 46, 0.95) 100%);
  padding: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.monitor-name {
  font-size: 12px;
  color: #ffffff;
  font-weight: bold;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
}

.monitor-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: bold;
}

.monitor-status.active {
  background: linear-gradient(135deg, #4a90e2, #1e3c72);
  color: #fff;
  box-shadow: 0 0 8px rgba(74, 144, 226, 0.5);
}

.monitor-status.warning {
  background: linear-gradient(135deg, #ff8a65, #ff6b6b);
  color: #fff;
  box-shadow: 0 0 8px rgba(255, 138, 101, 0.5);
}

/* 图表容器样式 - 撑满父容器 */
.chart-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart {
  width: 100%;
  flex: 1;
}

/* 动画效果 */
@keyframes highlight {
  0% {
    background: linear-gradient(135deg,
        rgba(255, 107, 107, 0.5) 0%,
        rgba(255, 138, 101, 0.3) 100%);
  }

  100% {
    background: linear-gradient(135deg,
        rgba(255, 107, 107, 0.2) 0%,
        rgba(255, 138, 101, 0.1) 100%);
  }
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.2) 0%,
      rgba(15, 26, 46, 0.3) 100%);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #ff8a65, #4a90e2);
  border-radius: 3px;
  box-shadow: 0 0 5px rgba(255, 138, 101, 0.5);
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #4a90e2, #ff8a65);
  box-shadow: 0 0 8px rgba(255, 138, 101, 0.8);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .dashboard-main {
    flex-direction: column;
    padding: 15px;
  }

  .dashboard-left,
  .dashboard-right {
    flex: none;
  }

  .main-title {
    font-size: 32px;
  }
}

/* 左侧面板内部布局 */
.dashboard-left .panel.factory-overview {
  flex: 0 0 auto;
}

.dashboard-left .panel.safety-chart {
  flex: 1;
  min-height: 165px;
  display: flex;
  flex-direction: column;
}

.dashboard-left .panel.system-chart {
  flex: 0 0 auto;
  min-height: 160px;
  display: flex;
  flex-direction: column;
}

.dashboard-left .panel.staff-distribution {
  flex: 1;
  min-height: 165px;
  display: flex;
  flex-direction: column;
}

/* 中间面板内部布局 */
.dashboard-center .panel.alert-data {
  flex: 0 0 auto;
}

.dashboard-center .panel.map-panel {
  flex: 1;
  min-height: 300px;
  display: flex;
  flex-direction: column;
}

.dashboard-center .panel.alert-history {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
}

/* 右侧面板内部布局 */
.dashboard-right .panel.behavior-analysis {
  flex: 0 0 auto;
}

.dashboard-right .panel.compliance-chart {
  flex: 1;
  min-height: 150px;
  display: flex;
  flex-direction: column;
}

.dashboard-right .panel.live-monitor {
  flex: 0 0 auto;
  min-height: 180px;
}

.dashboard-right .panel.risk-distribution {
  flex: 1;
  min-height: 150px;
  display: flex;
  flex-direction: column;
}

/* 员工分布样式 */
.distribution-list {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
}

/* 数据绑定管理器样式 */
.data-binding-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(5px);
}

.data-binding-modal {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 95vw;
  height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.data-binding-modal .modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  background: linear-gradient(135deg, #1e3c72, #4a90e2);
  color: white;
  border-radius: 12px 12px 0 0;
}

.data-binding-modal .modal-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: bold;
}

.close-btn {
  background: none;
  border: none;
  color: white;
  font-size: 28px;
  cursor: pointer;
  padding: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

.data-binding-modal>.data-binding-manager {
  flex: 1;
  overflow-y: auto;
  background: #f5f5f5;
}

/* 热力图面板样式 */
.heatmap-panel {
  flex: 0 0 auto;

}

.heatmap-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 465px;
}

.heatmap-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-map {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  max-width: 240px;
}

.area-block {
  text-align: center;
  line-height: 1.2;
  transition: all 0.3s ease;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.area-block:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

/* 地图缩放对话框样式 */
.dashboard-map-dialog {
  --el-dialog-bg-color: transparent;
}

.dashboard-map-dialog .el-dialog {
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.95) 0%,
      rgba(15, 26, 46, 0.98) 100%);
  border: 2px solid rgba(255, 138, 101, 0.6);
  border-radius: 16px;
  box-shadow:
    0 25px 80px rgba(0, 0, 0, 0.5),
    0 0 50px rgba(255, 138, 101, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(20px);
  overflow: hidden;
}

.dashboard-map-dialog .el-dialog__header {
  padding: 0;
  margin: 0;
  border-bottom: none;
}

.dashboard-map-dialog .el-dialog__body {
  padding: 0;
  background: transparent;
}

.dashboard-map-dialog .el-dialog__footer {
  padding: 0;
  background: transparent;
  border-top: none;
}

.dialog-header-custom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 30px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.3) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  border-bottom: 1px solid rgba(255, 138, 101, 0.4);
  position: relative;
}

.dialog-header-custom::before {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg,
      transparent,
      #ff8a65,
      #4a90e2,
      #ff8a65,
      transparent);
  animation: headerGlow 3s ease-in-out infinite alternate;
}

.dialog-title-custom {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
}

.title-icon {
  font-size: 24px;
  filter: drop-shadow(0 0 8px rgba(255, 138, 101, 0.6));
}

.title-text {
  font-size: 24px;
  font-weight: bold;
  background: linear-gradient(135deg, #ffffff, #ffe0b5);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 20px rgba(255, 138, 101, 0.6);
}

.dialog-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.zoom-info {
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  padding: 6px 12px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.3) 0%,
      rgba(255, 138, 101, 0.3) 100%);
  border-radius: 20px;
  border: 1px solid rgba(255, 138, 101, 0.4);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.close-btn-custom {
  background: linear-gradient(135deg,
      rgba(255, 107, 107, 0.8) 0%,
      rgba(255, 138, 101, 0.8) 100%);
  border: 1px solid rgba(255, 138, 101, 0.6);
  color: #ffffff;
  display: flex;
  gap: 8px;
  /* width: 40px; */
  /* height: 40px; */
  border-radius: 25px;
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
  /* display: flex;
  align-items: center;
  justify-content: center; */
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.3);
}

.close-btn-custom:hover {
  background: linear-gradient(135deg,
      rgba(255, 138, 101, 0.9) 0%,
      rgba(255, 107, 107, 0.9) 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255, 138, 101, 0.5);
}

.map-zoom-container {
  position: relative;
  height: 75vh;
  background: linear-gradient(135deg,
      rgba(15, 26, 46, 0.8) 0%,
      rgba(30, 60, 114, 0.6) 100%);
  border-radius: 0;
  overflow: hidden;
  border: none;
  margin: 0;
}

.zoom-canvas {
  width: 100%;
  height: 100%;
  cursor: grab;
  display: block;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 0;
}

.zoom-canvas:active {
  cursor: grabbing;
}

.zoom-controls {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.9) 0%,
      rgba(15, 26, 46, 0.95) 100%);
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(255, 138, 101, 0.4);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 0 20px rgba(255, 138, 101, 0.2);
  backdrop-filter: blur(15px);
}

.zoom-btn {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.8) 0%,
      rgba(255, 138, 101, 0.8) 100%);
  border: 1px solid rgba(255, 138, 101, 0.6);
  border-radius: 12px;
  color: #ffffff;
  font-size: 18px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.3);
}

.zoom-btn:hover {
  background: linear-gradient(135deg,
      rgba(255, 138, 101, 0.9) 0%,
      rgba(74, 144, 226, 0.9) 100%);
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 6px 20px rgba(255, 138, 101, 0.5);
}

.zoom-btn:active {
  transform: translateY(0) scale(1);
  box-shadow: 0 2px 10px rgba(255, 138, 101, 0.4);
}

.zoom-tips {
  position: absolute;
  bottom: 20px;
  left: 20px;
  display: flex;
  gap: 16px;
  z-index: 10;
}

.tip-item {
  background: linear-gradient(135deg,
      rgba(30, 60, 114, 0.9) 0%,
      rgba(15, 26, 46, 0.95) 100%);
  color: #ffffff;
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid rgba(255, 138, 101, 0.4);
  font-size: 12px;
  font-weight: 500;
  backdrop-filter: blur(15px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  opacity: 0.9;
  transition: opacity 0.3s ease;
}

.tip-item:hover {
  opacity: 1;
}

.dialog-footer-custom {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 10px 30px;
  background: linear-gradient(135deg,
      rgba(15, 26, 46, 0.8) 0%,
      rgba(30, 60, 114, 0.6) 100%);
  border-top: 1px solid rgba(255, 138, 101, 0.4);
}

.footer-btn {
  display: flex;
  /* align-items: center; */
  gap: 8px;
  /* padding: 12px 24px; */
  border-radius: 25px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  border: 1px solid;
}

.footer-btn.secondary {
  background: linear-gradient(135deg,
      rgba(108, 117, 125, 0.8) 0%,
      rgba(73, 80, 87, 0.8) 100%);
  border-color: rgba(108, 117, 125, 0.6);
  color: #ffffff;
}

.footer-btn.secondary:hover {
  background: linear-gradient(135deg,
      rgba(73, 80, 87, 0.9) 0%,
      rgba(108, 117, 125, 0.9) 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.footer-btn.primary {
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.8) 0%,
      rgba(255, 138, 101, 0.8) 100%);
  border-color: rgba(255, 138, 101, 0.6);
  color: #ffffff;
}

.footer-btn.primary:hover {
  background: linear-gradient(135deg,
      rgba(255, 138, 101, 0.9) 0%,
      rgba(74, 144, 226, 0.9) 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(255, 138, 101, 0.5);
}

.btn-icon {
  font-size:16px;transition: transform 0.3s ease;
}

.footer-btn:hover .btn-icon {
  transform: scale(1.2);
}

.alert-fade-enter-active, 
.alert-fade-leave-active {
  transition: opacity 0.5s ease; /* 只有透明度过渡 */
}

.alert-fade-enter-from, 
.alert-fade-leave-to {
  opacity: 0;
  /* transform: translateY(-30px); */
}

.table-row {
  display: flex;
  padding: 10px 12px;
}
</style>