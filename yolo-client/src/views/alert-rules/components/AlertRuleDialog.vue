<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑规则' : '新建规则'"
    width="50%"
    top="5vh"
    destroy-on-close
    append-to-body
    class="rule-dialog high-priority-dialog"
    @closed="handleClosed"
  >
    <div v-loading="referenceLoading" class="dialog-body">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-divider content-position="left">基本信息</el-divider>

        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：VLM 火情 + 区域聚众" />
        </el-form-item>

        <div class="form-row-2">
          <el-form-item label="设备">
            <el-select
              v-model="form.device_id"
              clearable
              filterable
              placeholder="全部"
              class="w-full"
              popper-class="rule-select-popper"
            >
              <el-option
                v-for="device in deviceList"
                :key="device.device_id"
                :label="formatDeviceLabel(device)"
                :value="device.device_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="推送标签">
            <el-select
              v-model="form.push_tags"
              clearable
              filterable
              allow-create
              default-first-option
              placeholder="匹配推送配置"
              class="w-full"
              popper-class="rule-select-popper"
            >
              <el-option v-for="tag in pushTagOptions" :key="tag" :label="tag" :value="tag" />
            </el-select>
          </el-form-item>
        </div>

        <div class="form-row-3">
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="form.priority" :min="0" :max="10000" controls-position="right" class="w-full" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" placeholder="可选" />
          </el-form-item>
        </div>

        <el-divider content-position="left">匹配逻辑</el-divider>

        <div class="form-row-2">
          <el-form-item label="组合">
            <el-radio-group v-model="form.definition.logic">
              <el-radio-button value="AND">全部满足</el-radio-button>
              <el-radio-button value="OR">任一满足</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="同设备">
            <el-switch v-model="form.definition.same_device" />
          </el-form-item>
        </div>

        <div class="form-row-3 timing-row">
          <el-form-item label="窗口">
            <el-input-number v-model="form.definition.window_sec" :min="10" :max="86400" controls-position="right" class="w-full" />
          </el-form-item>
          <el-form-item label="持续">
            <el-input-number v-model="form.definition.duration_sec" :min="0" :max="86400" controls-position="right" class="w-full" />
          </el-form-item>
          <el-form-item label="冷却">
            <el-input-number v-model="form.definition.cooldown_sec" :min="0" :max="86400" controls-position="right" class="w-full" />
          </el-form-item>
        </div>
        <div class="timing-help">
          <span>窗口</span> 扫描最近 N 秒事件，AND 时各条件须在此范围内；
          <span>持续</span> 条件须连续满足秒数（0=即时）；
          <span>冷却</span> 命中后 N 秒内不重复告警。
        </div>

        <el-divider content-position="left">
          <span>触发条件</span>
          <el-button type="primary" link class="divider-btn" @click="addCondition">添加</el-button>
        </el-divider>

        <div v-for="(cond, index) in form.definition.conditions" :key="index" class="cond-block">
          <div class="cond-row">
            <span class="cond-idx">{{ index + 1 }}</span>
            <el-select
              v-model="cond.source"
              class="cond-source"
              popper-class="rule-select-popper"
              @change="resetConditionFields(cond)"
            >
              <el-option v-for="opt in SOURCE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>

            <template v-if="cond.source === 'vlm_finding'">
              <el-select
                v-model="cond.job_id"
                clearable
                filterable
                placeholder="巡检任务"
                class="cond-field"
                popper-class="rule-select-popper"
                @change="onVlmJobChange(cond)"
              >
                <el-option
                  v-for="job in vlmJobs"
                  :key="job.job_id"
                  :label="formatVlmJobLabel(job)"
                  :value="job.job_id"
                />
              </el-select>
              <el-select
                v-model="cond.labels"
                multiple
                collapse-tags
                collapse-tags-tooltip
                clearable
                filterable
                allow-create
                :disabled="!cond.job_id"
                :placeholder="vlmLabelPlaceholder(cond)"
                class="cond-field"
                popper-class="rule-select-popper"
                @change="onVlmLabelsChange(cond)"
              >
                <el-option
                  v-for="label in getVlmLabelOptions(cond.job_id)"
                  :key="label"
                  :label="label"
                  :value="label"
                />
              </el-select>
              <el-checkbox v-model="cond.needs_alert_only" class="cond-check">仅告警</el-checkbox>
            </template>

            <template v-else-if="cond.source === 'detection_event'">
              <el-select
                v-model="cond.event_type"
                clearable
                filterable
                placeholder="事件大类"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option v-for="opt in DETECTION_EVENT_TYPES" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
              <el-select
                v-model="cond.scenario_type"
                clearable
                filterable
                placeholder="场景类型"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option v-for="opt in SCENARIO_TYPES" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
              <el-select
                v-model="cond.label"
                clearable
                filterable
                allow-create
                placeholder="子事件类型"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option
                  v-for="opt in DETECTION_META_EVENT_TYPES"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </template>

            <template v-else-if="cond.source === 'external_event'">
              <el-select
                v-model="cond.event_type"
                clearable
                placeholder="事件类型"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option v-for="opt in EXTERNAL_EVENT_TYPES" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
              <el-select
                v-model="cond.label"
                clearable
                filterable
                allow-create
                placeholder="引擎名称（可选）"
                class="cond-field"
                popper-class="rule-select-popper"
              />
            </template>

            <template v-else-if="cond.source === 'smart_event'">
              <el-select
                v-model="cond.scheme_id"
                clearable
                filterable
                placeholder="订阅方案"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option
                  v-for="scheme in smartSchemes"
                  :key="scheme.id"
                  :label="formatSchemeLabel(scheme)"
                  :value="scheme.id"
                />
              </el-select>
              <el-select
                v-model="cond.event_type"
                clearable
                filterable
                placeholder="订阅事件类型"
                class="cond-field"
                popper-class="rule-select-popper"
              >
                <el-option v-for="opt in SMART_EVENT_TYPES" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </template>

            <el-button
              type="danger"
              link
              :disabled="form.definition.conditions.length <= 1"
              class="cond-del"
              @click="removeCondition(index)"
            >
              删除
            </el-button>
          </div>
          <div v-if="cond.source === 'vlm_finding' && cond.job_id && !getVlmLabelOptions(cond.job_id).length" class="cond-hint">
            该任务未配置告警标签，可在 VLM 巡检任务中设置 alert_labels，或手动输入标签（多选时任一命中即可）。
          </div>
        </div>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import alertRuleApi, {
  SOURCE_OPTIONS,
  DETECTION_EVENT_TYPES,
  DETECTION_META_EVENT_TYPES,
  SCENARIO_TYPES,
  EXTERNAL_EVENT_TYPES,
  SMART_EVENT_TYPES,
  defaultCondition,
  defaultDefinition,
  normalizeListResponse
} from '@/api/alert_rule'
import deviceApi from '@/api/device'
import smartSchemeApi from '@/api/smart_scheme'
import { usePushConfigTags } from '@/composables/usePushConfigTags'

