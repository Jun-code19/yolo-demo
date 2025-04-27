<template>
  <div class="crowd-analysis-list">
    <div class="header">
      <h2>人群分析任务</h2>
      <el-button type="primary" @click="router.push('/crowd-analysis/create')">
        创建任务
      </el-button>
    </div>

    <el-card>
      <el-table
        v-loading="loading"
        :data="jobList"
        border
        style="width: 100%"
      >
        <el-table-column prop="job_name" label="任务名称" width="180" />
        <el-table-column label="监控设备" min-width="180">
          <template #default="scope">
            <el-tag v-for="id in scope.row.device_ids" :key="id" size="small" style="margin-right: 5px">
              {{ getDeviceName(id) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="检测模型" width="180">
          <template #default="scope">
            {{ getModelName(scope.row.models_id) }}
          </template>
        </el-table-column>
        <el-table-column label="位置信息" width="150">
          <template #default="scope">
            {{ scope.row.location_info?.name || '无' }}
          </template>
        </el-table-column>
        <el-table-column label="执行频率" width="150">
          <template #default="scope">
            <span v-if="scope.row.cron_expression">{{ scope.row.cron_expression }}</span>
            <span v-else>每{{ scope.row.interval }}秒</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近执行" width="180">
          <template #default="scope">
            {{ scope.row.last_run ? formatDate(scope.row.last_run) : '未执行' }}
          </template>
        </el-table-column>
        <el-table-column label="人数统计" width="120">
          <template #default="scope">
            <span v-if="scope.row.last_result">
              {{ scope.row.last_result.total_person_count || 0 }}人
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="viewDetail(scope.row.job_id)">
              详情
            </el-button>
            <el-button size="small" type="success" @click="runJob(scope.row.job_id)">
              立即执行
            </el-button>
            <el-button 
              size="small" 
              :type="scope.row.is_active ? 'warning' : 'primary'"
              @click="toggleJobStatus(scope.row.job_id, scope.row.is_active)"
            >
              {{ scope.row.is_active ? '停止' : '启动' }}
            </el-button>
            <el-button size="small" type="danger" @click="deleteJob(scope.row.job_id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="jobList.length > 0">
        <el-pagination
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="currentPage"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import { formatDate } from '@/utils/date'

const router = useRouter()
const loading = ref(false)
const jobList = ref([])
const deviceMap = ref({})
const modelMap = ref({})
const total = ref(0)
const pageSize = ref(10)
const currentPage = ref(1)

onMounted(() => {
  fetchJobs()
  fetchDevices()
  fetchModels()
})

const fetchJobs = async () => {
  loading.value = true
  try {
    const res = await crowdAnalysisApi.getAnalysisJobs()
    jobList.value = res.data
    total.value = res.data.length
  } catch (error) {
    ElMessage.error('获取任务列表失败')
    console.error(error)
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
  } catch (error) {
    console.error('获取设备列表失败', error)
  }
}

const fetchModels = async () => {
  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    modelMap.value = {}
    res.data.forEach(item => {
      modelMap.value[item.model_id] = item.model_name
    })
  } catch (error) {
    console.error('获取模型列表失败', error)
  }
}

const getDeviceName = (deviceId) => {
  return deviceMap.value[deviceId] || deviceId
}

const getModelName = (modelId) => {
  return modelMap.value[modelId] || modelId
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

const viewDetail = (jobId) => {
  router.push(`/crowd-analysis/detail/${jobId}`)
}

const runJob = async (jobId) => {
  try {
    await crowdAnalysisApi.runAnalysisJobNow(jobId)
    ElMessage.success('任务已开始执行')
    
    // 创建定时器，每3秒刷新一次任务列表，直到指定任务状态变为完成或出错
    const statusCheckInterval = setInterval(async () => {
      await fetchJobs()
      // 查找当前任务
      const currentJob = jobList.value.find(job => job.job_id === jobId)
      // 如果任务完成或出错，停止定时器
      if (currentJob && ['completed', 'error'].includes(currentJob.status)) {
        clearInterval(statusCheckInterval)
        if (currentJob.status === 'completed') {
          ElMessage.success('任务执行完成')
        } else if (currentJob.status === 'error') {
          ElMessage.error(`任务执行出错: ${currentJob.last_error || '未知错误'}`)
        }
      }
    }, 3000)
    
    // 30分钟后自动停止检查，避免无限循环
    setTimeout(() => {
      clearInterval(statusCheckInterval)
    }, 30 * 60 * 1000)
    
    // 立即刷新一次
    fetchJobs()
  } catch (error) {
    ElMessage.error('执行任务失败')
    console.error(error)
  }
}

const toggleJobStatus = async (jobId, isActive) => {
  try {
    if (isActive) {
      // 暂停任务
      await crowdAnalysisApi.pauseAnalysisJob(jobId)
      ElMessage.success('任务已暂停')
    } else {
      // 恢复任务
      await crowdAnalysisApi.resumeAnalysisJob(jobId)
      ElMessage.success('任务已恢复')
    }
    fetchJobs()
  } catch (error) {
    ElMessage.error(`${isActive ? '暂停' : '恢复'}任务失败`)
    console.error(error)
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
    } catch (error) {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }).catch(() => {})
}

const handleSizeChange = (size) => {
  pageSize.value = size
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
  display: flex;
  justify-content: flex-end;
}
</style>
