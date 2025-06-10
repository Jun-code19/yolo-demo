<template>
  <div class="edge-server-detail">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" type="primary" plain class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
        <div class="header-info">
          <h2>{{ serverInfo?.name || '边缘服务器详情' }}</h2>
          <p class="server-address">{{ serverInfo?.ip_address }}:{{ serverInfo?.port }}</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="refreshing" type="success">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <el-button @click="openServerLogin" type="primary">
          <el-icon><Link /></el-icon>
          登录服务器
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="loading-card">
        <el-icon class="is-loading loading-icon"><Loading /></el-icon>
        <p>正在加载服务器信息...</p>
      </div>
    </div>

    <div v-else-if="!serverAPI" class="error-container">
      <div class="error-card">
        <el-result
          icon="error"
          title="服务器不可访问"
          sub-title="无法连接到边缘服务器，请检查服务器状态和网络连接"
        >
          <template #extra>
            <el-button type="primary" @click="goBack">返回列表</el-button>
          </template>
        </el-result>
      </div>
    </div>

    <div v-else class="dashboard-grid">
      <!-- 服务器状态卡片 -->
      <div class="status-card" :class="getStatusClass(serverInfo?.status)">
        <div class="status-indicator" :class="serverInfo?.status"></div>
        <div class="status-info">
          <h3>服务器状态</h3>
          <p class="status-text">{{ getStatusText(serverInfo?.status) }}</p>
          <div class="status-details">
            <div class="detail-item">
              <span class="label">最后检查:</span>
              <span class="value">{{ formatTime(serverInfo?.last_checked) }}</span>
            </div>
            <div class="detail-item">
              <span class="label">运行时间:</span>
              <span class="value">{{ formatTime(serverInfo?.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 系统信息卡片 -->
      <div class="info-card">
        <div class="card-header">
          <h3>系统信息</h3>
          <el-tag :type="getStatusType(serverInfo?.status)">
            {{ getStatusText(serverInfo?.status) }}
          </el-tag>
        </div>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">系统版本</span>
            <span class="value">{{ systemData?.version?.FileSystemVersion || 'N/A' }}</span>
          </div>
          <div class="info-item">
            <span class="label">内核版本</span>
            <span class="value">{{ systemData?.version?.KernelVersion || 'N/A' }}</span>
          </div>
          <div class="info-item">
            <span class="label">设备序列号</span>
            <span class="value">{{ systemData?.device?.deviceSN || 'N/A' }}</span>
          </div>
          <div class="info-item">
            <span class="label">机器ID</span>
            <span class="value">{{ systemData?.device?.mashineID || 'N/A' }}</span>
          </div>
        </div>
      </div>

      <!-- 资源使用情况 -->
      <div class="resource-cards">
        <div class="resource-card">
          <div class="resource-header">
            <h4>内存使用</h4>
            <span class="percentage">{{ getMemoryUsage() }}%</span>
          </div>
          <div class="progress-container">
            <el-progress 
              :percentage="getMemoryUsage()" 
              :color="getProgressColor(getMemoryUsage())"
              :stroke-width="6"
              :show-text="false"
            />
          </div>
          <p class="resource-text">
            {{ formatUnitValue(systemData?.system?.memU) }} / 
            {{ formatUnitValue(systemData?.system?.memT) }}
          </p>
        </div>

        <div class="resource-card">
          <div class="resource-header">
            <h4>磁盘使用</h4>
            <span class="percentage">{{ getDiskUsage() }}%</span>
          </div>
          <div class="progress-container">
            <el-progress 
              :percentage="getDiskUsage()" 
              :color="getProgressColor(getDiskUsage())"
              :stroke-width="6"
              :show-text="false"
            />
          </div>
          <p class="resource-text">
            {{ formatUnitValue(systemData?.system?.diskU) }} / 
            {{ formatUnitValue(systemData?.system?.diskT) }}
          </p>
        </div>

        <div class="resource-card">
          <div class="resource-header">
            <h4>Flash存储</h4>
            <span class="percentage">{{ getFlashUsage() }}%</span>
          </div>
          <div class="progress-container">
            <el-progress 
              :percentage="getFlashUsage()" 
              :color="getProgressColor(getFlashUsage())"
              :stroke-width="6"
              :show-text="false"
            />
          </div>
          <p class="resource-text">
            {{ formatUnitValue(systemData?.system?.flashU) }} / 
            {{ formatUnitValue(systemData?.system?.flashT) }}
          </p>
        </div>
      </div>

      <!-- 性能监控图表 -->
      <div class="chart-card">
        <div class="card-header">
          <h3>性能监控</h3>
          <div class="chart-legend">
            <span class="legend-item cpu">
              <span class="legend-dot"></span>
              CPU使用率
            </span>
            <span class="legend-item memory">
              <span class="legend-dot"></span>
              内存使用率
            </span>
          </div>
        </div>
        <div ref="chartContainer" class="chart-container"></div>
      </div>

      <!-- 功能选项卡 -->
      <div class="tabs-card">
        <div class="tabs-header">
          <h3>功能模块</h3>
        </div>
        <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="custom-tabs">
          <!-- 算法引擎 -->
          <el-tab-pane label="算法引擎" name="engines">
            <div v-loading="tabLoading" class="tab-content">
              <div v-if="engines.length === 0" class="empty-state">
                <el-empty description="暂无算法引擎数据" />
              </div>
              <div v-else class="engines-grid">
                <div 
                  v-for="engine in engines" 
                  :key="engine.engineId" 
                  class="engine-card"
                >
                  <div class="engine-header">
                    <h4>{{ engine.engineName }}</h4>
                    <div class="engine-status">
                      <el-tag 
                        :type="engine.engineStatus === 'running' ? 'success' : 'danger'"
                        size="small"
                      >
                        {{ engine.engineStatus === 'running' ? '运行中' : '已停止' }}
                      </el-tag>
                      <el-tag 
                        v-if="engine.onBoot"
                        type="info"
                        size="small"
                        style="margin-left: 8px;"
                      >
                        开机启动
                      </el-tag>
                    </div>
                  </div>
                  <div class="engine-info">
                    <div class="info-row">
                      <span class="label">引擎ID:</span>
                      <span class="value">{{ engine.engineId }}</span>
                    </div>
                    <div class="info-row">
                      <span class="label">版本:</span>
                      <span class="value">{{ engine.engineVersion }}</span>
                    </div>
                    <div class="info-row">
                      <span class="label">置信度:</span>
                      <span class="value">{{ (engine.confThreshold * 100).toFixed(1) }}%</span>
                    </div>
                    <div class="info-row">
                      <span class="label">识别类型:</span>
                      <span class="value">{{ engine.classCount }}种</span>
                    </div>
                    <div v-if="engine.engineTypes.length > 0" class="class-types">
                      <div class="class-type-label">支持类型:</div>
                      <div class="class-type-tags">
                        <el-tag 
                          v-for="(type, index) in engine.engineTypes" 
                          :key="index"
                          size="small"
                          type="info"
                          class="class-type-tag"
                        >
                          {{ type }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 视频通道 -->
          <el-tab-pane label="视频通道" name="channels">
            <div v-loading="tabLoading" class="tab-content">
              <div v-if="channels.length === 0" class="empty-state">
                <el-empty description="暂无视频通道数据" />
              </div>
              <div v-else class="channels-grid">
                <div 
                  v-for="channel in channels" 
                  :key="channel.chNo" 
                  class="channel-card"
                >
                  <div class="channel-header">
                    <h4>[{{ channel.chNo }}] {{ channel.location }}</h4>
                    <div class="channel-tags">
                      <el-tag 
                        :type="channel.aiDetectSwitch ? 'success' : 'info'"
                        size="small"
                      >
                        {{ channel.aiDetectSwitch ? 'AI启用' : 'AI禁用' }}
                      </el-tag>
                      <el-tag 
                        :type="channel.switch ? 'success' : 'danger'"
                        size="small"
                        style="margin-left: 8px;"
                      >
                        {{ channel.switch ? '开启' : '关闭' }}
                      </el-tag>
                    </div>
                  </div>
                  
                  <!-- 截图预览区域 -->
                  <div class="channel-preview">
                    <div v-if="channel.LatestPic" class="preview-image">
                      <img 
                        :src="serverAPI.getChannelImage(channel.LatestPic)" 
                        :alt="`通道${channel.chNo}截图`"
                        @error="handleImageError"
                        @click="previewImage(channel.LatestPic)"
                      />
                      <div class="preview-overlay" @click="previewImage(channel.LatestPic)">
                        <el-icon class="preview-icon"><ZoomIn /></el-icon>
                      </div>
                    </div>
                    <div v-else class="no-preview-placeholder">
                      <el-icon class="placeholder-icon"><Picture /></el-icon>
                      <span>暂无截图</span>
                    </div>
                  </div>
                  
                  <div class="channel-info">
                    <p class="channel-name">{{ channel.location }}</p>
                    <p class="model-name">
                      模型: {{ channel.modelName }}
                      <span v-if="channel.models.length > 1" class="model-count">
                        (共{{ channel.models.length }}个)
                      </span>
                    </p>
                    <p v-if="channel.desc" class="channel-desc">{{ channel.desc }}</p>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 历史事件 -->
          <el-tab-pane label="历史事件" name="events">
            <div class="events-section">
              <!-- 筛选器 -->
              <div class="events-filter">
                <el-form :model="eventFilter" inline size="small">
                  <el-form-item label="通道" style="width: 220px;">
                    <el-select v-model="eventFilter.chNo" placeholder="全部通道" clearable>
                      <el-option 
                        v-for="ch in channels" 
                        :key="ch.chNo" 
                        :label="`通道${ch.chNo} - ${ch.location}`" 
                        :value="ch.chNo.toString()"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="事件类型" style="width: 200px;">
                    <el-select v-model="eventFilter.eventType" placeholder="全部类型" clearable>
                      <el-option 
                        v-for="type in eventTypes" 
                        :key="type.typeValue" 
                        :label="type.typeName" 
                        :value="type.typeValue"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="时间范围">
                    <el-date-picker
                      v-model="eventFilter.dateRange"
                      type="datetimerange"
                      range-separator="至"
                      start-placeholder="开始时间"
                      end-placeholder="结束时间"
                      size="small"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" @click="loadEvents" size="small">查询</el-button>
                    <el-button @click="resetEventFilter" size="small">重置</el-button>
                  </el-form-item>
                </el-form>
              </div>

              <!-- 事件列表 -->
              <div v-loading="tabLoading" class="events-content">
                <div v-if="events.length === 0" class="empty-state">
                  <el-empty description="暂无历史事件数据" />
                </div>
                <div v-else class="events-list">
                  <el-table :data="events" stripe style="width: 100%">
                    <el-table-column prop="chNo" label="通道" width="100">
                      <template #default="scope">
                        <el-tag size="small" type="primary">{{ scope.row.chNo }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="location" label="位置" width="150" />
                    <el-table-column prop="typeName" label="事件类型" min-width="180" show-overflow-tooltip />
                    <el-table-column prop="confidence" label="置信度" width="150">
                      <template #default="scope">
                        <el-tag 
                          :type="scope.row.confidence > 0.8 ? 'success' : scope.row.confidence > 0.6 ? 'warning' : 'danger'"
                          size="small"
                        >
                          {{ (scope.row.confidence * 100).toFixed(1) }}%
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="targetList" label="检测目标" width="150" show-overflow-tooltip>
                      <template #default="scope">
                        <span v-if="scope.row.targetList && scope.row.targetList.length > 0">
                          {{ scope.row.targetList.length }}个目标
                          <el-tooltip :content="scope.row.targetList.map(t => t.targetName).join(', ')">
                            <el-icon class="info-icon"><InfoFilled /></el-icon>
                          </el-tooltip>
                        </span>
                        <span v-else class="no-target">无检测目标</span>
                      </template>
                    </el-table-column>
                    <el-table-column prop="eventTimeStr" label="发生时间" width="200" />
                    <el-table-column label="截图预览" width="150">
                      <template #default="scope">
                        <div v-if="scope.row.picPath" class="table-image-preview">
                          <img 
                            :src="serverAPI.getEventImage(scope.row.picPath)" 
                            :alt="'事件截图'"
                            @click="previewEventImage(scope.row.picPath)"
                            @error="handleImageError"
                          />
                        </div>
                        <span v-else class="no-image">无截图</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="150">
                      <template #default="scope">
                        <el-button type="text" size="small" @click="previewImage(scope.row.picPath)">查看图片</el-button>
                      </template>
                    </el-table-column>
                  </el-table>

                  <!-- 分页 -->
                  <div class="pagination-container">
                    <el-pagination
                      v-model:current-page="eventPagination.page"
                      v-model:page-size="eventPagination.limit"
                      :page-sizes="[10, 20, 50]"
                      :total="eventPagination.total"
                      layout="total, sizes, prev, pager, next, jumper"
                      @size-change="loadEvents"
                      @current-change="loadEvents"
                      size="small"
                    />
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 图片预览对话框 -->
    <el-dialog 
      v-model="imagePreviewVisible" 
      title="图片预览" 
      width="60%" 
      :z-index="9999"
      :modal="true"
      :append-to-body="true"
      :close-on-click-modal="true"
      class="image-preview-dialog"
    >
      <div class="image-preview">
        <img :src="previewImageUrl" alt="预览图片" style="max-width: 100%; height: auto;" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Link, Loading, ZoomIn, Picture, InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import edgeServerAPI from '@/api/edge-server'

const router = useRouter()
const route = useRoute()

// 数据状态
const loading = ref(true)
const refreshing = ref(false)
const tabLoading = ref(false)
const serverInfo = ref(null)
const serverAPI = ref(null)
const systemData = reactive({
  version: null,
  system: null,
  device: null,
  cpuData: []
})

// 选项卡数据
const activeTab = ref('engines')
const engines = ref([])
const channels = ref([])
const events = ref([])
const eventTypes = ref([])

// 事件筛选
const eventFilter = reactive({
  chNo: '',
  eventType: '',
  dateRange: []
})

const eventPagination = reactive({
  page: 1,
  limit: 20,
  total: 0
})

// 图片预览
const imagePreviewVisible = ref(false)
const previewImageUrl = ref('')

// 图表相关
const chartContainer = ref()
let chartInstance = null
let dataRefreshTimer = null

// 初始化
onMounted(async () => {
  await loadServerInfo()
  if (serverAPI.value) {
    await loadSystemData()
    await nextTick()
    initChart()
    startDataRefresh()
  }
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
  }
  if (dataRefreshTimer) {
    clearInterval(dataRefreshTimer)
  }
})

// 加载服务器信息
const loadServerInfo = async () => {
  try {
    const serverId = route.params.serverId
    const response = await edgeServerAPI.getServer(serverId)
    serverInfo.value = response
    
    // 创建服务器API实例
    if (response.status === 'online') {
      serverAPI.value = edgeServerAPI.createServerAPI(response.ip_address, response.port)
    }
  } catch (error) {
    console.error('加载服务器信息失败:', error)
    ElMessage.error('加载服务器信息失败')
  } finally {
    loading.value = false
  }
}

// 加载系统数据
const loadSystemData = async () => {
  if (!serverAPI.value) return
  
  try {
    const [versionRes, systemRes, deviceRes] = await Promise.all([
      serverAPI.value.getSystemVersion(),
      serverAPI.value.getSystemFlash(),
      serverAPI.value.getDeviceInfo()
    ])
    
    systemData.version = versionRes.result
    systemData.system = systemRes.result
    systemData.device = deviceRes.result
    
    // 更新后端服务器状态
    await edgeServerAPI.updateServerStatus(serverInfo.value.id, {
      status: 'online',
      system_info: systemData.system,
      version_info: systemData.version,
      device_info: systemData.device
    })

    loadEngines()
  } catch (error) {
    console.error('加载系统数据失败:', error)
  }
}

// 加载CPU数据
const loadCPUData = async () => {
  if (!serverAPI.value) return
  
  try {
    const response = await serverAPI.value.getCPUStatic()
    if (response.code === 0 && response.data && Array.isArray(response.data)) {
      // 清空现有数据，使用API返回的历史数据
      systemData.cpuData = []
      
      // 处理API返回的数据数组
      response.data.forEach(item => {
        const dataPoint = {
          time: new Date(item.time).toLocaleTimeString(), // 转换时间格式
          timestamp: new Date(item.time).getTime(),
          cpu: parseFloat(item.cpu) * 100, // 转换为百分比
          mem: parseFloat(item.mem) * 100  // 转换为百分比
        }
        systemData.cpuData.push(dataPoint)
      })
      
      updateChart()
    } else {
      // 如果API格式不同，回退到原来的逻辑
      const cpuResponse = await serverAPI.value.getCPUStatic()
      if (cpuResponse.result) {
        const now = new Date()
        const dataPoint = {
          time: now.toLocaleTimeString(),
          timestamp: now.getTime(),
          cpu: cpuResponse.result.CPUPercent || 0,
          mem: cpuResponse.result.MemPercent || 0
        }
        
        systemData.cpuData.push(dataPoint)
        
        // 保持最近20个数据点
        if (systemData.cpuData.length > 20) {
          systemData.cpuData.shift()
        }
        
        updateChart()
      }
    }
  } catch (error) {
    console.error('加载CPU数据失败:', error)
  }
}

// 初始化图表
const initChart = () => {
  if (!chartContainer.value) return
  
  chartInstance = echarts.init(chartContainer.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: function (params) {
        let result = params[0].name + '<br/>'
        params.forEach(param => {
          result += `${param.seriesName}: ${param.value}%<br/>`
        })
        return result
      }
    },
    legend: {
      show: false
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: []
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [
      {
        name: 'CPU使用率',
        type: 'line',
        smooth: true,
        data: [],
        itemStyle: {
          color: '#409EFF'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
          ])
        }
      },
      {
        name: '内存使用率',
        type: 'line',
        smooth: true,
        data: [],
        itemStyle: {
          color: '#67C23A'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
            { offset: 1, color: 'rgba(103, 194, 58, 0.1)' }
          ])
        }
      }
    ]
  }
  
  chartInstance.setOption(option)
  
  // 添加窗口resize监听
  const handleResize = () => {
    if (chartInstance) {
      chartInstance.resize()
    }
  }
  
  window.addEventListener('resize', handleResize)
  
  // 使用ResizeObserver监听容器大小变化
  if (window.ResizeObserver) {
    const resizeObserver = new ResizeObserver(() => {
      if (chartInstance) {
        chartInstance.resize()
      }
    })
    resizeObserver.observe(chartContainer.value)
  }
}

