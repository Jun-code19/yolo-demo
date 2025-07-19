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
            <span>晴</span>
            <span>22°C</span>
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
                <div class="overview-value">{{ factoryData.factoryCount }}</div>
                <div class="overview-label">任务数量</div>
                <!-- 任务总数为检测配置任务列表中所有任务数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon area-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.areaCount }}</div>
                <div class="overview-label">监控设备</div>
                <!-- 监控设备为设备列表中所有监控数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon staff-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.staffCount }}</div>
                <div class="overview-label">检测事件</div>
                <!-- 检测事件为检测事件列表中所有检测事件数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon camera-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.cameraCount }}</div>
                <div class="overview-label">项目数量</div>
                <!-- 项目数量为人群分析中所有项目数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon device-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.deviceCount }}</div>
                <div class="overview-label">边缘设备</div>
                <!-- 边缘设备为边缘设备列表中所有边缘设备数量 -->
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon event-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.eventCount }}</div>
                <div class="overview-label">异常事件</div>
                <!-- 异常事件为数据事件列表中所有异常事件数量 -->
              </div>
            </div>
          </div>
        </div>

        <!-- 项目排队时长 -->
        <!-- 暂定 -->
        <div class="panel safety-chart">
          <h3 class="panel-title">项目排队时长</h3>
          <div class="chart-container">
            <div ref="safetyChartRef" class="chart"></div>
          </div>
        </div>

        <!-- 游客分布 -->
        <!-- 游客分布为人群分析中各任务的游客数量 -->
        <div class="panel staff-distribution">
          <h3 class="panel-title">游客分布</h3>
          <div class="distribution-list">
            <div class="distribution-item" v-for="item in staffDistribution" :key="item.area">
              <div class="area-name">{{ item.area }}</div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: item.percentage + '%' }"></div>
              </div>
              <div class="area-count">{{ item.count }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 中间面板 -->
      <div class="dashboard-center">
        <!-- 检测告警数据 -->
        <!-- 检测告警数据为数据事件列表中的异常事件类别统计 -->
        <div class="panel alert-data">
          <h3 class="panel-title">检测告警数据</h3>
          <div class="alert-stats">
            <div class="alert-item" v-for="(item, index) in alertData" :key="item.engine_name">
              <div class="alert-value"
                :class="index === alertData.length - 1 ? 'danger' : index % 4 === 0 ? 'warning' : index % 4 === 1 ? 'info' : index % 4 === 2 ? 'success' : 'danger'">
                {{ item.detection_count }}</div>
              <div class="alert-label">{{ item.engine_name }}</div>
            </div>
          </div>
        </div>

        <!-- 人数热力图 -->
        <div class="panel heatmap-panel">
          <h3 class="panel-title">
            人数热力图
          </h3>
          <div class="heatmap-container">
            <DashboardHeatMap @open-map-zoom="handleOpenMapZoom" />
          </div>
        </div>

        <!-- 事件告警信息 -->
        <!-- 事件告警信息为数据事件列表中的异常事件 -->
        <div class="panel alert-history">
          <h3 class="panel-title">事件告警信息</h3>
          <div class="alert-table">
            <div class="table-header">
              <div class="col">告警类型</div>
              <div class="col">设备名称</div>
              <div class="col">通道名称</div>
              <div class="col">检测数量</div>
              <div class="col">置信度</div>
              <div class="col">时间</div>
              <div class="col">状态</div>
            </div>
            <div class="table-body">
              <div v-for="alert in alertHistory" :key="alert.id" class="table-row"
                :class="{ 'highlight': alert.isNew }">
                <div class="col">{{ alert.type }}</div>
                <div class="col">{{ alert.device }}</div>
                <div class="col">{{ alert.name }}</div>
                <div class="col">{{ alert.detection_count }}</div>
                <div class="col">{{ alert.confidence }}</div>
                <div class="col">{{ alert.time }}</div>
                <div class="col">
                  <span class="status-badge" :class="alert.status">
                    {{ alert.statusText }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧面板 -->
      <div class="dashboard-right">
        <!-- 检测各类型分析 -->
        <!-- 检测各类型分析为检测类型/算法引擎的分类统计 -->
        <div class="panel behavior-analysis">
          <h3 class="panel-title">检测各类型分析</h3>
          <div class="behavior-stats">
            <div class="behavior-item" v-for="item in behaviorStats" :key="item.type">
              <div class="behavior-icon" :class="item.icon"></div>
              <div class="behavior-content">
                <div class="behavior-name">{{ item.name }}</div>
                <div class="behavior-value">{{ item.value }}</div>
                <div class="behavior-trend" :class="item.trend > 0 ? 'up' : item.trend < 0 ? 'down' : 'equal'">
                  {{ item.trend > 0 ? '↑' : item.trend < 0 ? '↓' : '-' }} {{ Math.abs(item.trend) }}% </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 历史数据事件 -->
          <!-- 历史数据事件为数据事件列表中的历史事件统计 -->
          <div class="panel compliance-chart">
            <h3 class="panel-title">历史数据事件</h3>
            <div class="chart-container">
              <div ref="complianceChartRef" class="chart"></div>
            </div>
          </div>

          <!-- 最新报警推送 -->
          <!-- 最新报警推送为数据事件列表中的最新报警推送 -->
          <div class="panel live-monitor">
            <h3 class="panel-title">最新报警推送</h3>
            <div class="monitor-grid">
              <div class="monitor-item" v-for="monitor in liveMonitors" :key="monitor.id">
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

const router = useRouter()

// 响应式数据
const currentTime = ref('')
const safetyChartRef = ref(null)
const complianceChartRef = ref(null)
const riskChartRef = ref(null)

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

// 使用简化的数据管理
import { useDashboardData } from '@/composables/useDashboardData.js'

const {
  data,
  isLoading,
  hasErrors,
  refreshData,
  stopAutoRefresh
} = useDashboardData()

// 获取图片URL
const getImageUrl = (imagePath) => {
  // 使用后端提供的图片服务API
  if (imagePath) {
    return `/api/v2/data-listeners/images/${encodeURIComponent(imagePath)}`
  }
}

// 处理图片加载错误
const handleImageError = (event) => {
  event.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjRjVGNUY1Ii8+CjxwYXRoIGQ9Ik0yMCAzMEMyNS41MjI5IDMwIDMwIDI1LjUyMjkgMzAgMjBDMzAgMTQuNDc3MSAyNS41MjI5IDEwIDIwIDEwQzE0LjQ3NzEgMTAgMTAgMTQuNDc3MSAxMCAyMEMxMCAyNS41MjI5IDE0LjQ3NzEgMzAgMjAgMzBaIiBmaWxsPSIjQ0NDQ0NDIi8+CjxwYXRoIGQ9Ik0yMCAyMi41QzIxLjM4MDcgMjIuNSAyMi41IDIxLjM4MDcgMjIuNSAyMEMyMi41IDE4LjYxOTMgMjEuMzgwNyAxNy41IDIwIDE3LjVDMTguNjE5MyAxNy41IDE3LjUgMTguNjE5MyAxNy41IDIwQzE3LjUgMjEuMzgwNyAxOC42MTkzIDIyLjUgMjAgMjIuNVoiIGZpbGw9IiNGRkZGRkYiLz4KPC9zdmc+'
  event.target.style.opacity = '0.5'
}

// 简化的数据访问
const factoryData = computed(() => data.factoryData)
const alertData = computed(() => data.alertData)
const staffDistribution = computed(() => data.staffDistribution)
const alertHistory = computed(() => data.alertHistory)
const behaviorStats = computed(() => data.behaviorStats)
const liveMonitors = computed(() => data.liveMonitors)
const historicalStats = computed(() => data.historicalStats)

let timeInterval = null
let dataUpdateInterval = null

// 图表实例存储
let safetyChart = null
let complianceChart = null
let riskChart = null

// 初始化图表
const initCharts = () => {
  // 安全作业合格率图表
  safetyChart = echarts.init(safetyChartRef.value)
  updateSafetyChart()

  // 历史数据事件图表
  complianceChart = echarts.init(complianceChartRef.value)
  updateComplianceChart()

  // 风险占比分类图表
  riskChart = echarts.init(riskChartRef.value)
  updateRiskChart()

  // 响应式处理
  window.addEventListener('resize', () => {
    safetyChart?.resize()
    complianceChart?.resize()
    riskChart?.resize()
  })
}

// 更新安全作业合格率图表
const updateSafetyChart = () => {
  if (!safetyChart) return

  safetyChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '13%',
      right: '10%',
      top: '20%',
      bottom: '20%'
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
        return params[0].name + '<br/>' +
          '<span style="color:#ff8a65;">排队时长:</span> ' +
          params[0].value + ' 分钟';
      }
    },
    xAxis: {
      type: 'category',
      data: ['A区', 'B区', 'C区', 'D区', 'E区'],
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
      axisTick: {
        lineStyle: { color: '#ff8a65' }
      }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        color: '#ffffff',
        fontSize: 12,
        fontWeight: 'bold',
        formatter: '{value} 分钟'
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
    series: [{
      data: [100, 80, 70, 60, 50],
      type: 'bar',
      barWidth: '50%',
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#ff8a65' },
          { offset: 0.5, color: '#4a90e2' },
          { offset: 1, color: '#1e3c72' }
        ]),
        borderColor: '#ff8a65',
        borderWidth: 2,
        shadowBlur: 15,
        shadowColor: 'rgba(255, 138, 101, 0.5)'
      },
      animationDelay: (idx) => idx * 200,
      animationDuration: 1000
    }]
  })
}

