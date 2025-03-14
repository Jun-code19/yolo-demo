<template>
  <div class="system-logs-container">
    <div class="page-header">
      <h2>系统日志</h2>
      <div class="filter-options">
        <el-input
          v-model="filters.userId"
          placeholder="用户ID"
          clearable
          style="width: 180px; margin-right: 10px"
        />
        <el-select
          v-model="filters.actionType"
          placeholder="操作类型"
          clearable
          style="width: 180px; margin-right: 10px"
        >
          <el-option label="设备创建" value="create_device" />
          <el-option label="设备更新" value="update_device" />
          <el-option label="设备删除" value="delete_device" />
          <el-option label="用户登录" value="login" />
        </el-select>
        <el-button type="primary" @click="loadData">
          <el-icon><Search /></el-icon>筛选
        </el-button>
      </div>
    </div>

    <!-- 日志列表 -->
    <el-card class="log-list">
      <el-table :data="logs" style="width: 100%" v-loading="loading">
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
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import deviceApi from '@/api/device'

// 列表数据
const loading = ref(false)
const logs = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选条件
const filters = reactive({
  userId: '',
  actionType: ''
})

// 加载日志数据
const loadData = async () => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const params = {
      skip,
      limit: pageSize.value
    }
    
    if (filters.userId) {
      params.user_id = filters.userId
    }
    
    if (filters.actionType) {
      params.action_type = filters.actionType
    }
    
    const response = await deviceApi.getSyslogs(params)
    logs.value = response.data
    total.value = response.data.length // 实际应用中应从后端获取总数
  } catch (error) {
    console.error('加载日志数据失败:', error)
    ElMessage.error('加载日志数据失败，请检查网络连接或服务器状态')
  } finally {
    loading.value = false
  }
}

// 初始化
onMounted(() => {
  loadData()
})

// 分页处理
const handleSizeChange = (val) => {
  pageSize.value = val
  loadData()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadData()
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
    'login': '用户登录'
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
    'update_password':'warning',
    'update_profile':'warning',
    'upload_model':'success',
    'delete_model':'danger',
    'activate_model':'success',
    'deactivate_model':'warning'
    
  }
  return typeTagMap[type] || ''
}
</script>

<style scoped>
.system-logs-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
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