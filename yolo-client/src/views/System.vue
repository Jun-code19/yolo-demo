<template>
  <div class="system-container">
    <div class="page-header">
      <!-- <h2>系统管理</h2> -->
      <el-tabs v-model="activeTab" class="system-tabs">
        <el-tab-pane label="系统状态" name="status"></el-tab-pane>
        <el-tab-pane label="系统日志" name="logs"></el-tab-pane>
        <el-tab-pane label="检测日志" name="detection_logs"></el-tab-pane>
      </el-tabs>
    </div>

    <!-- 系统状态面板 -->
    <div v-if="activeTab === 'status'">
      <div class="status-header">
        <el-button type="primary" @click="refreshStatus">
          <el-icon>
            <Refresh />
          </el-icon>
          刷新
        </el-button>
      </div>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-card class="status-card">
            <template #header>
              <div class="card-header">
                <span>系统资源</span>
                <el-tag type="success" v-if="systemStatus.status === 'normal'">运行正常</el-tag>
                <el-tag type="warning" v-else-if="systemStatus.status === 'warning'">需要注意</el-tag>
                <el-tag type="danger" v-else>异常</el-tag>
              </div>
            </template>

            <div class="resource-list">
              <div class="resource-item">
                <div class="item-header">
                  <span>CPU 使用率</span>
                  <span>{{ systemStatus.cpu }}%</span>
                </div>
                <el-progress :percentage="systemStatus.cpu" :status="getCpuStatus(systemStatus.cpu)" />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>内存使用率</span>
                  <span>{{ systemStatus.memory }}%</span>
                </div>
                <el-progress :percentage="systemStatus.memory" :status="getMemoryStatus(systemStatus.memory)" />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>GPU 使用率</span>
                  <span>{{ systemStatus.gpu }}%</span>
                </div>
                <el-progress :percentage="systemStatus.gpu" :status="getGpuStatus(systemStatus.gpu)" />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>磁盘使用率</span>
                  <span>{{ systemStatus.disk }}%</span>
                </div>
                <el-progress :percentage="systemStatus.disk" :status="getDiskStatus(systemStatus.disk)" />
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card class="status-card">
            <template #header>
              <div class="card-header">
                <span>服务状态</span>
                <el-button-group>
                  <el-button type="primary" link @click="startAllServices">
                    启动全部
                  </el-button>
                  <el-button type="danger" link @click="stopAllServices">
                    停止全部
                  </el-button>
                </el-button-group>
              </div>
            </template>

            <div class="service-list">
              <div v-for="service in services" :key="service.name" class="service-item">
                <div class="service-info">
                  <el-icon :class="['status-icon', service.status]">
                    <CircleCheck v-if="service.status === 'running'" />
                    <Warning v-else-if="service.status === 'stopped'" />
                    <Loading v-else />
                  </el-icon>
                  <span class="service-name">{{ service.name }}</span>
                  <el-tag size="small" :type="getServiceTagType(service.status)">
                    {{ getServiceStatusText(service.status) }}
                  </el-tag>
                </div>
                <div class="service-actions">
                  <el-button-group>
                    <el-button type="primary" link :disabled="service.status === 'running'"
                      @click="startService(service)">
                      启动
                    </el-button>
                    <el-button type="danger" link :disabled="service.status === 'stopped'"
                      @click="stopService(service)">
                      停止
                    </el-button>
                  </el-button-group>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" class="mt-20">
        <el-col :span="24">
          <el-card class="status-card">
            <template #header>
              <div class="card-header">
                <span>实时日志</span>
                <el-button type="primary" link @click="clearLogs">
                  清空日志
                </el-button>
              </div>
            </template>

            <el-table :data="logs" style="width: 100%" height="300">
              <el-table-column prop="time" label="时间" width="180" />
              <el-table-column prop="level" label="级别" width="100">
                <template #default="{ row }">
                  <el-tag :type="getLogLevelType(row.level)" size="small">
                    {{ row.level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="内容" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
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
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Refresh, CircleCheck, Warning, Loading, Search, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import systemLogApi from '@/api/system_log'

// 选项卡控制
const activeTab = ref('status')

// 系统状态数据
const systemStatus = ref({
  status: 'normal',
  cpu: 0,
  memory: 0,
  gpu: 0,
  disk: 0
})

// 服务列表
const services = ref([
  { name: '检测服务', status: 'stopped' },
  { name: '数据服务', status: 'stopped' },
  { name: '数据库服务', status: 'stopped' },
  { name: '网页服务', status: 'stopped' }
])

// 系统日志
const logs = ref([])

// 检测日志
const detectionLogs = ref([])

// 刷新状态
const refreshStatus = async () => {
  try {
    const response = await systemLogApi.getSystemStatus()

    if (response.status === 200) {
      // 更新系统状态
      systemStatus.value = {
        status: response.data.status,
        cpu: response.data.cpu,
        memory: response.data.memory,
        gpu: response.data.gpu,
        disk: response.data.disk
      }

      // 更新服务状态
      if (response.data.services && response.data.services.length > 0) {
        services.value = response.data.services
      }

      // 更新日志
      if (response.data.logs && response.data.logs.length > 0) {
        logs.value = response.data.logs
      }

      // 不显示通知，避免频繁刷新时打扰用户
    } else {
      // console.error('获取系统状态失败:', response)
    }
  } catch (error) {
    // console.error('获取系统状态失败:', error)
    ElMessage.error('获取系统状态失败，请检查网络连接')
  }
}

// 资源状态判断
const getCpuStatus = (value) => value > 90 ? 'exception' : value > 70 ? 'warning' : 'success'
const getMemoryStatus = (value) => value > 90 ? 'exception' : value > 80 ? 'warning' : 'success'
const getGpuStatus = (value) => value > 90 ? 'exception' : value > 70 ? 'warning' : 'success'
const getDiskStatus = (value) => value > 90 ? 'exception' : value > 80 ? 'warning' : 'success'

// 服务状态文本
const getServiceStatusText = (status) => {
  const statusMap = {
    running: '运行中',
    stopped: '已停止',
    starting: '启动中',
    stopping: '停止中'
  }
  return statusMap[status]
}

// 服务状态标签类型
const getServiceTagType = (status) => {
  const typeMap = {
    running: 'success',
    stopped: 'danger',
    starting: 'warning',
    stopping: 'warning'
  }
  return typeMap[status]
}

// 日志级别标签类型
const getLogLevelType = (level) => {
  const typeMap = {
    INFO: 'info',
    WARNING: 'warning',
    ERROR: 'danger',
    DEBUG: ''
  }
  return typeMap[level]
}

// 服务操作
const startService = async (service) => {
  try {
    service.status = 'starting'

    // 根据服务名称确定服务ID
    let serviceId = ''
    if (service.name === '检测服务') {
      serviceId = 'detect'
    } else if (service.name === '数据服务') {
      serviceId = 'data'
    } else if (service.name === '数据库服务') {
      serviceId = 'database'
    } else if (service.name === '网页服务') {
      serviceId = 'frontend'
    }

    if (!serviceId) {
      throw new Error('未知服务')
    }

    // 调用API启动服务
    const response = await systemLogApi.controlService(serviceId, 'start')

    if (response.status === 200) {
      service.status = 'running'
      addLog('INFO', `服务 ${service.name} 已启动`)
      ElMessage.success(`${service.name}已启动`)
    } else {
      service.status = 'stopped'
      addLog('ERROR', `服务 ${service.name} 启动失败`)
      ElMessage.error(`${service.name}启动失败`)
    }
  } catch (error) {
    // console.error('启动服务失败:', error)
    service.status = 'stopped'
    addLog('ERROR', `服务 ${service.name} 启动失败: ${error.message}`)
    ElMessage.error(`${service.name}启动失败: ${error.response?.data?.detail || error.message}`)
  }
}

const stopService = async (service) => {
  try {
    service.status = 'stopping'

    // 根据服务名称确定服务ID
    let serviceId = ''
    if (service.name === '检测服务') {
      serviceId = 'detect'
    } else if (service.name === '数据服务') {
      serviceId = 'data'
    } else if (service.name === '数据库服务') {
      serviceId = 'database'
    } else if (service.name === '网页服务') {
      serviceId = 'frontend'
    }

    if (!serviceId) {
      throw new Error('未知服务')
    }

    // 调用API停止服务
    const response = await systemLogApi.controlService(serviceId, 'stop')

    if (response.status === 200) {
      service.status = 'stopped'
      addLog('INFO', `服务 ${service.name} 已停止`)
      ElMessage.success(`${service.name}已停止`)
    } else {
      service.status = 'running'
      addLog('ERROR', `服务 ${service.name} 停止失败`)
      ElMessage.error(`${service.name}停止失败`)
    }
  } catch (error) {
    // console.error('停止服务失败:', error)
    service.status = 'running'
    addLog('ERROR', `服务 ${service.name} 停止失败: ${error.message}`)
    ElMessage.error(`${service.name}停止失败: ${error.response?.data?.detail || error.message}`)
  }
}

const startAllServices = async () => {
  for (const service of services.value) {
    if (service.status === 'stopped') {
      await startService(service)
    }
  }
}

const stopAllServices = async () => {
  const result = await ElMessageBox.confirm(
    '确定要停止所有服务吗？这可能会影响正在进行的检测任务。',
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).catch(() => false)

  if (result) {
    for (const service of services.value) {
      if (service.status === 'running') {
        await stopService(service)
      }
    }
  }
}

// 日志操作
const addLog = (level, message) => {
  logs.value.unshift({
    time: new Date().toLocaleString(),
    level,
    message
  })
}

const clearLogs = async () => {
  const result = await ElMessageBox.confirm(
    '确定要清空所有日志吗？',
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).catch(() => false)

  if (result) {
    logs.value = []
    addLog('INFO', '日志已清空')
  }
}

// 定时刷新
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

// 操作类型映射
const actionTypes = {
  device: {
    label: '设备管理',
    options: {
      'create_device': '创建设备',
      'update_device': '更新设备',
      'delete_device': '删除设备',
      'device_status_change': '设备状态变更'
    }
  },
  detectionconfig: {
    label: '检测管理',
    options: {
      'create_detection_config': '创建检测配置',
      'update_detection_config': '更新检测配置',
      'delete_detection_config': '删除检测配置',
      'start_detection': '启动检测任务',
      'stop_detection': '停止检测任务'
    }
  },
  detectionevent: {
    label: '检测事件',
    options: {
      'create_detection_event': '创建检测事件',
      'update_detection_event': '更新检测事件',
      'delete_detection_event': '删除检测事件',
      'export_detection_events': '导出检测事件'
    }
  },
  model: {
    label: '模型管理',
    options: {
      'upload_model': '上传模型',
      'delete_model': '删除模型',
      'toggle_model': '启用/禁用模型',
      'update_model_config': '更新模型配置'
    }
  },
  crowd: {
    label: '人群分析',
    options: {
      'create_crowd_task': '创建人群分析任务',
      'update_crowd_task': '更新人群分析任务',
      'delete_crowd_task': '删除人群分析任务',
      'export_crowd_results': '导出人群分析结果',
      'pause_crowd_task': '暂停人群分析任务',
      'resume_crowd_task': '恢复人群分析任务',
      'run_crowd_task': '运行人群分析任务'
    }
  },
  push: {
    label: '推送管理',
    options: {
      'create_data_push': '创建推送配置',
      'update_data_push': '更新推送配置',
      'delete_data_push': '删除推送配置',
      'toggle_data_push': '启用/禁用推送配置'
    }
  },
  system: {
    label: '系统管理',
    options: {
      'clear_system_logs': '清除系统日志',
      'export_system_logs': '导出系统日志',
      'update_system_config': '更新系统配置',
      'restart_service': '重启服务'
    }
  },
  user: {
    label: '用户管理',
    options: {
      'create_user': '创建用户',
      'update_user': '更新用户',
      'delete_user': '删除用户',
      'update_user_permission': '更新用户权限',
      'change_password': '修改密码',
      'login': '用户登录',
      'logout': '用户登出'
    }
  },
  data: {
    label: '数据管理',
    options: {
      'export_data': '导出数据',
      'import_data': '导入数据',
      'backup_system': '系统备份',
      'restore_system': '系统恢复'
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

// 获取操作类型标签样式
const getActionTypeTag = (type) => {
  const typeTagMap = {
    // 设备管理
    'create_device': 'success',
    'update_device': 'warning',
    'delete_device': 'danger',
    'device_status_change': 'info',
    // 检测管理
    'create_detection_config': 'success',
    'update_detection_config': 'warning',
    'delete_detection_config': 'danger',
    'toggle_detection_config': 'info',
    'create_detection_event': 'success',
    'update_detection_event': 'warning',
    'delete_detection_event': 'danger',
    'export_detection_events': 'success',
    // 模型管理
    'upload_model': 'success',
    'delete_model': 'danger',
    'toggle_model': 'info',
    'update_model_config': 'warning',
    // 人群分析
    'create_crowd_task': 'success',
    'update_crowd_task': 'warning',
    'delete_crowd_task': 'danger',
    'export_crowd_results': 'success',
    // 推送管理
    'create_push_config': 'success',
    'update_push_config': 'warning',
    'delete_push_config': 'danger',
    'toggle_push_config': 'info',
    // 系统管理
    'clear_system_logs': 'success',
    'export_system_logs': 'success',
    'update_system_config': 'warning',
    'restart_service': 'warning',
    // 用户管理
    'create_user': 'success',
    'update_user': 'warning',
    'delete_user': 'danger',
    'update_user_permission': 'info',
    'change_password': 'success',
    'login': 'success',
    'logout': 'success',
    // 数据管理
    'export_data': 'success',
    'import_data': 'success',
    'backup_system': 'success',
    'restore_system': 'success'
  }
  return typeTagMap[type] || ''
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
  refreshStatus()
  refreshInterval = setInterval(refreshStatus, 5000)

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

.status-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 20px;
}

.status-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.resource-item {
  background-color: #f8fafc;
  padding: 16px;
  border-radius: 8px;
}

.item-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 14px;
}

.service-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.service-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background-color: #f8fafc;
  border-radius: 8px;
}

.service-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-icon {
  font-size: 18px;
}

.status-icon.running {
  color: #67c23a;
}

.status-icon.stopped {
  color: #f56c6c;
}

.status-icon.starting,
.status-icon.stopping {
  color: #e6a23c;
}

.service-name {
  font-size: 14px;
  color: #2c3e50;
}

.mt-20 {
  margin-top: 20px;
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