// 更新图表
const updateChart = () => {
  if (!chartInstance) return
  
  const timeData = systemData.cpuData.map(item => item.time)
  const cpuData = systemData.cpuData.map(item => item.cpu.toFixed(1))
  const memoryData = systemData.cpuData.map(item => item.mem.toFixed(1))
  
  chartInstance.setOption({
    xAxis: {
      data: timeData
    },
    series: [
      { data: cpuData },
      { data: memoryData }
    ]
  })
}

// 开始数据刷新
const startDataRefresh = () => {
  // 立即加载一次CPU数据
  loadCPUData()
  
  // 每30秒刷新一次（因为现在获取的是历史数据，不需要太频繁）
  dataRefreshTimer = setInterval(() => {
    loadCPUData()
  }, 30000)
}

// 选项卡切换
const handleTabChange = async (tabName) => {
  tabLoading.value = true
  
  try {
    switch (tabName) {
      case 'engines':
        await loadEngines()
        break
      case 'channels':
        await loadChannels()
        break
      case 'events':
        await loadEventTypes()
        await loadEvents()
        break
    }
  } catch (error) {
    console.error('加载选项卡数据失败:', error)
  } finally {
    tabLoading.value = false
  }
}

// 加载算法引擎
const loadEngines = async () => {
  try {
    const response = await serverAPI.value.getAlgorithmEngines()
    if (response.code === 0 && response.result && response.result.engines) {
      engines.value = response.result.engines.map(engine => {
        // 提取所有识别类型
        const classTypes = []
        if (engine.model?.class?.value && Array.isArray(engine.model.class.value)) {
          engine.model.class.value.forEach(classItem => {
            if (classItem.sub_cls && Array.isArray(classItem.sub_cls)) {
              classItem.sub_cls.forEach(subClass => {
                if (subClass.enable) {
                  classTypes.push(subClass.name)
                }
              })
            } else if (classItem.name) {
              classTypes.push(classItem.name)
            }
          })
        }
        
        return {
          engineId: engine.id,
          engineName: engine.name,
          engineVersion: engine.version,
          engineStatus: engine.isRunning ? 'running' : 'stopped',
          engineTypes: classTypes, // 改为数组
          engineType: classTypes.length > 0 ? classTypes.join(', ') : '未知类型', // 兼容原有显示
          confThreshold: engine.model?.conf_thresh?.value || 0,
          onBoot: engine.onBoot,
          classCount: classTypes.length
        }
      })
    } else {
      engines.value = response.result || []
    }
  } catch (error) {
    console.error('加载算法引擎失败:', error)
    engines.value = []
  }
}

