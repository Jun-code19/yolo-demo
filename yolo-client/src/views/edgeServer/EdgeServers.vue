<template>
  <div class="edge-servers-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>边缘AI设备管理</h2>
        <p class="header-desc">管理和监控您的边缘AI计算设备</p>
      </div>
      <div class="header-actions">
        <el-button 
          type="success" 
          size="default" 
          @click="refreshAllServers"
          :loading="loading"
          icon="Refresh"
        >
          刷新状态
        </el-button>
        <el-button type="primary" size="default" @click="showAddDialog" icon="Plus">
          添加设备
        </el-button>
      </div>
    </div>

    <!-- 服务器网格 -->
    <div class="servers-grid" v-loading="loading">
      <div 
        v-for="server in servers" 
        :key="server.id" 
        class="server-card"
        :class="{ 'online': server.status === 'online', 'offline': server.status === 'offline' }"
      >
        <!-- 服务器状态指示器 -->
        <div class="status-indicator" :class="server.status"></div>
        
        <!-- 服务器基本信息 -->
        <div class="server-header">
          <div class="server-name">{{ server.name }}</div>
          <el-tag 
            :type="getStatusType(server.status)" 
            size="small"
            :loading="server.status === 'checking'"
          >
            {{ getStatusText(server.status) }}
          </el-tag>
        </div>

        <div class="server-info">
          <div class="info-item">
            <span class="label">IP地址:</span>
            <span class="value">{{ server.ip_address }}:{{ server.port }}</span>
          </div>
          <div class="info-item" v-if="server.description">
            <span class="label">描述:</span>
            <span class="value">{{ server.description }}</span>
          </div>
          <div class="info-item" v-if="server.last_checked">
            <span class="label">最后检查:</span>
            <span class="value">{{ formatTime(server.last_checked) }}</span>
          </div>
        </div>

        <!-- 系统信息 -->
        <div class="system-info" v-if="server.version_info || server.system_info">
          <div v-if="server.device_info" class="info-item">
            <span class="label">设备序列号:</span>
            <span class="value">{{ server.device_info.deviceSN || 'N/A' }}</span>
          </div>
          <div v-if="server.version_info" class="info-item">
            <span class="label">硬件版本:</span>
            <span class="value">{{ server.version_info.KernelVersion || 'N/A' }}</span>
          </div>
          <div v-if="server.version_info" class="info-item">
            <span class="label">软件版本:</span>
            <span class="value">{{ server.version_info.FileSystemVersion || 'N/A' }}</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="server-actions">
          <el-button-group>
            <el-button 
              size="small" 
              type="primary"
              @click="openServerDashboard(server)"
              :disabled="server.status !== 'online'"
            >
              <el-icon><Monitor /></el-icon>
              监控面板
            </el-button>
            <el-button 
              size="small" 
              type="success"
              @click="openServerLogin(server)"
              :disabled="server.status !== 'online'"
            >
              <el-icon><Link /></el-icon>
              登录
            </el-button>
          </el-button-group>
          
          <el-dropdown @command="handleCommand" trigger="click">
            <el-button size="small" type="info">
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :command="{ action: 'edit', server }">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-dropdown-item>
                <el-dropdown-item :command="{ action: 'test', server }">
                  <el-icon><Connection /></el-icon>
                  测试连接
                </el-dropdown-item>
                <el-dropdown-item :command="{ action: 'delete', server }" divided>
                  <el-icon><Delete /></el-icon>
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="servers.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无服务器">
          <el-button type="primary" @click="showAddDialog">添加第一台服务器</el-button>
        </el-empty>
      </div>
    </div>

    <!-- 添加/编辑服务器对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'add' ? '添加服务器' : '编辑服务器'"
      width="500px"
      @close="resetDialog"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="服务器名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入服务器名称" />
        </el-form-item>
        <el-form-item label="IP地址" prop="ip">
          <el-input v-model="form.ip" placeholder="请输入IP地址" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input 
            v-model="form.description" 
            type="textarea" 
            placeholder="请输入服务器描述（可选）"
            :rows="3"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="info" @click="testConnection" :loading="testing">
            测试连接
          </el-button>
          <el-button type="primary" @click="saveServer" :loading="saving">
            {{ dialogMode === 'add' ? '添加' : '更新' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Plus, 
  Refresh, 
  Monitor, 
  Link, 
  Edit, 
  Delete, 
  Connection,
  MoreFilled
} from '@element-plus/icons-vue'
import edgeServerAPI from '@/api/edge-server'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const servers = ref([])
const dialogVisible = ref(false)
const dialogMode = ref('add') // 'add' | 'edit'
const currentEditingServer = ref(null)
const testing = ref(false)
const saving = ref(false)

// 表单数据
const form = reactive({
  name: '',
  ip: '',
  port: 80,
  description: ''
})

const formRef = ref()

// 表单验证规则
const formRules = {
  name: [
    { required: true, message: '请输入服务器名称', trigger: 'blur' },
    { min: 1, max: 100, message: '名称长度在 1 到 100 个字符', trigger: 'blur' }
  ],
  ip: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    { 
      pattern: /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/, 
      message: '请输入正确的IP地址格式', 
      trigger: 'blur' 
    }
  ],
  port: [
    { required: true, message: '请输入端口号', trigger: 'blur' },
    { type: 'number', min: 1, max: 65535, message: '端口号范围为 1-65535', trigger: 'blur' }
  ]
}

// 方法
const loadServers = async () => {
  loading.value = true
  try {
    const response = await edgeServerAPI.getServerList()
    servers.value = response.items || []
  } catch (error) {
    // console.error('加载服务器列表失败:', error)
    ElMessage.error('加载服务器列表失败')
  } finally {
    loading.value = false
  }
}

