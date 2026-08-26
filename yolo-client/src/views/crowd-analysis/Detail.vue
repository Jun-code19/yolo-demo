<template>
  <div class="crowd-analysis-detail">
    <div class="header">
      <h2>{{ job.job_name || '任务详情' }}</h2>
      <div>
        <el-button @click="goBack">返回列表</el-button>
        <el-button type="primary" @click="runJob">立即执行</el-button>
        <el-button :type="job.is_active ? 'warning' : 'success'" @click="toggleJobStatus">
          {{ job.is_active ? '停止任务' : '启动任务' }}
        </el-button>
        <el-dropdown @command="handleExport" class="export-button">
          <el-button type="primary" plain>
            数据导出<i class="el-icon-arrow-down el-icon--right"></i>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="7">最近7天</el-dropdown-item>
              <el-dropdown-item command="30">最近30天</el-dropdown-item>
              <el-dropdown-item command="90">最近90天</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-card class="info-card" v-loading="loading">
      <template #header>
        <div>
          <span>基本信息</span>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ job.job_id }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ job.job_name }}</el-descriptions-item>
        <el-descriptions-item label="整轮间隔">{{ job.interval || 0 }}秒/轮</el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="getStatusType(job.status)">{{ job.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(job.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="最近执行">{{ job.last_run ? formatDate(job.last_run) : '未执行' }}</el-descriptions-item>
        <el-descriptions-item label="设备来源">
          {{ job.device_mode === 'group' ? '按设备分组' : '手动选择' }}
        </el-descriptions-item>
        <el-descriptions-item label="生效时段">{{ scheduleSummary }}</el-descriptions-item>
        <el-descriptions-item label="监控设备数量">{{ job.device_ids?.length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="检测模型">{{ modelInfo?.model_name || job.models_id }}</el-descriptions-item>
        <el-descriptions-item label="置信度阈值">{{ Math.round((job.confidence_threshold || 0.5) * 100) }}%</el-descriptions-item>
        <el-descriptions-item label="标签">
          <el-tag v-for="tag in (job.tags || [])" :key="tag" size="small" style="margin-right: 5px">
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="位置信息" :span="2">
          {{ getLocationInfo() }}
        </el-descriptions-item>
        <el-descriptions-item label="人数预警阈值">
          {{ job.warning_threshold ? `${job.warning_threshold}人` : '不预警' }}
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          {{ job.description || '无' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="result-card" v-if="job.last_result">
      <template #header>
        <div>
          <span>最近分析结果</span>
          <span style="margin-left: 10px; color: #909399; font-size: 13px">
            ({{ job.last_result?.timestamp ? formatDateTime(job.last_result.timestamp) : '' }})
          </span>
        </div>
      </template>
      <div class="result-summary">
        <div class="total-count">
          <span class="count-number">{{ job.last_result?.total_person_count || 0 }}</span>
          <span class="count-label">总人数</span>
        </div>
      </div>
    </el-card>

    <el-card class="devices-card" v-if="job.device_ids && job.device_ids.length > 0">
      <template #header>
        <div>
          <span>监控设备列表</span>
        </div>
      </template>
      <el-table :data="devicesList" border style="width: 100%">
        <el-table-column prop="device_id" label="设备ID" width="180" />
        <el-table-column prop="device_name" label="设备名称" width="180" />
        <el-table-column prop="ip_address" label="IP地址" width="180" />
        <el-table-column prop="channel" label="通道号" width="180" />
        <el-table-column prop="location" label="位置信息" width="180" />
        <el-table-column v-if="job.last_result?.camera_counts" label="人数" width="180">
          <template #default="scope">
            {{ job.last_result.camera_counts?.find(item => item.device_id === scope.row.device_id)?.person_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column v-if="job.last_result?.camera_counts" label="预览图" width="150">
          <template #default="scope">
            <el-button
              v-if="getCameraPreview(scope.row.device_id)"
              link
              type="primary"
              @click="showFullImage(getCameraPreview(scope.row.device_id))"
            >
              查看
            </el-button>
            <span v-else>无预览图</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="180">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'online' ? 'success' : 'danger'">
              {{ scope.row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>历史数据</span>
          <div class="history-toolbar">
            <el-radio-group v-model="chartViewMode" size="small" @change="renderHistoryChart">
              <el-radio-button label="total">总人数</el-radio-button>
              <el-radio-button label="stack">设备堆叠</el-radio-button>
              <el-radio-button label="heatmap">热力图</el-radio-button>
            </el-radio-group>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 300px;"
              @change="fetchHistoryData"
            />
          </div>
        </div>
      </template>

      <div class="chart-summary" v-if="hasHistoryData && historySummary">
        <div class="summary-item">
          <span class="summary-label">峰值人数</span>
          <span class="summary-value peak">{{ historySummary.peak }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">平均人数</span>
          <span class="summary-value">{{ historySummary.avg }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">采样点数</span>
          <span class="summary-value">{{ historySummary.points }}</span>
        </div>
        <div class="summary-item" v-if="job.warning_threshold">
          <span class="summary-label">预警阈值</span>
          <span class="summary-value warn">{{ job.warning_threshold }}人</span>
        </div>
      </div>

      <div class="chart-container" ref="chartContainer" v-loading="historyLoading">
        <div id="historyChart" :style="{ width: '100%', height: chartHeight + 'px' }"></div>
      </div>

      <div class="no-data" v-if="!hasHistoryData && !historyLoading">
        <el-empty description="暂无历史数据" />
      </div>

      <p v-if="hasHistoryData" class="chart-hint">{{ chartHintText }}</p>
    </el-card>

    <el-card class="error-card" v-if="job.last_error">
      <template #header>
        <div>
          <span>错误信息</span>
        </div>
      </template>
      <el-alert type="error" :title="job.last_error" :closable="false" show-icon />
    </el-card>

    <!-- 全屏预览对话框 -->
    <el-dialog v-model="fullImageVisible" title="检测结果详情" width="50%" top="5vh" :before-close="handleCloseFullImage"
      :close-on-click-modal="true" :z-index="9999" :modal="true" :append-to-body="true" class="full-image-dialog">
      <div class="full-image-container">
        <div class="image-info">
          <h3>{{ currentImage.device_name }}</h3>
          <p>位置: {{ currentImage.location || '未知' }}</p>
          <p>时间: {{ formatDateTime(currentImage.timestamp) }}</p>
          <p>检测到人数: <span class="person-count">{{ currentImage.person_count }}</span></p>
        </div>
        <div class="image-wrapper">
          <img v-if="currentImage.preview_image" :src="getImageUrl(currentImage.preview_image)" alt="检测结果"
            class="full-preview-image" />
        </div>
        <div class="detection-details" v-if="currentImage.person_detections && currentImage.person_detections.length">
          <h4>检测详情</h4>
          <el-table :data="currentImage.person_detections" border size="small">
            <el-table-column label="#" type="index" width="50" />
            <el-table-column label="类别" width="100">
              <template #default="scope">
                {{ scope.row.class_id + ' : ' + scope.row.class_name }}
              </template>
            </el-table-column>
            <el-table-column label="位置" width="180">
              <template #default="scope">
                {{ formatBoxCoordinates(scope.row.bbox) }}
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="100">
              <template #default="scope">
                <el-progress :percentage="Math.round(scope.row.confidence * 100)"
                  :color="getConfidenceColor(scope.row.confidence)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import { formatDate, formatDateTime } from '@/utils/date'
import {
  scheduleFromBackend,
  legacyRuntimeToSchedule,
  formatScheduleSummary
} from '@/utils/weeklySchedule'
import * as echarts from 'echarts'

const router = useRouter()
const route = useRoute()

const goBack = () => {
  router.replace({ name: 'CrowdAnalysis' })
}
const loading = ref(false)
const job = ref({})
const devicesList = ref([])
const cameraCounts = ref([])
const dateRange = ref([])
const hasHistoryData = ref(false)
const modelInfo = ref(null)
const fullImageVisible = ref(false)
const currentImage = ref(null)
const historyLoading = ref(false)
const chartViewMode = ref('total')
const historyData = ref([])
const sampledHistoryData = ref([])
const historySummary = ref(null)
const chartHeight = ref(420)
let chart = null
let chartResizeHandler = null
let initChartTimer = null
let statusCheckInterval = null
let statusCheckTimeout = null
let pageAlive = false

const isPageActive = () => pageAlive

const clearStatusPolling = () => {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval)
    statusCheckInterval = null
  }
  if (statusCheckTimeout) {
    clearTimeout(statusCheckTimeout)
    statusCheckTimeout = null
  }
}

const cleanupChart = () => {
  if (chartResizeHandler) {
    window.removeEventListener('resize', chartResizeHandler)
    chartResizeHandler = null
  }
  if (chart) {
    try {
      chart.dispose()
    } catch {
      // ignore dispose errors
    }
    chart = null
  }
}

const cleanupPage = () => {
  pageAlive = false
  if (initChartTimer) {
    clearTimeout(initChartTimer)
    initChartTimer = null
  }
  clearStatusPolling()
  cleanupChart()
  loading.value = false
  historyLoading.value = false
}

const scheduleSummary = computed(() => {
  const runtime = job.value.schedule_config?.runtime
  if (!runtime) return '全时段'
  if (runtime.time_period_mode === 'all') return '全时段'
  if (runtime.time_period_mode === 'weekly' && runtime.weekly_schedule) {
    return formatScheduleSummary(scheduleFromBackend(runtime.weekly_schedule))
  }
  return formatScheduleSummary(legacyRuntimeToSchedule(runtime))
})

const chartHintText = computed(() => {
  const map = {
    total: '总人数趋势（面积图），适合查看整体客流变化与预警线。',
    stack: '各设备人数堆叠，总高度等于总人数，便于对比设备占比。',
    heatmap: '时间 × 设备热力图，设备多时可快速发现热点时段与点位。'
  }
  return map[chartViewMode.value] || ''
})

const DEVICE_COLORS = [
  '#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399',
  '#9B59B6', '#1ABC9C', '#3498DB', '#E74C3C', '#2ECC71'
]

const scheduleHistoryInit = () => {
  if (initChartTimer) {
    clearTimeout(initChartTimer)
  }
  initChartTimer = setTimeout(() => {
    if (!isPageActive()) return
    initChart()
    fetchHistoryData()
  }, 100)
}

onMounted(() => {
  pageAlive = true

  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 1)
  dateRange.value = [start, end]

  fetchJobDetail()
})

onBeforeUnmount(() => {
  cleanupPage()
})

const fetchJobDetail = async () => {
  if (!isPageActive()) return
  loading.value = true
  try {
    const jobId = route.params.id
    const res = await crowdAnalysisApi.getAnalysisJob(jobId)
    if (!isPageActive()) return
    job.value = res.data

    if (job.value.last_result?.camera_counts) {
      cameraCounts.value = job.value.last_result.camera_counts
    }

    if (job.value.models_id) {
      fetchModelInfo()
    }
    if (job.value.device_ids?.length > 0) {
      fetchDevicesInfo()
    }

    scheduleHistoryInit()
  } catch (error) {
    if (isPageActive()) {
      ElMessage.error('获取任务详情失败')
    }
  } finally {
    if (isPageActive()) {
      loading.value = false
    }
  }
}

const fetchDevicesInfo = async () => {
  try {
    if (!job.value.device_ids || job.value.device_ids.length === 0) return

    const res = await crowdAnalysisApi.getDevicesDetails(job.value.device_ids)
    if (!isPageActive()) return
    if (res.data) {
      devicesList.value = res.data
    }
  } catch (error) {
    if (!isPageActive()) return
    devicesList.value = job.value.device_ids.map(id => ({
      device_id: id,
      device_name: `设备 ${id}`,
      ip_address: '-',
      location: '-',
      status: 'offline'
    }))
  }
}

const fetchModelInfo = async () => {
  if (!job.value?.models_id) return

  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    const models = res.data || []
    modelInfo.value = models.find(m => m.model_id === job.value.models_id) || null
  } catch (error) {
    // console.error('获取模型信息失败:', error)
  }
}

const getStatusType = (status) => {
  const map = {
    scheduled: 'info',
    running: 'warning',
    completed: 'success',
    error: 'danger',
    created: 'primary',
    paused: 'info'
  }
  return map[status] || 'primary'
}

const getLocationInfo = () => {
  if (!job.value.location_info) return '无'

  const info = []
  if (job.value.location_info.name) {
    info.push(job.value.location_info.name)
  }
  if (job.value.location_info.address) {
    info.push(job.value.location_info.address)
  }
  if (job.value.location_info.coordinates &&
    job.value.location_info.coordinates.length === 2) {
    info.push(`坐标: ${job.value.location_info.coordinates.join(', ')}`)
  }

  return info.length > 0 ? info.join(' | ') : '无'
}

const getImageUrl = (imageData) => {
  if (!imageData) return ''
  if (typeof imageData === 'string') {
    if (imageData.startsWith('data:image')) {
      return imageData
    }
    return `data:image/jpeg;base64,${imageData}`
  }
  return `data:image/jpeg;base64,${imageData}`
}

const getCameraPreview = (deviceId) => {
  const item = cameraCounts.value.find(entry => entry.device_id === deviceId)
  if (!item?.preview_image) return null
  return item
}

const runJob = async () => {
  if (!job.value?.job_id) {
    ElMessage.warning('任务信息尚未加载完成')
    return
  }
  try {
    await crowdAnalysisApi.runAnalysisJobNow(job.value.job_id)
    ElMessage.success('任务已开始执行')

    clearStatusPolling()

    statusCheckInterval = setInterval(async () => {
      if (!isPageActive()) {
        clearStatusPolling()
        return
      }
      await fetchJobDetail()
      const shouldStopPolling =
        !job.value.is_active ||
        ['completed', 'error', 'paused'].includes(job.value.status)
      if (shouldStopPolling) {
        clearStatusPolling()
        if (isPageActive() && job.value.status === 'completed') {
          ElMessage.success('任务执行完成')
        } else if (isPageActive() && job.value.status === 'error') {
          ElMessage.error(`任务执行出错: ${job.value.last_error || '未知错误'}`)
        }
      }
    }, 3000)

    statusCheckTimeout = setTimeout(() => {
      clearStatusPolling()
    }, 30 * 60 * 1000)

    fetchJobDetail()
  } catch (error) {
    ElMessage.error('执行任务失败')
  }
}

const toggleJobStatus = async () => {
  if (!job.value?.job_id) {
    ElMessage.warning('任务信息尚未加载完成')
    return
  }
  try {
    if (job.value.is_active) {
      await crowdAnalysisApi.pauseAnalysisJob(job.value.job_id)
      ElMessage.success('任务已暂停')
      clearStatusPolling()
    } else {
      await crowdAnalysisApi.resumeAnalysisJob(job.value.job_id)
      ElMessage.success('任务已恢复')
    }
    fetchJobDetail()
  } catch (error) {
    ElMessage.error(`${job.value.is_active ? '暂停' : '恢复'}任务失败`)
  }
}

const handleExport = async (days) => {
  try {
    const res = await crowdAnalysisApi.exportAnalysisResults(job.value.job_id, days)

    // 处理导出数据，这里可以是下载文件或展示数据
    if (res.data && res.data.data) {
      // 创建CSV数据
      const csvContent = generateCSV(res.data.data)

      // 创建下载链接
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `人群分析_${job.value.job_name}_${days}天.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      ElMessage.success('导出成功')
    } else {
      ElMessage.warning('无数据可导出')
    }
  } catch (error) {
    ElMessage.error('导出失败')
    // console.error(error)
  }
}

const generateCSV = (data) => {
  // 生成CSV格式数据
  const header = '日期,总人数,位置\n'
  let content = header

  if (data.results && data.results.length > 0) {
    data.results.forEach(item => {
      content += `${formatDateTime(item.timestamp)},${item.total_person_count},${data.job_name}\n`
    })
  }

  return content
}

const formatAxisTime = (value) => {
  const date = new Date(value)
  return `${date.getMonth() + 1}-${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
}

const sampleDataByInterval = (data, intervalMs) => {
  if (data.length <= 1) return data

  const sampled = [data[0]]
  let lastSampledTime = new Date(data[0].timestamp).getTime()

  for (let i = 1; i < data.length; i++) {
    const currentTime = new Date(data[i].timestamp).getTime()
    if (currentTime - lastSampledTime >= intervalMs) {
      sampled.push(data[i])
      lastSampledTime = currentTime
    }
  }

  if (sampled[sampled.length - 1] !== data[data.length - 1]) {
    sampled.push(data[data.length - 1])
  }

  return sampled
}

const buildDeviceNameMap = (data) => {
  const map = {}
  data.forEach(item => {
    item.camera_counts?.forEach(camera => {
      map[camera.device_id] = camera.device_name || `设备${camera.device_id}`
    })
  })
  return map
}

const computeHistorySummary = (data) => {
  if (!data.length) return null
  const totals = data.map(item => Number(item.total_person_count) || 0)
  const peak = Math.max(...totals)
  const avg = Math.round(totals.reduce((a, b) => a + b, 0) / totals.length)
  return { peak, avg, points: data.length }
}

const buildTotalChartOption = (data) => {
  const seriesData = data.map(item => [new Date(item.timestamp).getTime(), item.total_person_count || 0])
  const threshold = job.value.warning_threshold

  return {
    title: {
      text: '总人数变化趋势',
      left: 'center',
      subtext: '按小时采样',
      subtextStyle: { fontSize: 12, color: '#909399' }
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const point = params?.[0]
        if (!point) return ''
        return `${formatDateTime(new Date(point.value[0]))}<br/>${point.marker} 总人数：<b>${point.value[1]}</b> 人`
      }
    },
    grid: { left: 48, right: 24, top: 72, bottom: 72, containLabel: true },
    toolbox: {
      feature: {
        saveAsImage: { title: '保存' },
        myRefresh: {
          show: true,
          title: '刷新',
          icon: 'path://M512 64a448 448 0 1 1 0 896 448 448 0 0 1 0-896zm-38.4 224a32 32 0 0 0-49.92 40.32L512 316.8l87.68 108.16a32 32 0 1 0 49.92-40.32L512 236.8l-38.4 47.36z',
          onclick: () => refreshHistoryData()
        }
      }
    },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
    xAxis: {
      type: 'time',
      splitLine: { show: false },
      axisLabel: { formatter: formatAxisTime }
    },
    yAxis: {
      type: 'value',
      name: '人数',
      min: 0,
      splitLine: { lineStyle: { type: 'dashed' } }
    },
    series: [{
      name: '总人数',
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.35)' },
            { offset: 1, color: 'rgba(64,158,255,0.04)' }
          ]
        }
      },
      lineStyle: { width: 2, color: '#409EFF' },
      itemStyle: { color: '#409EFF' },
      markLine: threshold ? {
        silent: true,
        symbol: 'none',
        lineStyle: { color: '#F56C6C', type: 'dashed' },
        label: { formatter: `预警 ${threshold}人` },
        data: [{ yAxis: threshold }]
      } : undefined,
      data: seriesData
    }]
  }
}

const buildStackChartOption = (data) => {
  const deviceNames = buildDeviceNameMap(data)
  const deviceIds = Object.keys(deviceNames)
  const timestamps = data.map(item => new Date(item.timestamp).getTime())

  const series = deviceIds.map((deviceId, index) => ({
    name: deviceNames[deviceId],
    type: 'line',
    stack: 'total',
    smooth: true,
    showSymbol: false,
    areaStyle: { opacity: 0.85 },
    emphasis: { focus: 'series' },
    lineStyle: { width: 1 },
    itemStyle: { color: DEVICE_COLORS[index % DEVICE_COLORS.length] },
    data: data.map(item => {
      const camera = item.camera_counts?.find(c => c.device_id === deviceId)
      return camera?.person_count || 0
    })
  }))

  return {
    title: {
      text: '各设备人数堆叠',
      left: 'center',
      subtext: '总高度 = 总人数',
      subtextStyle: { fontSize: 12, color: '#909399' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      data: deviceIds.map(id => deviceNames[id])
    },
    grid: { left: 48, right: 24, top: 72, bottom: deviceIds.length > 6 ? 96 : 72, containLabel: true },
    toolbox: { feature: { saveAsImage: { title: '保存' } } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 28 }],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timestamps.map(ts => formatAxisTime(ts))
    },
    yAxis: {
      type: 'value',
      name: '人数',
      min: 0,
      splitLine: { lineStyle: { type: 'dashed' } }
    },
    series
  }
}

const buildHeatmapOption = (data) => {
  const deviceNames = buildDeviceNameMap(data)
  const deviceIds = Object.keys(deviceNames)
  const timeLabels = data.map(item => formatAxisTime(item.timestamp))
  const heatData = []
  let maxCount = 0

  data.forEach((item, timeIndex) => {
    deviceIds.forEach((deviceId, deviceIndex) => {
      const camera = item.camera_counts?.find(c => c.device_id === deviceId)
      const count = camera?.person_count || 0
      maxCount = Math.max(maxCount, count)
      heatData.push([timeIndex, deviceIndex, count])
    })
  })

  chartHeight.value = Math.max(420, deviceIds.length * 36 + 160)

  return {
    title: {
      text: '设备人数热力图',
      left: 'center',
      subtext: '颜色越深人数越多',
      subtextStyle: { fontSize: 12, color: '#909399' }
    },
    tooltip: {
      position: 'top',
      formatter: (params) => {
        const [x, y, value] = params.value
        return `${timeLabels[x]}<br/>${deviceNames[deviceIds[y]]}：<b>${value}</b> 人`
      }
    },
    grid: { left: 120, right: 48, top: 72, bottom: 72, containLabel: false },
    toolbox: { feature: { saveAsImage: { title: '保存' } } },
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8 }],
    xAxis: {
      type: 'category',
      data: timeLabels,
      splitArea: { show: true },
      axisLabel: { rotate: timeLabels.length > 12 ? 35 : 0, fontSize: 11 }
    },
    yAxis: {
      type: 'category',
      data: deviceIds.map(id => deviceNames[id]),
      splitArea: { show: true },
      axisLabel: { width: 100, overflow: 'truncate' }
    },
    visualMap: {
      min: 0,
      max: Math.max(maxCount, 1),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 32,
      inRange: { color: ['#eef5ff', '#409EFF', '#1d39c4'] }
    },
    series: [{
      name: '人数',
      type: 'heatmap',
      data: heatData,
      label: { show: maxCount <= 8, formatter: ({ value }) => (value[2] ? value[2] : '') },
      emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.2)' } }
    }]
  }
}

const renderHistoryChart = () => {
  if (!isPageActive() || !chart || !sampledHistoryData.value.length) return

  chartHeight.value = chartViewMode.value === 'heatmap'
    ? Math.max(420, Object.keys(buildDeviceNameMap(sampledHistoryData.value)).length * 36 + 160)
    : 420

  let option
  if (chartViewMode.value === 'stack') {
    option = buildStackChartOption(sampledHistoryData.value)
  } else if (chartViewMode.value === 'heatmap') {
    option = buildHeatmapOption(sampledHistoryData.value)
  } else {
    option = buildTotalChartOption(sampledHistoryData.value)
  }

  try {
    chart.clear()
    chart.setOption(option, true)
    chart.resize()
  } catch {
    // ignore
  }
}

const initChart = () => {
  if (!isPageActive()) return
  const chartDom = document.getElementById('historyChart')
  if (!chartDom) return

  cleanupChart()
  try {
    chart = echarts.init(chartDom)
  } catch {
    return
  }

  chartResizeHandler = () => chart && chart.resize()
  window.addEventListener('resize', chartResizeHandler)
  renderHistoryChart()
}

const fetchHistoryData = async () => {
  if (!isPageActive() || !job.value.job_id || !dateRange.value || dateRange.value.length < 2) return

  historyLoading.value = true
  try {
    const [startDate, endDate] = dateRange.value
    const res = await crowdAnalysisApi.getAnalysisHistory(job.value.job_id, startDate, endDate)
    if (!isPageActive()) return

    historyData.value = res.data.data_points || []
    hasHistoryData.value = historyData.value.length > 0

    if (!hasHistoryData.value) {
      sampledHistoryData.value = []
      historySummary.value = null
      return
    }

    const sortedData = [...historyData.value].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    sampledHistoryData.value = sampleDataByInterval(sortedData, 60 * 60 * 1000)
    historySummary.value = computeHistorySummary(sampledHistoryData.value)

    if (!chart) {
      initChart()
    } else {
      renderHistoryChart()
    }
  } catch (error) {
    if (isPageActive()) {
      ElMessage.error('获取历史数据失败')
    }
  } finally {
    if (isPageActive()) {
      historyLoading.value = false
    }
  }
}

const showFullImage = (image) => {
  // 深拷贝对象，避免修改原始数据
  currentImage.value = JSON.parse(JSON.stringify(image));
  fullImageVisible.value = true;
}

const handleCloseFullImage = () => {
  fullImageVisible.value = false;
}

const formatBoxCoordinates = (box) => {
  if (!box || !Array.isArray(box) || box.length < 4) {
    return '未知';
  }
  const [x1, y1, x2, y2] = box.map(coord => Math.round(coord));
  return `左上(${x1}, ${y1}) - 右下(${x2}, ${y2})`;
}

const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) {
    return '#67C23A'; // 高置信度 - 绿色
  } else if (confidence >= 0.6) {
    return '#E6A23C'; // 中等置信度 - 黄色
  } else {
    return '#F56C6C'; // 低置信度 - 红色
  }
}

const refreshHistoryData = async () => {
  try {

    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - 1)
    dateRange.value = [start, end]

    await fetchHistoryData();
  } catch (error) {
    // console.error('刷新历史数据失败', error);
    ElMessage.error('刷新历史数据失败');
  }
}