// 加载视频通道
const loadChannels = async () => {
  try {
    const response = await serverAPI.value.getVideoChannels()
    if (response.code === 0 && response.result) {
      channels.value = response.result.map(channel => ({
        chNo: channel.chNo,
        chName: channel.location, // 使用location作为通道名称
        location: channel.location,
        aiDetectSwitch: channel.aiDetectSwitch,
        status: channel.status,
        switch: channel.switch,
        models: channel.models || [],
        modelName: channel.models?.[0]?.name || '未配置',
        LatestPic: channel.imgPath,
        desc: channel.desc || '',
        playUrl: channel.playUrl,
        rtspURL: channel.rtspURL
      }))
    } else {
      channels.value = response.result || []
    }
  } catch (error) {
    console.error('加载视频通道失败:', error)
    channels.value = []
  }
}

// 加载事件类型
const loadEventTypes = async () => {
  try {
    const response = await serverAPI.value.getEventTypes()
    if (response.code === 0 && response.result) {
      eventTypes.value = response.result.map(type => ({
        typeValue: type.classId,
        typeName: type.className,
        desc: type.desc || ''
      }))
    } else {
      eventTypes.value = response.result || []
    }
  } catch (error) {
    console.error('加载事件类型失败:', error)
    eventTypes.value = []
  }
}