const refreshAllServers = async () => {
  if (servers.value.length === 0) return
  
  loading.value = true
  try {
    const promises = servers.value.map(async (server) => {
      server.status = 'checking'
      try {
        await edgeServerAPI.testAndUpdateServerStatus(server.id, server.ip_address, server.port)
      } catch (error) {
        // console.error(`更新服务器 ${server.name} 状态失败:`, error)
      }
    })
    
    await Promise.all(promises)
    await loadServers() // 重新加载获取最新状态
    ElMessage.success('状态刷新完成')
  } catch (error) {
    ElMessage.error('刷新状态失败')
  } finally {
    loading.value = false
  }
}

const getStatusType = (status) => {
  switch (status) {
    case 'online': return 'success'
    case 'offline': return 'danger'
    case 'checking': return 'warning'
    default: return 'info'
  }
}

const getStatusText = (status) => {
  switch (status) {
    case 'online': return '在线'
    case 'offline': return '离线'
    case 'checking': return '检查中'
    default: return '未知'
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return '从未'
  return new Date(timeStr).toLocaleString()
}

const formatMemory = (memory) => {
  if (!memory) return 'N/A'
  if (typeof memory === 'object' && memory.total) {
    const total = Math.round(memory.total / 1024 / 1024) // Convert to MB
    const used = Math.round((memory.total - memory.available) / 1024 / 1024)
    return `${used}/${total}MB`
  }
  return 'N/A'
}

const showAddDialog = () => {
  dialogMode.value = 'add'
  currentEditingServer.value = null
  resetForm()
  dialogVisible.value = true
}

const editServer = (server) => {
  dialogMode.value = 'edit'
  currentEditingServer.value = server
  Object.assign(form, {
    name: server.name,
    ip: server.ip_address,
    port: server.port,
    description: server.description || ''
  })
  dialogVisible.value = true
}

const testConnection = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validateField(['ip', 'port'])
    testing.value = true
    
    const serverAPI = edgeServerAPI.createServerAPI(form.ip, form.port)
    const result = await serverAPI.testConnection()
    
    if (result.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(`连接测试失败: ${result.error}`)
    }
  } catch (error) {
    if (typeof error === 'string') {
      // 表单验证错误
      return
    }
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

const saveServer = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    saving.value = true
    
    if (dialogMode.value === 'add') {
      await edgeServerAPI.addServer(form)
    } else {
      await edgeServerAPI.updateServer(currentEditingServer.value.id, form)
    }
    
    dialogVisible.value = false
    await loadServers()
  } catch (error) {
    if (error === false) {
      // 表单验证失败
      return
    }
    // console.error('保存服务器失败:', error)
  } finally {
    saving.value = false
  }
}

const deleteServer = async (server) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除服务器 "${server.name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await edgeServerAPI.removeServer(server.id)
    await loadServers()
  } catch (error) {
    if (error !== 'cancel') {
      // console.error('删除服务器失败:', error)
    }
  }
}

const openServerDashboard = (server) => {
  if (server.status !== 'online') {
    ElMessage.warning('服务器未在线，无法打开监控面板')
    return
  }
  
  router.push({
    name: 'EdgeServerDetail',
    params: { serverId: server.id }
  })
}

const openServerLogin = (server) => {
  const loginUrl = `http://${server.ip_address}:${server.port}`
  window.open(loginUrl, '_blank')
}

const handleCommand = ({ action, server }) => {
  switch (action) {
    case 'edit':
      editServer(server)
      break
    case 'test':
      testServerConnection(server)
      break
    case 'delete':
      deleteServer(server)
      break
  }
}

const testServerConnection = async (server) => {
  try {
    const result = await edgeServerAPI.testAndUpdateServerStatus(server.id, server.ip_address, server.port)
    if (result.success) {
      ElMessage.success('连接测试成功')
      await loadServers()
    } else {
      ElMessage.error(`连接测试失败: ${result.error}`)
    }
  } catch (error) {
    ElMessage.error('连接测试失败')
  }
}

const resetForm = () => {
  Object.assign(form, {
    name: '',
    ip: '',
    port: 80,
    description: ''
  })
  if (formRef.value) {
    formRef.value.resetFields()
  }
}

const resetDialog = () => {
  resetForm()
  currentEditingServer.value = null
}

// 页面初始化
onMounted(() => {
  loadServers()
})
</script>

<style scoped>
.edge-servers-container {
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
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-left h2 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.header-desc {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* 服务器网格 */
.servers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.server-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: relative;
  transition: all 0.3s ease;
  border-left: 4px solid #e4e7ed;
}

.server-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.server-card.online {
  border-left-color: #67c23a;
}

.server-card.offline {
  border-left-color: #f56c6c;
}

.status-indicator {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #e4e7ed;
}

.status-indicator.online {
  background-color: #67c23a;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.2);
}

.status-indicator.offline {
  background-color: #f56c6c;
  box-shadow: 0 0 0 2px rgba(245, 108, 108, 0.2);
}

.status-indicator.checking {
  background-color: #e6a23c;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.server-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.server-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.server-info {
  margin-bottom: 16px;
}

.system-info {
  margin-bottom: 20px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-item .label {
  color: #909399;
  font-weight: 500;
}

.info-item .value {
  color: #606266;
  font-family: 'Monaco', 'Consolas', monospace;
}

.server-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .edge-servers-container {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .servers-grid {
    grid-template-columns: 1fr;
  }
  
  /* .stats-cards {
    grid-template-columns: 1fr;
  } */
}

/* 按钮组样式优化 */
:deep(.el-button-group) {
  display: flex;
}

:deep(.el-button-group .el-button) {
  margin: 0;
}
</style>