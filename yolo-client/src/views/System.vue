<template>
  <div class="system-container">
    <div class="page-header">
      <h2>系统状态</h2>
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
              <span>系统日志</span>
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
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Refresh, CircleCheck, Warning, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

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

onMounted(() => {
  refreshStatus()
  refreshInterval = setInterval(refreshStatus, 5000)
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
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
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
</style> 