// 加载历史事件
const loadEvents = async () => {
  try {
    const params = {
      chNo: eventFilter.chNo,
      eventType: eventFilter.eventType,
      limit: eventPagination.limit,
      pageNo: eventPagination.page
    }
    
    if (eventFilter.dateRange && eventFilter.dateRange.length === 2) {
      params.startTime = Math.floor(new Date(eventFilter.dateRange[0]).getTime() / 1000)
      params.endTime = Math.floor(new Date(eventFilter.dateRange[1]).getTime() / 1000)
    } else {
      params.startTime = 0
      params.endTime = 0
    }
    
    const response = await serverAPI.value.getHistoryEvents(params)
    if (response.code === 0 && response.result) {
      events.value = response.result.map(event => {
        // 处理事件类型，去重并用|分隔
        let typeName = '未知事件'
        if (event.cnames) {
          // 去除首尾逗号，分割并去重
          const typeArray = event.cnames.replace(/^,+|,+$/g, '').split(',').filter(name => name.trim())
          const uniqueTypes = [...new Set(typeArray.filter(name => name.trim()))]
          typeName = uniqueTypes.length > 0 ? uniqueTypes.join(' | ') : '未知事件'
        }
        
        return {
          eventId: event.id,
          chNo: event.chNo,
          location: event.location,
          eventTime: parseInt(event.timeStamp),
          eventTimeStr: event.timeStampStr,
          typeName: typeName,
          confidence: event.detects?.detects?.[0]?.conf || 0,
          targetList: event.detects?.detects?.map(detect => ({
            targetName: detect.class_name,
            confidence: detect.conf,
            position: {
              x1: detect.x1,
              y1: detect.y1,
              x2: detect.x2,
              y2: detect.y2
            }
          })) || [],
          picPath: event.imgPath,
          smallPicPath: event.simgPath,
          cids: event.cids,
          cnames: event.cnames,
          flagID: event.flagID,
          geid: event.geid
        }
      })
      eventPagination.total = response.totalCount || 0
    } else {
      events.value = []
      eventPagination.total = 0
    }
  } catch (error) {
    console.error('加载历史事件失败:', error)
    events.value = []
    eventPagination.total = 0
  }
}

