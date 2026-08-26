<template>
  <div class="vlm-inspection-detail">
    <div class="header">
      <h2>{{ job.job_name || '巡检详情' }}</h2>
      <div>
        <el-button @click="goBack">返回列表</el-button>
        <el-button type="primary" @click="runJob" :loading="running" :disabled="job.is_running">立即巡检</el-button>
        <el-button :type="job.is_active ? 'warning' : 'success'" @click="toggleStatus">
          {{ job.is_active ? '停止任务' : '启动任务' }}
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!loading && job.job_id && !job.is_active"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>
        任务当前为<strong>暂停</strong>状态，不会自动定时巡检。请点击右上角「启动任务」或列表页的「启动」按钮。
      </template>
    </el-alert>

    <el-alert
      v-if="job.is_running"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>巡检正在执行中，完成后可刷新查看执行历史与发现记录。</template>
    </el-alert>

    <el-card v-loading="loading" class="info-card">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ job.job_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="job.is_running ? 'warning' : (job.is_active ? 'success' : 'info')">
            {{ job.is_running ? '执行中' : (job.is_active ? (job.status || 'scheduled') : '已暂停 · 需启动') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="VLM 模型">{{ job.vlm_model_id }}</el-descriptions-item>
        <el-descriptions-item label="Prompt">{{ job.prompt_id }}</el-descriptions-item>
        <el-descriptions-item label="告警标签">
          <el-tag v-for="t in (job.alert_labels || [])" :key="t" size="small" style="margin-right: 4px">{{ t }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最低置信度">{{ Math.round((job.min_confidence || 0.7) * 100) }}%</el-descriptions-item>
        <el-descriptions-item label="整轮间隔">{{ job.interval }} 秒</el-descriptions-item>
        <el-descriptions-item label="设备数">
          {{ job.device_count ?? job.resolved_device_ids?.length ?? job.device_ids?.length ?? 0 }}
          <span v-if="job.device_mode === 'group'" class="device-mode-hint">（分组实时统计）</span>
        </el-descriptions-item>
        <el-descriptions-item label="最近执行">{{ job.last_run ? formatDate(job.last_run) : '未执行' }}</el-descriptions-item>
        <el-descriptions-item label="最近告警数">{{ job.last_result?.alert_count ?? '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="执行历史" name="runs">
          <el-table v-loading="runsLoading" :data="runs" border>
            <el-table-column label="开始时间" width="170">
              <template #default="scope">{{ formatDateTime(scope.row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="结束时间" width="170">
              <template #default="scope">{{ scope.row.finished_at ? formatDateTime(scope.row.finished_at) : '-' }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="90">
              <template #default="scope">{{ scope.row.duration_sec != null ? `${scope.row.duration_sec}s` : '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="scope">
                <el-tag :type="getRunStatusType(scope.row.status)" size="small">{{ getRunStatusLabel(scope.row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="设备" width="120">
              <template #default="scope">
                {{ scope.row.device_success }}/{{ scope.row.device_total }}
                <span v-if="scope.row.device_failed" class="fail-count">(失败 {{ scope.row.device_failed }})</span>
              </template>
            </el-table-column>
            <el-table-column prop="alert_count" label="告警" width="70" />
            <el-table-column label="Run ID" min-width="200" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.run_id }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="巡检发现" name="findings">
          <div class="findings-toolbar">
            <el-checkbox v-model="alertsOnly" @change="fetchFindings">仅告警</el-checkbox>
          </div>
          <el-table v-loading="findingsLoading" :data="findings" border>
            <el-table-column label="时间" width="170">
              <template #default="scope">{{ formatDateTime(scope.row.timestamp) }}</template>
            </el-table-column>
            <el-table-column prop="device_name" label="设备" width="140" />
            <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
            <el-table-column label="告警" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.needs_alert ? 'danger' : 'info'" size="small">
                  {{ scope.row.needs_alert ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="120">
              <template #default="scope">
                <el-tag v-for="l in (scope.row.alert_labels || [])" :key="l" size="small" style="margin-right: 4px">{{ l }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Run" min-width="120" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.run_id }}</template>
            </el-table-column>
            <el-table-column label="截图" width="90">
              <template #default="scope">
                <el-button v-if="scope.row.snapshot_path" link type="primary" @click="previewImage(scope.row.snapshot_path)">查看</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="latency_ms" label="耗时(ms)" width="100" />
            <el-table-column prop="error" label="错误" min-width="120" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="imageVisible" title="巡检截图" width="720px" append-to-body>
      <img v-if="previewUrl" :src="previewUrl" style="max-width: 100%" alt="snapshot" @error="handleImageError" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { vlmInspectionApi } from '@/api/vlm_inspection'
import { formatDate, formatDateTime } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const findingsLoading = ref(false)
const runsLoading = ref(false)
const running = ref(false)
const job = ref({})
const findings = ref([])
const runs = ref([])
const alertsOnly = ref(false)
const activeTab = ref('runs')
const imageVisible = ref(false)
const previewUrl = ref('')

const goBack = () => router.replace({ name: 'VlmInspection' })

const getRunStatusLabel = status => {
  const map = {
    running: '执行中',
    completed: '已完成',
    partial: '部分失败',
    error: '失败',
    cancelled: '已中断'
  }
  return map[status] || status || '-'
}

const getRunStatusType = status => {
  const map = {
    running: 'warning',
    completed: 'success',
    partial: 'warning',
    error: 'danger',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

const fetchJob = async () => {
  loading.value = true
  try {
    const res = await vlmInspectionApi.getJob(route.params.id)
    job.value = res.data
  } catch {
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const fetchRuns = async () => {
  runsLoading.value = true
  try {
    const res = await vlmInspectionApi.getRuns(route.params.id, { page: 1, page_size: 30 })
    runs.value = res.data.data || []
    if (res.data.is_running != null) {
      job.value.is_running = res.data.is_running
    }
  } catch {
    ElMessage.error('加载执行历史失败')
  } finally {
    runsLoading.value = false
  }
}

const fetchFindings = async () => {
  findingsLoading.value = true
  try {
    const res = await vlmInspectionApi.getFindings(route.params.id, {
      page: 1,
      page_size: 50,
      alerts_only: alertsOnly.value
    })
    findings.value = res.data.data || []
  } catch {
    ElMessage.error('加载发现记录失败')
  } finally {
    findingsLoading.value = false
  }
}

const handleTabChange = name => {
  if (name === 'runs' && !runs.value.length) fetchRuns()
  if (name === 'findings' && !findings.value.length) fetchFindings()
}

const runJob = async () => {
  running.value = true
  try {
    await vlmInspectionApi.runJobNow(job.value.job_id)
    ElMessage.success('已开始巡检，请稍后刷新')
    job.value.is_running = true
    setTimeout(() => {
      fetchJob()
      fetchRuns()
      fetchFindings()
    }, 3000)
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '执行失败'
    ElMessage.error(msg)
  } finally {
    running.value = false
  }
}

const toggleStatus = async () => {
  try {
    if (job.value.is_active) {
      await vlmInspectionApi.pauseJob(job.value.job_id)
      ElMessage.success('已停止定时调度（若正在巡检会中断当前轮次）')
    } else {
      await vlmInspectionApi.resumeJob(job.value.job_id)
      ElMessage.success('已启动')
    }
    fetchJob()
    setTimeout(fetchRuns, 2000)
  } catch {
    ElMessage.error('操作失败')
  }
}

const getSnapshotUrl = (path) => {
  if (!path) return ''
  if (/^(data:|https?:)/i.test(path)) return path
  const normalized = path.replace(/^\/+/, '').replace(/\\/g, '/')
  return `/api/v1/files/${normalized}`
}

const previewImage = path => {
  previewUrl.value = getSnapshotUrl(path)
  imageVisible.value = true
}

const handleImageError = (event) => {
  event.target.alt = '截图加载失败'
  event.target.style.opacity = '0.5'
}

onMounted(() => {
  fetchJob()
  fetchRuns()
})
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.info-card {
  margin-bottom: 16px;
}
.findings-toolbar {
  margin-bottom: 12px;
}
.fail-count {
  color: var(--el-color-danger);
  font-size: 12px;
}
.device-mode-hint {
  margin-left: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
