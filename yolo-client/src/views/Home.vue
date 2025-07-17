<template>
  <div class="home-container">
    <!-- 主要统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#409EFF"><VideoCameraFilled /></el-icon>
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
              <el-icon color="#67C23A"><DataLine /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.events?.detection_events?.total || 0 }}</div>
              <div class="stat-label">检测事件总数</div>
              <div class="stat-detail">
                <span class="total">累计检测事件</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#E6A23C"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ comprehensiveData.events?.external_events?.total || 0 }}</div>
              <div class="stat-label">外部事件总数</div>
              <div class="stat-detail">
                <span class="total">累计外部事件</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon color="#F56C6C"><Timer /></el-icon>
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
    <el-row :gutter="20" class="module-stats-row">
      <el-col :md="8" :sm="12" :xs="24">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>模型管理</span>
              <el-tag type="success">{{ comprehensiveData.summary?.active_models || 0 }}/{{ comprehensiveData.summary?.total_models || 0 }}</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">活跃模型:</span>
              <span class="value">{{ comprehensiveData.summary?.active_models || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">检测配置:</span>
              <span class="value">{{ comprehensiveData.summary?.active_detection_configs || 0 }}/{{ comprehensiveData.summary?.total_detection_configs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">人群分析:</span>
              <span class="value">{{ comprehensiveData.summary?.active_crowd_jobs || 0 }}/{{ comprehensiveData.summary?.total_crowd_jobs || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="8" :sm="12" :xs="24">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>数据推送</span>
              <el-tag type="success">{{ comprehensiveData.summary?.active_push_configs || 0 }}/{{ comprehensiveData.summary?.total_push_configs || 0 }}</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">推送配置:</span>
              <span class="value">{{ comprehensiveData.summary?.active_push_configs || 0 }}/{{ comprehensiveData.summary?.total_push_configs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">数据监听:</span>
              <span class="value">{{ comprehensiveData.summary?.active_listeners || 0 }}/{{ comprehensiveData.summary?.total_listeners || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">边缘设备:</span>
              <span class="value">{{ comprehensiveData.summary?.online_edge_servers || 0 }}/{{ comprehensiveData.summary?.total_edge_servers || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="8" :sm="12" :xs="24">
        <el-card class="module-card">
          <template #header>
            <div class="card-header">
              <span>系统管理</span>
              <el-tag type="info">{{ comprehensiveData.users?.total || 0 }} 用户</el-tag>
            </div>
          </template>
          <div class="module-content">
            <div class="module-item">
              <span class="label">系统用户:</span>
              <span class="value">{{ comprehensiveData.users?.total || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">系统日志:</span>
              <span class="value">{{ comprehensiveData.summary?.total_system_logs || 0 }}</span>
            </div>
            <div class="module-item">
              <span class="label">检测日志:</span>
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
                  <span class="legend-color logs"></span>
                  系统日志
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
              <div 
                v-for="activity in comprehensiveData.recent_activities" 
                :key="activity.event_id"
                class="activity-item"
              >
                <div class="activity-content">
                  <div class="activity-text">{{ activity.content }}</div>
                  <div class="activity-meta">
                    <span class="activity-time">{{ activity.timestamp }}</span>
                    <el-tag size="small" :type="activity.source === 'detection' ? 'primary' : 'success'">
                      {{ activity.source === 'detection' ? '本地检测' : '外部事件' }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 检测事件统计 -->
    <el-row :gutter="20" class="distribution-row">
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>检测事件分布统计</span>
            </div>
          </template>
          <div class="dual-chart-container">
            <div class="chart-section">
              <div class="chart-title">状态分布</div>
              <div class="distribution-chart">
                <div ref="detectionStatusChartRef" class="chart"></div>
              </div>
            </div>
            <div class="chart-section">
              <div class="chart-title">类型分布</div>
              <div class="distribution-chart">
                <div ref="detectionTypeChartRef" class="chart"></div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>外部事件分布统计</span>
            </div>
          </template>
          <div class="dual-chart-container">
            <div class="chart-section">
              <div class="chart-title">状态分布</div>
              <div class="distribution-chart">
                <div ref="externalStatusChartRef" class="chart"></div>
              </div>
            </div>
            <div class="chart-section">
              <div class="chart-title">引擎分布</div>
              <div class="distribution-chart">
                <div ref="externalEngineChartRef" class="chart"></div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 人群分析统计 -->
    <el-row :gutter="20" class="distribution-row">
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>人群分析任务统计</span>
            </div>
          </template>
          <div class="distribution-chart">
            <div ref="crowdJobChartRef" class="chart"></div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>人群分析趋势</span>
            </div>
          </template>
          <div class="distribution-chart">
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
  Timer,
  CircleCheck,
  VideoCamera,
  Hide,
  ArrowUp,
  ArrowDown
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import deviceApi from '@/api/device'

const router = useRouter()
const chartRef = ref(null)
const detectionStatusChartRef = ref(null)
const detectionTypeChartRef = ref(null)
const externalStatusChartRef = ref(null)
const externalEngineChartRef = ref(null)
const crowdJobChartRef = ref(null)
const crowdTrendChartRef = ref(null)
const activityContainer = ref(null)

let chart = null
let detectionStatusChart = null
let detectionTypeChart = null
let externalStatusChart = null
let externalEngineChart = null
let crowdJobChart = null
let crowdTrendChart = null

const comprehensiveData = reactive({
  summary: {},
  events: {},
  distributions: {},
  users: {},
  performance: {},
  trends: {},
  recent_activities: [],
  crowd_analysis: {}
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
  renderDetectionStatusChart()
  renderDetectionTypeChart()
  renderExternalStatusChart()
  renderExternalEngineChart()
  renderCrowdJobChart()
  renderCrowdTrendChart()
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
  const logsData = trends.map(item => item.system_logs)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: ['检测事件', '外部事件', '系统日志']
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
        name: '系统日志',
        type: 'line',
        data: logsData,
        itemStyle: {
          color: '#E6A23C'
        },
        smooth: true
      }
    ]
  }
  
  chart.setOption(option)
}

// 获取模型类型名称
const getEventTypeName = (eventType) => {
  const typeMap = {
    'object_detection': '目标检测',
    'smart_behavior': '智能行为',
    'smart_counting': '智能人数统计',
    'segmentation': '图像分割',
    'keypoint': '关键点检测',
    'pose': '姿态估计',
    'face': '人脸识别',
    'other': '其他类型'
  }
  return typeMap[eventType] || eventType
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

// 渲染检测事件状态分布图表
const renderDetectionStatusChart = () => {
  if (!detectionStatusChartRef.value) return
  
  if (!detectionStatusChart) {
    detectionStatusChart = echarts.init(detectionStatusChartRef.value)
  }
  
  const statusDistribution = comprehensiveData.events?.detection_events?.status_distribution || {}
  const data = Object.entries(statusDistribution).map(([status, count]) => ({
    name: getStatusLabel(status),
    value: count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '检测事件状态',
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: function(params) {
            // 如果数值为0，不显示标签
            if (params.value === 0) return '';
            // 如果百分比小于5%，不显示标签
            // if (params.percent < 5) return '';
            // 显示名称和百分比
            return params.name + '\n' + params.percent.toFixed(0) + '%';
          },
          fontSize: 10,
          lineHeight: 12
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  detectionStatusChart.setOption(option)
}

// 渲染检测事件类型分布图表
const renderDetectionTypeChart = () => {
  if (!detectionTypeChartRef.value) return
  
  if (!detectionTypeChart) {
    detectionTypeChart = echarts.init(detectionTypeChartRef.value)
  }
  
  const typeDistribution = comprehensiveData.events?.detection_events?.type_distribution || {}
  const data = Object.entries(typeDistribution).map(([type, count]) => ({
    name: getEventTypeName(type),
    value: count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '检测事件类型',
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: function(params) {
            // 如果数值为0，不显示标签
            if (params.value === 0) return '';
            // 如果百分比小于5%，不显示标签
            // if (params.percent < 5) return '';
            // 显示名称和百分比
            return params.name + '\n' + params.percent.toFixed(0) + '%';
          },
          fontSize: 10,
          lineHeight: 12
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  detectionTypeChart.setOption(option)
}

// 渲染外部事件状态分布图表
const renderExternalStatusChart = () => {
  if (!externalStatusChartRef.value) return
  
  if (!externalStatusChart) {
    externalStatusChart = echarts.init(externalStatusChartRef.value)
  }
  
  const statusDistribution = comprehensiveData.events?.external_events?.status_distribution || {}
  const data = Object.entries(statusDistribution).map(([status, count]) => ({
    name: getStatusLabel(status),
    value: count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '外部事件状态',
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: function(params) {
            // 如果数值为0，不显示标签
            if (params.value === 0) return '';
            // 如果百分比小于5%，不显示标签
            // if (params.percent < 5) return '';
            // 显示名称和百分比
            return params.name + '\n' + params.percent.toFixed(0) + '%';
          },
          fontSize: 10,
          lineHeight: 12
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  externalStatusChart.setOption(option)
}

// 渲染外部事件引擎分布图表
const renderExternalEngineChart = () => {
  if (!externalEngineChartRef.value) return
  
  if (!externalEngineChart) {
    externalEngineChart = echarts.init(externalEngineChartRef.value)
  }
  
  const engineDistribution = comprehensiveData.events?.external_events?.engine_distribution || {}
  const data = Object.entries(engineDistribution).map(([engine, count]) => ({
    name: engine || '未知引擎',
    value: count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '外部事件引擎',
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: function(params) {
            // 如果数值为0，不显示标签
            if (params.value === 0) return '';
            // 如果百分比小于5%，不显示标签
            // if (params.percent < 5) return '';
            // 显示名称和百分比
            return params.name + '\n' + params.percent.toFixed(0) + '%';
          },
          fontSize: 10,
          lineHeight: 12
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  externalEngineChart.setOption(option)
}

// 渲染人群分析任务统计图表
const renderCrowdJobChart = () => {
  if (!crowdJobChartRef.value) return
  
  if (!crowdJobChart) {
    crowdJobChart = echarts.init(crowdJobChartRef.value)
  }
  
  const jobDistribution = comprehensiveData.crowd_analysis?.job_distribution || []
  const data = jobDistribution.map(job => ({
    name: job.job_name,
    value: job.count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    series: [
      {
        name: '人群分析任务',
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '50%'],
        data: data,
        label: {
          show: true,
          position: 'outside',
          formatter: function(params) {
            // 如果数值为0，不显示标签
            if (params.value === 0) return '';
            // 如果百分比小于5%，不显示标签
            // if (params.percent < 5) return '';
            // 显示名称和百分比
            return params.name + '\n' + params.percent.toFixed(0) + '%';
          },
          fontSize: 10,
          lineHeight: 12
        },
        labelLine: {
          show: true,
          length: 8,
          length2: 8,
          smooth: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  crowdJobChart.setOption(option)
}

// 渲染人群分析趋势图表
const renderCrowdTrendChart = () => {
  if (!crowdTrendChartRef.value) return
  
  if (!crowdTrendChart) {
    crowdTrendChart = echarts.init(crowdTrendChartRef.value)
  }
  
  const jobDistribution = comprehensiveData.crowd_analysis?.job_distribution || []
  const jobNames = jobDistribution.map(job => job.job_name)
  const avgCounts = jobDistribution.map(job => job.avg_count)
  const maxCounts = jobDistribution.map(job => job.max_count)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: ['平均人数', '最大人数']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: jobNames,
      axisLabel: {
        rotate: 30
      }
    },
    yAxis: {
      type: 'value',
      name: '人数'
    },
    series: [
      {
        name: '平均人数',
        type: 'bar',
        data: avgCounts,
        itemStyle: {
          color: '#409EFF'
        }
      },
      {
        name: '最大人数',
        type: 'bar',
        data: maxCounts,
        itemStyle: {
          color: '#67C23A'
        }
      }
    ]
  }
  
  crowdTrendChart.setOption(option)
}

// 查看更多事件
const viewMoreEvents = () => {
  router.push('/detection/events')
}

// 窗口大小变化时调整图表大小
const handleResize = () => {
  if (chart) chart.resize()
  if (detectionStatusChart) detectionStatusChart.resize()
  if (detectionTypeChart) detectionTypeChart.resize()
  if (externalStatusChart) externalStatusChart.resize()
  if (externalEngineChart) externalEngineChart.resize()
  if (crowdJobChart) crowdJobChart.resize()
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
  if (detectionStatusChart) {
    detectionStatusChart.dispose()
    detectionStatusChart = null
  }
  if (detectionTypeChart) {
    detectionTypeChart.dispose()
    detectionTypeChart = null
  }
  if (externalStatusChart) {
    externalStatusChart.dispose()
    externalStatusChart = null
  }
  if (externalEngineChart) {
    externalEngineChart.dispose()
    externalEngineChart = null
  }
  if (crowdJobChart) {
    crowdJobChart.dispose()
    crowdJobChart = null
  }
  if (crowdTrendChart) {
    crowdTrendChart.dispose()
    crowdTrendChart = null
  }
})

// 监听数据变化，更新图表
watch(() => comprehensiveData.trends, () => {
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

.module-stats-row {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.module-item .label {
  color: #606266;
  font-size: 14px;
}

.module-item .value {
  color: #303133;
  font-weight: 500;
  font-size: 14px;
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

.distribution-chart {
  height: 300px;
  width: 100%;
}

.dual-chart-container {
  display: flex;
  gap: 20px;
  height: 350px;
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