// 重置事件筛选器
const resetEventFilter = () => {
  eventFilter.chNo = ''
  eventFilter.eventType = ''
  eventFilter.dateRange = []
  eventPagination.page = 1
  loadEvents()
}

// 预览图片
const previewImage = (imagePath) => {
  previewImageUrl.value = serverAPI.value.getChannelImage(imagePath)
  imagePreviewVisible.value = true
}

const previewEventImage = (imagePath) => {
  previewImageUrl.value = serverAPI.value.getEventImage(imagePath)
  imagePreviewVisible.value = true
}

// 工具函数
const goBack = () => {
  router.push({ name: 'EdgeServers' })
}

const openServerLogin = () => {
  if (serverInfo.value) {
    const loginUrl = `http://${serverInfo.value.ip_address}:${serverInfo.value.port}`
    window.open(loginUrl, '_blank')
  }
}

const refreshData = async () => {
  refreshing.value = true
  try {
    await loadSystemData()
    if (activeTab.value === 'engines') await loadEngines()
    if (activeTab.value === 'channels') await loadChannels()
    if (activeTab.value === 'events') await loadEvents()
    ElMessage.success('数据刷新成功')
  } catch (error) {
    ElMessage.error('数据刷新失败')
  } finally {
    refreshing.value = false
  }
}

