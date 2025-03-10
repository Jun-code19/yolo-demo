<template>
  <div class="models-container">
    <el-card class="model-card">
      <template #header>
        <div class="card-header">
          <h2>视频检测模型管理</h2>
          <el-button type="primary" @click="showUploadDialog">上传新模型</el-button>
        </div>
      </template>
      
      <!-- 模型列表 -->
      <div v-loading="loading">
        <el-tabs type="border-card">
          <!-- 按模型类型分组展示 -->
          <el-tab-pane v-for="(models, type) in groupedModels" :key="type" :label="getModelTypeName(type)">
            <el-table :data="models" border style="width: 100%">
              <el-table-column prop="model_name" label="模型名称" width="180" />
              <el-table-column prop="format" label="格式" width="100">
                <template #default="scope">
                  <el-tag>{{ scope.row.format.toUpperCase() }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="file_size" label="文件大小" width="120">
                <template #default="scope">
                  {{ formatFileSize(scope.row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column prop="upload_time" label="上传时间" width="180">
                <template #default="scope">
                  {{ formatDate(scope.row.upload_time) }}
                </template>
              </el-table-column>
              <el-table-column prop="is_active" label="状态" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.is_active ? 'success' : 'info'">
                    {{ scope.row.is_active ? '已激活' : '未激活' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="240">
                <template #default="scope">
                  <el-button type="primary" size="small" @click="viewModelDetails(scope.row)">
                    查看详情
                  </el-button>
                  <el-button 
                    :type="scope.row.is_active ? 'warning' : 'success'" 
                    size="small"
                    @click="toggleModelActive(scope.row)"
                  >
                    {{ scope.row.is_active ? '停用' : '启用' }}
                  </el-button>
                  <el-button type="danger" size="small" @click="confirmDelete(scope.row)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <!-- 如果没有模型 -->
          <div v-if="!Object.keys(groupedModels).length" class="no-data">
            <el-empty description="暂无模型数据，请上传模型文件"></el-empty>
          </div>
        </el-tabs>
      </div>
    </el-card>
    
    <!-- 上传模型对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传模型" width="500px">
      <el-form :model="uploadForm" label-width="80px" :rules="uploadRules" ref="uploadFormRef">
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="uploadForm.modelName" placeholder="请输入模型名称"></el-input>
        </el-form-item>
        
        <el-form-item label="模型类型" prop="modelType">
          <el-select v-model="uploadForm.modelType" placeholder="请选择模型类型" style="width: 100%">
            <el-option label="目标检测" value="object_detection"></el-option>
            <el-option label="图像分割" value="segmentation"></el-option>
            <el-option label="关键点检测" value="keypoint"></el-option>
            <el-option label="姿态估计" value="pose"></el-option>
            <el-option label="人脸识别" value="face"></el-option>
            <el-option label="其他类型" value="other"></el-option>
          </el-select>
        </el-form-item>
        
        <el-form-item label="模型文件" prop="modelFile">
          <el-upload
            class="model-upload"
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            accept=".pt,.onnx,.pth,.weights"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            :on-remove="handleRemove"
            :file-list="uploadForm.fileList"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                仅支持 .pt/.onnx/.pth/.weights 格式的模型文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="3" placeholder="请输入模型描述（可选）"></el-input>
        </el-form-item>
        
        <el-form-item label="参数">
          <el-collapse>
            <el-collapse-item title="添加模型参数（可选）">
              <el-form-item v-for="(param, index) in uploadForm.parameters" :key="index">
                <div style="display: flex; margin-bottom: 10px;">
                  <el-input v-model="param.key" placeholder="参数名" style="width: 40%; margin-right: 10px;"></el-input>
                  <el-input v-model="param.value" placeholder="参数值" style="width: 40%; margin-right: 10px;"></el-input>
                  <el-button type="danger" @click="removeParam(index)">删除</el-button>
                </div>
              </el-form-item>
              <el-button type="primary" @click="addParam">添加参数</el-button>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="uploadModel" :loading="uploading">上传</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 模型详情对话框 -->
    <el-dialog v-model="detailsDialogVisible" title="模型详情" width="700px">
      <div v-if="selectedModel" class="model-details">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模型ID">{{ selectedModel.model_id }}</el-descriptions-item>
          <el-descriptions-item label="模型名称">{{ selectedModel.model_name }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ getModelTypeName(selectedModel.model_type) }}</el-descriptions-item>
          <el-descriptions-item label="文件格式">{{ selectedModel.format.toUpperCase() }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ formatFileSize(selectedModel.file_size) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="selectedModel.is_active ? 'success' : 'info'">
              {{ selectedModel.is_active ? '已激活' : '未激活' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ formatDate(selectedModel.upload_time) }}</el-descriptions-item>
          <el-descriptions-item label="最后使用">{{ selectedModel.last_used ? formatDate(selectedModel.last_used) : '暂未使用' }}</el-descriptions-item>
          <el-descriptions-item label="文件路径" :span="2">{{ selectedModel.file_path }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ selectedModel.description || '暂无描述' }}</el-descriptions-item>
        </el-descriptions>
        
        <h3 class="mt-4">模型参数</h3>
        <el-table v-if="selectedModel.parameters && Object.keys(selectedModel.parameters).length" 
                 :data="formatParameters(selectedModel.parameters)" 
                 border 
                 style="width: 100%"
                 class="mt-2">
          <el-table-column prop="key" label="参数名" width="200" />
          <el-table-column prop="value" label="参数值" />
        </el-table>
        <el-empty v-else description="暂无参数信息"></el-empty>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import deviceApi from '@/api/device'

// 数据加载状态
const loading = ref(false)
const uploading = ref(false)

// 模型列表
const models = ref([])

// 对话框显示状态
const uploadDialogVisible = ref(false)
const detailsDialogVisible = ref(false)

// 选中的模型
const selectedModel = ref(null)

// 上传表单
const uploadFormRef = ref(null)
const uploadForm = ref({
  modelName: '',
  modelType: '',
  description: '',
  modelFile: null,
  fileList: [],
  parameters: []
})

// 表单验证规则
const uploadRules = {
  modelName: [
    { required: true, message: '请输入模型名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  modelType: [
    { required: true, message: '请选择模型类型', trigger: 'change' }
  ],
  modelFile: [
    { required: true, message: '请上传模型文件', trigger: 'change' }
  ]
}

// 按模型类型分组
const groupedModels = computed(() => {
  const groups = {}
  models.value.forEach(model => {
    if (!groups[model.model_type]) {
      groups[model.model_type] = []
    }
    groups[model.model_type].push(model)
  })
  return groups
})

// 加载模型列表
const loadModels = async () => {
  loading.value = true
  try {
    const { data } = await deviceApi.getModels()
    models.value = data
  } catch (error) {
    console.error('加载模型列表失败:', error)
    ElMessage.error('加载模型列表失败')
  } finally {
    loading.value = false
  }
}

// 初始化
onMounted(() => {
  loadModels()
})

// 显示上传对话框
const showUploadDialog = () => {
  uploadForm.value = {
    modelName: '',
    modelType: '',
    description: '',
    modelFile: null,
    fileList: [],
    parameters: []
  }
  uploadDialogVisible.value = true
}

// 文件变更处理
const handleFileChange = (file) => {
  uploadForm.value.modelFile = file.raw
}

// 文件数量超出限制
const handleExceed = () => {
  ElMessage.warning('只能上传一个模型文件')
}

// 移除文件
const handleRemove = () => {
  uploadForm.value.modelFile = null
}

// 添加参数
const addParam = () => {
  uploadForm.value.parameters.push({ key: '', value: '' })
}

// 移除参数
const removeParam = (index) => {
  uploadForm.value.parameters.splice(index, 1)
}

// 上传模型
const uploadModel = async () => {
  if (!uploadFormRef.value) return
  
  await uploadFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    if (!uploadForm.value.modelFile) {
      ElMessage.error('请上传模型文件')
      return
    }
    
    uploading.value = true
    try {
      // 创建FormData
      const formData = new FormData()
      formData.append('model_file', uploadForm.value.modelFile)
      formData.append('model_name', uploadForm.value.modelName)
      formData.append('model_type', uploadForm.value.modelType)
      
      if (uploadForm.value.description) {
        formData.append('description', uploadForm.value.description)
      }
      
      // 处理自定义参数
      if (uploadForm.value.parameters.length > 0) {
        const params = {}
        uploadForm.value.parameters.forEach(p => {
          if (p.key && p.value) {
            params[p.key] = p.value
          }
        })
        formData.append('parameters', JSON.stringify(params))
      }
      
      // 发送请求
      await deviceApi.uploadModel(formData)
      
      ElMessage.success('模型上传成功')
      uploadDialogVisible.value = false
      loadModels() // 重新加载模型列表
    } catch (error) {
      console.error('上传模型失败:', error)
      ElMessage.error(`上传模型失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      uploading.value = false
    }
  })
}

// 查看模型详情
const viewModelDetails = (model) => {
  selectedModel.value = model
  detailsDialogVisible.value = true
}

// 切换模型激活状态
const toggleModelActive = async (model) => {
  try {
    const newStatus = !model.is_active
    await deviceApi.toggleModelActive(model.model_id, newStatus)
    model.is_active = newStatus
    ElMessage.success(`模型已${newStatus ? '激活' : '停用'}`)
  } catch (error) {
    console.error('更新模型状态失败:', error)
    ElMessage.error(`更新模型状态失败: ${error.response?.data?.detail || error.message}`)
  }
}

// 确认删除模型
const confirmDelete = (model) => {
  ElMessageBox.confirm(
    `确定要删除模型"${model.model_name}"吗？此操作将永久删除该模型文件，且无法恢复。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deviceApi.deleteModel(model.model_id)
      ElMessage.success('模型删除成功')
      loadModels() // 重新加载模型列表
    } catch (error) {
      console.error('删除模型失败:', error)
      ElMessage.error(`删除模型失败: ${error.response?.data?.detail || error.message}`)
    }
  }).catch(() => {
    // 取消删除
  })
}

// 格式化文件大小
const formatFileSize = (size) => {
  if (size < 1024) {
    return size + ' B'
  } else if (size < 1024 * 1024) {
    return (size / 1024).toFixed(2) + ' KB'
  } else if (size < 1024 * 1024 * 1024) {
    return (size / (1024 * 1024)).toFixed(2) + ' MB'
  } else {
    return (size / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取模型类型名称
const getModelTypeName = (type) => {
  const typeMap = {
    'object_detection': '目标检测',
    'segmentation': '图像分割',
    'keypoint': '关键点检测',
    'pose': '姿态估计',
    'face': '人脸识别',
    'other': '其他类型'
  }
  return typeMap[type] || type
}

// 格式化参数为表格数据
const formatParameters = (params) => {
  if (!params) return []
  return Object.entries(params).map(([key, value]) => {
    return {
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value)
    }
  })
}
</script>

<style scoped>
.models-container {
  padding: 20px;
}

.model-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.model-upload {
  width: 100%;
}

.no-data {
  padding: 40px 0;
  text-align: center;
}

.mt-2 {
  margin-top: 8px;
}

.mt-4 {
  margin-top: 16px;
}

.model-details {
  max-height: 600px;
  overflow-y: auto;
}
</style> 