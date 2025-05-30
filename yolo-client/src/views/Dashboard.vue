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
        <div class="weather-info">
          <span>晴</span>
          <span>22°C</span>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="dashboard-main">
      <!-- 左侧面板 -->
      <div class="dashboard-left">
        <!-- 工厂概况 -->
        <div class="panel factory-overview">
          <h3 class="panel-title">园区概况</h3>
          <div class="overview-grid">
            <div class="overview-item">
              <div class="overview-icon factory-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.factoryCount }}</div>
                <div class="overview-label">项目数量</div>
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon area-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.areaCount }}</div>
                <div class="overview-label">监控区域</div>
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon staff-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.staffCount }}</div>
                <div class="overview-label">员工总数</div>
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon camera-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.cameraCount }}</div>
                <div class="overview-label">监控总数</div>
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon device-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.deviceCount }}</div>
                <div class="overview-label">外来车辆</div>
              </div>
            </div>
            <div class="overview-item">
              <div class="overview-icon event-icon"></div>
              <div class="overview-content">
                <div class="overview-value">{{ factoryData.eventCount }}</div>
                <div class="overview-label">异常事件</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 安全作业合格率 -->
        <div class="panel safety-chart">
          <h3 class="panel-title">项目排队时长</h3>
          <div class="chart-container">
            <div ref="safetyChartRef" class="chart"></div>
          </div>
        </div>

        <!-- 员工分布 -->
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
        <!-- 监控告警数据 -->
        <div class="panel alert-data">
          <h3 class="panel-title">检测告警数据</h3>
          <div class="alert-stats">
            <div class="alert-item">
              <div class="alert-value danger">{{ alertData.helmet }}</div>
              <div class="alert-label">未戴安全帽</div>
            </div>
            <div class="alert-item">
              <div class="alert-value warning">{{ alertData.phone }}</div>
              <div class="alert-label">玩手机</div>
            </div>
            <div class="alert-item">
              <div class="alert-value info">{{ alertData.area }}</div>
              <div class="alert-label">区域入侵</div>
            </div>
            <div class="alert-item">
              <div class="alert-value success">{{ alertData.smoke }}</div>
              <div class="alert-label">烟雾监测</div>
            </div>
            <div class="alert-item">
              <div class="alert-value danger">{{ alertData.event }}</div>
              <div class="alert-label">异常事件</div>
            </div>
          </div>
        </div>

        <!-- 工厂安装监测分布 -->
        <div class="panel map-panel">
          <h3 class="panel-title">园区监测点分布</h3>
          <div class="map-container">
            <img src="/images/map/宜春1-熊出没.jpg" alt="园区地图" class="map-img" />
            <!-- 监测点位 -->
            <div class="monitoring-points">
              <div 
                v-for="(point, index) in monitoringPoints" 
                :key="index"
                class="monitoring-point"
                :style="{ left: point.x + '%', top: point.y + '%' }"
                :class="point.status"
              >
                <div class="point-dot"></div>
                <div class="point-ripple"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 安全行为告警历史 -->
        <div class="panel alert-history">
          <h3 class="panel-title">设备告警信息</h3>
          <div class="alert-table">
            <div class="table-header">
              <div class="col">告警类型</div>
              <div class="col">设备名称</div>
              <div class="col">时间</div>
              <div class="col">状态</div>
            </div>
            <div class="table-body">
              <div 
                v-for="alert in alertHistory" 
                :key="alert.id"
                class="table-row"
                :class="{ 'highlight': alert.isNew }"
              >
                <div class="col">{{ alert.type }}</div>
                <div class="col">{{ alert.device }}</div>
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
        <!-- 安全行为类型分析 -->
        <div class="panel behavior-analysis">
          <h3 class="panel-title">检测各类型分析</h3>
          <div class="behavior-stats">
            <div class="behavior-item" v-for="item in behaviorStats" :key="item.type">
              <div class="behavior-icon" :class="item.icon"></div>
              <div class="behavior-content">
                <div class="behavior-name">{{ item.name }}</div>
                <div class="behavior-value">{{ item.value }}</div>
                <div class="behavior-trend" :class="item.trend > 0 ? 'up' : 'down'">
                  {{ item.trend > 0 ? '↑' : '↓' }} {{ Math.abs(item.trend) }}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 安全事件合格率 -->
        <div class="panel compliance-chart">
          <h3 class="panel-title">历史数据事件</h3>
          <div class="chart-container">
            <div ref="complianceChartRef" class="chart"></div>
          </div>
        </div>

        <!-- 实时监控画面 -->
        <div class="panel live-monitor">
          <h3 class="panel-title">最新报警推送</h3>
          <div class="monitor-grid">
            <div class="monitor-item" v-for="monitor in liveMonitors" :key="monitor.id">
              <div class="monitor-screen">
                <img :src="monitor.image" :alt="monitor.name" />
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

        <!-- 风险占比分类 -->
        <div class="panel risk-distribution">
          <h3 class="panel-title">风险占比分类</h3>
          <div class="chart-container">
            <div ref="riskChartRef" class="chart"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