const getStatusType = (status) => {
  switch (status) {
    case 'online': return 'success'
    case 'offline': return 'danger'
    default: return 'info'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'online': return '在线'
    case 'offline': return '离线'
    default: return '未知'
  }
}

const getStatusClass = (status) => {
  switch (status) {
    case 'online': return 'online'
    case 'offline': return 'offline'
    default: return 'unknown'
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return '从未'
  return new Date(timeStr).toLocaleString()
}

const formatEventTime = (timestamp) => {
  return new Date(timestamp * 1000).toLocaleString()
}

const formatUnitValue = (value) => {
  if (!value || typeof value !== 'string') return '0 B'
  
  // 直接返回原始格式，去掉括号
  const match = value.match(/^([\d.]+)\s*\(([^)]+)\)$/)
  if (match) {
    const [, number, unit] = match
    return `${number} ${unit}`
  }
  return value
}

// 保留原有的formatBytes函数，用于处理纯数字字节值
const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const getMemoryUsage = () => {
  if (!systemData.system?.memT || !systemData.system?.memU) return 0
  
  const totalBytes = parseUnitValue(systemData.system.memT)
  const usedBytes = parseUnitValue(systemData.system.memU)
  
  if (totalBytes === 0) return 0
  return Math.round((usedBytes / totalBytes) * 100)
}

