<template>
  <div class="vlm-inspection-list">
    <div class="header">
      <h2>VLM 巡检任务</h2>
      <div class="header-actions">
        <el-button type="primary" @click="openCreateDialog">创建任务</el-button>
      </div>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>
        定时截图 → VLM 语义检测。请先在
        <el-link type="primary" @click="router.push('/models/vlm')">模型管理 · VLM 大模型</el-link>
        中注册模型并配置 API Key，可用图片试跑验证 Prompt。
        告警推送需在<strong>数据推送配置</strong>的 tags 中包含任务标签（如 <code>vlm_inspection</code> 或 <code>vlm_alert</code>）。
      </template>
    </el-alert>

    <el-card>
      <el-table v-loading="loading" :data="jobList" border style="width: 100%">
        <el-table-column prop="job_name" label="任务名称" min-width="140" />
        <el-table-column label="VLM 模型" min-width="120">
          <template #default="scope">
            {{ getModelName(scope.row.vlm_model_id) }}
          </template>
        </el-table-column>
        <el-table-column label="Prompt" min-width="130">
          <template #default="scope">
            {{ getPromptName(scope.row.prompt_id) }}
          </template>
        </el-table-column>
        <el-table-column label="告警标签" min-width="160">
          <template #default="scope">
            <template v-if="(scope.row.alert_labels || []).length">
              <el-tooltip
                :content="formatAlertLabelsTooltip(scope.row.alert_labels)"
                placement="top"
                :show-after="300"
                :disabled="scope.row.alert_labels.length <= VISIBLE_ALERT_LABEL_COUNT"
              >
                <div class="alert-labels-cell">
                  <el-tag
                    v-for="tag in scope.row.alert_labels.slice(0, VISIBLE_ALERT_LABEL_COUNT)"
                    :key="tag"
                    size="small"
                    class="alert-label-tag"
                  >
                    {{ tag }}
                  </el-tag>
                  <el-tag
                    v-if="scope.row.alert_labels.length > VISIBLE_ALERT_LABEL_COUNT"
                    size="small"
                    type="info"
                    effect="plain"
                    class="alert-label-more"
                  >
                    +{{ scope.row.alert_labels.length - VISIBLE_ALERT_LABEL_COUNT }}
                  </el-tag>
                </div>
              </el-tooltip>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="设备" min-width="100">
          <template #default="scope">
            {{ scope.row.device_count ?? scope.row.device_ids?.length ?? 0 }} 台
            <el-tag v-if="scope.row.device_mode === 'group'" size="small" type="info" style="margin-left: 4px">分组</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="整轮间隔" width="100">
          <template #default="scope">{{ scope.row.interval || 0 }}秒</template>
        </el-table-column>
        <el-table-column label="生效时段" min-width="100">
          <template #default="scope">{{ getScheduleSummary(scope.row.schedule_config) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row)">{{ getStatusLabel(scope.row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近告警" width="90">
          <template #default="scope">
            {{ scope.row.last_result?.alert_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="scope">
            <el-button-group>
              <el-button size="small" type="info" @click="viewDetail(scope.row.job_id)">详情</el-button>
              <el-button size="small" type="primary" @click="openEditDialog(scope.row.job_id)">编辑</el-button>
              <el-button
                size="small"
                :type="scope.row.is_active ? 'warning' : 'success'"
                @click="toggleJobStatus(scope.row.job_id, scope.row.is_active)"
              >
                {{ scope.row.is_active ? '停止' : '启动' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteJob(scope.row.job_id)">删除</el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="totalCount > 0" class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="totalCount"
          layout="prev, pager, next, jumper, ->, total, sizes"
          @size-change="fetchJobs"
          @current-change="fetchJobs"
        />
      </div>
    </el-card>

    <VlmInspectionDialog
      v-model="dialogVisible"
      :is-edit="isEdit"
      :job-id="currentJobId"
      @saved="handleDialogSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { vlmInspectionApi } from '@/api/vlm_inspection'
import {
  scheduleFromBackend,
  legacyRuntimeToSchedule,
  formatScheduleSummary
} from '@/utils/weeklySchedule'
import VlmInspectionDialog from './VlmInspectionDialog.vue'

const router = useRouter()
const VISIBLE_ALERT_LABEL_COUNT = 3
const loading = ref(false)
const jobList = ref([])
const modelMap = ref({})
const promptMap = ref({})
const pageSize = ref(20)
const currentPage = ref(1)
const totalCount = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const currentJobId = ref('')

onMounted(async () => {
  await Promise.all([fetchJobs(), fetchModels(), fetchPrompts()])
})

const fetchJobs = async () => {
  loading.value = true
  try {
    const res = await vlmInspectionApi.getJobs({ page: currentPage.value, page_size: pageSize.value })
    jobList.value = res.data.data
    totalCount.value = res.data.total
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const fetchModels = async () => {
  try {
    const res = await vlmInspectionApi.getAvailableVlmModels()
    modelMap.value = {}
    ;(res.data || []).forEach(item => {
      modelMap.value[item.model_id] = item.model_name
    })
  } catch {
    // ignore
  }
}

const fetchPrompts = async () => {
  try {
    const res = await vlmInspectionApi.getPrompts()
    promptMap.value = {}
    ;(res.data || []).forEach(item => {
      promptMap.value[item.prompt_id] = item.name
    })
  } catch {
    // ignore
  }
}

const getModelName = id => modelMap.value[id] || id || '-'
const getPromptName = id => promptMap.value[id] || id || '-'

const formatAlertLabelsTooltip = (labels) => (labels || []).join('、') || '-'

const getScheduleSummary = scheduleConfig => {
  const runtime = scheduleConfig?.runtime
  if (!runtime) return '全时段'
  if (runtime.time_period_mode === 'all') return '全时段'
  if (runtime.time_period_mode === 'weekly' && runtime.weekly_schedule) {
    return formatScheduleSummary(scheduleFromBackend(runtime.weekly_schedule))
  }
  return formatScheduleSummary(legacyRuntimeToSchedule(runtime))
}

const getStatusType = row => {
  if (row.is_running) return 'warning'
  const map = { scheduled: 'warning', running: 'warning', completed: 'success', error: 'danger', paused: 'info', created: 'primary', cancelled: 'info' }
  return map[row.status] || 'info'
}

const getStatusLabel = row => {
  if (row.is_running) return '执行中'
  if (!row.is_active) return '已暂停 · 需启动'
  return row.status || 'unknown'
}

const openCreateDialog = () => {
  isEdit.value = false
  currentJobId.value = ''
  dialogVisible.value = true
}

const handleDialogSaved = (payload) => {
  fetchJobs()
  if (payload?.created) {
    ElMessage.warning('任务已创建但默认为暂停状态，请点击「启动」后才会定时巡检')
  }
}

const openEditDialog = jobId => {
  isEdit.value = true
  currentJobId.value = jobId
  dialogVisible.value = true
}

const viewDetail = jobId => {
  router.push({ name: 'VlmInspectionDetail', params: { id: jobId } })
}

const toggleJobStatus = async (jobId, active) => {
  try {
    if (active) {
      await vlmInspectionApi.pauseJob(jobId)
      ElMessage.success('任务已停止')
    } else {
      await vlmInspectionApi.resumeJob(jobId)
      ElMessage.success('任务已启动')
    }
    fetchJobs()
  } catch {
    ElMessage.error('操作失败')
  }
}

const deleteJob = jobId => {
  ElMessageBox.confirm('确定删除此巡检任务?', '提示', { type: 'warning' })
    .then(async () => {
      await vlmInspectionApi.deleteJob(jobId)
      ElMessage.success('删除成功')
      fetchJobs()
    })
    .catch(() => {})
}
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.pagination {
  margin-top: 20px;
  text-align: right;
}

.alert-labels-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 100%;
  cursor: default;
}

.alert-label-tag {
  flex-shrink: 0;
  max-width: none;
}

.alert-label-more {
  flex-shrink: 0;
}
</style>
