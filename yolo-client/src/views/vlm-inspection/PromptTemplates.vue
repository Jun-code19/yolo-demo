<template>
  <div class="prompt-templates-page">
    <div class="header">
      <div class="header-main">
        <el-button text class="back-link" @click="router.push('/vlm-inspection')">← 返回任务列表</el-button>
        <h2>Prompt 模板库</h2>
      </div>
      <div v-if="isAdmin" class="header-actions">
        <el-button @click="handleExport">导出自定义 JSON</el-button>
        <el-button @click="triggerImport">导入 JSON</el-button>
        <el-button type="primary" @click="openCreate">新建模板</el-button>
      </div>
    </div>

    <p class="page-desc">
      内置模板只读；自定义写入 <code>registry.custom.json</code>，可通过
      <code>PROMPT_REGISTRY_CUSTOM_PATH</code> 挂载迁移。
    </p>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="templates" border style="width: 100%">
        <el-table-column prop="prompt_id" label="ID" min-width="160" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="适用场景" width="180">
          <template #default="{ row }">
            <el-tag v-for="s in row.scopes || []" :key="s" size="small" class="scope-tag">
              {{ scopeLabel(s) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.builtin ? 'info' : 'success'" size="small">
              {{ row.builtin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openView(row)">查看</el-button>
            <el-button v-if="row.builtin && isAdmin" link type="primary" @click="cloneFrom(row)">复制为自定义</el-button>
            <el-button v-if="!row.builtin && isAdmin" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.builtin && isAdmin" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="780px"
      destroy-on-close
      append-to-body
      class="high-priority-dialog"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="dialogReadonly">
        <el-form-item v-if="dialogMode === 'create'" label="模板 ID（prompt_id）" prop="prompt_id">
          <el-input v-model="form.prompt_id" placeholder="小写英文开头，如 site_patrol_v1" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="适用场景" prop="scopes">
          <el-checkbox-group v-model="form.scopes">
            <el-checkbox label="vlm_inspection">VLM 巡检任务</el-checkbox>
            <el-checkbox label="detection_pipeline">检测推理管道</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="默认告警标签">
          <el-select v-model="form.default_alert_labels" multiple filterable allow-create teleported style="width: 100%" />
        </el-form-item>
        <el-form-item label="System Prompt" prop="system">
          <el-input v-model="form.system" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="User 模板" prop="user_template">
          <el-input v-model="form.user_template" type="textarea" :rows="12" />
          <p class="field-hint">可用占位符 <code>{alert_labels}</code>；YOLO 复检还可使用 <code>{yolo_class}</code>、<code>{yolo_conf}</code>。</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ dialogReadonly ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!dialogReadonly" type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <input ref="importInputRef" type="file" accept="application/json,.json" style="display: none" @change="onImportFile" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import vlmInspectionApi from '@/api/vlm_inspection'

const router = useRouter()
const loading = ref(false)
const templates = ref([])
const isAdmin = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref('view')
const dialogReadonly = ref(true)
const saving = ref(false)
const formRef = ref(null)
const importInputRef = ref(null)
const editingId = ref('')

const form = reactive({
  prompt_id: '',
  name: '',
  description: '',
  default_alert_labels: [],
  system: '',
  user_template: '',
  scopes: ['vlm_inspection', 'detection_pipeline']
})

const rules = {
  prompt_id: [{ required: true, message: '请输入 prompt_id', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  system: [{ required: true, message: '请输入 system', trigger: 'blur' }],
  user_template: [{ required: true, message: '请输入 user 模板', trigger: 'blur' }],
  scopes: [{ type: 'array', required: true, min: 1, message: '至少选择一个场景', trigger: 'change' }]
}

const dialogTitle = computed(() => {
  if (dialogMode.value === 'create') return '新建 Prompt 模板'
  if (dialogMode.value === 'edit') return `编辑 · ${editingId.value}`
  return `查看 · ${editingId.value}`
})

function scopeLabel(s) {
  if (s === 'vlm_inspection') return 'VLM 巡检'
  if (s === 'detection_pipeline') return '检测管道'
  return s
}

function readIsAdmin() {
  try {
    const raw = localStorage.getItem('userInfo')
    if (!raw) return false
    return JSON.parse(raw).role === 'admin'
  } catch {
    return false
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await vlmInspectionApi.getPrompts({ detail: true })
    templates.value = res.data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载模板失败')
  } finally {
    loading.value = false
  }
}

function fillForm(item) {
  form.prompt_id = item.prompt_id
  form.name = item.name || ''
  form.description = item.description || ''
  form.default_alert_labels = [...(item.default_alert_labels || [])]
  form.system = item.system || ''
  form.user_template = item.user_template || ''
  form.scopes = [...(item.scopes || ['vlm_inspection', 'detection_pipeline'])]
}

async function openView(row) {
  dialogMode.value = 'view'
  dialogReadonly.value = true
  editingId.value = row.prompt_id
  try {
    const res = await vlmInspectionApi.getPrompt(row.prompt_id)
    fillForm(res.data)
    dialogVisible.value = true
  } catch {
    ElMessage.error('加载详情失败')
  }
}

function openCreate() {
  dialogMode.value = 'create'
  dialogReadonly.value = false
  editingId.value = ''
  Object.assign(form, {
    prompt_id: '',
    name: '',
    description: '',
    default_alert_labels: [],
    system: '你是视频监控分析助手。只输出 JSON，不要 markdown。',
    user_template: '需要关注的告警项：{alert_labels}\n\n请分析画面并输出 JSON。',
    scopes: ['vlm_inspection', 'detection_pipeline']
  })
  dialogVisible.value = true
}

async function openEdit(row) {
  dialogMode.value = 'edit'
  dialogReadonly.value = false
  editingId.value = row.prompt_id
  const res = await vlmInspectionApi.getPrompt(row.prompt_id)
  fillForm(res.data)
  dialogVisible.value = true
}

async function cloneFrom(row) {
  const res = await vlmInspectionApi.getPrompt(row.prompt_id)
  const data = res.data
  dialogMode.value = 'create'
  dialogReadonly.value = false
  editingId.value = ''
  Object.assign(form, {
    prompt_id: `${row.prompt_id}_custom`.slice(0, 64),
    name: `${data.name}（副本）`,
    description: data.description || '',
    default_alert_labels: [...(data.default_alert_labels || [])],
    system: data.system || '',
    user_template: data.user_template || '',
    scopes: [...(data.scopes || ['vlm_inspection', 'detection_pipeline'])]
  })
  dialogVisible.value = true
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async valid => {
    if (!valid) return
    saving.value = true
    const body = {
      name: form.name,
      description: form.description,
      default_alert_labels: form.default_alert_labels,
      system: form.system,
      user_template: form.user_template,
      scopes: form.scopes
    }
    try {
      if (dialogMode.value === 'create') {
        await vlmInspectionApi.createPrompt({ prompt_id: form.prompt_id.trim(), ...body })
        ElMessage.success('已创建')
      } else {
        await vlmInspectionApi.updatePrompt(editingId.value, body)
        ElMessage.success('已保存')
      }
      dialogVisible.value = false
      await loadList()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除自定义模板「${row.name}」？`, '确认', { type: 'warning' })
    await vlmInspectionApi.deletePrompt(row.prompt_id)
    ElMessage.success('已删除')
    await loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleExport() {
  try {
    const res = await vlmInspectionApi.exportCustomPrompts()
    const blob = new Blob([JSON.stringify(res.data || {}, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'registry.custom.json'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导出失败')
  }
}

function triggerImport() {
  importInputRef.value?.click()
}

async function onImportFile(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  try {
    const text = await file.text()
    const templatesObj = JSON.parse(text)
    const merge = await ElMessageBox.confirm('是否与现有自定义模板合并？选「取消」则整表替换。', '导入方式', {
      confirmButtonText: '合并',
      cancelButtonText: '替换',
      distinguishCancelAndClose: true,
      type: 'info'
    })
      .then(() => true)
      .catch(action => (action === 'cancel' ? false : null))
    if (merge === null) return
    const res = await vlmInspectionApi.importCustomPrompts({ merge, templates: templatesObj })
    ElMessage.success(`已导入 ${res.data?.imported ?? 0} 条`)
    await loadList()
  } catch (e) {
    if (e !== 'close') ElMessage.error(e.response?.data?.detail || '导入失败')
  }
}

onMounted(() => {
  isAdmin.value = readIsAdmin()
  loadList()
})
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-main h2 {
  margin: 4px 0 0;
  font-size: 20px;
}

.back-link {
  padding-left: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.page-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.page-desc code {
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 0 4px;
  border-radius: 3px;
}

.scope-tag {
  margin-right: 4px;
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.field-hint code {
  font-size: 12px;
  background: var(--el-fill-color-light);
  padding: 0 4px;
  border-radius: 3px;
}
</style>
