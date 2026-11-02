<template>
  <div class="system-container">
    <div class="page-header">
      <!-- <h2>系统管理</h2> -->
      <el-tabs v-model="activeTab" class="system-tabs">
        <el-tab-pane label="系统状态" name="status"></el-tab-pane>
        <el-tab-pane label="系统日志" name="logs"></el-tab-pane>
        <el-tab-pane label="检测日志" name="detection_logs"></el-tab-pane>
        <el-tab-pane label="地图配置" name="map_config"></el-tab-pane>
        <el-tab-pane label="设备监控" name="device_monitor"></el-tab-pane>
      </el-tabs>
    </div>

    <!-- 系统状态面板 -->
    <div v-if="activeTab === 'status'" class="status-panel" v-loading="statusLoading">
      <div class="status-header">
        <span class="status-hint">每 60 秒自动刷新 · 当前时间以服务端为准</span>
        <el-button type="primary" @click="refreshStatus">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <el-card class="status-card info-card">
        <template #header>
          <div class="card-header">
            <span>主机信息</span>
            <el-tag type="success" v-if="systemStatus.status === 'normal'">运行正常</el-tag>
            <el-tag type="warning" v-else-if="systemStatus.status === 'warning'">需要注意</el-tag>
            <el-tag type="danger" v-else>异常</el-tag>
          </div>
        </template>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="主机名">{{ systemInfo.hostname || '—' }}</el-descriptions-item>
          <el-descriptions-item label="应用">
            {{ systemInfo.app_name }} {{ systemInfo.app_version }}
          </el-descriptions-item>
          <el-descriptions-item label="Python">{{ systemInfo.python_version || '—' }}</el-descriptions-item>
          <el-descriptions-item label="当前时间">{{ systemInfo.current_time || '—' }}</el-descriptions-item>
          <el-descriptions-item label="开机时间">{{ systemInfo.boot_time || '—' }}</el-descriptions-item>
          <el-descriptions-item label="运行时长">{{ systemInfo.uptime_text || '—' }}</el-descriptions-item>
          <el-descriptions-item label="系统" :span="2">{{ systemInfo.platform || '—' }}</el-descriptions-item>
          <el-descriptions-item label="架构">{{ systemInfo.architecture || '—' }}</el-descriptions-item>
          <el-descriptions-item label="启用检测任务">{{ detectionInfo.enabled_configs }} 个</el-descriptions-item>
          <el-descriptions-item label="激活模型">{{ detectionInfo.active_models }} 个</el-descriptions-item>
          <el-descriptions-item label="GPU">
            <template v-if="showGpu">{{ systemStatus.gpu.name || '已检测到' }}</template>
            <template v-else>未检测到 NVIDIA GPU</template>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="status-card">
        <template #header>
          <div class="card-header">
            <span>系统资源</span>
          </div>
        </template>
        <el-row :gutter="20" class="resource-grid">
          <el-col :xs="24" :sm="12" :lg="8">
            <div class="resource-item">
              <div class="item-header">
                <span>CPU</span>
                <span>{{ formatPercent(systemStatus.cpu.percent) }}%</span>
              </div>
              <el-progress
                :percentage="clampPercent(systemStatus.cpu.percent)"
                :status="getCpuStatus(systemStatus.cpu.percent)"
              />
              <div class="item-footer">
                <span>逻辑核 {{ systemStatus.cpu.total }}{{ systemStatus.cpu.physical ? ` / 物理核 ${systemStatus.cpu.physical}` : '' }}</span>
                <span>约占用 {{ systemStatus.cpu.used }} 核</span>
              </div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="8">
            <div class="resource-item">
              <div class="item-header">
                <span>内存</span>
                <span>{{ formatPercent(systemStatus.memory.percent) }}%</span>
              </div>
              <el-progress
                :percentage="clampPercent(systemStatus.memory.percent)"
                :status="getMemoryStatus(systemStatus.memory.percent)"
              />
              <div class="item-footer">
                <span>已用 {{ systemStatus.memory.used }} / {{ systemStatus.memory.total }} GB</span>
                <span>可用 {{ systemStatus.memory.available ?? '—' }} GB</span>
              </div>
            </div>
          </el-col>
          <el-col v-if="showGpu" :xs="24" :sm="12" :lg="8">
            <div class="resource-item">
              <div class="item-header">
                <span>GPU{{ systemStatus.gpu.name ? ` · ${systemStatus.gpu.name}` : '' }}</span>
                <span>{{ formatPercent(systemStatus.gpu.percent) }}%</span>
              </div>
              <el-progress
                :percentage="clampPercent(systemStatus.gpu.percent)"
                :status="getGpuStatus(systemStatus.gpu.percent)"
              />
              <div class="item-footer">
                <span>显存 {{ systemStatus.gpu.used }} / {{ systemStatus.gpu.total }} GB</span>
                <span v-if="gpuDevices.length > 1">共 {{ gpuDevices.length }} 张卡</span>
              </div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="8">
            <div class="resource-item">
              <div class="item-header">
                <span>系统盘</span>
                <span>{{ formatPercent(systemStatus.disk.percent) }}%</span>
              </div>
              <el-progress
                :percentage="clampPercent(systemStatus.disk.percent)"
                :status="getDiskStatus(systemStatus.disk.percent)"
              />
              <div class="item-footer">
                <span class="path-text">{{ systemStatus.disk.path || '—' }}</span>
                <span>{{ systemStatus.disk.used }} / {{ systemStatus.disk.total }} GB</span>
              </div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="8">
            <div class="resource-item">
              <div class="item-header">
                <span>应用目录盘</span>
                <span>{{ formatPercent(dataStorage.percent) }}%</span>
              </div>
              <el-progress
                :percentage="clampPercent(dataStorage.percent)"
                :status="getDiskStatus(dataStorage.percent)"
              />
              <div class="item-footer">
                <span class="path-text" :title="dataStorage.path">{{ dataStorage.path || '—' }}</span>
                <span>{{ dataStorage.used }} / {{ dataStorage.total }} GB</span>
              </div>
            </div>
          </el-col>
        </el-row>

        <div v-if="gpuDevices.length > 1" class="gpu-list">
          <div v-for="gpu in gpuDevices" :key="gpu.id" class="gpu-item">
            <div class="item-header">
              <span>#{{ gpu.id }} {{ gpu.name }}</span>
              <span>{{ formatPercent(gpu.percent) }}%</span>
            </div>
            <el-progress :percentage="clampPercent(gpu.percent)" :status="getGpuStatus(gpu.percent)" />
            <div class="item-footer">
              <span>显存 {{ gpu.memory_used }} / {{ gpu.memory_total }} GB</span>
              <span v-if="gpu.temperature != null">温度 {{ gpu.temperature }}°C</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 系统日志面板 -->
    <div v-if="activeTab === 'logs'">
      <div class="logs-panel">
        <!-- 筛选条件 -->
        <el-card class="filter-card">
          <el-form :inline="true" :model="logFilters" class="filter-form">
            <el-form-item label="时间范围">
              <el-date-picker v-model="logFilters.dateRange" type="daterange" range-separator="至"
                start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="操作类型">
              <el-select v-model="logFilters.actionType" placeholder="请选择操作类型" clearable
                style="width: 180px; margin-right: 10px">
                <el-option-group v-for="(group, key) in actionTypes" :key="key" :label="group.label">
                  <el-option v-for="(label, value) in group.options" :key="value" :label="label" :value="value">
                    <div class="model-option">
                      <span class="model-name">{{ label }}</span>
                      <span class="model-desc">{{ value }}</span>
                    </div>
                  </el-option>
                </el-option-group>
              </el-select>
              <el-input v-model="logFilters.actionType" placeholder="请输入自定义操作类型" style="width: 180px; margin-right: 10px"></el-input>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="resetFilter">重置</el-button>
            </el-form-item>
            <el-form-item class="action-buttons">
              <el-button type="primary" @click="handleExport">
                <el-icon>
                  <Download />
                </el-icon>导出日志
              </el-button>
              <el-button type="danger" @click="handleClear">
                <el-icon>
                  <Delete />
                </el-icon>清除日志
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 日志列表 -->
        <el-card class="log-list">
          <el-table :data="sysLogs" style="width: 100%" v-loading="logsLoading">
            <!-- <el-table-column prop="log_id" label="日志ID" width="80" /> -->
            <el-table-column prop="user_id" label="用户ID" min-width="120" />
            <el-table-column prop="action_type" label="操作类型" min-width="120">
              <template #default="{ row }">
                <el-tag :type="getActionTypeTag(row.action_type)">
                  {{ getActionTypeText(row.action_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="target_id" label="目标ID" min-width="120" />
            <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
            <el-table-column prop="log_time" label="操作时间" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.log_time) }}
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination">
            <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="total"
              :page-sizes="[10, 20, 50, 100]" layout="prev, pager, next, jumper, ->, total, sizes"
              @size-change="handleSizeChange" @current-change="handleCurrentChange" />
          </div>
        </el-card>
      </div>
    </div>

    <!-- 检测日志面板 -->
    <div v-if="activeTab === 'detection_logs'">
      <div class="logs-panel">
        <!-- 筛选条件 -->
        <el-card class="filter-card">
          <el-form :inline="true" class="filter-form">
            <el-form-item label="时间范围">
              <el-date-picker v-model="detectionLogFilters.dateRange" type="daterange" range-separator="至"
                start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="操作类型">
              <el-select v-model="detectionLogFilters.operation" placeholder="请选择操作类型" clearable
                style="width: 180px; margin-right: 10px">
                <el-option label="启动" value="start"></el-option>
                <el-option label="停止" value="stop"></el-option>
                <el-option label="自动启动" value="auto_start"></el-option>
                <el-option label="自动停止" value="auto_stop"></el-option>
                <el-option label="定时设置" value="schedule"></el-option>
                <el-option label="取消定时" value="unschedule"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="detectionLogFilters.status" placeholder="请选择状态" clearable
                style="width: 120px; margin-right: 10px">
                <el-option label="成功" value="success"></el-option>
                <el-option label="失败" value="failed"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleDetectionLogSearch">查询</el-button>
              <el-button @click="resetDetectionLogFilter">重置</el-button>
            </el-form-item>
            <el-form-item class="action-buttons">
              <el-button type="primary" @click="handleExportDetectionLogs">
                <el-icon>
                  <Download />
                </el-icon>导出日志
              </el-button>
              <el-button type="danger" @click="handleClearDetectionLogs">
                <el-icon>
                  <Delete />
                </el-icon>清除日志
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 日志列表 -->
        <el-card class="log-list">
          <el-table :data="detectionLogs" style="width: 100%" v-loading="detectionLogsLoading">
            <el-table-column prop="device_name" label="设备名称" min-width="120" />
            <el-table-column prop="config_name" label="检测配置" min-width="120" />
            <el-table-column prop="operation" label="操作类型" min-width="100">
              <template #default="{ row }">
                <el-tag :type="getOperationTypeTag(row.operation)">
                  {{ getOperationTypeText(row.operation) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
                  {{ row.status === 'success' ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="详情" min-width="200" show-overflow-tooltip />
            <el-table-column prop="username" label="执行用户" min-width="100" />
            <el-table-column prop="created_at" label="操作时间" min-width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination">
            <el-pagination v-model:current-page="detectionLogCurrentPage" v-model:page-size="detectionLogPageSize"
              :total="detectionLogTotal" :page-sizes="[10, 20, 50, 100]"
              layout="prev, pager, next, jumper, ->, total, sizes" @size-change="handleDetectionLogSizeChange"
              @current-change="handleDetectionLogCurrentChange" />
          </div>
        </el-card>
      </div>
    </div>

    <!-- 设备监控配置 -->
    <div v-if="activeTab === 'device_monitor'" class="integrations-panel">
      <el-card>
        <template #header>
          <div class="card-header">
            <div>
              <div class="panel-title">设备在线监控</div>
              <div class="panel-desc">配置 RTSP/TCP/HTTP 探活策略；NVR 通道建议优先 RTSP</div>
            </div>
          </div>
        </template>
        <DeviceMonitorConfig />
      </el-card>
    </div>

    <!-- 地图配置 -->
    <div v-if="activeTab === 'map_config'" class="integrations-panel">
      <DashboardMapConfig />
    </div>

    <!-- 清除日志对话框 -->
    <el-dialog v-model="clearDialogVisible" title="清除系统日志" width="400px">
      <el-form :model="clearForm" label-width="120px">
        <el-form-item label="清除天数">
          <el-input-number v-model="clearForm.days" :min="1" :max="365" :step="1" step-strictly />
        </el-form-item>
        <el-form-item>
          <span class="warning-text">注意：此操作将永久删除指定天数前的所有日志记录，且不可恢复！</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="clearDialogVisible = false">取消</el-button>
          <el-button type="danger" @click="confirmClear" :loading="clearing">
            确认清除
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 清除检测日志对话框 -->
    <el-dialog v-model="clearDetectionLogDialogVisible" title="清除检测日志" width="400px">
      <el-form :model="clearDetectionLogForm" label-width="120px">
        <el-form-item label="清除天数">
          <el-input-number v-model="clearDetectionLogForm.days" :min="1" :max="365" :step="1" step-strictly />
        </el-form-item>
        <el-form-item>
          <span class="warning-text">注意：此操作将永久删除指定天数前的所有检测日志记录，且不可恢复！</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="clearDetectionLogDialogVisible = false">取消</el-button>
          <el-button type="danger" @click="confirmClearDetectionLog" :loading="clearingDetectionLog">
            确认清除
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import systemLogApi from '@/api/system_log'
import DashboardMapConfig from '@/components/DashboardMapConfig.vue'
import DeviceMonitorConfig from '@/components/DeviceMonitorConfig.vue'

const route = useRoute()

// 选项卡控制
const activeTab = ref('status')

const syncTabFromRoute = () => {
  const tab = route.query.tab
  if (tab === 'map_config' || tab === 'integrations') {
    activeTab.value = 'map_config'
  } else if (tab === 'device_monitor') {
    activeTab.value = 'device_monitor'
  }
}

watch(() => route.query.tab, syncTabFromRoute)

const defaultDisk = () => ({ path: '', percent: 0, total: 0, used: 0, free: 0 })

const statusLoading = ref(false)
const systemStatus = ref({
  status: 'normal',
  cpu: { percent: 0, total: 0, physical: 0, used: 0 },
  memory: { percent: 0, total: 0, used: 0, available: 0 },
  gpu: { percent: 0, total: 0, used: 0, name: '', available: false, devices: [] },
  disk: defaultDisk()
})
const systemInfo = ref({
  hostname: '',
  platform: '',
  architecture: '',
  python_version: '',
  app_name: 'yolo-demo',
  app_version: '',
  current_time: '',
  boot_time: '',
  uptime_text: ''
})
const dataStorage = ref(defaultDisk())
const detectionInfo = ref({ enabled_configs: 0, active_models: 0 })

const showGpu = computed(() => {
  const g = systemStatus.value.gpu || {}
  return !!(g.available || (g.total || 0) > 0 || (g.percent || 0) > 0)
})
const gpuDevices = computed(() => systemStatus.value.gpu?.devices || [])

const clampPercent = (value) => {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.min(100, Math.max(0, Math.round(n)))
}
const formatPercent = (value) => {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Number.isInteger(n) ? n : Number(n.toFixed(1))
}

const refreshStatus = async () => {
  statusLoading.value = true
  try {
    const response = await systemLogApi.getSystemStatus()
    if (response.status !== 200) return
    const data = response.data || {}
    systemStatus.value = {
      status: data.status || 'normal',
      cpu: { percent: 0, total: 0, physical: 0, used: 0, ...(data.cpu || {}) },
      memory: { percent: 0, total: 0, used: 0, available: 0, ...(data.memory || {}) },
      gpu: {
        percent: 0,
        total: 0,
        used: 0,
        name: '',
        available: false,
        devices: [],
        ...(data.gpu || {})
      },
      disk: { ...defaultDisk(), ...(data.disk || {}) }
    }
    systemInfo.value = {
      hostname: '',
      platform: '',
      architecture: '',
      python_version: '',
      app_name: 'yolo-demo',
      app_version: '',
      current_time: '',
      boot_time: '',
      uptime_text: '',
      ...(data.system || {})
    }
    dataStorage.value = { ...defaultDisk(), ...(data.data_storage || {}) }
    detectionInfo.value = {
      enabled_configs: data.detection?.enabled_configs || 0,
      active_models: data.detection?.active_models || 0
    }
  } catch (error) {
    ElMessage.error('获取系统状态失败，请检查网络连接')
  } finally {
    statusLoading.value = false
  }
}

const getCpuStatus = (value) => value > 90 ? 'exception' : value > 70 ? 'warning' : 'success'
const getMemoryStatus = (value) => value > 90 ? 'exception' : value > 80 ? 'warning' : 'success'
const getGpuStatus = (value) => value > 90 ? 'exception' : value > 70 ? 'warning' : 'success'
const getDiskStatus = (value) => value > 90 ? 'exception' : value > 80 ? 'warning' : 'success'

let refreshInterval

// =========================
// 系统日志部分（从SystemLogs.vue集成）
// =========================

// 日志数据
const logsLoading = ref(false)
const sysLogs = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const clearDialogVisible = ref(false)
const clearing = ref(false)
const clearForm = reactive({
  days: 30
})

// 日志筛选条件
const logFilters = reactive({
  dateRange: [],
  actionType: '',
  userId: ''
})

// 操作类型映射（与后端 log_action 实际写入对齐）
const actionTypes = {
  device: {
    label: '设备管理',
    options: {
      create_device: '创建设备',
      update_device: '更新设备',
      delete_device: '删除设备',
      device_status_change: '设备状态变更',
      import_devices: '导入设备',
      export_devices: '导出设备',
      export_device_template: '导出设备模板',
      create_device_group: '创建设备组',
      update_device_group: '更新设备组',
      delete_device_group: '删除设备组'
    }
  },
  detectionconfig: {
    label: '检测管理',
    options: {
      create_detection_config: '创建检测配置',
      update_detection_config: '更新检测配置',
      delete_detection_config: '删除检测配置',
      toggle_detection_active: '启用/禁用检测配置',
      toggle_detection_config: '启用/禁用检测配置',
      start_detection: '启动检测任务',
      stop_detection: '停止检测任务'
    }
  },
  detectionevent: {
    label: '检测事件',
    options: {
      create_detection_event: '创建检测事件',
      update_detection_event: '更新检测事件',
      delete_detection_event: '删除检测事件',
      batch_delete_detection_events: '批量删除检测事件',
      export_detection_events: '导出检测事件',
      cleanup_detection_events: '清理过期检测事件',
      cleanup_expired_events: '清理过期事件'
    }
  },
  model: {
    label: '模型管理',
    options: {
      upload_model: '上传模型',
      update_model: '更新模型',
      delete_model: '删除模型',
      activate_model: '启用模型',
      deactivate_model: '禁用模型',
      toggle_model: '启用/禁用模型',
      update_model_config: '更新模型配置'
    }
  },
  crowd: {
    label: '人群分析',
    options: {
      create_crowd_task: '创建人群分析任务',
      update_crowd_task: '更新人群分析任务',
      delete_crowd_task: '删除人群分析任务',
      export_crowd_results: '导出人群分析结果',
      pause_crowd_task: '暂停人群分析任务',
      resume_crowd_task: '恢复人群分析任务',
      run_crowd_task: '立即执行人群分析任务'
    }
  },
  push: {
    label: '推送管理',
    options: {
      create_data_push: '创建推送配置',
      update_data_push: '更新推送配置',
      delete_data_push: '删除推送配置',
      toggle_data_push: '启用/禁用推送配置',
      test_data_push: '测试推送配置',
      create_push_config: '创建推送配置',
      update_push_config: '更新推送配置',
      delete_push_config: '删除推送配置',
      toggle_push_config: '启用/禁用推送配置'
    }
  },
  smart: {
    label: '事件订阅',
    options: {
      create_smart_scheme: '创建事件订阅',
      update_smart_scheme: '更新事件订阅',
      delete_smart_scheme: '删除事件订阅',
      start_smart_scheme: '启动事件订阅',
      stop_smart_scheme: '停止事件订阅',
      restart_smart_scheme: '重启事件订阅',
      update_smart_event: '更新智能事件',
      delete_smart_event: '删除智能事件',
      batch_delete_events: '批量删除事件',
      batch_process_events: '批量处理事件',
      batch_ignore_events: '批量忽略事件',
      cleanup_smart_events: '清理过期智能事件'
    }
  },
  listener: {
    label: '数据监听',
    options: {
      create_listener_config: '创建监听配置',
      update_listener_config: '更新监听配置',
      delete_listener_config: '删除监听配置',
      start_listener: '启动监听',
      stop_listener: '停止监听',
      restart_listener: '重启监听',
      batch_start_listeners: '批量启动监听',
      batch_stop_listeners: '批量停止监听',
      update_external_event: '更新外部事件',
      delete_event: '删除外部事件',
      cleanup_external_events: '清理外部事件'
    }
  },
  alert: {
    label: '复合告警',
    options: {
      create_alert_rule: '创建告警规则',
      update_alert_rule: '更新告警规则',
      delete_alert_rule: '删除告警规则',
      evaluate_alert_rules: '手动评估告警规则'
    }
  },
  vlm: {
    label: 'VLM 巡检',
    options: {
      bootstrap_qwen_vlm: '注册 Qwen-VL 模型',
      create_vlm_model: '注册 VLM 模型',
      update_vlm_model: '更新 VLM 模型',
      delete_vlm_model: '删除 VLM 模型',
      update_vlm_api_key: '更新 VLM API Key',
      import_prompt_templates: '导入 Prompt 模板',
      create_prompt_template: '创建 Prompt 模板',
      update_prompt_template: '更新 Prompt 模板',
      delete_prompt_template: '删除 Prompt 模板',
      create_vlm_inspection: '创建 VLM 巡检任务',
      update_vlm_inspection: '更新 VLM 巡检任务',
      delete_vlm_inspection: '删除 VLM 巡检任务',
      pause_vlm_inspection: '暂停 VLM 巡检任务',
      resume_vlm_inspection: '恢复 VLM 巡检任务',
      run_vlm_inspection: '立即执行 VLM 巡检'
    }
  },
  edge: {
    label: '边缘服务器',
    options: {
      create_edge_server: '创建边缘服务器',
      update_edge_server: '更新边缘服务器',
      update_edge_server_status: '更新边缘服务器状态',
      delete_edge_server: '删除边缘服务器'
    }
  },
  system: {
    label: '系统管理',
    options: {
      clear_system_logs: '清除系统日志',
      export_system_logs: '导出系统日志',
      clear_detection_logs: '清除检测日志',
      export_detection_logs: '导出检测日志',
      update_system_config: '更新系统配置',
      restart_service: '重启服务'
    }
  },
  user: {
    label: '用户管理',
    options: {
      create_user: '创建用户',
      create_admin: '创建管理员',
      update_user: '更新用户',
      update_profile: '更新个人信息',
      delete_user: '删除用户',
      update_user_permission: '更新用户权限',
      change_password: '修改密码',
      login: '用户登录',
      logout: '用户登出'
    }
  },
  data: {
    label: '数据管理',
    options: {
      export_data: '导出数据',
      import_data: '导入数据',
      backup_system: '系统备份',
      restore_system: '系统恢复'
    }
  }
}

// 加载日志数据
const loadLogData = async () => {
  logsLoading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const params = {
      skip,
      limit: pageSize.value
    }

    if (logFilters.userId) {
      params.user_id = logFilters.userId
    }

    if (logFilters.actionType) {
      params.action_type = logFilters.actionType
    }

    if (logFilters.dateRange && logFilters.dateRange.length === 2) {
      params.start_date = logFilters.dateRange[0]
      params.end_date = logFilters.dateRange[1]
    }

    const response = await systemLogApi.getSyslogs(params)
    sysLogs.value = response.data.data
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('加载日志数据失败，请检查网络连接或服务器状态')
  } finally {
    logsLoading.value = false
  }
}

// 分页处理
const handleSizeChange = (val) => {
  pageSize.value = val
  loadLogData()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadLogData()
}

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN')
}

// 获取操作类型文本
const getActionTypeText = (type) => {
  for (const group of Object.values(actionTypes)) {
    if (group.options[type]) {
      return group.options[type]
    }
  }
  return type
}

// 获取操作类型标签样式（按动作语义推断，覆盖未单独列出的类型）
const getActionTypeTag = (type) => {
  const key = String(type || '')
  if (/^(delete|stop|clear|cleanup|deactivate|logout|pause|batch_delete|batch_stop|batch_ignore)/.test(key)) {
    return 'danger'
  }
  if (/^(update|change|toggle|restart|restore)/.test(key)) {
    return 'warning'
  }
  if (/^(create|upload|start|run|activate|resume|login|export|import|evaluate|bootstrap|test|backup|batch_start|batch_process)/.test(key)) {
    return 'success'
  }
  return 'info'
}

// 处理导出
const handleExport = async () => {
  try {
    const params = {}
    if (logFilters.dateRange && logFilters.dateRange.length === 2) {
      params.start_date = logFilters.dateRange[0]
      params.end_date = logFilters.dateRange[1]
    }
    if (logFilters.actionType) {
      params.action_type = logFilters.actionType
    }

    const response = await systemLogApi.exportSystemLogs(params)
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `system_logs_${new Date().toISOString().split('T')[0]}.json`
    link.click()
    window.URL.revokeObjectURL(url)

    ElMessage.success('日志导出成功')
  } catch (error) {
    ElMessage.error('日志导出失败')
  }
}

// 处理清除日志
const handleClear = () => {
  clearDialogVisible.value = true
}

// 确认清除日志
const confirmClear = async () => {
  try {
    clearing.value = true
    await systemLogApi.clearSystemLogs(clearForm.days)
    ElMessage.success('日志清除成功')
    clearDialogVisible.value = false
    loadLogData()
  } catch (error) {
    ElMessage.error('日志清除失败')
  } finally {
    clearing.value = false
  }
}

// 处理查询
const handleSearch = () => {
  currentPage.value = 1
  loadLogData()
}

// 重置筛选条件
const resetFilter = () => {
  logFilters.dateRange = []
  logFilters.actionType = ''
  logFilters.userId = ''
  handleSearch()
}

// 检测日志数据
const detectionLogs = ref([])
const detectionLogsLoading = ref(false)
const detectionLogCurrentPage = ref(1)
const detectionLogPageSize = ref(10)
const detectionLogTotal = ref(0)

// 检测日志筛选条件
const detectionLogFilters = reactive({
  dateRange: [],
  operation: '',
  status: '',
  device_id: '',
  config_id: ''
})

// 操作类型文本映射
const operationTypeMap = {
  'start': '启动',
  'stop': '停止',
  'auto_start': '自动启动',
  'auto_stop': '自动停止',
  'schedule': '定时设置',
  'unschedule': '取消定时'
}

// 获取操作类型文本
const getOperationTypeText = (type) => {
  return operationTypeMap[type] || type
}

// 获取操作类型标签颜色
const getOperationTypeTag = (type) => {
  const tagMap = {
    'start': 'success',
    'stop': 'danger',
    'auto_start': 'success',
    'auto_stop': 'warning',
    'schedule': 'info',
    'unschedule': 'info'
  }
  return tagMap[type] || 'info'
}

// 加载检测日志数据
const loadDetectionLogData = async () => {
  detectionLogsLoading.value = true
  try {
    const skip = (detectionLogCurrentPage.value - 1) * detectionLogPageSize.value
    const params = {
      skip,
      limit: detectionLogPageSize.value
    }

    if (detectionLogFilters.operation) {
      params.operation = detectionLogFilters.operation
    }

    if (detectionLogFilters.status) {
      params.status = detectionLogFilters.status
    }

    if (detectionLogFilters.device_id) {
      params.device_id = detectionLogFilters.device_id
    }

    if (detectionLogFilters.config_id) {
      params.config_id = detectionLogFilters.config_id
    }

    if (detectionLogFilters.dateRange && detectionLogFilters.dateRange.length === 2) {
      params.start_date = detectionLogFilters.dateRange[0]
      params.end_date = detectionLogFilters.dateRange[1]
    }

    const response = await systemLogApi.getDetectionLogs(params)
    detectionLogs.value = response.data.data
    detectionLogTotal.value = response.data.total
  } catch (error) {
    ElMessage.error('加载检测日志数据失败，请检查网络连接或服务器状态')
  } finally {
    detectionLogsLoading.value = false
  }
}

// 检测日志分页处理
const handleDetectionLogSizeChange = (val) => {
  detectionLogPageSize.value = val
  loadDetectionLogData()
}

const handleDetectionLogCurrentChange = (val) => {
  detectionLogCurrentPage.value = val
  loadDetectionLogData()
}

// 处理检测日志查询
const handleDetectionLogSearch = () => {
  detectionLogCurrentPage.value = 1
  loadDetectionLogData()
}

// 重置检测日志筛选条件
const resetDetectionLogFilter = () => {
  detectionLogFilters.dateRange = []
  detectionLogFilters.operation = ''
  detectionLogFilters.status = ''
  detectionLogFilters.device_id = ''
  detectionLogFilters.config_id = ''
  handleDetectionLogSearch()
}

// 检测日志清除相关
const clearDetectionLogDialogVisible = ref(false)
const clearingDetectionLog = ref(false)
const clearDetectionLogForm = reactive({
  days: 30
})

// 处理导出检测日志
const handleExportDetectionLogs = async () => {
  try {
    const params = {}
    if (detectionLogFilters.dateRange && detectionLogFilters.dateRange.length === 2) {
      params.start_date = detectionLogFilters.dateRange[0]
      params.end_date = detectionLogFilters.dateRange[1]
    }
    if (detectionLogFilters.operation) {
      params.operation = detectionLogFilters.operation
    }
    if (detectionLogFilters.status) {
      params.status = detectionLogFilters.status
    }
    if (detectionLogFilters.device_id) {
      params.device_id = detectionLogFilters.device_id
    }
    if (detectionLogFilters.config_id) {
      params.config_id = detectionLogFilters.config_id
    }

    const response = await systemLogApi.exportDetectionLogs(params)

    // 处理文件下载
    const blob = new Blob([response.data], {
      type: response.headers['content-type']
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `detection_logs_${new Date().toISOString().split('T')[0]}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('检测日志导出成功')
  } catch (error) {
    // console.error('导出检测日志失败:', error)
    ElMessage.error('检测日志导出失败')
  }
}

// 处理清除检测日志
const handleClearDetectionLogs = () => {
  clearDetectionLogDialogVisible.value = true
}

// 确认清除检测日志
const confirmClearDetectionLog = async () => {
  try {
    clearingDetectionLog.value = true
    await systemLogApi.clearDetectionLogs(clearDetectionLogForm.days)
    ElMessage.success('检测日志清除成功')
    clearDetectionLogDialogVisible.value = false
    loadDetectionLogData()
  } catch (error) {
    // console.error('清除检测日志失败:', error)
    ElMessage.error('检测日志清除失败')
  } finally {
    clearingDetectionLog.value = false
  }
}

// 页面初始化
onMounted(() => {
  syncTabFromRoute()
  refreshStatus()
  refreshInterval = setInterval(refreshStatus, 60000)

  // 加载系统日志
  loadLogData()

  // 加载检测日志
  loadDetectionLogData()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.system-container {
  padding: 20px;
}

.model-option {
  display: flex;
  flex-direction: column;
}

.model-name {
  /* font-weight: bold; */
  color: #303133;
  margin-bottom: 2px;
}

.model-desc {
  font-size: 12px;
  color: #909399;
}

.page-header {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 10px 0;
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
}

.system-tabs {
  margin-bottom: 10px;
}

.status-panel {
  margin-top: 4px;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}

.status-hint {
  color: #909399;
  font-size: 13px;
}

.status-card {
  margin-bottom: 24px;
}

.info-card :deep(.el-card__body) {
  padding-top: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.resource-grid {
  margin-top: 4px;
}

.resource-grid :deep(.el-col) {
  margin-bottom: 20px;
}

.resource-item,
.gpu-item {
  background-color: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  height: 100%;
  box-sizing: border-box;
}

.item-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 14px;
}

.item-footer {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.path-text {
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gpu-list {
  margin-top: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

/* 系统日志样式 */
.filter-options {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.filter-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.filter-card .el-form {
  margin-bottom: 0;
}

.filter-card .el-form-item {
  margin-bottom: 0;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.log-list {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.logs-panel {
  margin-top: 20px;
}

.integrations-panel {
  margin-top: 20px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.panel-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
  font-weight: normal;
}

.header-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.warning-text {
  color: #f56c6c;
  font-size: 14px;
}

.action-buttons {
  margin-left: auto;
}
</style> 