const getDiskUsage = () => {
  if (!systemData.system?.diskT || !systemData.system?.diskU) return 0
  
  const totalBytes = parseUnitValue(systemData.system.diskT)
  const usedBytes = parseUnitValue(systemData.system.diskU)
  
  if (totalBytes === 0) return 0
  return Math.round((usedBytes / totalBytes) * 100)
}

const getFlashUsage = () => {
  if (!systemData.system?.flashT || !systemData.system?.flashU) return 0
  
  const totalBytes = parseUnitValue(systemData.system.flashT)
  const usedBytes = parseUnitValue(systemData.system.flashU)
  
  if (totalBytes === 0) return 0
  return Math.round((usedBytes / totalBytes) * 100)
}

const getProgressColor = (percentage) => {
  if (percentage < 50) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

// 解析带单位的数据字符串（如"1.710(GB)"）转换为字节数
const parseUnitValue = (value) => {
  if (!value || typeof value !== 'string') return 0
  
  // 使用正则提取数字和单位
  const match = value.match(/^([\d.]+)\s*\(([^)]+)\)$/)
  if (!match) return 0
  
  const [, numberStr, unit] = match
  const number = parseFloat(numberStr)
  
  // 根据单位转换为字节
  switch (unit.toUpperCase()) {
    case 'B': return number
    case 'KB': return number * 1024
    case 'MB': return number * 1024 * 1024
    case 'GB': return number * 1024 * 1024 * 1024
    case 'TB': return number * 1024 * 1024 * 1024 * 1024
    default: return number
  }
}

const handleImageError = () => {
  // 处理图片加载错误后的逻辑
  console.error('图片加载失败')
}
</script>

<style scoped>
.edge-server-detail {
  padding: 24px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-btn {
  border-radius: 8px;
}

.header-info h2 {
  margin: 0 0 4px 0;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.server-address {
  margin: 0;
  color: #909399;
  font-size: 14px;
  font-family: 'Monaco', 'Consolas', monospace;
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* 加载和错误状态 */
.loading-container, .error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.loading-card, .error-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  text-align: center;
}

.loading-icon {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 16px;
}

.loading-card p {
  margin: 0;
  color: #606266;
  font-size: 16px;
}

/* 仪表板网格 */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 20px;
}

/* 状态卡片 */
.status-card {
  grid-column: span 4;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
}

.status-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: #e4e7ed;
}

.status-card.online::before {
  background: #67c23a;
}

.status-card.offline::before {
  background: #f56c6c;
}

.status-indicator {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: #e4e7ed;
}

.status-indicator.online {
  background-color: #67c23a;
  box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.2);
}

.status-indicator.offline {
  background-color: #f56c6c;
  box-shadow: 0 0 0 3px rgba(245, 108, 108, 0.2);
}

.status-info h3 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.status-text {
  margin: 0 0 16px 0;
  color: #409eff;
  font-size: 16px;
  font-weight: 500;
}

.status-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.detail-item .label {
  color: #909399;
}

.detail-item .value {
  color: #606266;
  font-family: 'Monaco', 'Consolas', monospace;
}

