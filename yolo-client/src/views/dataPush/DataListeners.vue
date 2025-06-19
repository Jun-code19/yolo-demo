<template>
  <div class="data-listeners">
    <div class="page-header">
      <div class="header-content">
        <h1>数据监听器管理</h1>
        <p>管理第三方数据源监听器配置</p>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建监听器
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon">
                <el-icon color="#409EFF"><Monitor /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.configs?.total || 0 }}</div>
                <div class="stat-label">总监听器</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon">
                <el-icon color="#67C23A"><VideoPlay /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.runtime?.running_count || 0 }}</div>
                <div class="stat-label">运行中</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon">
                <el-icon color="#E6A23C"><Bell /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.events?.today || 0 }}</div>
                <div class="stat-label">今日事件</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon">
                <el-icon color="#F56C6C"><DataAnalysis /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.events?.total || 0 }}</div>
                <div class="stat-label">总事件数</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 过滤器 -->
    <el-card class="filter-card">
      <div class="filters">
        <el-select
          v-model="filters.listener_type"
          placeholder="监听器类型"
          clearable
          style="width: 150px"
          @change="loadData"
        >
          <el-option label="TCP" value="tcp" />
          <el-option label="MQTT" value="mqtt" />
          <el-option label="HTTP" value="http" />
        </el-select>

        <el-select
          v-model="filters.enabled"
          placeholder="启用状态"
          clearable
          style="width: 120px"
          @change="loadData"
        >
          <el-option label="已启用" :value="true" />
          <el-option label="已禁用" :value="false" />
        </el-select>

        <el-input
          v-model="searchText"
          placeholder="搜索监听器名称"
          style="width: 200px"
          @keyup.enter="loadData"
        >
          <template #append>
            <el-button @click="loadData">
              <el-icon><Search /></el-icon>
            </el-button>
          </template>
        </el-input>

        <div class="batch-actions">
          <el-button
            v-if="selectedIds.length > 0"
            type="success"
            @click="batchStart"
            :loading="batchLoading"
          >
            批量启动
          </el-button>
          <el-button
            v-if="selectedIds.length > 0"
            type="warning"
            @click="batchStop"
            :loading="batchLoading"
          >
            批量停止
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card">
      <el-table
        :data="configs"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="name" label="名称" width="120">
          <template #default="{ row }">
            <div class="name-cell">
              <span class="name">{{ row.name }}</span>
              <span class="description">{{ row.description }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="listener_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.listener_type)">
              {{ row.listener_type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag
                :type="row.enabled ? 'success' : 'info'"
                effect="light"
                size="small"
              >
                {{ row.enabled ? '已启用' : '已禁用' }}
              </el-tag>
              <el-tag
                v-if="row.runtime_status?.status"
                :type="getRuntimeStatusType(row.runtime_status.status)"
                effect="plain"
                size="small"
                style="margin-top: 2px;"
              >
                {{ getRuntimeStatusText(row.runtime_status.status) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="事件统计" width="150">
          <template #default="{ row }">
            <div class="stats-cell" v-if="row.runtime_status">
              <div>接收: {{ row.runtime_status.events_received || 0 }}</div>
              <div>处理: {{ row.runtime_status.events_processed || 0 }}</div>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="最后事件" min-width="150">
          <template #default="{ row }">
            <span v-if="row.runtime_status?.last_event_time">
              {{ formatDateTime(row.runtime_status.last_event_time) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="150">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button
                v-if="!row.enabled || row.runtime_status?.status !== 'running'"
                type="success"
                size="small"
                @click="startListener(row)"
                :loading="row.starting"
              >
                启动
              </el-button>
              <el-button
                v-else
                type="warning"
                size="small"
                @click="stopListener(row)"
                :loading="row.stopping"
              >
                停止
              </el-button>
              
              <el-button
                type="primary"
                size="small"
                @click="editConfig(row)"
              >
                编辑
              </el-button>
              
              <el-button
                type="danger"
                size="small"
                @click="deleteConfig(row)"
              >
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 配置对话框 -->
    <ListenerConfigDialog
      v-model="dialogVisible"
      :config="editingConfig"
      :templates="templates"
      @saved="handleConfigSaved"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, Plus, Monitor, VideoPlay, Bell, DataAnalysis, Search
} from '@element-plus/icons-vue'
import ListenerConfigDialog from '../../components/ListenerConfigDialog.vue'
import { dataListenerApi } from '../../api/dataListener'

// 响应式数据
const loading = ref(false)
const batchLoading = ref(false)
const dialogVisible = ref(false)
const configs = ref([])
const templates = ref({})
const editingConfig = ref(null)
const selectedIds = ref([])
const searchText = ref('')

// 过滤器
const filters = reactive({
  listener_type: '',
  enabled: null
})

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 统计数据
const stats = ref({
  configs: { total: 0 },
  events: { total: 0, today: 0 },
  runtime: { running_count: 0 }
})

// 计算属性
const selectedConfigs = computed(() => {
  return configs.value.filter(config => selectedIds.value.includes(config.config_id))
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
    
    if (searchText.value) {
      // 简单的名称搜索过滤
      params.search = searchText.value
    }

    const response = await dataListenerApi.getConfigs(params)
    
    if (response.data.status === 'success') {
      configs.value = response.data.data.configs
      pagination.total = response.data.data.pagination.total
    }
  } catch (error) {
    // console.error('加载数据失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await dataListenerApi.getStats()
    if (response.data.status === 'success') {
      stats.value = response.data.data
    }
  } catch (error) {
    // console.error('加载统计数据失败:', error)
  }
}

const refreshData = async () => {
  await Promise.all([
    loadData(),
    loadStats()
  ])
}

const showCreateDialog = () => {
  editingConfig.value = null
  dialogVisible.value = true
}

const editConfig = (config) => {
  editingConfig.value = config
  dialogVisible.value = true
}

const startListener = async (config) => {
  try {
    config.starting = true
    
    const response = await dataListenerApi.startListener(config.config_id)
    
    if (response.data.status === 'success') {
      ElMessage.success('监听器启动成功')
      await refreshData()
    } else {
      ElMessage.error(response.data.message || '启动失败')
    }
  } catch (error) {
    // console.error('启动监听器失败:', error)
    ElMessage.error('启动监听器失败')
  } finally {
    config.starting = false
  }
}

const stopListener = async (config) => {
  try {
    config.stopping = true
    
    const response = await dataListenerApi.stopListener(config.config_id)
    
    if (response.data.status === 'success') {
      ElMessage.success('监听器停止成功')
      await refreshData()
    } else {
      ElMessage.error(response.data.message || '停止失败')
    }
  } catch (error) {
    // console.error('停止监听器失败:', error)
    ElMessage.error('停止监听器失败')
  } finally {
    config.stopping = false
  }
}

const deleteConfig = async (config) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除监听器 "${config.name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      }
    )

    const response = await dataListenerApi.deleteConfig(config.config_id)
    
    if (response.data.status === 'success') {
      ElMessage.success('删除成功')
      await refreshData()
    } else {
      ElMessage.error(response.data.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      // console.error('删除配置失败:', error)
      ElMessage.error('删除配置失败')
    }
  }
}

const batchStart = async () => {
  try {
    batchLoading.value = true
    
    const response = await dataListenerApi.batchStart(selectedIds.value)
    
    if (response.data.status === 'success') {
      const results = response.data.data.results
      const successCount = results.filter(r => r.status === 'success').length
      ElMessage.success(`成功启动 ${successCount} 个监听器`)
      await refreshData()
    }
  } catch (error) {
    // console.error('批量启动失败:', error)
    ElMessage.error('批量启动失败')
  } finally {
    batchLoading.value = false
  }
}

const batchStop = async () => {
  try {
    batchLoading.value = true
    
    const response = await dataListenerApi.batchStop(selectedIds.value)
    
    if (response.data.status === 'success') {
      const results = response.data.data.results
      const successCount = results.filter(r => r.status === 'success').length
      ElMessage.success(`成功停止 ${successCount} 个监听器`)
      await refreshData()
    }
  } catch (error) {
    // console.error('批量停止失败:', error)
    ElMessage.error('批量停止失败')
  } finally {
    batchLoading.value = false
  }
}

const handleSelectionChange = (selection) => {
  selectedIds.value = selection.map(item => item.config_id)
}

const handleConfigSaved = () => {
  dialogVisible.value = false
  refreshData()
}

// 工具函数
const getTypeTagType = (type) => {
  const typeMap = {
    tcp: 'primary',
    mqtt: 'success',
    http: 'warning',
    websocket: 'info',
    sdk: 'danger'
  }
  return typeMap[type] || 'info'
}

const getRuntimeStatusType = (status) => {
  const statusMap = {
    running: 'success',
    stopped: 'info',
    error: 'danger',
    not_found: 'warning'
  }
  return statusMap[status] || 'info'
}

const getRuntimeStatusText = (status) => {
  const statusMap = {
    running: '运行中',
    stopped: '已停止',
    error: '错误',
    not_found: '未找到'
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
    loadStats(),
    // loadTemplates()
  ])
})
</script>

<style scoped>
.data-listeners {
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

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  border: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.stat-content {
  display: flex;
  align-items: center;
  padding: 10px 0;
}

.stat-icon {
  font-size: 32px;
  margin-right: 16px;
}

.stat-info {
  flex: 1;
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

.batch-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.table-card {
  min-height: 400px;
}

.name-cell {
  display: flex;
  flex-direction: column;
}

.name {
  font-weight: 500;
  color: #333;
}

.description {
  font-size: 12px;
  color: #666;
  margin-top: 2px;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stats-cell {
  font-size: 12px;
  color: #666;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.el-button-group .el-button {
  margin-left: 0;
}
</style> 