</script>

<style scoped>
.crowd-analysis-detail {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.info-card,
.result-card,
.devices-card,
.history-card,
.error-card {
  margin-bottom: 20px;
}

.result-summary {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.total-count {
  text-align: center;
  padding: 20px;
  border-radius: 4px;
  background-color: #f0f9eb;
}

.count-number {
  font-size: 42px;
  font-weight: bold;
  color: #67c23a;
  display: block;
}

.count-label {
  font-size: 16px;
  color: #606266;
}

.sub-title {
  margin: 20px 0 10px;
  font-size: 16px;
  color: #606266;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.history-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.chart-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 12px 16px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 6px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-label {
  font-size: 12px;
  color: #909399;
}

.summary-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.summary-value.peak {
  color: #409EFF;
}

.summary-value.warn {
  color: #F56C6C;
}

.chart-container {
  position: relative;
  margin-top: 8px;
}

.chart-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.no-data {
  padding: 40px 0;
  text-align: center;
}

.export-button {
  margin-left: 12px;
}

.full-image-container {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.image-info {
  /* margin-bottom: 20px; */
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.image-info h3 {
  margin-top: 0;
  color: #303133;
}

.image-info p {
  margin: 5px 0;
  color: #606266;
}

.person-count {
  font-weight: bold;
  color: #409EFF;
  font-size: 18px;
}

.image-wrapper {
  display: flex;
  justify-content: center;
  margin: 20px 0;
  background-color: #000;
  padding: 10px;
  border-radius: 4px;
  width: 100%;
}

.full-preview-image {
  max-height: 70vh;
  max-width: 100%;
  object-fit: contain;
}

.detection-details {
  margin-bottom: 20px;
  width: 100%;
}

.detection-details h4 {
  margin-bottom: 15px;
  color: #303133;
}

.hint,
.cron-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 5px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.model-option,
.class-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-id {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}

.full-image-dialog {
  z-index: 9999;
}
</style>