// 响应式数据
const currentTime = ref('')
const safetyChartRef = ref(null)
const complianceChartRef = ref(null)
const riskChartRef = ref(null)

// 工厂概况数据
const factoryData = reactive({
  factoryCount: 5,
  areaCount: 230,
  staffCount: 3458,
  cameraCount: 14,
  deviceCount: 12,
  eventCount: 3732
})

// 告警数据
const alertData = reactive({
  helmet: 1,
  phone: 11,
  area: 38,
  smoke: 1,
  event: 64
})

// 员工分布数据
const staffDistribution = reactive([
  { area: 'A车间', count: 749, percentage: 85 },
  { area: 'B车间', count: 631, percentage: 70 },
  { area: 'C车间', count: 525, percentage: 60 },
  { area: 'D车间', count: 444, percentage: 50 },
  { area: 'E车间', count: 375, percentage: 42 },
  { area: 'F车间', count: 350, percentage: 40 }
])

// 监测点位数据
const monitoringPoints = reactive([
  { x: 25, y: 30, status: 'active' },
  { x: 45, y: 45, status: 'active' },
  { x: 65, y: 35, status: 'warning' },
  { x: 75, y: 55, status: 'active' },
  { x: 85, y: 40, status: 'active' },
  { x: 35, y: 65, status: 'danger' },
  { x: 55, y: 70, status: 'active' }
])

// 告警历史数据
const alertHistory = reactive([
  { id: 1, type: '未戴安全帽', device: '摄像头001', time: '13:25:32', status: 'danger', statusText: '未处理', isNew: true },
  { id: 2, type: '玩手机', device: '摄像头003', time: '13:20:15', status: 'warning', statusText: '处理中', isNew: false },
  { id: 3, type: '区域入侵', device: '摄像头005', time: '13:15:48', status: 'success', statusText: '已处理', isNew: false },
  { id: 4, type: '烟雾检测', device: '摄像头002', time: '13:10:22', status: 'danger', statusText: '未处理', isNew: false },
  { id: 5, type: '人员聚集', device: '摄像头004', time: '13:05:11', status: 'success', statusText: '已处理', isNew: false }
])

// 行为统计数据
const behaviorStats = reactive([
  { type: 'production', name: '生产设备', value: 2014, trend: 5.2, icon: 'production-icon' },
  { type: 'storage', name: '存储区域', value: 3804, trend: -2.1, icon: 'storage-icon' },
  { type: 'operation', name: '作业监测', value: 2024, trend: 8.3, icon: 'operation-icon' },
  { type: 'maintenance', name: '车辆监测', value: 2048, trend: 3.7, icon: 'maintenance-icon' },
  { type: 'environment', name: '环境监测', value: 2011, trend: -1.5, icon: 'environment-icon' },
  { type: 'safety', name: '安全环保', value: 2324, trend: 12.8, icon: 'safety-icon' }
])