// 更新历史数据事件图表
const updateComplianceChart = () => {
  if (!complianceChart) return

  // 确保有数据
  const chartData = historicalStats.value || []

  // 动态计算Y轴最大值
  const maxValue = Math.max(...chartData.map(item => item.value || 0), 100)
  const yAxisMax = Math.ceil(maxValue * 1.2) // 增加20%的缓冲

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
        if (params && params[0]) {
          return params[0].name + '<br/>' +
            '<span style="color:#ff8a65;">事件数量:</span> ' +
            params[0].value;
        }
        return '';
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
    series: [{
      data: chartData.map(item => item.value || 0),
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: {
        color: '#ff8a65',
        width: 4,
        shadowBlur: 15,
        shadowColor: 'rgba(255, 138, 101, 0.5)'
      },
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
          { offset: 0.5, color: 'rgba(74, 144, 226, 0.2)' },
          { offset: 1, color: 'rgba(30, 60, 114, 0.1)' }
        ])
      },
      animationDuration: 2000
    }]
  })
}

// 更新检测类型占比分类图表
const updateRiskChart = () => {
  if (!riskChart) return

  // 计算总值
  const total = behaviorStats.value.reduce((sum, item) => sum + item.value, 0)

  // 使用 behaviorStats 数据，并计算百分比
  const chartData = behaviorStats.value.map(item => ({
    value: total > 0 ? Number(((item.value / total) * 100).toFixed(1)) : 0,
    name: item.name,
    itemStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
        { offset: 0, color: item.trend > 0 ? '#4CAF50' : item.trend < 0 ? '#ff6b6b' : '#4a90e2' },
        { offset: 1, color: item.trend > 0 ? '#2E7D32' : item.trend < 0 ? '#ff8a65' : '#4a90e2' }
      ]),
      shadowBlur: 15,
      shadowColor: item.trend > 0 ? 'rgba(76, 175, 80, 0.5)' : item.trend < 0 ? 'rgba(255, 138, 101, 0.5)' : 'rgba(74, 144, 226, 0.5)'
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
        fontSize: 14,
        fontWeight: 'bold',
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
  timeInterval = setInterval(updateTime, 1000)

  // 延迟初始化图表，确保DOM已渲染
  setTimeout(() => {
    initCharts()
  }, 100)
})

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
})
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
  /* min-height: 250px; */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.table-header {
  display: flex;
  background: linear-gradient(135deg,
      rgba(74, 144, 226, 0.3) 0%,
      rgba(255, 138, 101, 0.2) 100%);
  padding: 12px;
  font-weight: bold;
  color: #ffffff;
  border-radius: 6px;
  margin-bottom: 10px;
  border: 1px solid rgba(255, 138, 101, 0.4);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.table-body {
  flex: 1;
  overflow-y: auto;
  max-height: 140px;
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
  grid-template-columns: repeat(v-bind('behaviorStats.length'), 1fr);
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
  margin-bottom: 4px;
  text-align: center;
}

.behavior-value {
  font-size: 16px;
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

.dashboard-left .panel.staff-distribution {
  flex: 0 0 auto;
  min-height: 280px;
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
  space-y: 12px;
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
  font-size: 16px;transition: transform 0.3s ease;
}

.footer-btn:hover .btn-icon {
  transform: scale(1.2);
}
</style>