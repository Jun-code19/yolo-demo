<template>
  <div class="vlm-management">
    <el-tabs v-model="activePanel" class="vlm-tabs">
      <el-tab-pane label="VLM 模型" name="models">
        <div class="panel-header">
          <el-alert type="info" show-icon :closable="false" class="info-alert">
            <template #title>
              支持<strong>OpenAI 兼容多模态接口</strong>：阿里云 DashScope、OpenAI、智谱、DeepSeek、本地 Ollama 等。
              填写各厂商的 <code>base_url</code>、<code>model_name</code> 与 API Key 即可接入（Ollama 本地一般无需 Key）。
            </template>
          </el-alert>
          <div class="panel-actions">
            <el-button :loading="bootstrapping" @click="handleBootstrap">快速注册 Qwen-VL</el-button>
            <el-button type="primary" @click="openCustomDialog()">添加自定义 VLM</el-button>
            <el-button @click="fetchModels">刷新</el-button>
          </div>
        </div>

        <el-card v-loading="modelsLoading">
          <el-table :data="vlmModels" border style="width: 100%">
            <el-table-column prop="models_name" label="显示名称" min-width="130" />
            <el-table-column label="Provider" width="120">
              <template #default="{ row }">{{ row.parameters?.provider || '-' }}</template>
            </el-table-column>
            <el-table-column label="远程 model_name" min-width="130">
              <template #default="{ row }">{{ row.parameters?.model_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="base_url" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.parameters?.base_url || '-' }}</template>
            </el-table-column>
            <el-table-column label="视觉" width="80">
              <template #default="{ row }">
                <el-tag :type="row.parameters?.supports_vision !== false ? 'success' : 'danger'" size="small">
                  {{ row.parameters?.supports_vision !== false ? '支持' : '不支持' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="API Key" width="100">
              <template #default="{ row }">
                <el-tag :type="row.api_key_configured ? 'success' : 'warning'" size="small">
                  {{ row.api_key_configured ? '已配置' : '未配置' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '激活' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openCustomDialog(row)">编辑</el-button>
                <el-button link type="primary" @click="openApiKeyDialog(row)">Key</el-button>
                <el-button link type="primary" @click="goTest(row)">试跑</el-button>
                <el-button link :type="row.is_active ? 'warning' : 'success'" @click="toggleModelActive(row)">
                  {{ row.is_active ? '停用' : '启用' }}
                </el-button>
                <el-button link type="danger" @click="deleteModel(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!modelsLoading && !vlmModels.length" description="暂无 VLM 模型，请添加或快速注册" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="图片试跑" name="test">
        <el-row :gutter="20">
          <el-col :span="10">
            <el-card header="试跑配置">
              <el-form label-width="100px">
                <el-form-item label="VLM 模型" required>
                  <el-select v-model="testForm.vlm_model_id" placeholder="选择模型" style="width: 100%">
                    <el-option
                      v-for="m in activeVlmModels"
                      :key="m.models_id"
                      :label="m.models_name"
                      :value="m.models_id"
                      :disabled="!isModelReady(m)"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="Prompt 模板">
                  <el-select v-model="testForm.prompt_id" style="width: 100%" @change="handlePromptChange">
                    <el-option v-for="p in prompts" :key="p.prompt_id" :label="p.name" :value="p.prompt_id" />
                  </el-select>
                  <p v-if="currentTestPromptDesc" class="field-hint">{{ currentTestPromptDesc }}</p>
                </el-form-item>

                <el-form-item
                  v-if="testForm.prompt_id === 'custom_freeform_v1'"
                  label="自定义 Prompt"
                  required
                >
                  <el-input
                    v-model="testForm.prompt_override"
                    type="textarea"
                    :rows="8"
                    :placeholder="customPromptPlaceholder"
                  />
                  <p class="field-hint">可用 <code>{alert_labels}</code> 插入告警标签列表，保存后将覆盖上方模板。</p>
                </el-form-item>

                <el-form-item label="告警标签">
                  <el-select
                    v-model="testForm.alert_labels"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    placeholder="输入或选择"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="label in suggestedTestLabels"
                      :key="label"
                      :label="label"
                      :value="label"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="最低置信度">
                  <el-slider v-model="testForm.min_confidence" :min="0.1" :max="1" :step="0.05" show-input />
                </el-form-item>
                <el-form-item label="试跑图片" required>
                  <el-upload
                    drag
                    action="#"
                    :auto-upload="false"
                    :show-file-list="false"
                    accept=".jpg,.jpeg,.png,.bmp,.webp"
                    :on-change="handleImageChange"
                  >
                    <el-icon class="upload-icon"><UploadFilled /></el-icon>
                    <div class="el-upload__text">拖拽或点击上传图片</div>
                  </el-upload>
                  <div v-if="previewUrl" class="preview-wrap">
                    <img :src="previewUrl" alt="preview" class="preview-img" />
                    <el-button link type="danger" @click="clearImage">移除</el-button>
                  </div>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="testing" :disabled="!canRunTest" @click="runTest">
                    开始试跑
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="14">
            <el-card v-loading="testing" header="试跑结果">
              <template v-if="!testResult && !testError">
                <el-empty description="上传图片并点击「开始试跑」" />
              </template>
              <template v-else-if="testError">
                <el-alert type="error" :title="testError" show-icon :closable="false" />
              </template>
              <template v-else>
                <el-descriptions :column="2" border size="small" class="result-desc">
                  <el-descriptions-item label="耗时">{{ testResult.latency_ms || 0 }} ms</el-descriptions-item>
                  <el-descriptions-item label="调用状态">
                    <el-tag :type="testResult.ok ? 'success' : 'danger'" size="small">
                      {{ testResult.ok ? '成功' : '失败' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="是否告警">
                    <el-tag :type="testResult.result?.needs_alert ? 'danger' : 'info'" size="small">
                      {{ testResult.result?.needs_alert ? '是' : '否' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="命中标签">
                    <el-tag
                      v-for="tag in (testResult.result?.alert_labels || [])"
                      :key="tag"
                      size="small"
                      type="danger"
                      style="margin-right: 4px"
                    >{{ tag }}</el-tag>
                    <span v-if="!(testResult.result?.alert_labels || []).length">-</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="摘要" :span="2">{{ testResult.result?.summary || '-' }}</el-descriptions-item>
                </el-descriptions>

                <h4 class="section-title">Findings</h4>
                <el-table
                  v-if="(testResult.result?.findings || []).length"
                  :data="testResult.result.findings"
                  border
                  size="small"
                  style="width: 100%"
                >
                  <el-table-column prop="label" label="Label" width="120" />
                  <el-table-column prop="confidence" label="置信度" width="90">
                    <template #default="{ row }">{{ (row.confidence ?? 0).toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="severity" label="级别" width="90" />
                  <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
                  <el-table-column label="Attributes" min-width="140">
                    <template #default="{ row }">
                      {{ row.attributes ? JSON.stringify(row.attributes) : '-' }}
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-else description="无 findings" :image-size="60" />

                <el-collapse v-if="testResult.raw_text" class="raw-collapse">
                  <el-collapse-item title="原始响应 / JSON" name="raw">
                    <pre class="raw-json">{{ formatRawResponse(testResult) }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </template>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="customDialogVisible"
      :title="customEditId ? '编辑 VLM 模型' : '添加自定义 VLM'"
      width="560px"
      append-to-body
      destroy-on-close
    >
      <el-form ref="customFormRef" :model="customForm" :rules="customRules" label-width="110px">
        <el-form-item v-if="!customEditId" label="接入预设">
          <el-select v-model="customForm.preset_id" style="width: 100%" @change="applyPreset">
            <el-option v-for="p in providers" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称" prop="models_name">
          <el-input v-model="customForm.models_name" placeholder="如：GPT-4o 巡检" />
        </el-form-item>
        <el-form-item label="Provider" prop="provider">
          <el-input v-model="customForm.provider" placeholder="qwen_vl / openai_compatible" />
        </el-form-item>
        <el-form-item label="base_url" prop="base_url">
          <el-input v-model="customForm.base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="model_name" prop="model_name">
          <el-input v-model="customForm.model_name" placeholder="gpt-4o / qwen-vl-plus / llava" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="customForm.api_key"
            type="password"
            show-password
            :placeholder="customForm.api_key_required ? 'sk-... 或 env:VAR_NAME' : '本地 Ollama 可留空'"
          />
          <p class="field-hint">{{ currentPresetHint }}</p>
        </el-form-item>
        <el-form-item label="需要 API Key">
          <el-switch v-model="customForm.api_key_required" />
        </el-form-item>
        <el-form-item label="超时(秒)">
          <el-input-number v-model="customForm.timeout_sec" :min="10" :max="300" />
        </el-form-item>
        <el-form-item label="temperature">
          <el-slider v-model="customForm.temperature" :min="0" :max="1" :step="0.1" show-input />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="customForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="customDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="customSaving" @click="saveCustomModel">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="apiKeyDialogVisible" title="配置 API Key" width="480px" append-to-body>
      <p v-if="apiKeyTargetModel" class="hint">模型：<strong>{{ apiKeyTargetModel.models_name }}</strong></p>
      <el-input v-model="apiKeyInput" type="password" show-password placeholder="sk-... 或 env:DASHSCOPE_API_KEY" />
      <template #footer>
        <el-button @click="apiKeyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="apiKeySaving" @click="saveApiKey">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import deviceApi from '@/api/device'
import { vlmInspectionApi } from '@/api/vlm_inspection'

const route = useRoute()
const router = useRouter()

const activePanel = ref(route.query.tab === 'test' ? 'test' : 'models')
const modelsLoading = ref(false)
const bootstrapping = ref(false)
const vlmModels = ref([])
const prompts = ref([])
const providers = ref([])

const customDialogVisible = ref(false)
const customEditId = ref('')
const customSaving = ref(false)
const customFormRef = ref(null)
const customForm = reactive({
  preset_id: 'dashscope_qwen',
  models_name: '',
  provider: 'qwen_vl',
  base_url: '',
  model_name: '',
  api_key: '',
  description: '',
  temperature: 0.2,
  timeout_sec: 60,
  api_key_required: true
})

const customRules = {
  models_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请输入 provider', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 base_url', trigger: 'blur' }],
  model_name: [{ required: true, message: '请输入 model_name', trigger: 'blur' }]
}

const apiKeyDialogVisible = ref(false)
const apiKeyInput = ref('')
const apiKeySaving = ref(false)
const apiKeyTargetModel = ref(null)

const testForm = reactive({
  vlm_model_id: '',
  prompt_id: 'general_patrol_v1',
  prompt_override: '',
  alert_labels: ['fire', 'fight', 'fall'],
  min_confidence: 0.7
})
const testFile = ref(null)
const previewUrl = ref('')
const testing = ref(false)
const testResult = ref(null)
const testError = ref('')

const activeVlmModels = computed(() => vlmModels.value.filter(m => m.is_active))
const canRunTest = computed(() => {
  if (!testForm.vlm_model_id || !testFile.value || testing.value) return false
  if (testForm.prompt_id === 'custom_freeform_v1' && !testForm.prompt_override?.trim()) return false
  return true
})

const defaultAlertLabels = ['fire', 'smoke', 'fight', 'fall', 'smoking', 'swimming', 'red_top', 'blue_top']

const customPromptPlaceholder = `请根据实际画面分析，关注告警项：{alert_labels}

规则：
- 命中关注项时 findings 写入对应 label，confidence 0.85~1.0
- 未命中时 findings 为 []，needs_alert 为 false
- 只输出 JSON，不要 markdown`

const currentTestPromptDesc = computed(() => {
  const p = prompts.value.find(item => item.prompt_id === testForm.prompt_id)
  return p?.description || ''
})

const suggestedTestLabels = computed(() => {
  const p = prompts.value.find(item => item.prompt_id === testForm.prompt_id)
  const fromPrompt = p?.default_alert_labels || []
  return [...new Set([...fromPrompt, ...defaultAlertLabels])]
})

const currentPresetHint = computed(() => {
  const p = providers.value.find(item => item.id === customForm.preset_id)
  return p?.api_key_hint || '支持 env:环境变量名，从服务端 .env 读取'
})

const isModelReady = (m) => {
  if (m.parameters?.supports_vision === false) return false
  if (m.parameters?.api_key_required === false) return true
  return m.api_key_configured
}

const normalizeVlmRow = (m) => ({
  models_id: m.model_id || m.models_id,
  models_name: m.models_name,
  description: m.description,
  is_active: m.is_active,
  api_key_configured: m.api_key_configured,
  parameters: m.parameters || {}
})

const fetchModels = async () => {
  modelsLoading.value = true
  try {
    const res = await vlmInspectionApi.listVlmModels()
    vlmModels.value = (res.data || []).map(normalizeVlmRow)
    if (!testForm.vlm_model_id) {
      const first = activeVlmModels.value.find(isModelReady) || activeVlmModels.value[0]
      if (first) testForm.vlm_model_id = first.models_id
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载 VLM 模型失败')
  } finally {
    modelsLoading.value = false
  }
}

const fetchPrompts = async () => {
  try {
    const res = await vlmInspectionApi.getPrompts()
    prompts.value = res.data || []
  } catch {
    prompts.value = []
  }
}

const fetchProviders = async () => {
  try {
    const res = await vlmInspectionApi.getVlmProviders()
    providers.value = res.data || []
  } catch {
    providers.value = []
  }
}

const applyPreset = (presetId) => {
  const p = providers.value.find(item => item.id === presetId)
  if (!p) return
  customForm.provider = p.provider
  customForm.base_url = p.base_url || ''
  customForm.model_name = p.model_name || ''
  customForm.api_key_required = p.api_key_required !== false
  if (!customForm.models_name) customForm.models_name = p.name
}

const resetCustomForm = () => {
  Object.assign(customForm, {
    preset_id: 'dashscope_qwen',
    models_name: '',
    provider: 'qwen_vl',
    base_url: '',
    model_name: '',
    api_key: '',
    description: '',
    temperature: 0.2,
    timeout_sec: 60,
    api_key_required: true
  })
  applyPreset('dashscope_qwen')
}

const openCustomDialog = (row = null) => {
  customEditId.value = row?.models_id || ''
  if (row) {
    Object.assign(customForm, {
      preset_id: 'custom',
      models_name: row.models_name,
      provider: row.parameters?.provider || 'openai_compatible',
      base_url: row.parameters?.base_url || '',
      model_name: row.parameters?.model_name || '',
      api_key: '',
      description: row.description || '',
      temperature: row.parameters?.temperature ?? 0.2,
      timeout_sec: row.parameters?.timeout_sec ?? 60,
      api_key_required: row.parameters?.api_key_required !== false
    })
  } else {
    resetCustomForm()
  }
  customDialogVisible.value = true
}

const buildCustomPayload = () => {
  const payload = {
    models_name: customForm.models_name.trim(),
    provider: customForm.provider.trim(),
    base_url: customForm.base_url.trim(),
    model_name: customForm.model_name.trim(),
    description: customForm.description?.trim() || undefined,
    temperature: customForm.temperature,
    timeout_sec: customForm.timeout_sec,
    api_key_required: customForm.api_key_required
  }
  if (customForm.api_key?.trim()) payload.api_key = customForm.api_key.trim()
  return payload
}

const saveCustomModel = async () => {
  if (!customFormRef.value) return
  if (customForm.base_url.toLowerCase().includes('deepseek.com')) {
    ElMessage.error('DeepSeek 官方 API 不支持传图，请改用 Qwen-VL / GPT-4o / GLM-4V / Ollama')
    return
  }
  await customFormRef.value.validate(async valid => {
    if (!valid) return
    customSaving.value = true
    try {
      const payload = buildCustomPayload()
      if (customEditId.value) {
        await vlmInspectionApi.updateVlmModel(customEditId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await vlmInspectionApi.createVlmModel(payload)
        ElMessage.success('注册成功')
      }
      customDialogVisible.value = false
      await fetchModels()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    } finally {
      customSaving.value = false
    }
  })
}

const handleBootstrap = async () => {
  bootstrapping.value = true
  try {
    const res = await vlmInspectionApi.bootstrapQwenModel()
    ElMessage.success(res.data?.message || '注册成功')
    await fetchModels()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    bootstrapping.value = false
  }
}

const openApiKeyDialog = (row = null) => {
  apiKeyTargetModel.value = row || vlmModels.value[0] || null
  if (!apiKeyTargetModel.value) {
    ElMessage.warning('请先添加 VLM 模型')
    return
  }
  apiKeyInput.value = ''
  apiKeyDialogVisible.value = true
}

const saveApiKey = async () => {
  if (!apiKeyTargetModel.value) return
  if (!apiKeyInput.value.trim()) {
    ElMessage.warning('请输入 API Key')
    return
  }
  apiKeySaving.value = true
  try {
    await vlmInspectionApi.updateVlmCredentials(apiKeyTargetModel.value.models_id, apiKeyInput.value.trim())
    ElMessage.success('API Key 已保存')
    apiKeyDialogVisible.value = false
    await fetchModels()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    apiKeySaving.value = false
  }
}

const toggleModelActive = async (row) => {
  const next = !row.is_active
  const action = next ? '启用' : '停用'
  try {
    await ElMessageBox.confirm(`确定${action}模型「${row.models_name}」？`, '确认', { type: 'warning' })
    await deviceApi.toggleModelActive(row.models_id, next)
    ElMessage.success(`${action}成功`)
    await fetchModels()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || `${action}失败`)
  }
}

const deleteModel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除 VLM 模型「${row.models_name}」？`, '确认', { type: 'warning' })
    await vlmInspectionApi.deleteVlmModel(row.models_id)
    ElMessage.success('删除成功')
    await fetchModels()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const goTest = (row) => {
  testForm.vlm_model_id = row.models_id
  activePanel.value = 'test'
  router.replace({ path: '/models/vlm', query: { tab: 'test' } })
}

const handlePromptChange = (promptId) => {
  const p = prompts.value.find(item => item.prompt_id === promptId)
  if (p?.default_alert_labels?.length) {
    testForm.alert_labels = [...p.default_alert_labels]
  }
  if (promptId !== 'custom_freeform_v1') {
    testForm.prompt_override = ''
  }
}

const handleImageChange = (uploadFile) => {
  if (!uploadFile?.raw) return
  testFile.value = uploadFile.raw
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
  testResult.value = null
  testError.value = ''
}

const clearImage = () => {
  testFile.value = null
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

const runTest = async () => {
  if (!canRunTest.value) return
  testing.value = true
  testResult.value = null
  testError.value = ''
  try {
    const fd = new FormData()
    fd.append('vlm_model_id', testForm.vlm_model_id)
    fd.append('prompt_id', testForm.prompt_id)
    fd.append('alert_labels', testForm.alert_labels.join(','))
    fd.append('min_confidence', String(testForm.min_confidence))
    if (testForm.prompt_override?.trim()) {
      fd.append('prompt_override', testForm.prompt_override.trim())
    }
    fd.append('file', testFile.value)
    const res = await vlmInspectionApi.testInspection(fd)
    testResult.value = res.data
    if (res.data?.error) testError.value = res.data.error
  } catch (e) {
    testError.value = e.response?.data?.detail || e.message || '试跑失败'
  } finally {
    testing.value = false
  }
}

const formatRawResponse = (data) => {
  if (data?.raw_parsed) return JSON.stringify(data.raw_parsed, null, 2)
  return data?.raw_text || ''
}

onMounted(async () => {
  await Promise.all([fetchProviders(), fetchModels(), fetchPrompts()])
})
</script>

<style scoped>
.vlm-management { padding: 0; }
.panel-header { margin-bottom: 16px; }
.info-alert { margin-bottom: 12px; }
.panel-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.hint, .field-hint { margin: 8px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.upload-icon { font-size: 48px; color: var(--el-color-primary); margin-bottom: 8px; }
.preview-wrap { margin-top: 12px; text-align: center; }
.preview-img { max-width: 100%; max-height: 200px; border-radius: 6px; border: 1px solid var(--el-border-color); }
.result-desc { margin-bottom: 16px; }
.section-title { margin: 16px 0 8px; font-size: 14px; font-weight: 600; }
.raw-collapse { margin-top: 16px; }
.raw-json {
  margin: 0; padding: 12px; background: #1e1e1e; color: #dcdcdc;
  border-radius: 6px; font-size: 12px; line-height: 1.5;
  overflow: auto; max-height: 320px; white-space: pre-wrap; word-break: break-all;
}
</style>
