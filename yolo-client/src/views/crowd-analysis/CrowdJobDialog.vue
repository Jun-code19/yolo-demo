<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑人群分析任务' : '创建人群分析任务'"
    width="920px"
    top="5vh"
    destroy-on-close
    append-to-body
    class="crowd-job-dialog high-priority-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-alert
      v-if="formError"
      title="保存失败"
      :description="formError"
      type="error"
      show-icon
      closable
      @close="formError = ''"
      style="margin-bottom: 15px"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="config-form">
      <el-tabs v-model="activeTab" class="config-tabs">
        <el-tab-pane label="基本设置" name="basic">
          <div class="section-container">
            <el-form-item label="任务名称" prop="job_name">
              <el-input v-model="form.job_name" placeholder="请输入任务名称" />
            </el-form-item>

            <el-form-item label="设备来源" prop="device_mode">
              <el-radio-group v-model="form.device_mode">
                <el-radio-button value="manual">按设备</el-radio-button>
                <el-radio-button value="group">按分组</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item v-if="form.device_mode === 'group'" label="设备分组" prop="group_id">
              <el-select
                v-model="form.group_id"
                placeholder="请选择设备分组"
                filterable
                teleported
                style="width: 100%"
                @change="handleGroupChange"
              >
                <el-option
                  v-for="group in deviceGroups"
                  :key="group.group_id"
                  :label="`${group.group_name} (${group.device_count || 0}台)`"
                  :value="group.group_id"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-else label="监控设备" prop="device_ids">
              <el-select
                v-model="form.device_ids"
                multiple
                filterable
                teleported
                placeholder="请选择监控设备"
                style="width: 100%"
              >
                <el-option
                  v-for="device in availableDevices"
                  :key="device.device_id"
                  :label="device.device_name"
                  :value="device.device_id"
                >
                  <span>{{ device.device_name }}</span>
                  <span v-if="device.location" class="option-sub">({{ device.location }})</span>
                </el-option>
              </el-select>
            </el-form-item>

            <div class="form-row form-row-polling">
              <el-form-item label="主取帧方式" class="form-item">
                <el-select v-model="form.group_settings.frame_source_primary" teleported style="width: 100%">
                  <el-option label="API 截图" value="snapshot" />
                  <el-option label="RTSP 单帧" value="rtsp" />
                </el-select>
              </el-form-item>
              <el-form-item label="备用取帧" class="form-item">
                <el-select v-model="form.group_settings.frame_source_fallback" teleported style="width: 100%">
                  <el-option label="API 截图" value="snapshot" />
                  <el-option label="RTSP 单帧" value="rtsp" />
                </el-select>
              </el-form-item>
              <el-form-item label="设备间隔" class="form-item form-item-compact-number">
                <div class="input-with-unit">
                  <el-input-number
                    v-model="form.group_settings.device_interval_sec"
                    :min="0"
                    :max="3600"
                    :step="0.5"
                    :precision="1"
                    controls-position="right"
                  />
                  <span class="unit-label">秒/台</span>
                </div>
              </el-form-item>
              <el-form-item label="整轮间隔" prop="interval" class="form-item form-item-compact-number">
                <div class="input-with-unit">
                  <el-input-number
                    v-model="form.interval"
                    :min="60"
                    :max="86400"
                    :step="60"
                    controls-position="right"
                  />
                  <span class="unit-label">秒/轮</span>
                </div>
              </el-form-item>
            </div>

            <div class="form-row form-row-three">
              <el-form-item label="检测模型" prop="models_id" class="form-item">
                <el-select
                  v-model="form.models_id"
                  placeholder="请选择检测模型"
                  filterable
                  teleported
                  style="width: 100%"
                  @change="handleModelChange"
                >
                  <el-option
                    v-for="model in availableModels"
                    :key="model.model_id"
                    :label="`${model.model_name} (${getModelTypeName(model.model_type)})`"
                    :value="model.model_id"
                  />
                </el-select>
              </el-form-item>

              <el-form-item prop="detect_classes" class="form-item form-item-classes">
                <template #label>
                  <div class="form-item-label-row">
                    <span>目标类别</span>
                    <span v-if="modelClasses.length > 0" class="label-extra">
                      <el-button link size="small" @click.stop="selectAllClasses">全选</el-button>
                      <el-button
                        link
                        size="small"
                        @click.stop="clearAllClasses"
                        v-if="form.detect_classes.length > 0"
                      >
                        清空
                      </el-button>
                      <span class="selected-count">{{ form.detect_classes.length }}/{{ modelClasses.length }}</span>
                    </span>
                  </div>
                </template>
                <el-select
                  v-model="form.detect_classes"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                  filterable
                  teleported
                  placeholder="请选择目标类别"
                  style="width: 100%"
                >
                  <el-option
                    v-for="classItem in modelClasses"
                    :key="classItem.value"
                    :label="classItem.label"
                    :value="classItem.value"
                  >
                    <div class="class-option">
                      <span>{{ classItem.label }}</span>
                      <span class="class-id">{{ classItem.value }}</span>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>

              <el-form-item label="置信度阈值" prop="confidence_threshold" class="form-item sensitivity-item">
                <div class="sensitivity-control">
                  <el-input-number
                    v-model="form.confidence_threshold"
                    :min="0.1"
                    :max="0.9"
                    :step="0.05"
                    :precision="2"
                    controls-position="right"
                    class="sensitivity-input"
                  />
                  <div class="sensitivity-presets">
                    <button
                      v-for="preset in confidencePresets"
                      :key="preset.value"
                      type="button"
                      class="sensitivity-preset"
                      :class="{ active: isConfidencePresetActive(preset.value) }"
                      @click="form.confidence_threshold = preset.value"
                    >
                      {{ preset.label }}
                    </button>
                  </div>
                </div>
              </el-form-item>
            </div>
   
          </div>
        </el-tab-pane>

        <el-tab-pane label="运行策略" name="runtime">
          <div class="runtime-panel">
            <el-form-item label="生效时段" class="runtime-schedule-item">
              <WeeklyTimeSchedule v-model="weeklySchedule" />
            </el-form-item>
          </div>
        </el-tab-pane>

        <el-tab-pane label="高级设置" name="advanced">
          <el-form-item label="推送模式">
            <el-radio-group v-model="form.group_settings.push_mode">
              <el-radio value="per_device">逐设备推送</el-radio>
              <el-radio value="bundled">打包 JSON 推送</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="标签">
            <el-tag
              v-for="tag in form.tags"
              :key="tag"
              closable
              style="margin-right: 5px"
              @close="removeTag(tag)"
            >
              {{ tag }}
            </el-tag>
            <el-input
              v-if="inputVisible"
              ref="tagInputRef"
              v-model="inputValue"
              size="small"
              @keyup.enter="confirmTag"
              @blur="confirmTag"
            />
            <el-button v-else size="small" @click="showTagInput">+ 添加标签</el-button>
          </el-form-item>

          <el-form-item label="位置名称">
            <el-input v-model="form.location_info.name" placeholder="位置名称" />
          </el-form-item>

          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="经度">
                <el-input v-model="form.location_info.coordinates[0]" type="number" placeholder="经度" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="纬度">
                <el-input v-model="form.location_info.coordinates[1]" type="number" placeholder="纬度" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="详细地址">
            <el-input v-model="form.location_info.address" placeholder="详细地址" />
          </el-form-item>

          <el-form-item label="人数预警阈值">
            <el-input-number v-model="form.warning_threshold" :min="0" />
            <div class="hint">0 表示不预警</div>
          </el-form-item>

          <el-form-item label="预警消息">
            <el-input v-model="form.warning_message" placeholder="支持 {location}、{count}、{threshold} 等变量" />
          </el-form-item>

          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" placeholder="任务描述" />
          </el-form-item>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)" :disabled="submitting">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitForm">
        {{ isEdit ? '保存修改' : '创建任务' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import deviceApi from '@/api/device'
import WeeklyTimeSchedule from '@/components/WeeklyTimeSchedule.vue'
import {
  createFullWeekSchedule,
  isFullWeekSchedule,
  scheduleToBackend,
  scheduleFromBackend,
  legacyRuntimeToSchedule
} from '@/utils/weeklySchedule'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  isEdit: { type: Boolean, default: false },
  jobId: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const formRef = ref(null)
const tagInputRef = ref(null)
const submitting = ref(false)
const formError = ref('')
const activeTab = ref('basic')
const inputVisible = ref(false)
const inputValue = ref('')
const availableDevices = ref([])
const availableModels = ref([])
const deviceGroups = ref([])
const modelClasses = ref([])
const weeklySchedule = ref(createFullWeekSchedule())

const defaultGroupSettings = () => ({
  frame_source_primary: 'snapshot',
  frame_source_fallback: 'rtsp',
  device_interval_sec: 1,
  push_mode: 'per_device'
})

const form = reactive({
  job_name: '',
  device_mode: 'manual',
  group_id: '',
  device_ids: [],
  models_id: '',
  detect_classes: [],
  confidence_threshold: 0.5,
  interval: 300,
  tags: ['crowd_analysis'],
  group_settings: defaultGroupSettings(),
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
  models_id: [{ required: true, message: '请选择检测模型', trigger: 'change' }],
  group_id: [{
    validator: (_, __, cb) => {
      if (form.device_mode === 'group' && !form.group_id) cb(new Error('请选择设备分组'))
      else cb()
    },
    trigger: 'change'
  }],
  device_ids: [{
    validator: (_, __, cb) => {
      if (form.device_mode === 'manual' && (!form.device_ids || !form.device_ids.length)) {
        cb(new Error('请选择至少一个监控设备'))
      } else cb()
    },
    trigger: 'change'
  }],
  interval: [{
    validator: (_, value, cb) => {
      if (value == null || value < 60) cb(new Error('整轮间隔不能小于60秒'))
      else cb()
    },
    trigger: 'change'
  }]
}

const getModelTypeName = (type) => {
  const map = {
    object_detection: '目标检测',
    smart_behavior: '智能行为',
    smart_counting: '智能人数统计'
  }
  return map[type] || type || '模型'
}

const confidencePresets = [
  { label: '低', value: 0.3 },
  { label: '中', value: 0.5 },
  { label: '高', value: 0.7 }
]

const isConfidencePresetActive = (value) => Math.abs(form.confidence_threshold - value) < 0.001

const selectAllClasses = () => {
  form.detect_classes = modelClasses.value.map(item => item.value)
}

const clearAllClasses = () => {
  form.detect_classes = []
}

const buildRuntimeConfig = () => {
  const isAllTime = isFullWeekSchedule(weeklySchedule.value)
  const runtime = { time_period_mode: isAllTime ? 'all' : 'weekly' }
  if (!isAllTime) {
    runtime.weekly_schedule = scheduleToBackend(weeklySchedule.value)
  }
  return runtime
}

const applyRuntimeConfig = (scheduleConfig) => {
  const runtime = scheduleConfig?.runtime || {}
  if (runtime.time_period_mode === 'weekly' && runtime.weekly_schedule) {
    weeklySchedule.value = scheduleFromBackend(runtime.weekly_schedule)
  } else {
    weeklySchedule.value = legacyRuntimeToSchedule(runtime)
  }
}

const resetForm = () => {
  Object.assign(form, {
    job_name: '',
    device_mode: 'manual',
    group_id: '',
    device_ids: [],
    models_id: '',
    detect_classes: [],
    confidence_threshold: 0.5,
    interval: 300,
    tags: ['crowd_analysis'],
    group_settings: defaultGroupSettings(),
    location_info: { name: '', coordinates: [0, 0], address: '', area_code: '' },
    warning_threshold: 0,
    warning_message: '人群密度预警：{location}区域人数达到{count}人，超过预警阈值({threshold}人)',
    description: ''
  })
  weeklySchedule.value = createFullWeekSchedule()
  activeTab.value = 'basic'
  formError.value = ''
  modelClasses.value = []
}

const isCrowdAnalysisModel = (model) => {
  const type = (model?.model_type || model?.models_type || '').toLowerCase()
  return type !== 'vlm' && model?.is_active
}

const loadOptions = async () => {
  const [devicesRes, modelsRes, groupsRes] = await Promise.all([
    crowdAnalysisApi.getAvailableDevices(),
    crowdAnalysisApi.getAvailableModels(),
    deviceApi.getDeviceGroups()
  ])
  availableDevices.value = devicesRes.data || []
  availableModels.value = (modelsRes.data || []).filter(isCrowdAnalysisModel)
  deviceGroups.value = groupsRes.data?.data || []
}

const loadJob = async () => {
  const res = await crowdAnalysisApi.getAnalysisJob(props.jobId)
  const job = res.data
  Object.assign(form, {
    job_name: job.job_name,
    device_mode: job.device_mode || 'manual',
    group_id: job.group_id || '',
    device_ids: [...(job.device_ids || [])],
    models_id: job.models_id || '',
    detect_classes: [...(job.detect_classes || [])],
    confidence_threshold: job.confidence_threshold || 0.5,
    interval: job.interval || 300,
    tags: [...(job.tags || ['crowd_analysis'])],
    group_settings: { ...defaultGroupSettings(), ...(job.group_settings || {}) },
    location_info: {
      name: job.location_info?.name || '',
      coordinates: [...(job.location_info?.coordinates || [0, 0])],
      address: job.location_info?.address || '',
      area_code: job.location_info?.area_code || ''
    },
    warning_threshold: job.warning_threshold || 0,
    warning_message: job.warning_message || form.warning_message,
    description: job.description || ''
  })
  applyRuntimeConfig(job.schedule_config || {})
  if (job.models_id) await handleModelChange(job.models_id, true)
}

const handleGroupChange = (groupId) => {
  form.device_ids = []
  const group = deviceGroups.value.find(item => item.group_id === groupId)
  if (group?.group_name) {
    form.job_name = group.group_name
  }
}

const handleModelChange = async (modelId, preserveSelection = false) => {
  if (!modelId) {
    modelClasses.value = []
    if (!preserveSelection) form.detect_classes = []
    return
  }
  try {
    const res = await crowdAnalysisApi.getModelClasses(modelId)
    const classesObj = res.data.classes || {}
    modelClasses.value = Object.entries(classesObj).map(([key, name]) => ({
      label: name,
      value: key
    }))
    if (!preserveSelection && modelClasses.value.length) {
      form.detect_classes = [modelClasses.value[0].value]
    }
  } catch {
    modelClasses.value = []
  }
}

const removeTag = (tag) => {
  form.tags.splice(form.tags.indexOf(tag), 1)
}

const showTagInput = () => {
  inputVisible.value = true
  nextTick(() => tagInputRef.value?.focus())
}

const confirmTag = () => {
  const value = inputValue.value.trim()
  if (value && !form.tags.includes(value)) form.tags.push(value)
  inputVisible.value = false
  inputValue.value = ''
}

const buildPayload = () => {
  const payload = JSON.parse(JSON.stringify(form))
  payload.schedule_config = { runtime: buildRuntimeConfig() }
  payload.cron_expression = null
  if (payload.device_mode === 'group') {
    delete payload.device_ids
  } else {
    payload.group_id = null
  }
  return payload
}

const submitForm = async () => {
  if (!formRef.value) return
  formError.value = ''
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = buildPayload()
      if (props.isEdit) {
        await crowdAnalysisApi.updateAnalysisJob(props.jobId, payload)
        ElMessage.success('更新成功')
      } else {
        await crowdAnalysisApi.createAnalysisJob(payload)
        ElMessage.success('创建成功')
      }
      emit('saved')
      emit('update:modelValue', false)
    } catch (error) {
      formError.value = error.response?.data?.detail || error.message || '保存失败'
      ElMessage.error(formError.value)
    } finally {
      submitting.value = false
    }
  })
}

