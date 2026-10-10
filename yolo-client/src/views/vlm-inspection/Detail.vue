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
            <el-table-column label="框" width="70">
              <template #default="scope">
                <span>{{ countBBoxes(scope.row.findings) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="截图" width="90">
              <template #default="scope">
                <el-button v-if="scope.row.snapshot_path" link type="primary" @click="previewFinding(scope.row)">查看</el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="latency_ms" label="耗时(ms)" width="100" />
            <el-table-column prop="error" label="错误" min-width="120" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="imageVisible" title="巡检截图" width="720px" append-to-body @closed="resetPreview">
      <div class="preview-wrap">
        <img
          v-if="previewUrl"
          ref="previewImgRef"
          :src="previewUrl"
          class="preview-img"
          alt="snapshot"
          @load="drawOverlay"
          @error="handleImageError"
        />
        <canvas ref="overlayCanvasRef" class="preview-canvas" />
      </div>
      <p v-if="previewBBoxes.length" class="preview-hint">叠加 {{ previewBBoxes.length }} 个检测框（归一化/像素坐标）</p>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
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
const previewBBoxes = ref([])
const previewImgRef = ref(null)
const overlayCanvasRef = ref(null)

const goBack = () => router.replace({ name: 'VlmInspection' })

const countBBoxes = (findings) => {
  if (!Array.isArray(findings)) return 0
  return findings.filter((f) => Array.isArray(f?.bbox) && f.bbox.length >= 4).length
}

const extractBBoxes = (findings) => {
  if (!Array.isArray(findings)) return []
  return findings
    .filter((f) => Array.isArray(f?.bbox) && f.bbox.length >= 4)
    .map((f) => ({
      bbox: f.bbox.slice(0, 4).map(Number),
      label: f.label || '',
      confidence: Number(f.confidence) || 0
    }))
}

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

const resetPreview = () => {
  previewUrl.value = ''
  previewBBoxes.value = []
  const canvas = overlayCanvasRef.value
  if (canvas) {
    const ctx = canvas.getContext('2d')
    ctx && ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
}

const bboxToPixels = (bbox, width, height) => {
  let [x1, y1, x2, y2] = bbox.map(Number)
  if ([x1, y1, x2, y2].some((v) => Number.isNaN(v))) return null
  if (Math.max(x1, y1, x2, y2) <= 1.5) {
    x1 *= width
    x2 *= width
    y1 *= height
    y2 *= height
  }
  x1 = Math.max(0, Math.min(width - 1, Math.round(x1)))
  y1 = Math.max(0, Math.min(height - 1, Math.round(y1)))
  x2 = Math.max(0, Math.min(width - 1, Math.round(x2)))
  y2 = Math.max(0, Math.min(height - 1, Math.round(y2)))
  if (x2 <= x1 || y2 <= y1) return null
  return [x1, y1, x2, y2]
}

const drawOverlay = async () => {
  await nextTick()
  const img = previewImgRef.value
  const canvas = overlayCanvasRef.value
  if (!img || !canvas || !img.naturalWidth) return

  const displayW = img.clientWidth || img.naturalWidth
  const displayH = img.clientHeight || img.naturalHeight
  const scaleX = displayW / img.naturalWidth
  const scaleY = displayH / img.naturalHeight

  canvas.width = displayW
  canvas.height = displayH
  canvas.style.width = `${displayW}px`
  canvas.style.height = `${displayH}px`

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, displayW, displayH)
  ctx.strokeStyle = '#f59e0b'
  ctx.lineWidth = 2
  ctx.font = '12px sans-serif'
  ctx.fillStyle = '#f59e0b'

  for (const item of previewBBoxes.value) {
    const px = bboxToPixels(item.bbox, img.naturalWidth, img.naturalHeight)
    if (!px) continue
    const [x1, y1, x2, y2] = px
    const dx1 = x1 * scaleX
    const dy1 = y1 * scaleY
    const dx2 = x2 * scaleX
    const dy2 = y2 * scaleY
    ctx.strokeRect(dx1, dy1, dx2 - dx1, dy2 - dy1)
    const text = `${item.label || ''} ${item.confidence ? item.confidence.toFixed(2) : ''}`.trim()
    if (text) {
      ctx.fillText(text.slice(0, 40), dx1 + 2, Math.max(12, dy1 - 4))
    }
  }
}

const previewFinding = (row) => {
  previewUrl.value = getSnapshotUrl(row.snapshot_path)
  previewBBoxes.value = extractBBoxes(row.findings)
  imageVisible.value = true
  nextTick(() => {
    if (previewImgRef.value?.complete) drawOverlay()
  })
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
.preview-wrap {
  position: relative;
  display: inline-block;
  max-width: 100%;
  line-height: 0;
}
.preview-img {
  max-width: 100%;
  display: block;
}
.preview-canvas {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
}
.preview-hint {
  margin: 8px 0 0;
  color: #909399;
  font-size: 12px;
}
</style>