// 实时监控数据
const liveMonitors = reactive([
  { id: 1, name: '入口大门', image: '/images/help/device-form.png', status: 'active', statusText: '正常' },
  { id: 2, name: 'A车间', image: '/images/help/realtime-detection.png', status: 'warning', statusText: '告警' },
  { id: 3, name: 'B车间', image: '/images/help/video-detection.png', status: 'active', statusText: '正常' },
  { id: 4, name: '仓储区', image: '/images/help/image-detection.png', status: 'active', statusText: '正常' }
])

let timeInterval = null
let dataUpdateInterval = null

// 初始化图表
const initCharts = () => {
  // 安全作业合格率图表
  const safetyChart = echarts.init(safetyChartRef.value)
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
      formatter: function(params) {
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

  // 安全事件合格率图表
  const complianceChart = echarts.init(complianceChartRef.value)
  complianceChart.setOption({
    backgroundColor: 'transparent',
    grid: {
      left: '10%',
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
      }
    },
    xAxis: {
      type: 'category',
      data: ['2022-02-24', '2022-02-25', '2022-02-26'],
      axisLabel: { 
        color: '#ffffff',
        fontSize: 10,
        fontWeight: 'bold'
      },
      axisLine: { 
        lineStyle: { 
          color: '#ff8a65',
          width: 2
        } 
      }
    },
    yAxis: {
      type: 'value',
      max: 100,
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
      data: [85, 90, 95],
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

  // 风险占比分类图表
  const riskChart = echarts.init(riskChartRef.value)
  riskChart.setOption({
    backgroundColor: 'transparent',
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['50%', '50%'],
      data: [
        { 
          value: 35, 
          name: '生产设备', 
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
              { offset: 0, color: '#ff8a65' },
              { offset: 1, color: '#ff6b6b' }
            ]),
            shadowBlur: 15,
            shadowColor: 'rgba(255, 138, 101, 0.5)'
          } 
        },
        { 
          value: 25, 
          name: '人员行为', 
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
              { offset: 0, color: '#4a90e2' },
              { offset: 1, color: '#1e3c72' }
            ]),
            shadowBlur: 15,
            shadowColor: 'rgba(74, 144, 226, 0.5)'
          } 
        },
        { 
          value: 20, 
          name: '环境监测', 
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
              { offset: 0, color: '#ff8a65' },
              { offset: 1, color: '#4a90e2' }
            ]),
            shadowBlur: 15,
            shadowColor: 'rgba(255, 138, 101, 0.5)'
          } 
        },
        { 
          value: 20, 
          name: '其他', 
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
              { offset: 0, color: '#1e3c72' },
              { offset: 1, color: '#ff8a65' }
            ]),
            shadowBlur: 15,
            shadowColor: 'rgba(30, 60, 114, 0.5)'
          } 
        }
      ],
      label: {
        show: true,
        color: '#ffffff',
        fontSize: 14,
        fontWeight: 'bold',
        formatter: '{b}: {c}%',
        textShadowBlur: 10,
        textShadowColor: 'rgba(255, 138, 101, 0.8)'
      },
      labelLine: {
        lineStyle: {
          color: '#ffffff',
          width: 2
        }
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 20,
          shadowOffsetX: 0,
          shadowColor: 'rgba(255, 138, 101, 0.8)'
        },
        label: {
          fontSize: 16,
          color: '#ff8a65'
        }
      },
      animationType: 'scale',
      animationEasing: 'elasticOut',
      animationDelay: (idx) => idx * 200
    }]
  })

  // 响应式处理
  window.addEventListener('resize', () => {
    safetyChart.resize()
    complianceChart.resize()
    riskChart.resize()
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

// 模拟数据更新
const updateData = () => {
  // 随机更新告警数据
  alertData.helmet = Math.floor(Math.random() * 5)
  alertData.phone = Math.floor(Math.random() * 20) + 5
  alertData.area = Math.floor(Math.random() * 50) + 20
  alertData.smoke = Math.floor(Math.random() * 3)
  alertData.event = Math.floor(Math.random() * 100) + 50

  // 随机更新监测点状态
  monitoringPoints.forEach(point => {
    const statuses = ['active', 'warning', 'danger']
    if (Math.random() < 0.1) { // 10%概率改变状态
      point.status = statuses[Math.floor(Math.random() * statuses.length)]
    }
  })

  // 随机添加新告警
  if (Math.random() < 0.3) { // 30%概率添加新告警
    const types = ['未戴安全帽', '玩手机', '区域入侵', '烟雾检测', '人员聚集']
    const devices = ['摄像头001', '摄像头002', '摄像头003', '摄像头004', '摄像头005']
    const newAlert = {
      id: Date.now(),
      type: types[Math.floor(Math.random() * types.length)],
      device: devices[Math.floor(Math.random() * devices.length)],
      time: new Date().toLocaleTimeString(),
      status: 'danger',
      statusText: '未处理',
      isNew: true
    }
    alertHistory.unshift(newAlert)
    if (alertHistory.length > 10) {
      alertHistory.pop()
    }
    // 3秒后移除新标记
    setTimeout(() => {
      newAlert.isNew = false
    }, 3000)
  }
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  dataUpdateInterval = setInterval(updateData, 5000)
  
  // 延迟初始化图表，确保DOM已渲染
  setTimeout(() => {
    initCharts()
  }, 100)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (dataUpdateInterval) clearInterval(dataUpdateInterval)
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
  height: 80px;
  padding: 0 40px;
  background: linear-gradient(90deg, 
    rgba(30, 60, 114, 0.8) 0%, 
    rgba(74, 144, 226, 0.6) 50%, 
    rgba(255, 138, 101, 0.8) 100%
  );
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
  0% { opacity: 0.5; transform: scaleX(0.8); }
  100% { opacity: 1; transform: scaleX(1); }
}

.time-display {
  font-size: 18px;
  color: #ffffff;
  font-weight: 500;
  letter-spacing: 1px;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.main-title {
  font-size: 40px;
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
  0% { filter: drop-shadow(0 0 20px rgba(255, 138, 101, 0.4)); }
  100% { filter: drop-shadow(0 0 30px rgba(255, 138, 101, 0.8)); }
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
  padding: 20px;
  gap: 20px;
  position: relative;
  z-index: 5;
}

.dashboard-left,
.dashboard-center,
.dashboard-right {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dashboard-left {
  flex: 0 0 25vw;
  overflow-y: auto;
  height: calc(100vh - 120px);
}

.dashboard-center {
  flex: 1;
  overflow-y: auto;
  height: calc(100vh - 120px);
}

.dashboard-right {
  flex: 0 0 25vw;
  overflow-y: auto;
  height: calc(100vh - 120px);
  padding-right: 10px;
}

.panel {
  background: linear-gradient(135deg, 
    rgba(30, 60, 114, 0.7) 0%, 
    rgba(15, 26, 46, 0.8) 50%, 
    rgba(42, 77, 122, 0.7) 100%
  );
  border: 1px solid rgba(255, 138, 101, 0.4);
  border-radius: 12px;
  padding: 16px;
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
    transparent
  );
  border-radius: 12px 12px 0 0;
  animation: panelGlow 4s ease-in-out infinite alternate;
}

@keyframes panelGlow {
  0% { opacity: 0.5; }
  100% { opacity: 1; }
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
  padding: 15px;
  background: linear-gradient(135deg, 
    rgba(74, 144, 226, 0.15) 0%, 
    rgba(255, 138, 101, 0.1) 100%
  );
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
    rgba(255, 138, 101, 0.2) 100%
  );
  border-color: #ff8a65;
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(255, 138, 101, 0.3);
}

.overview-item:hover::before {
  left: 100%;
}

.overview-icon {
  width: 40px;
  height: 40px;
  margin-right: 12px;
  border-radius: 50%;
  background-size: 20px;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}

.factory-icon { background: linear-gradient(135deg, #ff8a65, #ff6b6b) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M12 2l3.09 6.26L22 9l-5 4.87L18.18 21 12 17.27 5.82 21 7 13.87 2 9l6.91-.74L12 2z"/></svg>') center/50% no-repeat; }
.area-icon { background: linear-gradient(135deg, #4a90e2, #1e3c72) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>') center/50% no-repeat; }
.staff-icon { background: linear-gradient(135deg, #ff8a65, #4a90e2) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M16 4c0-1.11.89-2 2-2s2 .89 2 2-.89 2-2 2-2-.89-2-2zm4 18v-6h2.5l-2.54-7.63A1.5 1.5 0 0 0 18.53 7h-.53c-.8 0-1.53.5-1.83 1.25L14.5 12.5l1.5 1.5L17 11h1l1.5 4.5H21V22h-1z"/></svg>') center/50% no-repeat; }
.camera-icon { background: linear-gradient(135deg, #4a90e2, #ff8a65) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>') center/50% no-repeat; }
.device-icon { background: linear-gradient(135deg, #ff8a65, #4a90e2) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11C5.84 5 5.28 5.42 5.08 6.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99z"/></svg>') center/50% no-repeat; }
.event-icon { background: linear-gradient(135deg, #ff6b6b, #ff8a65) url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>') center/50% no-repeat; }

.overview-content {
  flex: 1;
}

.overview-value {
  font-size: 26px;
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
  margin-bottom: 20px;
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

.alert-value.danger { color: #ff6b6b; }
.alert-value.warning { color: #ff8a65; }
.alert-value.info { color: #4a90e2; }
.alert-value.success { color: #4CAF50; }
.alert-value.primary { color: #1e3c72; }

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
    rgba(255, 138, 101, 0.2) 100%
  );
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
    rgba(255, 138, 101, 0.2) 100%
  );
  animation: highlight 3s ease;
}

.table-row:hover {
  background: linear-gradient(135deg, 
    rgba(74, 144, 226, 0.2) 0%, 
    rgba(255, 138, 101, 0.15) 100%
  );
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
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}

.behavior-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  background: linear-gradient(135deg, 
    rgba(74, 144, 226, 0.15) 0%, 
    rgba(255, 138, 101, 0.1) 100%
  );
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
    rgba(255, 138, 101, 0.2) 100%
  );
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

.production-icon { background: linear-gradient(135deg, #ff8a65, #ff6b6b); }
.storage-icon { background: linear-gradient(135deg, #4a90e2, #1e3c72); }
.operation-icon { background: linear-gradient(135deg, #ff8a65, #4a90e2); }
.maintenance-icon { background: linear-gradient(135deg, #4a90e2, #ff8a65); }
.environment-icon { background: linear-gradient(135deg, #ff8a65, #ff6b6b); }
.safety-icon { background: linear-gradient(135deg, #ff6b6b, #ff8a65); }

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
    rgba(255, 138, 101, 0.05) 100%
  );
  border: 1px solid rgba(255, 138, 101, 0.2);
  transition: all 0.3s ease;
}

.distribution-item:hover {
  background: linear-gradient(135deg, 
    rgba(74, 144, 226, 0.2) 0%, 
    rgba(255, 138, 101, 0.1) 100%
  );
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
    rgba(15, 26, 46, 0.4) 100%
  );
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
    rgba(15, 26, 46, 0.4) 100%
  );
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
    rgba(15, 26, 46, 0.95) 100%
  );
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
      rgba(255, 138, 101, 0.3) 100%
    ); 
  }
  100% { 
    background: linear-gradient(135deg, 
      rgba(255, 107, 107, 0.2) 0%, 
      rgba(255, 138, 101, 0.1) 100%
    ); 
  }
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: linear-gradient(135deg, 
    rgba(30, 60, 114, 0.2) 0%, 
    rgba(15, 26, 46, 0.3) 100%
  );
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
</style>