watch(() => props.modelValue, async (visible) => {
  if (!visible) return
  resetForm()
  await loadOptions()
  if (props.isEdit && props.jobId) {
    await loadJob()
  }
})

watch(() => form.device_mode, (mode) => {
  if (mode === 'group') {
    form.device_ids = []
    if (form.group_id) handleGroupChange(form.group_id)
  } else {
    form.group_id = ''
  }
})
</script>

<style scoped>
.section-container {
  padding: 4px 8px 12px 8px;
}

.form-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.form-row-three {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: flex-start;
  margin-top: 12px;
  padding-top: 8px;
}

.form-row-three .form-item {
  flex: 1;
  min-width: 0;
  margin-bottom: 0;
}

.form-row-three .form-item-classes {
  flex: 1.2;
}

.form-row-three .sensitivity-item {
  flex: 0 0 240px;
  max-width: 260px;
}

.sensitivity-item :deep(.el-form-item__content) {
  width: 100%;
}

.sensitivity-control {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.sensitivity-input {
  width: 100%;
}

.sensitivity-input :deep(.el-input-number) {
  width: 100%;
}

.sensitivity-presets {
  display: flex;
  gap: 4px;
  width: 100%;
}

.sensitivity-preset {
  flex: 1;
  min-width: 0;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
  border-radius: 4px;
  padding: 0 4px;
  height: 28px;
  line-height: 26px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.sensitivity-preset:hover {
  color: #409eff;
  border-color: #c6e2ff;
}

.sensitivity-preset.active {
  color: #409eff;
  border-color: #409eff;
  background: #ecf5ff;
  font-weight: 500;
}

.form-item-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}

.label-extra {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-weight: normal;
}

.label-extra .selected-count {
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}

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

.form-row-polling {
  flex-wrap: nowrap;
  align-items: flex-start;
  margin-top: 8px;
  margin-bottom: 4px;
}

.form-row-polling .form-item {
  flex: 1;
  min-width: 0;
  margin-bottom: 0;
}

.form-row-polling .form-item-compact-number {
  flex: 0 0 148px;
  max-width: 160px;
}

.form-row-polling .input-with-unit {
  flex-wrap: nowrap;
}

.form-row-polling .input-with-unit :deep(.el-input-number) {
  width: 100%;
}

.form-row-polling .unit-label {
  white-space: nowrap;
  font-size: 12px;
}

@media (max-width: 900px) {
  .form-row-three {
    flex-direction: column;
  }

  .form-row-three .sensitivity-item {
    flex: 1 1 100%;
    max-width: none;
  }

  .form-row-polling {
    flex-wrap: wrap;
  }

  .form-row-polling .form-item-compact-number {
    flex: 1 1 calc(50% - 8px);
    max-width: none;
  }
}

.runtime-panel {
  padding: 8px 0;
}

.runtime-schedule-item :deep(.el-form-item__content) {
  width: 100%;
}

.input-with-unit {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit-label,
.hint,
.option-sub {
  font-size: 12px;
  color: #909399;
}

.hint {
  margin-top: 6px;
  line-height: 1.5;
}
</style>
