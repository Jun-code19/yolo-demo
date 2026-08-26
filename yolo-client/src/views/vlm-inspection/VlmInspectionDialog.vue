<template>
  <el-dialog
    :model-value="modelValue"
    :title="isEdit ? '编辑 VLM 巡检任务' : '创建 VLM 巡检任务'"
    width="900px"
    top="5vh"
    destroy-on-close
    append-to-body
    class="high-priority-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-alert v-if="formError" :title="formError" type="error" show-icon closable @close="formError = ''" style="margin-bottom: 12px" />

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本设置" name="basic">
          <el-form-item label="任务名称" prop="job_name">
            <el-input v-model="form.job_name" placeholder="例如：园区夜间安全巡检" />
          </el-form-item>

          <el-form-item label="VLM 模型" prop="vlm_model_id">
            <el-select v-model="form.vlm_model_id" placeholder="请先在模型管理注册 VLM" teleported style="width: 100%">
              <el-option v-for="m in vlmModels" :key="m.model_id" :label="m.model_name" :value="m.model_id" />
            </el-select>
            <p v-if="!vlmModels.length" class="field-hint">
              暂无可用 VLM 模型，请前往
              <el-link type="primary" @click="goModelManagement">模型管理 · VLM 大模型</el-link>
              注册并配置 API Key。
            </p>
          </el-form-item>

          <el-form-item label="Prompt 模板" prop="prompt_id">
            <el-select v-model="form.prompt_id" teleported style="width: 100%" @change="handlePromptChange">
              <el-option v-for="p in prompts" :key="p.prompt_id" :label="p.name" :value="p.prompt_id">
                <div>{{ p.name }}</div>
                <div class="option-sub">{{ p.description }}</div>
              </el-option>
            </el-select>
            <p v-if="currentPromptDesc" class="field-hint">{{ currentPromptDesc }}</p>
          </el-form-item>

          <el-form-item label="告警标签">
            <el-select
              v-model="form.alert_labels"
              multiple
              filterable
              allow-create
              teleported
              style="width: 100%"
              placeholder="与 Prompt 中 label 对应，如 swimming、red_top"
            >
              <el-option v-for="label in suggestedLabels" :key="label" :label="label" :value="label" />
            </el-select>
            <p class="field-hint">只有 VLM 返回的 label 命中此处标签且置信度达标才会告警。可自由输入英文标签。</p>
          </el-form-item>

          <el-form-item label="最低置信度">
            <el-slider v-model="form.min_confidence" :min="0.1" :max="1" :step="0.05" show-input />
          </el-form-item>

          <el-form-item label="设备来源" prop="device_mode">
            <el-radio-group v-model="form.device_mode">
              <el-radio-button label="manual">按设备</el-radio-button>
              <el-radio-button label="group">按分组</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="form.device_mode === 'group'" label="设备分组" prop="group_id">
            <el-select v-model="form.group_id" filterable teleported style="width: 100%">
              <el-option v-for="g in deviceGroups" :key="g.group_id" :label="g.group_name" :value="g.group_id" />
            </el-select>
          </el-form-item>

          <el-form-item v-else label="监控设备" prop="device_ids">
            <el-select v-model="form.device_ids" multiple filterable teleported style="width: 100%">
              <el-option v-for="d in availableDevices" :key="d.device_id" :label="d.device_name" :value="d.device_id" />
            </el-select>
          </el-form-item>
        </el-tab-pane>

        <el-tab-pane label="巡检策略" name="schedule">
          <div class="form-row">
            <el-form-item label="整轮间隔（秒）" class="form-item">
              <el-input-number v-model="form.interval" :min="60" :max="86400" style="width: 100%" />
            </el-form-item>
            <el-form-item label="设备间隔（秒）" class="form-item">
              <el-input-number v-model="form.group_settings.device_interval_sec" :min="0" :max="600" :step="0.5" style="width: 100%" />
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="主取帧方式" class="form-item">
              <el-select v-model="form.group_settings.frame_source_primary" teleported style="width: 100%">
                <el-option label="API 截图" value="snapshot" />
                <el-option label="RTSP 单帧" value="rtsp" />
              </el-select>
            </el-form-item>
            <el-form-item label="备用取帧" class="form-item">
              <el-select v-model="form.group_settings.frame_source_fallback" teleported style="width: 100%">
                <el-option label="RTSP 单帧" value="rtsp" />
                <el-option label="API 截图" value="snapshot" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="生效时段">
            <WeeklyTimeSchedule v-model="weeklySchedule" />
          </el-form-item>
        </el-tab-pane>

        <el-tab-pane label="高级" name="advanced">
          <el-alert type="info" show-icon :closable="false" style="margin-bottom: 12px">
            <template #title>
              填写「自定义 Prompt」后会<strong>完全覆盖</strong>上方所选模板。可用 <code>{alert_labels}</code> 插入告警标签列表。
            </template>
          </el-alert>
          <el-form-item label="自定义 Prompt（覆盖模板）">
            <el-input
              v-model="form.prompt_override"
              type="textarea"
              :rows="10"
              :placeholder="customPromptPlaceholder"
            />
            <div class="prompt-actions">
              <el-button link type="primary" @click="fillSwimExample">填入：游泳检测示例</el-button>
              <el-button link type="primary" @click="fillFireExample">填入：明火烟雾示例</el-button>
              <el-button link type="primary" @click="fillClothingExample">填入：衣服颜色示例</el-button>
              <el-button link @click="form.prompt_override = ''">清空</el-button>
            </div>
          </el-form-item>
          <el-form-item label="推送标签">
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
              style="width: 120px"
              @keyup.enter="confirmTag"
              @blur="confirmTag"
            />
            <el-button v-else size="small" @click="showTagInput">+ 添加标签</el-button>
            <p class="field-hint">
              告警推送时会附带以上标签，以及 <code>vlm_inspection</code>、<code>vlm_alert</code>、<code>device_*</code>。
              数据推送配置的 tags 需包含任务标签或 <code>vlm_inspection</code> / <code>vlm_alert</code> 才能收到告警。
            </p>
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="2" />
          </el-form-item>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { vlmInspectionApi } from '@/api/vlm_inspection'
