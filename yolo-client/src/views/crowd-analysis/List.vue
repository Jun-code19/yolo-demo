<template>
  <div class="crowd-analysis-list">
    <div class="header">
      <h2>人群分析任务</h2>
      <el-button type="primary" @click="router.push('/crowd-analysis/create')">
        创建任务
      </el-button>
    </div>

    <el-card>
      <el-table
        v-loading="loading"
        :data="jobList"
        border
        style="width: 100%"
      >
        <el-table-column prop="job_name" label="任务名称" width="150" />
        <el-table-column label="监控设备" min-width="250">
          <template #default="scope">
            <el-popover
              placement="top"
              :width="300"
              trigger="hover"
            >
              <template #default>
                <div class="device-list">
                  <el-tag 
                    v-for="id in scope.row.device_ids" 
                    :key="id" 
                    size="small" 
                    style="margin: 2px"
                  >
                    {{ getDeviceName(id) }}
                  </el-tag>
                </div>
              </template>
              <template #reference>
                <div class="device-preview">
                  <el-tag 
                    v-for="(id, index) in scope.row.device_ids.slice(0, 2)" 
                    :key="id" 
                    size="small" 
                    style="margin-right: 5px"
                  >
                    {{ getDeviceName(id) }}
                  </el-tag>
                  <el-tag 
                    v-if="scope.row.device_ids.length > 2" 
                    size="small" 
                    type="info"
                  >
                    +{{ scope.row.device_ids.length - 2 }}
                  </el-tag>
                </div>
              </template>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column label="检测模型" width="150">
          <template #default="scope">
            {{ getModelName(scope.row.models_id) }}
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="120">
          <template #default="scope">
            {{ scope.row.confidence_threshold ? scope.row.confidence_threshold : '0.5' }}
          </template>
        </el-table-column>
        
        <el-table-column label="执行频率" width="120">
          <template #default="scope">
            <span v-if="scope.row.cron_expression">{{ scope.row.cron_expression }}</span>
            <span v-else>每{{ scope.row.interval }}秒</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近执行" width="120">
          <template #default="scope">
            {{ scope.row.last_run ? formatDate(scope.row.last_run) : '未执行' }}
          </template>
        </el-table-column>
        <el-table-column label="人数统计" width="120">
          <template #default="scope">
            <span v-if="scope.row.last_result">
              {{ scope.row.last_result.total_person_count || 0 }}人
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="位置信息" width="150">
          <template #default="scope">
            {{ scope.row.location_info?.name || '无' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button-group>
              <el-button size="small" type="info" @click="viewDetail(scope.row.job_id)">
                详情
              </el-button>
              <el-button size="small" type="primary" @click="editJob(scope.row)">
                编辑
              </el-button>
              <!-- <el-button size="small" type="success" @click="runJob(scope.row.job_id)">
                立即执行
              </el-button> -->
              <el-button 
                size="small" 
                :type="scope.row.is_active ? 'warning' : 'success'"
                @click="toggleJobStatus(scope.row.job_id, scope.row.is_active)"
              >
                {{ scope.row.is_active ? '停止' : '启动' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteJob(scope.row.job_id)">
                  删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="totalCount > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="totalCount"
          layout="prev, pager, next, jumper, ->, total, sizes"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 编辑任务对话框 -->
    <el-dialog 
      v-model="editDialogVisible" 
      title="编辑任务" 
      width="50%" top="5vh"
      :before-close="handleCloseEditDialog"
      :z-index="999999" 
      :modal="true" 
      :append-to-body="true" 
      class="edit-dialog high-priority-dialog"
    >
      <el-alert v-if="editFormError" title="保存失败" :description="editFormError" type="error" show-icon :closable="true"
        @close="editFormError = ''" style="margin-bottom: 15px;" />

      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="120px">
        <el-form-item label="任务名称" prop="job_name">
          <el-input v-model="editForm.job_name" placeholder="请输入任务名称" />
        </el-form-item>

        <el-form-item label="监控设备" prop="device_ids">
          <el-select 
            v-model="editForm.device_ids" 
            multiple 
            placeholder="请选择监控设备" 
            style="width: 100%"
            popper-class="edit-dialog-select"
            filterable
          >
            <el-option v-for="device in availableDevices" :key="device.device_id" :label="device.device_name"
              :value="device.device_id">
              <span>{{ device.device_name }}</span>
              <span v-if="device.location" style="color: #8492a6; font-size: 13px">
                ({{ device.location }})
              </span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="检测模型" prop="models_id">
          <el-select 
            v-model="editForm.models_id" 
            placeholder="请选择检测模型" 
            style="width: 100%" 
            @change="handleModelChange"
            popper-class="edit-dialog-select"
          >
            <el-option v-for="model in availableModels" :key="model.model_id"
              :label="`${model.model_name} (${getModelTypeName(model.model_type)})`" :value="model.model_id">
              <div class="model-option">
                <span>{{ model.model_name }}</span>
                <el-tag size="small" effect="plain">{{ getModelTypeName(model.model_type) }}</el-tag>
              </div>
            </el-option>
          </el-select>
          <div class="hint">所有设备将使用同一个模型进行分析</div>
        </el-form-item>

        <el-form-item label="检测类别" v-if="modelClasses.length > 0" prop="detect_classes">
          <el-select 
            v-model="editForm.detect_classes" 
            multiple 
            placeholder="请选择要检测的目标类别" 
            style="width: 100%"
            collapse-tags 
            collapse-tags-tooltip 
            :max-collapse-tags="4"
            popper-class="edit-dialog-select"
          >
            <el-option v-for="(classItem, index) in modelClasses" :key="classItem.value" :label="classItem.label"
              :value="classItem.value">
              <div class="class-option">
                <span>{{ classItem.label }}</span>
                <span class="class-id">{{ classItem.value }}</span>
              </div>
            </el-option>
          </el-select>
          <div class="hint">选择需要检测的对象类别</div>
        </el-form-item>

        <el-form-item label="置信度阈值" prop="confidence_threshold">
          <el-slider 
            v-model="editForm.confidence_threshold" 
            :min="0.1" 
            :max="1.0" 
            :step="0.05"
            :format-tooltip="val => `${Math.round(val * 100)}%`"
            style="width: 100%; margin-right: 20px;"
          />
          <div class="hint">检测结果的置信度阈值，数值越高检测越严格。当前值：{{ Math.round(editForm.confidence_threshold * 100) }}%</div>
        </el-form-item>

        <el-form-item label="执行频率">
          <el-radio-group v-model="editFrequencyType">
            <el-radio value="interval">间隔执行</el-radio>
            <el-radio value="cron">CRON表达式</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="执行间隔(秒)" v-if="editFrequencyType === 'interval'">
          <el-input-number v-model="editForm.interval" :min="5" :step="5" />
        </el-form-item>

        <el-form-item label="CRON表达式" v-if="editFrequencyType === 'cron'" prop="cron_expression">
          <el-input v-model="editForm.cron_expression" placeholder="例如: */30 * * * *" />
          <div class="cron-hint">例: "*/30 * * * *" 表示每30分钟执行一次</div>
        </el-form-item>

        <el-form-item label="标签">
          <el-tag v-for="tag in editForm.tags" :key="tag" closable @close="removeEditTag(tag)"
            style="margin-right: 5px">
            {{ tag }}
          </el-tag>
          <el-input v-if="editInputVisible" ref="editSaveTagInput" v-model="editInputValue" size="small"
            @keyup.enter="handleEditInputConfirm" @blur="handleEditInputConfirm" />
          <el-button v-else size="small" @click="showEditInput">+ 添加标签</el-button>
        </el-form-item>

        <el-form-item label="位置信息">
          <el-input v-model="editForm.location_info.name" placeholder="位置名称" />
        </el-form-item>

        <el-form-item label="位置坐标">
          <el-row :gutter="10">
            <el-col :span="11">
              <el-input v-model="editForm.location_info.coordinates[0]" placeholder="经度" type="number" />
            </el-col>
            <el-col :span="11">
              <el-input v-model="editForm.location_info.coordinates[1]" placeholder="纬度" type="number" />
            </el-col>
          </el-row>
        </el-form-item>

        <el-form-item label="位置地址">
          <el-input v-model="editForm.location_info.address" placeholder="详细地址" />
        </el-form-item>

        <el-form-item label="区域代码">
          <el-input v-model="editForm.location_info.area_code" placeholder="区域代码" />
        </el-form-item>

        <el-form-item label="人数预警阈值">
          <el-input-number v-model="editForm.warning_threshold" :min="0" placeholder="0表示不预警" />
          <div class="hint">当检测人数超过此阈值时触发预警，0表示不预警</div>
        </el-form-item>

        <el-form-item label="预警消息">
          <el-input v-model="editForm.warning_message" placeholder="预警消息模板，支持{location}、{count}、{threshold}等变量" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" placeholder="任务描述" />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleCloseEditDialog">取消</el-button>
          <el-button type="primary" @click="submitEditForm" :loading="editSubmitting">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import { formatDate } from '@/utils/date'

const router = useRouter()
const loading = ref(false)
const jobList = ref([])
const deviceMap = ref({})
const modelMap = ref({})
const pageSize = ref(20)
const currentPage = ref(1)
const totalCount = ref(0)

// 编辑表单相关变量
const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editSubmitting = ref(false)
const editInputVisible = ref(false)
const editInputValue = ref('')
const editSaveTagInput = ref(null)
const editFrequencyType = ref('interval')
const editFormError = ref('')
const availableDevices = ref([])
const availableModels = ref([])
const modelClasses = ref([])
const currentEditJobId = ref('')

const editForm = reactive({
  job_name: '',
  device_ids: [],
  models_id: '',
  detect_classes: [],
  confidence_threshold: 0.5,
  interval: 300,
  cron_expression: '',
  tags: [],
  location_info: {
    name: '',
    coordinates: [0, 0],
    address: '',
    area_code: ''
  },
  warning_threshold: 0,
  warning_message: '',
  description: ''
})

const editRules = {
  job_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  device_ids: [{ required: true, message: '请选择至少一个监控设备', trigger: 'change' }],
  models_id: [{ required: true, message: '请选择检测模型', trigger: 'change' }],
  cron_expression: [
    {
      validator: (rule, value, callback) => {
        if (editFrequencyType.value === 'cron' && !value) {
          callback(new Error('请输入CRON表达式'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

onMounted(() => {
  fetchJobs()
  fetchDevices()
  fetchModels()
})

// 注意：现在使用后端分页，不再需要前端计算分页数据

const fetchJobs = async () => {
  loading.value = true
  try {
    const res = await crowdAnalysisApi.getAnalysisJobs({
      page: currentPage.value,
      page_size: pageSize.value
    })
    jobList.value = res.data.data
    totalCount.value = res.data.total
  } catch (error) {
    ElMessage.error('获取任务列表失败')
    // console.error(error)
  } finally {
    loading.value = false
  }
}

const fetchDevices = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableDevices()
    deviceMap.value = {}
    res.data.forEach(item => {
      deviceMap.value[item.device_id] = item.device_name
    })
  } catch (error) {
    // console.error('获取设备列表失败', error)
  }
}

const fetchModels = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    modelMap.value = {}
    res.data.forEach(item => {
      modelMap.value[item.model_id] = item.model_name
    })
  } catch (error) {
    // console.error('获取模型列表失败', error)
  }
}

const getDeviceName = (deviceId) => {
  return deviceMap.value[deviceId] || deviceId
}

const getModelName = (modelId) => {
  return modelMap.value[modelId] || modelId
}

const getStatusType = (status) => {
  const map = {
    scheduled: 'warning',
    running: 'warning',
    completed: 'success',
    error: 'danger',
    created: 'primary',
    paused: 'info'
  }
  return map[status] || ''
}

const viewDetail = (jobId) => {
  router.push(`/crowd-analysis/detail/${jobId}`)
}

const toggleJobStatus = async (jobId, isActive) => {
  try {
    if (isActive) {
      // 暂停任务
      await crowdAnalysisApi.pauseAnalysisJob(jobId)
      ElMessage.success('任务已暂停')
    } else {
      // 恢复任务
      await crowdAnalysisApi.resumeAnalysisJob(jobId)
      ElMessage.success('任务已恢复')
    }
    fetchJobs()
  } catch (error) {
    ElMessage.error(`${isActive ? '暂停' : '恢复'}任务失败`)
    // console.error(error)
  }
}

const deleteJob = (jobId) => {
  ElMessageBox.confirm('确定删除此任务?', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await crowdAnalysisApi.deleteAnalysisJob(jobId)
      ElMessage.success('删除成功')
      fetchJobs()
    } catch (error) {
      ElMessage.error('删除失败')
      // console.error(error)
    }
  }).catch(() => {})
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1 // 重置到第一页
  fetchJobs() // 重新加载数据
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  fetchJobs() // 重新加载数据
}

// 编辑任务
const editJob = async (job) => {
  // 获取可用设备和模型
  if (availableDevices.value.length === 0) {
    await fetchAvailableDevices()
  }

  if (availableModels.value.length === 0) {
    await fetchAvailableModels()
  }

  // 记录当前编辑的任务ID
  currentEditJobId.value = job.job_id

  // 填充编辑表单数据
  Object.assign(editForm, {
    job_name: job.job_name,
    device_ids: [...(job.device_ids || [])],
    models_id: job.models_id || '',
    detect_classes: [...(job.detect_classes || [])],
    confidence_threshold: job.confidence_threshold || 0.5,
    interval: job.interval || 300,
    cron_expression: job.cron_expression || '',
    tags: [...(job.tags || [])],
    location_info: {
      name: job.location_info?.name || '',
      coordinates: [...(job.location_info?.coordinates || [0, 0])],
      address: job.location_info?.address || '',
      area_code: job.location_info?.area_code || ''
    },
    warning_threshold: job.warning_threshold || 0,
    warning_message: job.warning_message || '',
    description: job.description || ''
  })

  // 设置频率类型
  editFrequencyType.value = job.cron_expression ? 'cron' : 'interval'

  // 如果有模型ID，获取模型支持的类别
  if (job.models_id) {
    await handleModelChange(job.models_id)
  }

  editDialogVisible.value = true
}

// 处理模型变更，获取模型支持的类别
const handleModelChange = async (modelId) => {
  if (!modelId) {
    modelClasses.value = []
    editForm.detect_classes = []
    return
  }

  try {
    const res = await crowdAnalysisApi.getModelClasses(modelId)
    const classesObj = res.data.classes || {}
    modelClasses.value = Object.entries(classesObj).map(([key, name]) => ({
      label: name, // 显示的名称
      value: key   // 对应的键
    }));

  } catch (error) {
    // console.error('获取模型类别失败:', error)
    ElMessage.error('获取模型支持的类别失败')
    modelClasses.value = []
  }
}

// 关闭编辑对话框
const handleCloseEditDialog = () => {
  editDialogVisible.value = false
  editFormError.value = ''
}

// 移除编辑标签
const removeEditTag = (tag) => {
  editForm.tags.splice(editForm.tags.indexOf(tag), 1)
}

// 显示标签输入框
const showEditInput = () => {
  editInputVisible.value = true
  nextTick(() => {
    editSaveTagInput.value.focus()
  })
}

// 处理标签输入确认
const handleEditInputConfirm = () => {
  const value = editInputValue.value.trim()
  if (value && editForm.tags.indexOf(value) === -1) {
    editForm.tags.push(value)
  }
  editInputVisible.value = false
  editInputValue.value = ''
}

// 获取可用设备列表
const fetchAvailableDevices = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableDevices()
    availableDevices.value = res.data
  } catch (error) {
    ElMessage.error('获取监控设备列表失败')
    // console.error(error)
  }
}

// 获取可用模型列表
const fetchAvailableModels = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    availableModels.value = res.data.filter(model => model.is_active);
  } catch (error) {
    ElMessage.error('获取检测模型列表失败')
  }
}

// 获取模型类型名称
const getModelTypeName = (type) => {
  const typeMap = {
    'object_detection': '目标检测',
    'smart_behavior': '智能行为',
    'smart_counting': '智能人数统计',
    'segmentation': '图像分割',
    'keypoint': '关键点检测',
    'pose': '姿态估计',
    'face': '人脸识别',
    'other': '其他类型'
  }
  return typeMap[type] || type
}

// 提交编辑表单
const submitEditForm = async () => {
  if (!editFormRef.value) return

  editFormError.value = ''

  await editFormRef.value.validate(async (valid) => {
    if (!valid) return

    editSubmitting.value = true
    try {
      // 处理表单数据
      const formData = JSON.parse(JSON.stringify(editForm)) // 深拷贝避免修改原始表单

      // 根据频率类型设置
      if (editFrequencyType.value === 'interval') {
        delete formData.cron_expression
      } else {
        delete formData.interval
      }

      // 发送请求
      await crowdAnalysisApi.updateAnalysisJob(currentEditJobId.value, formData)
      ElMessage.success('更新成功')

      // 重新加载任务列表
      fetchJobs()

      // 关闭对话框
      editDialogVisible.value = false
    } catch (error) {
      // console.error('更新任务失败:', error)

      let errorMessage = '更新失败'
      if (error.response) {
        if (error.response.data && error.response.data.detail) {
          errorMessage = error.response.data.detail
        } else if (error.response.status === 422) {
          errorMessage = '请求数据验证失败，请检查表单输入'
        } else {
          errorMessage = `服务器错误 (${error.response.status})`
        }
      } else if (error.message) {
        errorMessage = error.message
      }

      editFormError.value = errorMessage
      ElMessage.error(errorMessage)
    } finally {
      editSubmitting.value = false
    }
  })
}

// 监听频率类型变化
watch(editFrequencyType, (val) => {
  if (val === 'interval') {
    editForm.cron_expression = ''
  } else {
    // 默认CRON表达式 - 每30分钟
    if (!editForm.cron_expression) {
      editForm.cron_expression = '*/30 * * * *'
    }
  }
})
</script>

<style scoped>
.crowd-analysis-list {
  width: 100%;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.pagination {
  margin-top: 20px;
  text-align: right;
}
.device-list {
  max-height: 200px;
  overflow-y: auto;
}
.device-preview {
  display: flex;
  align-items: center;
}

.hint,
.cron-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 5px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.model-option,
.class-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-id {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}

.edit-dialog {
  z-index: 9999;
}

/* 高优先级对话框样式 - 确保不被菜单和头部遮挡 */
.high-priority-dialog {
  z-index: 999999 !important;
}
</style>

<style>
/* 全局样式确保对话框最高优先级 */
.edit-dialog .el-dialog__wrapper {
  z-index: 10000 !important;
}

.edit-dialog .el-overlay {
  z-index: 9999 !important;
}

.edit-dialog .el-dialog {
  z-index: 10000 !important;
}

/* 确保下拉框选项在对话框中正常显示 */
.el-select-dropdown {
  z-index: 10001 !important;
}

.el-popper {
  z-index: 10001 !important;
}

/* 特别针对编辑对话框中的下拉框 */
.edit-dialog .el-select-dropdown {
  z-index: 10002 !important;
}

.edit-dialog .el-popper {
  z-index: 10002 !important;
}

/* 专门针对编辑对话框的下拉框弹出层 */
.edit-dialog-select {
  z-index: 10003 !important;
}

/* 日期选择器等其他popper元素 */
.el-picker-panel {
  z-index: 10001 !important;
}

.edit-dialog .el-picker-panel {
  z-index: 10002 !important;
}
</style>
