<template>
  <div class="system-container">
    <div class="page-header">
      <!-- <h2>系统管理</h2> -->
      <el-tabs v-model="activeTab" class="system-tabs">
        <el-tab-pane label="系统状态" name="status"></el-tab-pane>
        <el-tab-pane label="系统日志" name="logs"></el-tab-pane>
      </el-tabs>
    </div>

    <!-- 系统状态面板 -->
    <div v-if="activeTab === 'status'">
      <div class="status-header">
        <el-button type="primary" @click="refreshStatus">
          <el-icon><Refresh /></el-icon>
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
                <el-progress 
                  :percentage="systemStatus.cpu" 
                  :status="getCpuStatus(systemStatus.cpu)"
                />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>内存使用率</span>
                  <span>{{ systemStatus.memory }}%</span>
                </div>
                <el-progress 
                  :percentage="systemStatus.memory" 
                  :status="getMemoryStatus(systemStatus.memory)"
                />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>GPU 使用率</span>
                  <span>{{ systemStatus.gpu }}%</span>
                </div>
                <el-progress 
                  :percentage="systemStatus.gpu" 
                  :status="getGpuStatus(systemStatus.gpu)"
                />
              </div>

              <div class="resource-item">
                <div class="item-header">
                  <span>磁盘使用率</span>
                  <span>{{ systemStatus.disk }}%</span>
                </div>
                <el-progress 
                  :percentage="systemStatus.disk" 
                  :status="getDiskStatus(systemStatus.disk)"
                />
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
                    <el-button 
                      type="primary" 
                      link 
                      :disabled="service.status === 'running'"
                      @click="startService(service)"
                    >
                      启动
                    </el-button>
                    <el-button 
                      type="danger" 
                      link 
                      :disabled="service.status === 'stopped'"
                      @click="stopService(service)"
                    >
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
      <div class="filter-options">
        <el-input
          v-model="logFilters.userId"
          placeholder="用户ID"
          clearable
          style="width: 180px; margin-right: 10px"
        />
        <el-select
          v-model="logFilters.actionType"
          placeholder="操作类型"
          clearable
          style="width: 180px; margin-right: 10px"
        >
          <el-option label="设备创建" value="create_device" />
          <el-option label="设备更新" value="update_device" />
          <el-option label="设备删除" value="delete_device" />
          <el-option label="用户登录" value="login" />
          <el-option label="创建管理员" value="create_admin" />
          <el-option label="更新管理员" value="update_admin" />
          <el-option label="删除管理员" value="delete_admin" />
          <el-option label="修改密码" value="update_password" />
          <el-option label="更新个人资料" value="update_profile" />
          <el-option label="上传模型" value="upload_model" />
          <el-option label="删除模型" value="delete_model" />
          <el-option label="激活模型" value="activate_model" />
          <el-option label="停用模型" value="deactivate_model" />
        </el-select>
        <el-button type="primary" @click="loadLogData">
          <el-icon><Search /></el-icon>筛选
        </el-button>
      </div>

      <!-- 日志列表 -->
      <el-card class="log-list">
        <el-table :data="sysLogs" style="width: 100%" v-loading="logsLoading">
          <el-table-column prop="log_id" label="日志ID" width="80" />
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
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="prev, pager, next, jumper, ->, total, sizes"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Refresh, CircleCheck, Warning, Loading, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import deviceApi from '@/api/device'

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
  { name: 'WebSocket服务', status: 'stopped' },
  { name: '数据库服务', status: 'stopped' },
  { name: '缓存服务', status: 'stopped' }
])

// 系统日志
const logs = ref([])

// 刷新状态
const refreshStatus = async () => {
  try {
    // 这里添加实际的API调用
    // const response = await fetch('/api/system/status')
    // const data = await response.json()
    
    // 模拟数据
    systemStatus.value = {
      status: 'normal',
      cpu: Math.floor(Math.random() * 100),
      memory: Math.floor(Math.random() * 100),
      gpu: Math.floor(Math.random() * 100),
      disk: Math.floor(Math.random() * 100)
    }
    
    ElMessage.success('状态已更新')
  } catch (error) {
    ElMessage.error('获取系统状态失败')
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
    // 这里添加实际的API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    service.status = 'running'
    addLog('INFO', `服务 ${service.name} 已启动`)
  } catch (error) {
    service.status = 'stopped'
    addLog('ERROR', `服务 ${service.name} 启动失败`)
  }
}

const stopService = async (service) => {
  try {
    service.status = 'stopping'
    // 这里添加实际的API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    service.status = 'stopped'
    addLog('INFO', `服务 ${service.name} 已停止`)
  } catch (error) {
    service.status = 'running'
    addLog('ERROR', `服务 ${service.name} 停止失败`)
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

// 日志筛选条件
const logFilters = reactive({
  userId: '',
  actionType: ''
})

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
    
    const response = await deviceApi.getSyslogs(params)
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
  const typeMap = {
    'create_device': '设备创建',
    'update_device': '设备更新',
    'delete_device': '设备删除',
    'login': '用户登录',
    'create_admin': '创建管理员',
    'update_admin': '更新管理员',
    'delete_admin': '删除管理员',
    'update_password': '修改密码',
    'update_profile': '更新个人资料',
    'upload_model': '上传模型',
    'delete_model': '删除模型',
    'activate_model': '激活模型',
    'deactivate_model': '停用模型'
  }
  return typeMap[type] || type
}

// 获取操作类型标签样式
const getActionTypeTag = (type) => {
  const typeTagMap = {
    'create_device': 'success',
    'update_device': 'warning',
    'delete_device': 'danger',
    'login': 'info',
    'create_admin': 'success',
    'update_admin': 'warning',
    'delete_admin': 'danger',
    'update_password': 'warning',
    'update_profile': 'warning',
    'upload_model': 'success',
    'delete_model': 'danger',
    'activate_model': 'success',
    'deactivate_model': 'warning'
  }
  return typeTagMap[type] || ''
}

// 页面初始化
onMounted(() => {
  refreshStatus()
  refreshInterval = setInterval(refreshStatus, 5000)
  
  // 加载系统日志
  loadLogData()
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

.log-list {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}
</style> 