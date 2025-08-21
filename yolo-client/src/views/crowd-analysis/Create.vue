<template>
  <div class="create-crowd-analysis">
    <div class="header">
      <h2>创建人群分析任务</h2>
    </div>

    <el-alert
      v-if="formError"
      title="创建任务失败"
      :description="formError"
      type="error"
      show-icon
      :closable="true"
      @close="formError = ''"
      style="margin-bottom: 15px;"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" class="form">
      <el-form-item label="任务名称" prop="job_name">
        <el-input v-model="form.job_name" placeholder="请输入任务名称" />
      </el-form-item>

      <el-form-item label="监控设备" prop="device_ids">
        <el-select
          v-model="form.device_ids"
          multiple
          placeholder="请选择监控设备"
          style="width: 100%"
          filterable
        >
          <el-option
            v-for="device in availableDevices"
            :key="device.device_id"
            :label="device.device_name"
            :value="device.device_id"
          >
            <span>{{ device.device_name }}</span>
            <span v-if="device.location" style="color: #8492a6; font-size: 13px">
              ({{ device.location }})
            </span>
          </el-option>
        </el-select>
      </el-form-item>

      <el-form-item label="检测模型" prop="models_id">
        <el-select
          v-model="form.models_id"
          placeholder="请选择检测模型"
          style="width: 100%"
          @change="handleModelChange"
        >
          <el-option
            v-for="model in availableModels"
            :key="model.model_id"
            :label="`${model.model_name} (${getModelTypeName(model.model_type)})`"
            :value="model.model_id"
          >
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
            v-model="form.detect_classes"
            multiple
            placeholder="请选择要检测的目标类别"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="4"
          >
            <el-option v-for="(classItem, index) in modelClasses" :key="classItem.value" :label="classItem.label"
              :value="classItem.value">
              <div class="class-option">
                <span>{{ classItem.label }}</span>
                <span class="class-id">{{ classItem.value }}</span>
              </div>
            </el-option>
          </el-select>
          <div class="hint">选择需要检测的对象类别，默认选中第一个类别</div>
        </el-form-item>

        <el-form-item label="置信度阈值" prop="confidence_threshold">
          <el-slider 
            v-model="form.confidence_threshold" 
            :min="0.1" 
            :max="1.0" 
            :step="0.05"
            :format-tooltip="val => `${Math.round(val * 100)}%`"
            style="width: 100%; margin-right: 20px;"
          />
          <div class="hint">检测结果的置信度阈值，数值越高检测越严格。当前值：{{ Math.round(form.confidence_threshold * 100) }}%</div>
        </el-form-item>

      <el-form-item label="执行频率">
        <el-radio-group v-model="frequencyType">
          <el-radio value="interval">间隔执行</el-radio>
          <el-radio value="cron">CRON表达式</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="执行间隔(秒)" v-if="frequencyType === 'interval'">
        <el-input-number v-model="form.interval" :min="5" :step="5" />
      </el-form-item>

      <el-form-item label="CRON表达式" v-if="frequencyType === 'cron'" prop="cron_expression">
        <el-input v-model="form.cron_expression" placeholder="例如: */30 * * * *" />
        <div class="cron-hint">例: "*/30 * * * *" 表示每30分钟执行一次</div>
      </el-form-item>

      <el-form-item label="标签">
        <el-tag
          v-for="tag in form.tags"
          :key="tag"
          closable
          @close="removeTag(tag)"
          style="margin-right: 5px"
        >
          {{ tag }}
        </el-tag>
        <el-input
          v-if="inputVisible"
          ref="saveTagInput"
          v-model="inputValue"
          size="small"
          @keyup.enter="handleInputConfirm"
          @blur="handleInputConfirm"
        />
        <el-button v-else size="small" @click="showInput">+ 添加标签</el-button>
      </el-form-item>

      <el-form-item label="位置信息">
        <el-input v-model="form.location_info.name" placeholder="位置名称" />
      </el-form-item>

      <el-form-item label="位置坐标">
        <el-row :gutter="10">
          <el-col :span="11">
            <el-input
              v-model="form.location_info.coordinates[0]"
              placeholder="经度"
              type="number"
            />
          </el-col>
          <el-col :span="11">
            <el-input
              v-model="form.location_info.coordinates[1]"
              placeholder="纬度"
              type="number"
            />
          </el-col>
        </el-row>
      </el-form-item>

      <el-form-item label="位置地址">
        <el-input v-model="form.location_info.address" placeholder="详细地址" />
      </el-form-item>

      <el-form-item label="区域代码">
        <el-input v-model="form.location_info.area_code" placeholder="区域代码" />
      </el-form-item>

      <el-form-item label="人数预警阈值">
        <el-input-number 
          v-model="form.warning_threshold" 
          :min="0" 
          placeholder="0表示不预警"
        />
        <div class="hint">当检测人数超过此阈值时触发预警，0表示不预警</div>
      </el-form-item>

      <el-form-item label="预警消息">
        <el-input 
          v-model="form.warning_message" 
          placeholder="预警消息模板，支持{location}、{count}、{threshold}等变量"
        />
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          placeholder="任务描述"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="submitForm" :loading="submitting">创建任务</el-button>
        <el-button @click="router.push('/crowd-analysis')">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'