const emit = defineEmits(['saved'])

const visible = ref(false)
const isEdit = ref(false)
const editingId = ref('')
const submitting = ref(false)
const referenceLoading = ref(false)
const formRef = ref(null)
const deviceList = ref([])
const vlmJobs = ref([])
const smartSchemes = ref([])
const { pushTagOptions, loadPushConfigTags } = usePushConfigTags()

const form = reactive({
  name: '',
  description: '',
  enabled: true,
  device_id: '',
  priority: 100,
  push_tags: '',
  definition: defaultDefinition()
})

const rules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }]
}

const formatDeviceLabel = (device) => {
  const name = device.device_name || device.device_id
  return device.ip_address ? `${name} (${device.ip_address})` : name
}

const formatVlmJobLabel = (job) => job.job_name || job.job_id

const formatSchemeLabel = (scheme) => {
  const name = scheme.camera_name || scheme.camera_id || scheme.id
  const types = (scheme.event_types || []).join('/')
  return types ? `${name} (${types})` : name
}

const getVlmLabelOptions = (jobId) => {
  if (!jobId) return []
  const job = vlmJobs.value.find(item => item.job_id === jobId)
  return job?.alert_labels || []
}

const vlmLabelPlaceholder = (cond) => {
  if (!cond.job_id) return '请先选择巡检任务'
  const options = getVlmLabelOptions(cond.job_id)
  return options.length ? '命中告警标签' : '输入告警标签'
}