import deviceApi from '@/api/device'
import WeeklyTimeSchedule from '@/components/WeeklyTimeSchedule.vue'
import {
  createFullWeekSchedule,
  scheduleFromBackend,
  legacyRuntimeToSchedule,
  scheduleToBackend,
  isFullWeekSchedule
} from '@/utils/weeklySchedule'

const props = defineProps({
  modelValue: Boolean,
  isEdit: Boolean,
  jobId: String
})
const emit = defineEmits(['update:modelValue', 'saved'])

const router = useRouter()
const formRef = ref(null)
const activeTab = ref('basic')
const submitting = ref(false)
const formError = ref('')
const vlmModels = ref([])
const prompts = ref([])
const availableDevices = ref([])
const deviceGroups = ref([])
const weeklySchedule = ref(createFullWeekSchedule())
const inputVisible = ref(false)
const inputValue = ref('')
const tagInputRef = ref(null)
const defaultLabels = ['fire', 'smoke', 'fight', 'fall', 'smoking', 'swimming', 'red_top', 'blue_top']

const customPromptPlaceholder = `请根据实际画面分析，关注告警项：{alert_labels}

规则：
- 命中关注项时 findings 写入对应 label，confidence 0.85~1.0
- 未命中时 findings 为 []
- 禁止照抄下方 JSON 示例

输出 JSON（格式说明，非答案）：
{
  "findings": [{"label": "<命中时填写>", "confidence": 0.9, "description": "<实际描述>", "severity": "info"}],
  "summary": "<一句话总结；若命中可写「命中关注项：xxx」>",
  "needs_alert": false,
  "alert_labels": []
}`

