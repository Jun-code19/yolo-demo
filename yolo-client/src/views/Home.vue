<template>
  <div class="home-container">
    <el-row :gutter="20">
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>今日检测</span>
              <el-tag :type="getTrendType(dashboardData.cards?.today_events?.trend)">
                {{ formatTrend(dashboardData.cards?.today_events?.trend) }}
              </el-tag>
            </div>
          </template>
          <div class="card-content">
            <el-statistic :value="dashboardData.cards?.today_events?.value || 0">
              <template #prefix>
                <el-icon><VideoCameraFilled /></el-icon>
              </template>
            </el-statistic>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>异常数量</span>
              <el-tag type="danger">待处理</el-tag>
            </div>
          </template>
          <div class="card-content">
            <el-statistic :value="dashboardData.cards?.unhandled_events?.value || 0">
              <template #prefix>
                <el-icon><Warning /></el-icon>
              </template>
            </el-statistic>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>检测准确率</span>
              <el-tag type="success">良好</el-tag>
            </div>
          </template>
          <div class="card-content">
            <el-statistic :value="dashboardData.cards?.accuracy?.value || 0" :precision="1" suffix="%">
              <template #prefix>
                <el-icon><DataLine /></el-icon>
              </template>
            </el-statistic>
          </div>
        </el-card>
      </el-col>
      
      <el-col :md="6" :sm="12" :xs="24">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>平均耗时</span>
              <el-tag type="warning">秒</el-tag>
            </div>
          </template>
          <div class="card-content">
            <el-statistic :value="dashboardData.cards?.avg_detection_time?.value || 0" :precision="3">
              <template #prefix>
                <el-icon><Timer /></el-icon>
              </template>
            </el-statistic>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-4">
      <el-col :md="16" :sm="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>检测结果趋势</span>
              <div class="device-status">
                <span class="status-item">
                  <el-icon color="#67C23A"><CircleCheck /></el-icon>
                  在线设备: {{ dashboardData.devices?.online || 0 }}/{{ dashboardData.devices?.total || 0 }}
                </span>
                <span class="status-item">
                  <el-icon color="#67C23A"><VideoCamera /></el-icon>
                  活跃检测: {{ dashboardData.configs?.active || 0 }}/{{ dashboardData.configs?.total || 0 }}
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
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近检测</span>
              <el-button type="primary" link @click="viewMoreEvents">
                查看更多
              </el-button>
            </div>
          </template>
          <el-timeline v-if="dashboardData.recent_activities && dashboardData.recent_activities.length > 0">
            <el-timeline-item
              v-for="activity in dashboardData.recent_activities"
              :key="activity.event_id"
              :type="activity.type"
              :timestamp="activity.timestamp"
            >
              <el-link @click="viewEventDetail(activity.event_id)">{{ activity.content }}</el-link>
            </el-timeline-item>
          </el-timeline>
          <div v-else class="empty-data">
            <el-icon :size="48"><Hide /></el-icon>
            <p>暂无检测数据</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, watch, onUnmounted } from 'vue'
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
let chart = null
const dashboardData = reactive({
  cards: {
    today_events: { value: 0, trend: 0 },
    unhandled_events: { value: 0 },
    accuracy: { value: 0 },
    avg_detection_time: { value: 0 }
  },
  devices: { total: 0, online: 0 },
  configs: { total: 0, active: 0 },
  trend_data: [],
  event_distribution: {},
  recent_activities: []
})
const loading = ref(false)

// 获取仪表盘数据
const fetchDashboardData = async () => {
  loading.value = true
  try {
    const response = await deviceApi.getDashboardOverview()
    if (response.status === 200) {
      Object.assign(dashboardData, response.data)
      // 更新图表
      renderChart()
    }
  } catch (error) {
    console.error('获取仪表盘数据失败:', error)
    ElMessage.error('获取仪表盘数据失败')
  } finally {
    loading.value = false
  }
}

// 格式化趋势
const formatTrend = (trend) => {
  if (!trend || trend === 0) return '持平'
  const sign = trend > 0 ? '+' : ''
  return `${sign}${trend.toFixed(1)}%`
}

// 获取趋势类型
const getTrendType = (trend) => {
  if (!trend || trend === 0) return 'info'
  return trend > 0 ? 'success' : 'danger'
}

// 渲染图表
const renderChart = () => {
  if (!chartRef.value) return
  
  // 初始化图表
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  
  // 准备数据
  const dates = dashboardData.trend_data.map(item => item.date)
  const counts = dashboardData.trend_data.map(item => item.count)
  
  // 设置图表选项
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
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
      name: '检测事件数',
      nameLocation: 'end'
    },
    series: [
      {
        name: '检测事件',
        type: 'bar',
        data: counts,
        itemStyle: {
          color: '#409EFF'
        },
        emphasis: {
          itemStyle: {
            color: '#66B1FF'
          }
        },
        barWidth: '50%'
      }
    ]
  }
  
  // 设置图表
  chart.setOption(option)
}

// 查看事件详情
const viewEventDetail = (eventId) => {
  // router.push(`/detection/events/${eventId}`)
  
}

// 查看更多事件
const viewMoreEvents = () => {
  router.push('/detection/events')
}

// 窗口大小变化时调整图表大小
const handleResize = () => {
  if (chart) {
    chart.resize()
  }
}

// 页面加载时获取数据
onMounted(() => {
  fetchDashboardData()
  window.addEventListener('resize', handleResize)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  // 销毁图表实例
  if (chart) {
    chart.dispose()
    chart = null
  }
})

// 监听数据变化，更新图表
watch(() => dashboardData.trend_data, () => {
  renderChart()
}, { deep: true })
</script>

<style scoped>
.home-container {
  height: 100%;
  min-width: 0;
  padding: 20px;
}

.el-row {
  margin-bottom: 20px;
  &:last-child {
    margin-bottom: 0;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-content {
  text-align: center;
  padding: 20px 0;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.chart {
  height: 100%;
  width: 100%;
}

.mt-4 {
  margin-top: 20px;
}

.el-card {
  margin-bottom: 20px;
  height: 100%;
}

.device-status {
  display: flex;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  color: #606266;
}

.empty-data {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  padding: 40px 0;
}

.empty-data p {
  margin-top: 16px;
  font-size: 14px;
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
  
  .device-status {
    flex-direction: column;
    gap: 8px;
  }
  
  .chart-container {
    height: 250px;
  }
}
</style> 