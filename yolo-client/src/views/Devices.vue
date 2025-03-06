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
        <el-table-column prop="name" label="设备名称" min-width="150" />
        <el-table-column prop="ip" label="IP地址" min-width="150" />
        <el-table-column prop="port" label="端口" width="100" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'danger'">
              {{ row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
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
        label-width="80px"
      >
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="deviceForm.name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="IP地址" prop="ip">
          <el-input v-model="deviceForm.ip" placeholder="请输入IP地址" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number
            v-model="deviceForm.port"
            :min="1"
            :max="65535"
            placeholder="请输入端口号"
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
  name: '',
  ip: '',
  port: 554,
  username: '',
  password: ''
})

const deviceRules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  ip: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    { pattern: /^(\d{1,3}\.){3}\d{1,3}$/, message: '请输入正确的IP地址', trigger: 'blur' }
  ],
  port: [{ required: true, message: '请输入端口号', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 模拟数据加载
const loadData = async () => {
  loading.value = true
  try {
    // 模拟API请求
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // 模拟数据
    const mockData = Array(total.value).fill(0).map((_, index) => ({
      id: index + 1,
      name: `摄像头 ${index + 1}`,
      ip: `192.168.1.${index + 1}`,
      port: 554,
      username: 'admin',
      status: Math.random() > 0.3 ? 'online' : 'offline'
    }))
    
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    devices.value = mockData.slice(start, end)
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 初始化
onMounted(() => {
  total.value = 25 // 模拟总数据量
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
    name: '',
    ip: '',
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
    ...row,
    password: '******' // 实际应用中不应显示原密码
  })
}

// 删除设备
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确认删除设备 "${row.name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    // 模拟删除操作
    setTimeout(() => {
      ElMessage.success('删除成功')
      loadData()
    }, 500)
  }).catch(() => {})
}

// 预览设备
const handlePreview = (row) => {
  previewVisible.value = true
}

// 提交表单
const handleSubmit = () => {
  if (!deviceFormRef.value) return

  deviceFormRef.value.validate((valid) => {
    if (valid) {
      submitting.value = true
      // 模拟提交
      setTimeout(() => {
        ElMessage.success(dialogType.value === 'add' ? '添加成功' : '更新成功')
        dialogVisible.value = false
        submitting.value = false
        loadData()
      }, 1000)
    }
  })
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

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
}

.device-list {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  /* display: flex;
  justify-content: flex-end; */
}

.preview-container {
  width: 100%;
  height: 400px;
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-placeholder {
  text-align: center;
  color: #606266;
}

.video-placeholder .el-icon {
  margin-bottom: 16px;
}

:deep(.el-dialog__body) {
  padding-top: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

:deep(.el-form-item__content) {
  flex-wrap: nowrap;
}
</style> 