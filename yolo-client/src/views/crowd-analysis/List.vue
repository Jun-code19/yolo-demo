<template>
  <div class="crowd-analysis-list">
    <div class="header">
      <h2>人群分析任务</h2>
      <el-button type="primary" @click="openCreateDialog">创建任务</el-button>
    </div>

    <el-card>
      <el-table v-loading="loading" :data="jobList" border style="width: 100%">
        <el-table-column prop="job_name" label="任务名称" width="150" />
        <el-table-column label="设备来源" min-width="220">
          <template #default="scope">
            <template v-if="scope.row.device_mode === 'group'">
              <el-tag size="small" type="info">分组</el-tag>
              <span class="source-text">{{ getGroupName(scope.row.group_id) }}</span>
              <span class="source-count">({{ scope.row.device_ids?.length || 0 }}台)</span>
            </template>
            <el-popover v-else placement="top" :width="300" trigger="hover">
              <template #default>
                <div class="device-list">
                  <el-tag
                    v-for="id in scope.row.device_ids"
                    :key="id"
                    size="small"
                    style="margin: 2px"
                  >
                    {{ getDeviceName(id) }}
                  </el-tag>
                </div>
              </template>
              <template #reference>
                <div class="device-preview">
                  <el-tag
                    v-for="id in scope.row.device_ids.slice(0, 2)"
                    :key="id"
                    size="small"
                    style="margin-right: 5px"
                  >
                    {{ getDeviceName(id) }}
                  </el-tag>
                  <el-tag v-if="scope.row.device_ids.length > 2" size="small" type="info">
                    +{{ scope.row.device_ids.length - 2 }}
                  </el-tag>
                </div>
              </template>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column label="检测模型" width="150">
          <template #default="scope">
            {{ getModelName(scope.row.models_id) }}
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="90">
          <template #default="scope">
            {{ scope.row.confidence_threshold ?? '0.5' }}
          </template>
        </el-table-column>
        <el-table-column label="整轮间隔" width="110">
          <template #default="scope">
            {{ scope.row.interval || 0 }}秒/轮
          </template>
        </el-table-column>
        <el-table-column label="生效时段" min-width="120">
          <template #default="scope">
            {{ getScheduleSummary(scope.row.schedule_config) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近执行" width="150">
          <template #default="scope">
            {{ scope.row.last_run ? formatDate(scope.row.last_run) : '未执行' }}
          </template>
        </el-table-column>
        <el-table-column label="人数统计" width="100">
          <template #default="scope">
            <span v-if="scope.row.last_result">
              {{ scope.row.last_result.total_person_count || 0 }}人
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <!-- <el-table-column label="位置信息" width="120">
          <template #default="scope">
            {{ scope.row.location_info?.name || '无' }}
          </template>
        </el-table-column> -->
        <el-table-column label="操作" width="220" fixed="right">
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
          :page-sizes="[20, 50, 100, 200]"
          :total="totalCount"
          layout="prev, pager, next, jumper, ->, total, sizes"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <CrowdJobDialog
      v-model="dialogVisible"
      :is-edit="isEdit"
      :job-id="currentJobId"
      @saved="fetchJobs"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import deviceApi from '@/api/device'
import { formatDate } from '@/utils/date'
import {
  scheduleFromBackend,
  legacyRuntimeToSchedule,
  formatScheduleSummary
} from '@/utils/weeklySchedule'
import CrowdJobDialog from './CrowdJobDialog.vue'

const router = useRouter()
const loading = ref(false)
const jobList = ref([])
const deviceMap = ref({})
const modelMap = ref({})
const groupMap = ref({})
const pageSize = ref(20)
const currentPage = ref(1)
const totalCount = ref(0)

const dialogVisible = ref(false)
const isEdit = ref(false)
const currentJobId = ref('')

onMounted(() => {
  fetchJobs()
  fetchDevices()
  fetchModels()
  fetchGroups()
})

const fetchJobs = async () => {
  loading.value = true
  try {
    const res = await crowdAnalysisApi.getAnalysisJobs({
      page: currentPage.value,
      page_size: pageSize.value
    })
    jobList.value = res.data.data
    totalCount.value = res.data.total
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const fetchDevices = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableDevices()
    deviceMap.value = {}
    res.data.forEach(item => {
      deviceMap.value[item.device_id] = item.device_name
    })
  } catch {
    // ignore
  }
}

const fetchModels = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    modelMap.value = {}
    res.data.forEach(item => {
      modelMap.value[item.model_id] = item.model_name
    })
  } catch {
    // ignore
  }
}

const fetchGroups = async () => {
  try {
    const res = await deviceApi.getDeviceGroups()
    groupMap.value = {}
    ;(res.data?.data || []).forEach(item => {
      groupMap.value[item.group_id] = item.group_name
    })
  } catch {
    // ignore
  }
}

const getDeviceName = (deviceId) => deviceMap.value[deviceId] || deviceId
const getModelName = (modelId) => modelMap.value[modelId] || modelId
const getGroupName = (groupId) => groupMap.value[groupId] || groupId || '未设置'

const getScheduleSummary = (scheduleConfig) => {
  const runtime = scheduleConfig?.runtime
  if (!runtime) return '全时段'
  if (runtime.time_period_mode === 'all') return '全时段'
  if (runtime.time_period_mode === 'weekly' && runtime.weekly_schedule) {
    return formatScheduleSummary(scheduleFromBackend(runtime.weekly_schedule))
  }
  return formatScheduleSummary(legacyRuntimeToSchedule(runtime))
}

const getStatusType = (status) => {
  const map = {
    scheduled: 'warning',
    running: 'warning',
    completed: 'success',
    error: 'danger',
    created: 'primary',
    paused: 'info'
  }
  return map[status] || ''
}

const openCreateDialog = () => {
  isEdit.value = false
  currentJobId.value = ''
  dialogVisible.value = true
}

const openEditDialog = (jobId) => {
  isEdit.value = true
  currentJobId.value = jobId
  dialogVisible.value = true
}

const viewDetail = (jobId) => {
  router.push(`/crowd-analysis/detail/${jobId}`)
}

const toggleJobStatus = async (jobId, active) => {
  try {
    if (active) {
      await crowdAnalysisApi.pauseAnalysisJob(jobId)
      ElMessage.success('任务已暂停')
    } else {
      await crowdAnalysisApi.resumeAnalysisJob(jobId)
      ElMessage.success('任务已恢复')
    }
    fetchJobs()
  } catch {
    ElMessage.error(`${active ? '暂停' : '恢复'}任务失败`)
  }
}

const deleteJob = (jobId) => {
  ElMessageBox.confirm('确定删除此任务?', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await crowdAnalysisApi.deleteAnalysisJob(jobId)
      ElMessage.success('删除成功')
      fetchJobs()
    } catch {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchJobs()
}

const handleCurrentChange = (page) => {
  currentPage.value = page
  fetchJobs()
}
</script>

<style scoped>
.crowd-analysis-list {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.device-list {
  max-height: 200px;
  overflow-y: auto;
}

.device-preview,
.source-text {
  display: inline-flex;
  align-items: center;
}

.source-text {
  margin-left: 6px;
}

.source-count {
  margin-left: 4px;
  color: #909399;
  font-size: 12px;
}
</style>