const SWIM_PROMPT = `分析泳池/水域监控截图：
1. 是否有人游泳（label: swimming）
2. 是否存在溺水风险（label: drowning_risk）
3. 是否闯入禁区（label: unauthorized_entry）

规则：
- 命中「关注告警项」时必须在 findings 中写入，confidence 0.85~1.0
- 未命中时 findings 必须为 []
- 禁止照抄下方 JSON 示例

关注告警项：{alert_labels}

只输出 JSON（格式说明，非答案）：
{"findings":[{"label":"<命中时填写>","confidence":0.9,"description":"","severity":"info","attributes":{"person_count":0,"area":""}}],"summary":"","needs_alert":false,"alert_labels":[]}`

const FIRE_PROMPT = `检查图像中是否有明火、烟雾或异常热源。

规则：
- 确认存在时 findings 写入 fire 或 smoke，confidence 0.85~1.0
- 未发现时 findings 为 []
- 禁止照抄下方 JSON 示例

关注告警项：{alert_labels}

只输出 JSON（格式说明，非答案）：
{"findings":[{"label":"<命中时填 fire 或 smoke>","confidence":0.9,"description":"","severity":"critical"}],"summary":"","needs_alert":false,"alert_labels":[]}`

const CLOTHING_PROMPT = `识别画面中所有清晰可见人员的衣着颜色。
- label 用英文：red_top、blue_top、white_top、black_pants 等
- attributes 写 clothing_top、clothing_bottom（中文颜色）
- label 必须与 attributes 中的实际颜色一致
- 命中「关注告警项」时：必须在 findings 中写入该项，confidence 填 0.85~1.0
- 未命中时：findings 必须为 []
- 禁止照抄下方 JSON 示例中的 label 或数值

关注告警项：{alert_labels}

只输出 JSON（格式说明，非答案）：
{"findings":[{"label":"<命中时填写>","confidence":0.9,"description":"","severity":"info","attributes":{"clothing_top":"","clothing_bottom":""}}],"summary":"","needs_alert":false,"alert_labels":[]}`

const currentPromptDesc = computed(() => {
  const p = prompts.value.find(item => item.prompt_id === form.prompt_id)
  return p?.description || ''
})

const suggestedLabels = computed(() => {
  const p = prompts.value.find(item => item.prompt_id === form.prompt_id)
  const fromPrompt = p?.default_alert_labels || []
  return [...new Set([...fromPrompt, ...defaultLabels])]
})

const defaultGroupSettings = () => ({
  frame_source_primary: 'snapshot',
  frame_source_fallback: 'rtsp',
  device_interval_sec: 1
})

const form = reactive({
  job_name: '',
  device_mode: 'manual',
  group_id: '',
  device_ids: [],
  vlm_model_id: '',
  prompt_id: 'general_patrol_v1',
  prompt_override: '',
  alert_labels: ['fire', 'fight', 'fall'],
  min_confidence: 0.7,
  interval: 300,
  description: '',
  tags: ['vlm_inspection'],
  group_settings: defaultGroupSettings()
})

const rules = {
  job_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  vlm_model_id: [{ required: true, message: '请选择 VLM 模型', trigger: 'change' }],
  group_id: [{ validator: (_, v, cb) => (form.device_mode === 'group' && !v ? cb(new Error('请选择分组')) : cb()), trigger: 'change' }],
  device_ids: [{ validator: (_, v, cb) => (form.device_mode === 'manual' && (!v || !v.length) ? cb(new Error('请选择设备')) : cb()), trigger: 'change' }]
}

const buildRuntimeConfig = () => {
  const isAllTime = isFullWeekSchedule(weeklySchedule.value)
  const runtime = { time_period_mode: isAllTime ? 'all' : 'weekly' }
  if (!isAllTime) runtime.weekly_schedule = scheduleToBackend(weeklySchedule.value)
  return runtime
}

const applyRuntimeConfig = scheduleConfig => {
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
    vlm_model_id: '',
    prompt_id: 'general_patrol_v1',
    prompt_override: '',
    alert_labels: ['fire', 'fight', 'fall'],
    min_confidence: 0.7,
    interval: 300,
    description: '',
    tags: ['vlm_inspection'],
    group_settings: defaultGroupSettings()
  })
  weeklySchedule.value = createFullWeekSchedule()
  activeTab.value = 'basic'
  formError.value = ''
}