const onVlmJobChange = (cond) => {
  const options = getVlmLabelOptions(cond.job_id)
  if (Array.isArray(cond.labels) && cond.labels.length && options.length) {
    cond.labels = cond.labels.filter(item => options.includes(item))
  }
  cond.label = ''
}

const onVlmLabelsChange = (cond) => {
  if (!Array.isArray(cond.labels)) {
    cond.labels = []
  }
  cond.label = ''
}

const resetConditionFields = (cond) => {
  cond.label = ''
  cond.labels = []
  cond.event_type = ''
  cond.job_id = ''
  cond.needs_alert_only = cond.source === 'vlm_finding'
  cond.scenario_type = ''
  cond.scenario_id = ''
  cond.analysis_type = ''
  cond.scheme_id = ''
}

const addCondition = () => {
  form.definition.conditions.push(defaultCondition())
}

const removeCondition = (index) => {
  form.definition.conditions.splice(index, 1)
}

const resetForm = () => {
  form.name = ''
  form.description = ''
  form.enabled = true
  form.device_id = ''
  form.priority = 100
  form.push_tags = ''
  form.definition = defaultDefinition()
}

const loadReferenceData = async () => {
  referenceLoading.value = true
  try {
    const results = await Promise.allSettled([
      deviceApi.getDevices({ skip: 0, limit: 500 }),
      alertRuleApi.getReferenceVlmJobs({ limit: 500 }),
      smartSchemeApi.getSchemes({ page: 1, page_size: 500 }),
      loadPushConfigTags()
    ])

    if (results[0].status === 'fulfilled') {
      deviceList.value = normalizeListResponse(results[0].value.data)
    } else {
      deviceList.value = []
    }

    if (results[1].status === 'fulfilled') {
      const payload = results[1].value.data
      vlmJobs.value = Array.isArray(payload) ? payload : normalizeListResponse(payload)
    } else {
      vlmJobs.value = []
      ElMessage.warning('巡检任务加载失败，请确认 data-server 已启动并已迁移 VLM 表')
    }

    if (results[2].status === 'fulfilled') {
      smartSchemes.value = normalizeListResponse(results[2].value.data)
    } else {
      smartSchemes.value = []
    }
  } catch {
    deviceList.value = []
    vlmJobs.value = []
    smartSchemes.value = []
    ElMessage.warning('选项加载失败，请确认服务已启动')
  } finally {
    referenceLoading.value = false
  }
}

const openCreate = async () => {
  isEdit.value = false
  editingId.value = ''
  resetForm()
  visible.value = true
  await loadReferenceData()
}

const openEdit = async (row) => {
  isEdit.value = true
  editingId.value = row.rule_id
  form.name = row.name
  form.description = row.description || ''
  form.enabled = row.enabled
  form.device_id = row.device_id || ''
  form.priority = row.priority ?? 100
  form.push_tags = row.push_tags || ''
  form.definition = {
    ...defaultDefinition(),
    ...(row.definition || {}),
    conditions: (row.definition?.conditions?.length ? row.definition.conditions : [defaultCondition()]).map(item => {
      const merged = {
        ...defaultCondition(),
        ...item,
        needs_alert_only: item.needs_alert_only !== false
      }
      if ((!merged.labels || !merged.labels.length) && merged.label) {
        merged.labels = [merged.label]
      }
      if (!Array.isArray(merged.labels)) {
        merged.labels = []
      }
      return merged
    })
  }
  visible.value = true
  await loadReferenceData()
}