/* 信息卡片 */
.info-card {
  grid-column: span 8;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item .label {
  color: #909399;
  font-size: 14px;
  font-weight: 500;
}

.info-item .value {
  color: #606266;
  font-size: 14px;
  font-family: 'Monaco', 'Consolas', monospace;
}

/* 资源卡片 */
.resource-cards {
  grid-column: span 12;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.resource-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.resource-header h4 {
  margin: 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.percentage {
  color: #409eff;
  font-size: 18px;
  font-weight: 700;
}

.progress-container {
  margin-bottom: 12px;
}

.resource-text {
  margin: 0;
  color: #909399;
  font-size: 12px;
  text-align: center;
  font-family: 'Monaco', 'Consolas', monospace;
}

/* 图表卡片 */
.chart-card {
  grid-column: span 12;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-legend {
  display: flex;
  gap: 20px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #606266;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-item.cpu .legend-dot {
  background-color: #409eff;
}

.legend-item.memory .legend-dot {
  background-color: #67c23a;
}

.chart-container {
  height: 300px;
  margin-top: 16px;
}

/* 选项卡卡片 */
.tabs-card {
  grid-column: span 12;
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.tabs-header {
  margin-bottom: 20px;
}

.tabs-header h3 {
  margin: 0;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.tab-content {
  min-height: 300px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

/* 算法引擎网格 */
.engines-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.engine-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
}

.engine-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.engine-header h4 {
  margin: 0;
  color: #303133;
  font-size: 16px;
}

.engine-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.engine-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.class-types {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.class-type-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.class-type-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.class-type-tag {
  margin: 0 !important;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.info-row .label {
  color: #909399;
}

.info-row .value {
  color: #606266;
}

/* 视频通道网格 */
.channels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.channel-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.channel-header h4 {
  margin: 0;
  color: #303133;
  font-size: 16px;
  flex: 1;
}

.channel-tags {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.channel-info {
  margin-bottom: 12px;
}

.channel-name {
  margin: 0 0 4px 0;
  color: #606266;
  font-size: 14px;
  font-weight: 500;
}

.model-name {
  margin: 0 0 4px 0;
  color: #909399;
  font-size: 12px;
}

.model-count {
  color: #409eff;
  font-weight: 500;
}

.channel-desc {
  margin: 0;
  color: #909399;
  font-size: 12px;
  font-style: italic;
}

.channel-preview {
  margin-bottom: 12px;
}

.preview-image {
  position: relative;
  width: 100%;
  height: 200px;
  overflow: hidden;
  border-radius: 4px;
}

.preview-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 4px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.preview-image:hover .preview-overlay {
  opacity: 1;
}

.preview-icon {
  font-size: 24px;
  color: white;
}

.no-preview-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 200px;
  border: 1px dashed #e4e7ed;
  border-radius: 4px;
  color: #909399;
  font-size: 14px;
  gap: 8px;
}

.placeholder-icon {
  font-size: 24px;
  color: #909399;
}

/* 事件模块 */
.events-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.events-filter {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
}

.events-content {
  flex: 1;
}

.events-list {
  flex: 1;
  width: 100%;
  overflow-x: auto;
}

.events-list .el-table {
  width: 100%;
  min-width: 800px;
}

.events-list .el-table .el-table__body-wrapper {
  overflow-x: auto;
}

.table-image-preview {
  width: 80px;
  height: 50px;
  overflow: hidden;
  border-radius: 4px;
  cursor: pointer;
}

.table-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.table-image-preview:hover img {
  transform: scale(1.1);
}

.no-image, .no-target {
  color: #c0c4cc;
  font-size: 12px;
}

.info-icon {
  margin-left: 4px;
  color: #409eff;
  cursor: pointer;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: repeat(8, 1fr);
  }
  
  .status-card,
  .info-card {
    grid-column: span 8;
  }
  
  .resource-cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .edge-server-detail {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .header-left {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .status-card,
  .info-card,
  .resource-cards,
  .chart-card,
  .tabs-card {
    grid-column: span 1;
  }
  
  .info-grid {
    grid-template-columns: 1fr;
  }
  
  .engines-grid,
  .channels-grid {
    grid-template-columns: 1fr;
  }
  
  /* 移动端表格优化 */
  .events-list .el-table {
    min-width: 600px;
  }
  
  .events-list {
    overflow-x: scroll;
  }
}

/* 图片预览对话框样式 */
.image-preview-dialog {
  z-index: 9999 !important;
}

.image-preview-dialog .el-dialog {
  z-index: 9999 !important;
}

.image-preview-dialog .el-dialog__wrapper {
  z-index: 9999 !important;
}

.image-preview {
  text-align: center;
  padding: 20px;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>

<style>
/* 全局样式确保图片预览对话框最高优先级 */
.el-dialog__wrapper {
  z-index: 9999 !important;
}

.el-overlay {
  z-index: 9998 !important;
}

.image-preview-dialog .el-dialog__wrapper {
  z-index: 10000 !important;
}

.image-preview-dialog .el-overlay {
  z-index: 9999 !important;
}

/* 确保下拉框选项在对话框中正常显示 */
.el-select-dropdown {
  z-index: 10001 !important;
}

.el-popper {
  z-index: 10001 !important;
}

.el-picker-panel {
  z-index: 10001 !important;
}

/* 针对图片预览对话框中的下拉框 */
.image-preview-dialog .el-select-dropdown {
  z-index: 10002 !important;
}

.image-preview-dialog .el-popper {
  z-index: 10002 !important;
}

.image-preview-dialog .el-picker-panel {
  z-index: 10002 !important;
}
</style> 