const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)
const inputVisible = ref(false)
const inputValue = ref('')
const saveTagInput = ref(null)
const frequencyType = ref('interval')
const availableDevices = ref([])
const availableModels = ref([])
const formError = ref('')
const modelClasses = ref([])
// const selectedClasses = ref([])

const form = reactive({
  job_name: '',
  device_ids: [],
  models_id: '',
  detect_classes: [],
  confidence_threshold: 0.5,
  interval: 300,
  cron_expression: '',
  tags: ['crowd_analysis'],
  location_info: {
    name: '',
    coordinates: [0, 0],
    address: '',
    area_code: ''
  },
  warning_threshold: 0,
  warning_message: '人群密度预警：{location}区域人数达到{count}人，超过预警阈值({threshold}人)',
  description: ''
})

const rules = {
  job_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  device_ids: [{ required: true, message: '请选择至少一个监控设备', trigger: 'change' }],
  models_id: [{ required: true, message: '请选择检测模型', trigger: 'change' }],
  cron_expression: [
    { 
      validator: (rule, value, callback) => {
        if (frequencyType.value === 'cron' && !value) {
          callback(new Error('请输入CRON表达式'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

watch(frequencyType, (val) => {
  if (val === 'interval') {
    form.cron_expression = ''
  } else {
    // 默认CRON表达式 - 每30分钟
    if (!form.cron_expression) {
      form.cron_expression = '*/30 * * * *'
    }
  }
})

onMounted(() => {
  fetchAvailableDevices()
  fetchAvailableModels()
})

const fetchAvailableDevices = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableDevices()
    availableDevices.value = res.data
  } catch (error) {
    ElMessage.error('获取监控设备列表失败')
    // console.error(error)
  }
}

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

const removeTag = (tag) => {
  form.tags.splice(form.tags.indexOf(tag), 1)
}

const showInput = () => {
  inputVisible.value = true
  nextTick(() => {
    saveTagInput.value.focus()
  })
}

const handleInputConfirm = () => {
  const value = inputValue.value.trim()
  if (value && form.tags.indexOf(value) === -1) {
    form.tags.push(value)
  }
  inputVisible.value = false
  inputValue.value = ''
}

const handleModelChange = async (modelId) => {
  if (!modelId) {
    modelClasses.value = []
    form.detect_classes = []
    return
  }

  try {
    const res = await crowdAnalysisApi.getModelClasses(modelId)
    const classesObj = res.data.classes || {}
    modelClasses.value = Object.entries(classesObj).map(([key, name]) => ({
      label: name, // 显示的名称
      value: key   // 对应的键
    }));
    
    // 默认选中第一个类别
    if (modelClasses.value.length > 0) {
      form.detect_classes = [modelClasses.value[0].value]
    } else {
      form.detect_classes = []
    }
  } catch (error) {
    // console.error('获取模型类别失败:', error)
    ElMessage.error('获取模型支持的类别失败')
    modelClasses.value = []
  }
}

const submitForm = async () => {
  if (!formRef.value) return
  
  formError.value = ''
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      // 处理表单数据
      const formData = JSON.parse(JSON.stringify(form)) // 深拷贝避免修改原始表单
      
      // 根据频率类型设置
      if (frequencyType.value === 'interval') {
        delete formData.cron_expression
      } else {
        delete formData.interval
      }
      
      // 发送请求
      await crowdAnalysisApi.createAnalysisJob(formData)
      ElMessage.success('创建成功')
      router.push('/crowd-analysis')
    } catch (error) {
      // console.error('创建任务失败:', error)
      
      let errorMessage = '创建失败'
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
      
      formError.value = errorMessage
      ElMessage.error(errorMessage)
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.create-crowd-analysis {
  width: 100%;
}
.header {
  margin-bottom: 20px;
}
.form {
  max-width: 800px;
}
.cron-hint, .hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 5px;
}

.model-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-option, .class-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.class-id {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}
</style>