const cleanCondition = (cond) => {
  const payload = { source: cond.source }
  if (cond.source === 'vlm_finding') {
    if (cond.job_id) payload.job_id = cond.job_id
    payload.needs_alert_only = cond.needs_alert_only !== false
    if (Array.isArray(cond.labels) && cond.labels.length) {
      payload.labels = cond.labels.map(item => String(item).trim()).filter(Boolean)
    } else if (cond.label) {
      payload.label = cond.label
    }
  } else if (cond.source === 'detection_event') {
    if (cond.event_type) payload.event_type = cond.event_type
    if (cond.scenario_type) payload.scenario_type = cond.scenario_type
    if (cond.scenario_id) payload.scenario_id = cond.scenario_id
    if (cond.analysis_type) payload.analysis_type = cond.analysis_type
    if (cond.label) payload.label = cond.label
  } else if (cond.source === 'smart_event') {
    if (cond.scheme_id) payload.scheme_id = cond.scheme_id
    if (cond.event_type) payload.event_type = cond.event_type
    if (cond.label) payload.label = cond.label
  } else {
    if (cond.event_type) payload.event_type = cond.event_type
    if (cond.label) payload.label = cond.label
  }
  return payload
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  if (!form.definition.conditions.length) {
    ElMessage.warning('请至少添加一个条件')
    return
  }

  const payload = {
    name: form.name,
    description: form.description || null,
    enabled: form.enabled,
    device_id: form.device_id || null,
    priority: form.priority,
    push_tags: form.push_tags || null,
    definition: {
      logic: form.definition.logic,
      same_device: form.definition.same_device,
      window_sec: form.definition.window_sec,
      duration_sec: form.definition.duration_sec,
      cooldown_sec: form.definition.cooldown_sec,
      conditions: form.definition.conditions.map(cleanCondition)
    }
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      await alertRuleApi.updateRule(editingId.value, payload)
      ElMessage.success('规则已更新')
    } else {
      await alertRuleApi.createRule(payload)
      ElMessage.success('规则已创建')
    }
    visible.value = false
    emit('saved')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

const handleClosed = () => {
  formRef.value?.resetFields()
}

defineExpose({ openCreate, openEdit })
</script>

<style scoped>
.dialog-body {
  max-height: calc(80vh - 120px);
  overflow-x: hidden;
  overflow-y: auto;
}

.w-full {
  width: 100%;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0 12px;
}

.timing-row :deep(.el-form-item__label) {
  font-size: 12px;
}

.timing-help {
  margin: -4px 0 8px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
  background: #f5f7fa;
  border-radius: 4px;
}

.timing-help span {
  color: #606266;
  font-weight: 500;
}

.divider-btn {
  margin-left: 8px;
  vertical-align: baseline;
}

.cond-block {
  border-bottom: 1px solid #f0f2f5;
}

.cond-block:last-child {
  border-bottom: none;
}

.cond-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
}

.cond-hint {
  margin: 0 0 8px 28px;
  font-size: 12px;
  color: #e6a23c;
  line-height: 1.5;
}

.cond-idx {
  flex: 0 0 20px;
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.cond-source {
  width: 120px;
  flex-shrink: 0;
}

.cond-field {
  flex: 1;
  min-width: 100px;
}

.cond-check {
  flex-shrink: 0;
  margin-right: 4px;
}

.cond-del {
  margin-left: auto;
  flex-shrink: 0;
}

:deep(.el-divider) {
  margin: 20px 0 16px;
}

:deep(.el-divider__text) {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-input-number.w-full) {
  width: 100%;
}
</style>

<style>
.rule-dialog .el-dialog__body {
  padding: 16px 20px 8px;
  overflow-x: hidden;
}

.high-priority-dialog {
  z-index: 999999 !important;
}

.rule-select-popper {
  z-index: 1000000 !important;
}
</style>
