<template>
  <div class="data-events">
    <div class="page-header">
      <div class="header-content">
        <h1>事件监控</h1>
        <p>监控和查看外部数据源事件</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="exportEvents">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button 
          type="danger" 
          :disabled="selectedEvents.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedEvents.length }})
        </el-button>
      </div>
    </div>

    <!-- 实时统计 -->
    <div class="stats-row">
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-icon">
              <el-icon color="#409EFF"><Notification /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ realtimeStats.total_today || 0 }}</div>
              <div class="stat-label">今日事件</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-icon">
              <el-icon color="#67C23A"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ realtimeStats.processed_today || 0 }}</div>
              <div class="stat-label">已处理</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-icon">
              <el-icon color="#E6A23C"><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ realtimeStats.recent_1hour || 0 }}</div>
              <div class="stat-label">近1小时</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-icon">
              <el-icon color="#F56C6C"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ realtimeStats.alarms_today || 0 }}</div>
              <div class="stat-label">报警事件</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 过滤器 -->
    <el-card class="filter-card">
      <div class="filters">
        <el-select
          v-model="filters.config_id"
          placeholder="监听器"
          clearable
          style="width: 150px"
          @change="loadData"
        >
          <el-option
            v-for="config in listenerConfigs"
            :key="config.config_id"
            :label="config.name"
            :value="config.config_id"
          />
        </el-select>

        <el-select
          v-model="filters.event_type"
          placeholder="事件类型"
          clearable
          style="width: 150px"
          @change="loadData"
        >
          <el-option value="detection" label="检测事件" />
          <el-option value="alarm" label="报警事件" />
          <el-option value="status" label="状态事件" />
          <el-option value="command" label="命令事件" />
          <el-option value="heartbeat" label="心跳事件" />
          <el-option value="other" label="其他事件" />
        </el-select>

        <el-input
          v-model="filters.device_id"
          placeholder="设备ID"
          style="width: 150px"
          clearable
          @keyup.enter="loadData"
        />

        <!-- device_name_mappings中的key为设备ID，value为设备名称，device_name_mappings有值时显示下拉框，无值时可以手动输入需要筛选的值 -->
        <div v-if="Object.keys(device_name_mappings).length > 0">
          <el-select
            v-model="filters.device_name"
            placeholder="设备SN码"
            style="width: 150px"
            clearable
            @change="loadData"
          >
            <el-option
              v-for="device in Object.keys(device_name_mappings)"
              :key="device"
              :label="device_name_mappings[device]"
              :value="device"
            />
          </el-select>
        </div>
        <div v-else>
          <el-input
          v-model="filters.device_sn"
          placeholder="设备SN码"
          style="width: 150px"
          clearable
          @keyup.enter="loadData"
        />
        </div>

        <!-- engine_name_mappings中的key为引擎ID，value为引擎名称，engine_name_mappings有值时显示下拉框，无值时可以手动输入需要筛选的值 -->

        <div v-if="Object.keys(engine_name_mappings).length > 0">
          <el-select
            v-model="filters.engine_id"
            placeholder="算法引擎ID"
            style="width: 150px"
            clearable
            @change="loadData"
          >
            <el-option
              v-for="engine in Object.keys(engine_name_mappings)"
              :key="engine"
              :label="engine_name_mappings[engine]"
              :value="engine"
            />
          </el-select>
        </div>
        <div v-else>
          <el-input
            v-model="filters.engine_id"
            placeholder="算法引擎ID"
            style="width: 120px"
            clearable
            @keyup.enter="loadData"
          />
        </div>

        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          @change="handleDateChange"
          style="width: 300px"
        />

        <el-button type="primary" @click="loadData">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>

        <el-button @click="clearFilters">
          <el-icon><RefreshLeft /></el-icon>
          重置
        </el-button>

        <div class="auto-refresh">
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            @change="toggleAutoRefresh"
          />
        </div>
      </div>
    </el-card>

    <!-- 事件列表 -->
    <el-card class="table-card">
      <el-table
        :data="events"
        v-loading="loading"
        style="width: 100%"
        @row-click="showEventDetail"
        @selection-change="handleSelectionChange"
        row-class-name="clickable-row"
      >
        <!-- 选择列 -->
        <el-table-column type="selection" width="55" fixed="left"/>
         
        <el-table-column prop="device_id" label="设备ID" min-width="140">
          <template #default="{ row }">
            <span v-if="row.device_id">{{ row.device_id }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
<!-- 
        <el-table-column prop="channel_id" label="通道" width="80">
          <template #default="{ row }">
            <span v-if="row.channel_id">{{ row.channel_id }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column> -->

        <el-table-column prop="event_type" label="事件类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getEventTypeTagType(row.event_type)" size="small">
              {{ getEventTypeText(row.event_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="source_type" label="来源" width="80">
          <template #default="{ row }">
            <el-tag :type="getSourceTypeTagType(row.source_type)" size="small">
              {{ row.source_type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="device_sn" label="设备SN" width="120">
          <template #default="{ row }">
            <div v-if="row.device_sn || row.device_name">
              <div v-if="row.device_name">{{ row.device_name }}</div>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="engine_id" label="算法引擎" width="120">
          <template #default="{ row }">
            <div v-if="row.engine_id || row.engine_name">
              <div v-if="row.engine_name">{{ row.engine_name }}</div>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>

        <!-- 检测目标列 -->
        <el-table-column label="检测目标" min-width="150">
          <template #default="{ row }">
            <div v-if="getDetectionTargets(row).length > 0" class="detection-targets">
              <div class="targets-summary">
                <el-tag size="small" type="primary">{{ getDetectionTargets(row).length }}个目标</el-tag>
              </div>
              <div class="targets-detail">
                <div 
                  v-for="(target, index) in getDetectionTargets(row).slice(0, 2)" 
                  :key="index"
                  class="target-item"
                >
                  <span class="target-name">{{ target.class_name || '未知' }}</span>
                  <span class="target-confidence">{{ (target.confidence * 100).toFixed(1) }}%</span>
                </div>
                <div v-if="getDetectionTargets(row).length > 2" class="more-targets">
                  +{{ getDetectionTargets(row).length - 2 }}个
                </div>
              </div>
            </div>
            <span v-else class="text-muted">无检测目标</span>
          </template>
        </el-table-column>

        <!-- 图片列 -->
        <el-table-column label="图片" width="120">
          <template #default="{ row }">
            <div v-if="getEventImages(row).length > 0" class="image-column">
              <div 
                v-for="(image, index) in getEventImages(row).slice(0, 1)" 
                :key="index"
                class="thumbnail-container"
                @click.stop="openImagePreview(getEventImages(row), index)"
              >
                <img 
                  :src="getImageUrl(image.path)" 
                  :alt="image.title"
                  class="table-thumbnail"
                  @error="handleImageError"
                />
                <div class="image-overlay">
                  <el-icon class="preview-icon"><ZoomIn /></el-icon>
                </div>
              </div>
              <div v-if="getEventImages(row).length > 1" class="more-images">
                +{{ getEventImages(row).length - 1 }}
              </div>
            </div>
            <span v-else class="text-muted">无图片</span>
          </template>
        </el-table-column>

        <el-table-column prop="location" label="位置" min-width="120">
          <template #default="{ row }">
            <span v-if="row.location">{{ row.location }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>

        <!-- <el-table-column prop="confidence" label="置信度" width="80">
          <template #default="{ row }">
            <span v-if="row.confidence !== null">
              {{ (row.confidence * 100).toFixed(1) }}%
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column> -->

        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag
              :type="getStatusTagType(row.status)"
              size="small"
              effect="light"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="timestamp" label="发生时间" width="150">
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click.stop="showEventDetail(row)"
            >
              详情
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click.stop="handleSingleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[20, 50, 100, 200]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 事件详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="事件详情"
      width="1000px"
      :close-on-click-modal="false"
      :z-index="99999"
      append-to-body
      class="high-priority-dialog"
    >
      <div v-if="selectedEvent" class="event-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="事件ID">
            {{ selectedEvent.event_id }}
          </el-descriptions-item>
          <el-descriptions-item label="事件类型">
            <el-tag :type="getEventTypeTagType(selectedEvent.event_type)">
              {{ getEventTypeText(selectedEvent.event_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据源">
            <el-tag :type="getSourceTypeTagType(selectedEvent.source_type)">
              {{ selectedEvent.source_type.toUpperCase() }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="设备ID">
            {{ selectedEvent.device_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="设备SN">
            {{ selectedEvent.device_sn || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="设备名称">
            {{ selectedEvent.device_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="通道">
            {{ selectedEvent.channel_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="算法引擎ID">
            {{ selectedEvent.engine_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="算法引擎名称">
            {{ selectedEvent.engine_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="位置">
            {{ selectedEvent.location || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            <span v-if="selectedEvent.confidence !== null">
              {{ (selectedEvent.confidence * 100).toFixed(2) }}%
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(selectedEvent.status)">
              {{ getStatusText(selectedEvent.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="已处理">
            <el-tag :type="selectedEvent.processed ? 'success' : 'warning'">
              {{ selectedEvent.processed ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="发生时间">
            {{ formatDateTime(selectedEvent.timestamp) }}
          </el-descriptions-item>
          <el-descriptions-item label="接收时间">
            {{ formatDateTime(selectedEvent.created_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 检测目标详情 -->
        <div class="detail-section" v-if="getDetectionTargets(selectedEvent).length > 0">
          <h4>检测目标 ({{ getDetectionTargets(selectedEvent).length }}个)</h4>
          <el-table :data="getDetectionTargets(selectedEvent)" style="width: 100%">
            <el-table-column prop="class_name" label="目标类型" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ row.class_name || '未知' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="120">
              <template #default="{ row }">
                <span>{{ (row.confidence * 100).toFixed(2) }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="边界框" min-width="200">
              <template #default="{ row }">
                <span v-if="row.bbox">
                  ({{ row.bbox.x1 }}, {{ row.bbox.y1 }}) - ({{ row.bbox.x2 }}, {{ row.bbox.y2 }})
                </span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="class_id" label="类别ID" width="120">
              <template #default="{ row }">
                <span>{{ row.class_id || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="detail-section" v-if="selectedEvent.metadata">
          <h4>元数据</h4>
          <el-input
            v-model="formattedMetadata"
            type="textarea"
            :rows="6"
            readonly
          />
        </div>

        <div class="detail-section" v-if="selectedEvent.normalized_data">
          <h4>标准化数据</h4>
          <el-input
            v-model="formattedNormalizedData"
            type="textarea"
            :rows="8"
            readonly
          />
        </div>

        <div class="detail-section" v-if="selectedEvent.algorithm_data">
          <h4>算法数据</h4>
          <el-input
            v-model="formattedAlgorithmData"
            type="textarea"
            :rows="8"
            readonly
          />
        </div>

        <div class="detail-section" v-if="selectedEvent.original_data">
          <h4>原始数据</h4>
          <el-input
            v-model="formattedOriginalData"
            type="textarea"
            :rows="10"
            readonly
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="imagePreviewVisible"
      title="图片预览"
      width="900px"
      :close-on-click-modal="false"
      :z-index="100000"
      append-to-body
      class="image-preview-dialog high-priority-dialog"
    >
      <div v-if="previewImages.length > 0" class="image-preview-content">
        <!-- 图片导航 -->
        <div class="image-nav" v-if="previewImages.length > 1">
          <el-button-group>
            <el-button 
              v-for="(img, index) in previewImages" 
              :key="index"
              :type="index === currentImageIndex ? 'primary' : 'default'"
              size="small"
              @click="currentImageIndex = index"
            >
              {{ img.title }}
            </el-button>
          </el-button-group>
        </div>

        <!-- 当前图片 -->
        <div class="current-image-container">
          <div class="image-header">
            <h3>{{ previewImages[currentImageIndex]?.title }}</h3>
            <div class="image-actions">
              <el-button 
                type="primary" 
                size="small"
                @click="openOriginalImage"
                v-if="hasOriginalImage(previewImages[currentImageIndex])"
              >
                <el-icon><FullScreen /></el-icon>
                查看原图
              </el-button>
            </div>
          </div>
          <div class="image-display">
            <img 
              :src="getImageUrl(previewImages[currentImageIndex]?.path)" 
              :alt="previewImages[currentImageIndex]?.title"
              class="preview-image"
              @error="handleImageError"
            />
          </div>
          <div class="image-info">
            <span>文件大小: {{ formatFileSize(previewImages[currentImageIndex]?.file_size) }}</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="imagePreviewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 原图预览对话框 -->
    <el-dialog
      v-model="originalImageVisible"
      title="原图预览"
      width="40vw"
      :close-on-click-modal="false"
      :z-index="100001"
      append-to-body
      class="original-image-dialog high-priority-dialog"
    >
      <div class="original-image-content">
        <img 
          :src="originalImageUrl" 
          alt="原图"
          class="original-image"
          @error="handleImageError"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, Download, Notification, CircleCheck, Clock, Warning,
  Search, RefreshLeft, Delete, ZoomIn, FullScreen
} from '@element-plus/icons-vue'
import { dataListenerApi } from '../../api/dataListener'

// 响应式数据
const loading = ref(false)
const events = ref([])
const listenerConfigs = ref([])
const selectedEvent = ref(null)
const detailDialogVisible = ref(false)
const autoRefresh = ref(false)
const autoRefreshTimer = ref(null)
const dateRange = ref([])
const selectedEvents = ref([])
const imagePreviewVisible = ref(false)
const previewImages = ref([])
const currentImageIndex = ref(0)
const originalImageVisible = ref(false)
const originalImageUrl = ref('')
const device_name_mappings = ref({})
const engine_name_mappings = ref({})

// 过滤器
const filters = reactive({
  config_id: '',
  event_type: '',
  device_id: '',
  device_sn: '',
  channel_id: '',
  engine_id: '',
  start_time: null,
  end_time: null
})

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 实时统计
const realtimeStats = ref({
  total_today: 0,
  processed_today: 0,
  recent_1hour: 0,
  alarms_today: 0
})

// 计算属性
const formattedMetadata = computed(() => {
  if (!selectedEvent.value?.metadata) return ''
  return JSON.stringify(selectedEvent.value.metadata, null, 2)
})

const formattedNormalizedData = computed(() => {
  if (!selectedEvent.value?.normalized_data) return ''
  return JSON.stringify(selectedEvent.value.normalized_data, null, 2)
})

const formattedOriginalData = computed(() => {
  if (!selectedEvent.value?.original_data) return ''
  return JSON.stringify(selectedEvent.value.original_data, null, 2)
})

const formattedAlgorithmData = computed(() => {
  if (!selectedEvent.value?.algorithm_data) return ''
  return JSON.stringify(selectedEvent.value.algorithm_data, null, 2)
})

// 方法
const loadData = async () => {
  try {
    loading.value = true
    
    const params = {
      page: pagination.page,
      size: pagination.size,
      ...filters
    }

    const response = await dataListenerApi.getEvents(params)
    
    if (response.data.status === 'success') {
      events.value = response.data.data.events
      pagination.total = response.data.data.pagination.total
    }
  } catch (error) {
    // console.error('加载事件数据失败:', error)
    ElMessage.error('加载事件数据失败')
  } finally {
    loading.value = false
  }
}

const loadListenerConfigs = async () => {
  try {
    const response = await dataListenerApi.getConfigs({ size: 100 })
    if (response.data.status === 'success') {
      listenerConfigs.value = response.data.data.configs
    }
    const deviceEngineNameMappingsResponse = await dataListenerApi.getDeviceEngineNameMappings()
    if (deviceEngineNameMappingsResponse.data.status === 'success') {
      device_name_mappings.value = deviceEngineNameMappingsResponse.data.data.device_name_mappings || {}
      engine_name_mappings.value = deviceEngineNameMappingsResponse.data.data.engine_name_mappings || {}
    }
  } catch (error) {
    // console.error('加载监听器配置失败:', error)
  }
}

const loadRealtimeStats = async () => {
  try {
    // 模拟实时统计数据
    const now = new Date()
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000)

    const [todayResponse, recentResponse] = await Promise.all([
      dataListenerApi.getEvents({
        start_time: todayStart.toISOString(),
        size: 1
      }),
      dataListenerApi.getEvents({
        start_time: oneHourAgo.toISOString(),
        size: 1
      })
    ])

    realtimeStats.value = {
      total_today: todayResponse.data.data?.pagination?.total || 0,
      processed_today: Math.floor((todayResponse.data.data?.pagination?.total || 0) * 0.85),
      recent_1hour: recentResponse.data.data?.pagination?.total || 0,
      alarms_today: Math.floor((todayResponse.data.data?.pagination?.total || 0) * 0.1)
    }
  } catch (error) {
    // console.error('加载统计数据失败:', error)
  }
}

const refreshData = async () => {
  await Promise.all([
    loadData(),
    loadRealtimeStats()
  ])
}

const handleDateChange = (dates) => {
  if (dates && dates.length === 2) {
    filters.start_time = dates[0].toISOString()
    filters.end_time = dates[1].toISOString()
  } else {
    filters.start_time = null
    filters.end_time = null
  }
  loadData()
}

const clearFilters = () => {
  Object.assign(filters, {
    config_id: '',
    event_type: '',
    device_id: '',
    device_sn: '',
    channel_id: '',
    engine_id: '',
    start_time: null,
    end_time: null
  })
  dateRange.value = []
  pagination.page = 1
  loadData()
}

const showEventDetail = async (event) => {
  try {
    const response = await dataListenerApi.getEvent(event.event_id)
    if (response.data.status === 'success') {
      selectedEvent.value = response.data.data
      detailDialogVisible.value = true
    }
  } catch (error) {
    // console.error('获取事件详情失败:', error)
    ElMessage.error('获取事件详情失败')
  }
}

const toggleAutoRefresh = (enabled) => {
  if (enabled) {
    autoRefreshTimer.value = setInterval(() => {
      refreshData()
    }, 30000) // 30秒刷新一次
  } else {
    if (autoRefreshTimer.value) {
      clearInterval(autoRefreshTimer.value)
      autoRefreshTimer.value = null
    }
  }
}

const exportEvents = () => {
  // 导出功能实现
  ElMessage.info('导出功能开发中...')
}

// 选择变化处理
const handleSelectionChange = (selection) => {
  selectedEvents.value = selection
}

// 单个删除
const handleSingleDelete = async (event) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除事件 ${event.event_id.slice(-8)} 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await dataListenerApi.deleteEvent(event.event_id)
    ElMessage.success('删除成功')
    await loadData() // 重新加载数据
  } catch (error) {
    if (error !== 'cancel') {
      // console.error('删除事件失败:', error)
      ElMessage.error('删除事件失败')
    }
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedEvents.value.length === 0) {
    ElMessage.warning('请选择要删除的事件')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedEvents.value.length} 个事件吗？此操作不可恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const eventIds = selectedEvents.value.map(event => event.event_id)
    await dataListenerApi.batchDeleteEvents(eventIds)
    ElMessage.success(`成功删除 ${eventIds.length} 个事件`)
    selectedEvents.value = []
    await loadData() // 重新加载数据
  } catch (error) {
    if (error !== 'cancel') {
      // console.error('批量删除事件失败:', error)
      ElMessage.error('批量删除事件失败')
    }
  }
}

// 获取检测目标
const getDetectionTargets = (event) => {
  if (!event) return []
  
  // 从normalized_data.targets获取
  if (event.normalized_data?.targets?.length > 0) {
    return event.normalized_data.targets
  }
  
  // 从algorithm_data获取
  if (event.algorithm_data?.detections?.length > 0) {
    return event.algorithm_data.detections
  }
  
  // 从原始数据获取
  if (event.original_data?.detections?.length > 0) {
    return event.original_data.detections
  }
  
  if (event.original_data?.nn_output?.detections?.length > 0) {
    return event.original_data.nn_output.detections
  }
  
  return []
}

// 获取事件图片
const getEventImages = (event) => {
  if (!event?.normalized_data?.processed_images) return []
  
  const images = []
  const processedImages = event.normalized_data.processed_images
  
  Object.keys(processedImages).forEach(fieldName => {
    const imageData = processedImages[fieldName]
    
    if (imageData.error) return // 跳过处理失败的图片
    
    // 优先显示缩略图
    if (imageData.thumbnail_path) {
      images.push({
        title: `${fieldName} - 缩略图`,
        path: imageData.thumbnail_path,
        file_size: imageData.thumbnail_size || 0,
        original_path: imageData.original_path
      })
    }
    
    // 如果没有缩略图，显示原图
    if (!imageData.thumbnail_path && imageData.original_path) {
      images.push({
        title: `${fieldName} - 图片`,
        path: imageData.original_path,
        file_size: imageData.file_size || 0,
        original_path: imageData.original_path
      })
    }
  })
  
  return images
}

// 打开图片预览
const openImagePreview = (images, startIndex = 0) => {
  previewImages.value = images
  currentImageIndex.value = startIndex
  imagePreviewVisible.value = true
}

// 打开原图
const openOriginalImage = () => {
  const currentImage = previewImages.value[currentImageIndex.value]
  if (currentImage && currentImage.original_path) {
    originalImageUrl.value = getImageUrl(currentImage.original_path)
    originalImageVisible.value = true
  }
}

// 检查是否有原图
const hasOriginalImage = (image) => {
  return image && image.original_path && image.original_path !== image.path
}

// 获取图片URL
const getImageUrl = (imagePath) => {
  // 使用后端提供的图片服务API
  return `/api/v2/data-listeners/images/${encodeURIComponent(imagePath)}`
}

// 处理图片加载错误
const handleImageError = (event) => {
  event.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjRjVGNUY1Ii8+CjxwYXRoIGQ9Ik0yMCAzMEMyNS41MjI5IDMwIDMwIDI1LjUyMjkgMzAgMjBDMzAgMTQuNDc3MSAyNS41MjI5IDEwIDIwIDEwQzE0LjQ3NzEgMTAgMTAgMTQuNDc3MSAxMCAyMEMxMCAyNS41MjI5IDE0LjQ3NzEgMzAgMjAgMzBaIiBmaWxsPSIjQ0NDQ0NDIi8+CjxwYXRoIGQ9Ik0yMCAyMi41QzIxLjM4MDcgMjIuNSAyMi41IDIxLjM4MDcgMjIuNSAyMEMyMi41IDE4LjYxOTMgMjEuMzgwNyAxNy41IDIwIDE3LjVDMTguNjE5MyAxNy41IDE3LjUgMTguNjE5MyAxNy41IDIwQzE3LjUgMjEuMzgwNyAxOC42MTkzIDIyLjUgMjAgMjIuNVoiIGZpbGw9IiNGRkZGRkYiLz4KPC9zdmc+'
  event.target.style.opacity = '0.5'
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 工具函数
const getEventTypeTagType = (type) => {
  const typeMap = {
    detection: 'primary',
    alarm: 'danger',
    status: 'info',
    command: 'warning',
    heartbeat: 'success',
    other: ''
  }
  return typeMap[type] || ''
}

const getEventTypeText = (type) => {
  const typeMap = {
    detection: '检测',
    alarm: '报警',
    status: '状态',
    command: '命令',
    heartbeat: '心跳',
    other: '其他'
  }
  return typeMap[type] || type
}

const getSourceTypeTagType = (type) => {
  const typeMap = {
    tcp: 'primary',
    mqtt: 'success',
    http: 'warning',
    // websocket: 'info',
    // sdk: 'danger'
  }
  return typeMap[type] || 'info'
}

const getStatusTagType = (status) => {
  const statusMap = {
    pending: 'warning',
    processed: 'success',
    failed: 'danger',
    ignored: 'info'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusMap = {
    pending: '待处理',
    processed: '已处理',
    failed: '处理失败',
    ignored: '已忽略'
  }
  return statusMap[status] || status
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 生命周期
onMounted(async () => {
  await Promise.all([
    loadData(),
    loadListenerConfigs(),
    loadRealtimeStats()
  ])
})

onUnmounted(() => {
  if (autoRefreshTimer.value) {
    clearInterval(autoRefreshTimer.value)
  }
})
</script>

<style scoped>
.data-events {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-content h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.header-content p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  align-items: center;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  font-size: 32px;
  margin-right: 16px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 20px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.auto-refresh {
  margin-left: auto;
}

.table-card {
  min-height: 500px;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background-color: #f5f7fa;
}

.text-muted {
  color: #999;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.event-detail {
  max-height: 600px;
  overflow-y: auto;
}

.detail-section {
  margin-top: 20px;
}

.detail-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

/* 检测目标样式 */
.detection-targets {
  font-size: 12px;
}

.targets-summary {
  margin-bottom: 4px;
}

.targets-detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.target-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.target-name {
  color: #333;
  font-weight: 500;
}

.target-confidence {
  color: #409eff;
  font-weight: 600;
}

.more-targets {
  color: #909399;
  font-style: italic;
  text-align: center;
  margin-top: 2px;
}

/* 图片展示样式 */
.images-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 10px;
}

.image-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.image-header {
  padding: 12px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.image-header h5 {
  margin: 0 0 4px 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.image-info {
  font-size: 12px;
  color: #666;
}

.image-content {
  padding: 12px;
  text-align: center;
}

.event-image {
  max-width: 100%;
  max-height: 200px;
  cursor: pointer;
  border-radius: 4px;
  transition: transform 0.2s ease;
}

.event-image:hover {
  transform: scale(1.02);
}

/* 表格中的图片列样式 */
.image-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.thumbnail-container {
  position: relative;
  width: 60px;
  height: 45px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid #e4e7ed;
}

.table-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s ease;
}

.thumbnail-container:hover .table-thumbnail {
  transform: scale(1.1);
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.thumbnail-container:hover .image-overlay {
  opacity: 1;
}

.preview-icon {
  color: white;
  font-size: 16px;
}

.more-images {
  font-size: 12px;
  color: #666;
  text-align: center;
}

/* 图片预览对话框样式 */
.image-preview-dialog .el-dialog__body {
  padding: 20px;
}

.image-preview-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.image-nav {
  display: flex;
  justify-content: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.current-image-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.image-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.image-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.image-actions {
  display: flex;
  gap: 8px;
}

.image-display {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
}

.preview-image {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.image-info {
  text-align: center;
  color: #666;
  font-size: 14px;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

/* 原图预览对话框样式 */
.original-image-dialog .el-dialog__body {
  padding: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  background-color: #000;
}

.original-image-content {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

.original-image {
  max-width: 100%;
  max-height: 80vh;
  object-fit: contain;
  cursor: zoom-in;
}

.image-preview {
  text-align: center;
}

/* 高优先级对话框样式 - 确保不被菜单和头部遮挡 */
.high-priority-dialog {
  z-index: 99999 !important;
}

.image-preview-dialog {
  z-index: 100000 !important;
}

.original-image-dialog {
  z-index: 100001 !important;
}
</style> 