const loadOptions = async () => {
  const [modelsRes, promptsRes, devicesRes, groupsRes] = await Promise.all([
    vlmInspectionApi.getAvailableVlmModels(),
    vlmInspectionApi.getPrompts(),
    vlmInspectionApi.getAvailableDevices(),
    deviceApi.getDeviceGroups()
  ])
  vlmModels.value = modelsRes.data || []
  prompts.value = promptsRes.data || []
  availableDevices.value = devicesRes.data || []
  deviceGroups.value = groupsRes.data?.data || []
}

const goModelManagement = () => {
  emit('update:modelValue', false)
  router.push('/models/vlm')
}

const loadJob = async () => {
  const res = await vlmInspectionApi.getJob(props.jobId)
  const job = res.data
  Object.assign(form, {
    job_name: job.job_name,
    device_mode: job.device_mode || 'manual',
    group_id: job.group_id || '',
    device_ids: [...(job.device_ids || [])],
    vlm_model_id: job.vlm_model_id,
    prompt_id: job.prompt_id || 'general_patrol_v1',
    prompt_override: job.prompt_override || '',
    alert_labels: [...(job.alert_labels || [])],
    min_confidence: job.min_confidence ?? 0.7,
    interval: job.interval || 300,
    description: job.description || '',
    tags: [...(job.tags || ['vlm_inspection'])],
    group_settings: { ...defaultGroupSettings(), ...(job.group_settings || {}) }
  })
  applyRuntimeConfig(job.schedule_config || {})
}

const handlePromptChange = (promptId) => {
  const p = prompts.value.find(item => item.prompt_id === promptId)
  if (p?.default_alert_labels?.length) {
    form.alert_labels = [...p.default_alert_labels]
  }
  if (promptId === 'custom_freeform_v1') {
    activeTab.value = 'advanced'
  }
}

const fillSwimExample = () => {
  form.prompt_override = SWIM_PROMPT
  form.alert_labels = ['swimming', 'drowning_risk', 'unauthorized_entry']
  activeTab.value = 'advanced'
}

const fillFireExample = () => {
  form.prompt_override = FIRE_PROMPT
  form.alert_labels = ['fire', 'smoke']
  activeTab.value = 'advanced'
}

const fillClothingExample = () => {
  form.prompt_override = CLOTHING_PROMPT
  form.alert_labels = ['red_top', 'blue_top', 'yellow_top', 'black_top', 'white_top']
  activeTab.value = 'advanced'
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
  if (payload.device_mode === 'group') delete payload.device_ids
  else payload.group_id = null
  return payload
}

const submitForm = async () => {
  if (!formRef.value) return
  formError.value = ''
  await formRef.value.validate(async valid => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = buildPayload()
      if (props.isEdit) {
        await vlmInspectionApi.updateJob(props.jobId, payload)
        ElMessage.success('更新成功')
        emit('saved', { created: false })
      } else {
        await vlmInspectionApi.createJob(payload)
        ElMessage.success('创建成功')
        emit('saved', { created: true })
      }
      emit('update:modelValue', false)
    } catch (e) {
      formError.value = e.response?.data?.detail || e.message || '保存失败'
    } finally {
      submitting.value = false
    }
  })
}

watch(() => props.modelValue, async visible => {
  if (!visible) return
  resetForm()
  await loadOptions()
  if (props.isEdit && props.jobId) await loadJob()
})

watch(() => form.device_mode, mode => {
  if (mode === 'group') form.device_ids = []
  else form.group_id = ''
})
</script>

<style scoped>
.form-row {
  display: flex;
  gap: 16px;
}
.form-item {
  flex: 1;
}
.model-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.option-sub {
  font-size: 12px;
  color: #909399;
}
.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
.prompt-actions {
  margin-top: 8px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.field-hint code,
.el-alert code {
  font-size: 12px;
  background: #f4f4f5;
  padding: 0 4px;
  border-radius: 3px;
}
</style>
