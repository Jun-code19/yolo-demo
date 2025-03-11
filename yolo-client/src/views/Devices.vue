<template>
  <div class="devices-container">
    <div class="page-header">
      <h2>设备管理</h2>
      <el-button type="primary" @click="handleAdd">
        <el-icon><Plus /></el-icon>添加设备
      </el-button>
    </div>

    <!-- 设备列表 -->
    <el-card class="device-list">
      <el-table :data="devices" style="width: 100%" v-loading="loading">
        <el-table-column prop="device_id" label="设备ID" min-width="120" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="device_type" label="设备类型" min-width="120">
          <template #default="{ row }">
            <el-tag :type="getDeviceTypeTag(row.device_type)">
              {{ getDeviceTypeName(row.device_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP地址" min-width="150" />
        <el-table-column prop="port" label="端口" width="100" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'">
              {{ row.status ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_heartbeat" label="最后心跳" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button type="primary" link @click="handleEdit(row)">
                编辑
              </el-button>
              <el-button type="primary" link @click="handlePreview(row)">
                预览
              </el-button>
              <el-button type="danger" link @click="handleDelete(row)">
                删除
              </el-button>
            </el-button-group>
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

    <!-- 添加/编辑设备对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '添加设备' : '编辑设备'"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="deviceFormRef"
        :model="deviceForm"
        :rules="deviceRules"
        label-width="100px"
      >
        <el-form-item label="设备ID" prop="device_id">
          <el-input v-model="deviceForm.device_id" placeholder="请输入设备ID" :disabled="dialogType === 'edit'" />
        </el-form-item>
        <el-form-item label="设备名称" prop="device_name">
          <el-input v-model="deviceForm.device_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="deviceForm.device_type" placeholder="请选择设备类型" style="width: 100%">
            <el-option label="摄像头" value="camera" />
            <el-option label="边缘服务器" value="edge_server" />
            <el-option label="存储节点" value="storage_node" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP地址" prop="ip_address">
          <el-input v-model="deviceForm.ip_address" placeholder="请输入IP地址" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number
            v-model="deviceForm.port"
            :min="1"
            :max="65535"
            placeholder="请输入端口号"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="deviceForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="deviceForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      title="设备预览"
      width="800px"
      destroy-on-close
    >
      <div class="preview-container">
        <div class="video-placeholder">
          <el-icon :size="64"><VideoCamera /></el-icon>
          <p>视频预览区域</p>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="previewVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus, VideoCamera } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import deviceApi from '@/api/device'

// API 基础URL
const API_BASE_URL = 'http://localhost:8000/api/v1'

// 列表数据
const loading = ref(false)
const devices = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 对话框控制
const dialogVisible = ref(false)
const dialogType = ref('add')
const previewVisible = ref(false)
const submitting = ref(false)

// 表单相关
const deviceFormRef = ref(null)
const deviceForm = reactive({
  device_id: '',
  device_name: '',
  device_type: 'camera',
  ip_address: '',
  port: 554,
  username: '',
  password: ''
})

const deviceRules = {
  device_id: [{ required: true, message: '请输入设备ID', trigger: 'blur' }],
  device_name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  ip_address: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    {
      pattern: /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
      message: '请输入正确的IP地址',
      trigger: 'blur'
    }
  ],
  port: [{ required: true, message: '请输入端口号', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 加载设备数据
const loadData = async () => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const response = await deviceApi.getDevices({ skip, limit: pageSize.value })
    devices.value = response.data
    total.value = response.data.length // 实际应用中应从后端获取总数
  } catch (error) {
    console.error('加载设备数据失败:', error)
    ElMessage.error('加载设备数据失败，请检查网络连接或服务器状态')
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

// 添加设备
const handleAdd = () => {
  dialogType.value = 'add'
  dialogVisible.value = true
  Object.assign(deviceForm, {
    device_id: '',
    device_name: '',
    device_type: 'camera',
    ip_address: '',
    port: 554,
    username: '',
    password: ''
  })
}

// 编辑设备
const handleEdit = (row) => {
  dialogType.value = 'edit'
  dialogVisible.value = true
  Object.assign(deviceForm, {
    device_id: row.device_id,
    device_name: row.device_name,
    device_type: row.device_type,
    ip_address: row.ip_address,
    port: row.port,
    username: row.username,
    password: '' // 不显示密码，如果不修改则留空
  })
}

// 提交表单
const handleSubmit = async () => {
  if (!deviceFormRef.value) return
  
  await deviceFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      if (dialogType.value === 'add') {
        // 创建设备
        await deviceApi.createDevice(deviceForm)
        ElMessage.success('设备添加成功')
      } else {
        // 更新设备信息
        await deviceApi.updateDevice(deviceForm.device_id, deviceForm)
        ElMessage.success('设备更新成功')
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('操作失败:', error)
      ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      submitting.value = false
    }
  })
}

// 删除设备
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确认删除设备 "${row.device_name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deviceApi.deleteDevice(row.device_id)
      ElMessage.success('删除成功')
      loadData()
    } catch (error) {
      console.error('删除失败:', error)
      ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`)
    }
  }).catch(() => {})
}

// 预览设备
const handlePreview = (row) => {
  previewVisible.value = true
}

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN')
}

// 获取设备类型名称
const getDeviceTypeName = (type) => {
  const typeMap = {
    'camera': '摄像头',
    'edge_server': '边缘服务器',
    'storage_node': '存储节点'
  }
  return typeMap[type] || type
}

// 获取设备类型标签样式
const getDeviceTypeTag = (type) => {
  const typeTagMap = {
    'camera': '',
    'edge_server': 'success',
    'storage_node': 'warning'
  }
  return typeTagMap[type] || 'info'
}
</script>

<style scoped>
.devices-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.device-list {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
}
</style> 
