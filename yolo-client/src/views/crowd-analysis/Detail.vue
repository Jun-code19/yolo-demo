<template>
  <div class="crowd-analysis-detail">
    <div class="header">
      <h2>{{ job.job_name || '任务详情' }}</h2>
      <div>
        <el-button @click="router.push('/crowd-analysis')">返回列表</el-button>
        <el-button type="primary" @click="runJob">立即执行</el-button>
        <el-button :type="job.is_active ? 'warning' : 'success'" @click="toggleJobStatus">
          {{ job.is_active ? '停止任务' : '启动任务' }}
        </el-button>
        <el-dropdown @command="handleExport" class="export-button">
          <el-button type="primary" plain>
            数据导出<i class="el-icon-arrow-down el-icon--right"></i>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="7">最近7天</el-dropdown-item>
              <el-dropdown-item command="30">最近30天</el-dropdown-item>
              <el-dropdown-item command="90">最近90天</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-card class="info-card" v-loading="loading">
      <template #header>
        <div>
          <span>基本信息</span>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ job.job_id }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ job.job_name }}</el-descriptions-item>
        <el-descriptions-item label="执行频率">
          <span v-if="job.cron_expression">{{ job.cron_expression }}</span>
          <span v-else>每{{ job.interval }}秒</span>
        </el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag :type="getStatusType(job.status)">{{ job.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(job.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="最近执行">{{ job.last_run ? formatDate(job.last_run) : '未执行' }}</el-descriptions-item>
        <el-descriptions-item label="监控设备数量">{{ job.device_ids?.length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="检测模型">{{ modelInfo?.model_name || job.models_id }}</el-descriptions-item>
        <el-descriptions-item label="置信度阈值">{{ Math.round((job.confidence_threshold || 0.5) * 100) }}%</el-descriptions-item>
        <el-descriptions-item label="标签">
          <el-tag v-for="tag in job.tags" :key="tag" size="small" style="margin-right: 5px">
            {{ tag }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="位置信息" :span="2">
          {{ getLocationInfo() }}
        </el-descriptions-item>
        <el-descriptions-item label="人数预警阈值">
          {{ job.warning_threshold ? `${job.warning_threshold}人` : '不预警' }}
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          {{ job.description || '无' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="result-card" v-if="job.last_result">
      <template #header>
        <div>
          <span>最近分析结果</span>
          <span style="margin-left: 10px; color: #909399; font-size: 13px">
            ({{ job.last_result?.timestamp ? formatDateTime(job.last_result.timestamp) : '' }})
          </span>
        </div>
      </template>
      <div class="result-summary">
        <div class="total-count">
          <span class="count-number">{{ job.last_result?.total_person_count || 0 }}</span>
          <span class="count-label">总人数</span>
        </div>
      </div>
    </el-card>

    <el-card class="devices-card" v-if="job.device_ids && job.device_ids.length > 0">
      <template #header>
        <div>
          <span>监控设备列表</span>
        </div>
      </template>
      <el-table :data="devicesList" border style="width: 100%">
        <el-table-column prop="device_id" label="设备ID" width="180" />
        <el-table-column prop="device_name" label="设备名称" width="180" />
        <el-table-column prop="ip_address" label="IP地址" width="180" />
        <el-table-column prop="channel" label="通道号" width="180" />
        <el-table-column prop="location" label="位置信息" width="180" />
        <el-table-column v-if="job.last_result" label="人数" width="180">
          <template #default="scope">
            {{ job.last_result.camera_counts.find(item => item.device_id === scope.row.device_id)?.person_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column v-if="job.last_result" label="预览图" width="150">
          <template #default="scope">
            <el-image v-if="cameraCounts.find(item => item.device_id === scope.row.device_id)?.preview_image" :src="getImageUrl(cameraCounts.find(item => item.device_id === scope.row.device_id)?.preview_image)"
              style="max-height: 160px; max-width: 280px; cursor: pointer;" fit="contain" :initial-index="0"
              :z-index="3000" @click="showFullImage(cameraCounts.find(item => item.device_id === scope.row.device_id))" />
            <span v-else>无预览图</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="180">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'online' ? 'success' : 'danger'">
              {{ scope.row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>历史数据</span>
          <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期"
            end-placeholder="结束日期" @change="fetchHistoryData" size="small" style="width: 300px;" />
        </div>
      </template>

      <div class="chart-container" ref="chartContainer" v-loading="historyLoading">
        <div id="historyChart" style="width: 100%; height: 400px;"></div>
      </div>

      <div class="no-data" v-if="!hasHistoryData">
        <el-empty description="暂无历史数据" />
      </div>

      <!-- 历史数据表格视图 -->
      <div class="history-table-view" v-if="hasHistoryData">
        <div class="table-header">
          <div>
            <h4>历史记录</h4>
            <p class="data-hint">表格显示完整数据，图表显示采样数据</p>
          </div>
          <div class="table-controls">
            <el-radio-group v-model="historyViewMode" size="small" style="margin-left: 10px;">
              <el-radio-button value="chart">图表</el-radio-button>
              <el-radio-button value="table">表格</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <el-table v-if="historyViewMode === 'table'" :data="historyData" border size="small"
          style="width: 100%; margin-top: 15px;">
          <el-table-column label="时间" width="180">
            <template #default="scope">
              {{ formatDateTime(scope.row.timestamp) }}
            </template>
          </el-table-column>
          <el-table-column label="总人数" width="100">
            <template #default="scope">
              {{ scope.row.total_person_count }}
            </template>
          </el-table-column>
          <el-table-column label="设备人数详情">
            <template #default="scope">
              <el-tag v-for="camera in scope.row.camera_counts" :key="camera.device_id"
                style="margin-right: 5px; margin-bottom: 5px;" :type="camera.person_count > 0 ? 'primary' : 'info'">
                {{ camera.device_name || camera.device_id }}: {{ camera.person_count }}人
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-card class="error-card" v-if="job.last_error">
      <template #header>
        <div>
          <span>错误信息</span>
        </div>
      </template>
      <el-alert type="error" :title="job.last_error" :closable="false" show-icon />
    </el-card>

    <!-- 全屏预览对话框 -->
    <el-dialog v-model="fullImageVisible" title="检测结果详情" width="50%" top="5vh" :before-close="handleCloseFullImage"
      :close-on-click-modal="true" :z-index="9999" :modal="true" :append-to-body="true" class="full-image-dialog">
      <div class="full-image-container">
        <div class="image-info">
          <h3>{{ currentImage.device_name }}</h3>
          <p>位置: {{ currentImage.location || '未知' }}</p>
          <p>时间: {{ formatDateTime(currentImage.timestamp) }}</p>
          <p>检测到人数: <span class="person-count">{{ currentImage.person_count }}</span></p>
        </div>
        <div class="image-wrapper">
          <img v-if="currentImage.preview_image" :src="getImageUrl(currentImage.preview_image)" alt="检测结果"
            class="full-preview-image" />
        </div>
        <div class="detection-details" v-if="currentImage.person_detections && currentImage.person_detections.length">
          <h4>检测详情</h4>
          <el-table :data="currentImage.person_detections" border size="small">
            <el-table-column label="#" type="index" width="50" />
            <el-table-column label="类别" width="100">
              <template #default="scope">
                {{ scope.row.class_id + ' : ' + scope.row.class_name }}
              </template>
            </el-table-column>
            <el-table-column label="位置" width="180">
              <template #default="scope">
                {{ formatBoxCoordinates(scope.row.bbox) }}
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="100">
              <template #default="scope">
                <el-progress :percentage="Math.round(scope.row.confidence * 100)"
                  :color="getConfidenceColor(scope.row.confidence)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import { formatDate, formatDateTime } from '@/utils/date'
import * as echarts from 'echarts'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const job = ref({})
const devicesList = ref([])
const cameraCounts = ref([])
const dateRange = ref([])
const hasHistoryData = ref(false)
const modelInfo = ref(null)
const fullImageVisible = ref(false)
const currentImage = ref(null)
const historyLoading = ref(false)
const historyViewMode = ref('chart')
const historyData = ref([])
let chart = null

onMounted(() => {
  fetchJobDetail()
  // fetchDevicesInfo()
  // fetchModelInfo()

  // 初始化日期范围为最近7天
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 1)
  dateRange.value = [start, end]

  // 延迟初始化图表，确保DOM已加载
  setTimeout(() => {
    initChart()
    fetchHistoryData()
  }, 1000)
})

onBeforeUnmount(() => {
  if (chart) {
    chart.dispose()
  }
})

const fetchJobDetail = async () => {
  loading.value = true
  try {
    const jobId = route.params.id
    const res = await crowdAnalysisApi.getAnalysisJob(jobId)
    job.value = res.data

    // 如果有最近分析结果，提取摄像头分析数据
    if (job.value.last_result && job.value.last_result.camera_counts) {
      cameraCounts.value = job.value.last_result.camera_counts
    }

    // 获取模型信息
    if (job.value.models_id) {
      fetchModelInfo()
    }
    // 获取设备详情
    if (job.value.device_ids && job.value.device_ids.length > 0) {
      fetchDevicesInfo()
    }

  } catch (error) {
    // console.error(error)
    ElMessage.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

const fetchDevicesInfo = async () => {
  try {
    // 使用真实API获取设备详情
    if (!job.value.device_ids || job.value.device_ids.length === 0) return

    const res = await crowdAnalysisApi.getDevicesDetails(job.value.device_ids);
    if (res.data) {
      devicesList.value = res.data;
    }
  } catch (error) {
    // console.error('获取设备信息失败', error);
    // 出错时使用备用模拟数据
    const devicePromises = job.value.device_ids.map(id =>
      new Promise(resolve => {
        setTimeout(() => {
          resolve({
            device_id: id,
            device_name: `设备 ${id}`,
            ip_address: `192.168.1.${parseInt(Math.random() * 255)}`,
            location: `位置 ${id}`,
            status: Math.random() > 0.2 ? 'online' : 'offline'
          })
        }, 300)
      })
    );

    devicesList.value = await Promise.all(devicePromises);
  }
}

const fetchModelInfo = async () => {
  if (!job.value?.models_id) return

  try {
    const res = await crowdAnalysisApi.getAvailableModels()
    const models = res.data || []
    modelInfo.value = models.find(m => m.model_id === job.value.models_id) || null
  } catch (error) {
    // console.error('获取模型信息失败:', error)
  }
}

const getStatusType = (status) => {
  const map = {
    scheduled: 'info',
    running: 'warning',
    completed: 'success',
    error: 'danger',
    created: 'primary',
    paused: 'info'
  }
  return map[status] || 'primary'
}

const getLocationInfo = () => {
  if (!job.value.location_info) return '无'

  const info = []
  if (job.value.location_info.name) {
    info.push(job.value.location_info.name)
  }
  if (job.value.location_info.address) {
    info.push(job.value.location_info.address)
  }
  if (job.value.location_info.coordinates &&
    job.value.location_info.coordinates.length === 2) {
    info.push(`坐标: ${job.value.location_info.coordinates.join(', ')}`)
  }

  return info.length > 0 ? info.join(' | ') : '无'
}

const getImageUrl = (imageData) => {
  // 如果imageData是base64编码的图像数据
  if (typeof imageData === 'string') {
    if (imageData.startsWith('data:image')) {
      return imageData;
    } else {
      // 如果是纯base64字符串，添加前缀
      return `data:image/jpeg;base64,${imageData}`;
    }
  }

  // 其他情况下可能需要构建URL或处理二进制数据
  // 这里假设后端已经返回了可用的URL或base64数据
  return `data:image/jpeg;base64,${imageData}`;
}

const runJob = async () => {
  try {
    await crowdAnalysisApi.runAnalysisJobNow(job.value.job_id)
    ElMessage.success('任务已开始执行')

    // 创建定时器，每3秒刷新一次任务详情，直到任务状态变为完成或出错
    const statusCheckInterval = setInterval(async () => {
      await fetchJobDetail()
      // 检查当前任务状态
      if (['completed', 'error'].includes(job.value.status)) {
        clearInterval(statusCheckInterval)
        if (job.value.status === 'completed') {
          ElMessage.success('任务执行完成')
        } else if (job.value.status === 'error') {
          ElMessage.error(`任务执行出错: ${job.value.last_error || '未知错误'}`)
        }
      }
    }, 3000)

    // 30分钟后自动停止检查，避免无限循环
    setTimeout(() => {
      clearInterval(statusCheckInterval)
    }, 30 * 60 * 1000)

    // 立即刷新一次
    fetchJobDetail()
  } catch (error) {
    ElMessage.error('执行任务失败')
    // console.error(error)
  }
}

const toggleJobStatus = async () => {
  try {
    if (job.value.is_active) {
      // 暂停任务
      await crowdAnalysisApi.pauseAnalysisJob(job.value.job_id)
      ElMessage.success('任务已暂停')
    } else {
      // 恢复任务
      await crowdAnalysisApi.resumeAnalysisJob(job.value.job_id)
      ElMessage.success('任务已恢复')
    }
    // 刷新任务详情
    fetchJobDetail()
  } catch (error) {
    ElMessage.error(`${job.value.is_active ? '暂停' : '恢复'}任务失败`)
    // console.error(error)
  }
}

const handleExport = async (days) => {
  try {
    const res = await crowdAnalysisApi.exportAnalysisResults(job.value.job_id, days)

    // 处理导出数据，这里可以是下载文件或展示数据
    if (res.data && res.data.data) {
      // 创建CSV数据
      const csvContent = generateCSV(res.data.data)

      // 创建下载链接
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `人群分析_${job.value.job_name}_${days}天.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      ElMessage.success('导出成功')
    } else {
      ElMessage.warning('无数据可导出')
    }
  } catch (error) {
    ElMessage.error('导出失败')
    // console.error(error)
  }
}

const generateCSV = (data) => {
  // 生成CSV格式数据
  const header = '日期,总人数,位置\n'
  let content = header

  if (data.results && data.results.length > 0) {
    data.results.forEach(item => {
      content += `${formatDateTime(item.timestamp)},${item.total_person_count},${data.job_name}\n`
    })
  }

  return content
}

const initChart = () => {
  const chartDom = document.getElementById('historyChart')
  if (!chartDom) return

  chart = echarts.init(chartDom)

  // 基础配置
  const option = {
    title: {
      text: '人数变化趋势 (每30分钟采样)',
      left: 'center',
      subtext: '图表显示采样数据，表格显示完整数据',
      subtextStyle: {
        fontSize: 12,
        color: '#909399'
      }
    },
    tooltip: {
      trigger: 'axis',
      formatter: function (params) {
        if (params.length === 0) return '';
        const date = new Date(params[0].value[0]);
        let res = formatDateTime(date) + '<br/>';

        params.forEach(param => {
          res += param.marker + ' ' + param.seriesName + ': ' + param.value[1] + '人<br/>';
        });

        return res;
      }
    },
    legend: {
      data: ['总人数'],
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '60px',
      top: '60px',
      containLabel: true
    },
    toolbox: {
      feature: {
        saveAsImage: {
          title: '保存'
        },
        myRefresh: {
          show: true,
          title: '刷新',
          icon: 'path://M838.016 596.48a21.333333 21.333333 0 0 1 15.018667 26.154667 352.725333 352.725333 0 0 1-340.010667 259.84c-123.818667 0-236.629333-65.792-299.690667-167.637334v146.304a21.333333 21.333333 0 1 1-42.666666 0v-240.128a21.333333 21.333333 0 0 1 21.333333-21.333333c0.981333 0 1.834667 0.426667 2.730667 0.554667a20.906667 20.906667 0 0 1 20.565333 15.189333c37.674667 132.096 160.085333 224.384 297.728 224.384 139.52 0 262.4-93.866667 298.837333-228.309333a21.333333 21.333333 0 0 1 26.154667-15.018667z m-647.253333-144.042667a21.333333 21.333333 0 0 1-14.037334-26.709333 350.506667 350.506667 0 0 1 336.298667-247.210667 349.866667 349.866667 0 0 1 295.722667 162.090667V192a21.333333 21.333333 0 1 1 42.666666 0v240.042667c0 11.818667-9.514667 21.333333-21.333333 21.333333-0.853333 0-1.578667-0.384-2.432-0.469333-1.152-0.085333-2.133333-0.426667-3.285333-0.682667-1.109333-0.298667-2.218667-0.469333-3.242667-0.938667a21.077333 21.077333 0 0 1-12.586667-13.226666 308.224 308.224 0 0 0-295.509333-216.874667 308.010667 308.010667 0 0 0-295.552 217.216 21.333333 21.333333 0 0 1-26.709333 14.037333z',
          onclick: function () {
            refreshHistoryData();
          }
        },
        myDataSift: {
          show: true,
          title: '数据筛选',
          icon: 'path://M192 809.472a21.333333 21.333333 0 0 1-19.029333-30.976l183.552-363.52a21.333333 21.333333 0 1 1 38.101333 19.285333l-183.594667 363.52a21.333333 21.333333 0 0 1-19.029333 11.690667 M551.68 794.453333a21.248 21.248 0 0 1-18.986667-11.690666l-176.128-348.501334a21.333333 21.333333 0 1 1 38.058667-19.285333l176.128 348.501333a21.333333 21.333333 0 0 1-19.029333 31.018667 M551.68 794.453333a21.290667 21.290667 0 0 1-18.176-32.426666l269.781333-442.154667a21.333333 21.333333 0 1 1 36.437334 22.186667L569.941333 784.213333a21.290667 21.290667 0 0 1-18.218666 10.24 M641.706667 394.752a21.290667 21.290667 0 0 1-6.144-41.813333l179.626666-53.376a21.290667 21.290667 0 1 1 12.16 40.874666L647.765333 393.813333a21.76 21.76 0 0 1-6.101333 0.853334 M874.666667 520.917333a21.290667 21.290667 0 0 1-20.437334-15.232L800.853333 326.101333a21.333333 21.333333 0 0 1 40.96-12.202666l53.333334 179.626666a21.333333 21.333333 0 0 1-20.437334 27.392',
          onclick: function () {
            // console.log('数据筛选,功能开发中...')
          }
        }
      }
    },
    dataZoom: [{
      type: 'inside',
      start: 0,
      end: 100
    }, {
      start: 0,
      end: 100
    }],
    xAxis: {
      type: 'time',
      splitLine: {
        show: false
      },
      axisLabel: {
        formatter: function (value) {
          const date = new Date(value);
          return `${date.getMonth() + 1}-${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
        }
      }
    },
    yAxis: {
      type: 'value',
      name: '人数',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      },
      min: 0
    },
    series: [{
      name: '总人数',
      type: 'line',
      smooth: true,
      lineStyle: {
        width: 3,
        shadowColor: 'rgba(0,0,0,0.3)',
        shadowBlur: 10,
        shadowOffsetY: 8
      },
      itemStyle: {
        color: '#409EFF'
      },
      data: []
    }]
  }

  chart.setOption(option)

  // 监听窗口大小变化，调整图表大小
  window.addEventListener('resize', () => {
    chart && chart.resize()
  })
}

const fetchHistoryData = async () => {
  if (!job.value.job_id || !dateRange.value || dateRange.value.length < 2) return;

  try {
    historyLoading.value = true;
    const [startDate, endDate] = dateRange.value;

    const res = await crowdAnalysisApi.getAnalysisHistory(job.value.job_id, startDate, endDate);
    historyData.value = res.data.data_points || [];
    hasHistoryData.value = historyData.value.length > 0;

    // 更新图表 - 每半小时抽取一条数据
    if (chart && hasHistoryData.value) {
      // 对数据进行排序，确保时间顺序正确
      const sortedData = [...historyData.value].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      
      // 每半小时抽取一条数据（30分钟 = 30 * 60 * 1000毫秒）
      const sampledData = sampleDataByInterval(sortedData, 60 * 60 * 1000);
      
      // 准备总人数数据（使用采样后的数据）
      const totalPersonData = sampledData.map(item => {
        const timestamp = new Date(item.timestamp).getTime();
        return [timestamp, item.total_person_count];
      });

      // 准备各设备数据（使用采样后的数据）
      const deviceData = {};
      const deviceNames = {};

      sampledData.forEach(item => {
        if (item.camera_counts && item.camera_counts.length) {
          item.camera_counts.forEach(camera => {
            if (!deviceData[camera.device_id]) {
              deviceData[camera.device_id] = [];
              deviceNames[camera.device_id] = camera.device_name || `设备${camera.device_id}`;
            }

            const timestamp = new Date(item.timestamp).getTime();
            deviceData[camera.device_id].push([
              timestamp,
              camera.person_count
            ]);
          });
        }
      });

      // 构建图表系列
      const series = [{
        name: '总人数',
        type: 'line',
        smooth: true,
        lineStyle: {
          width: 3,
          shadowColor: 'rgba(0,0,0,0.3)',
          shadowBlur: 10,
          shadowOffsetY: 8
        },
        itemStyle: {
          color: '#409EFF'
        },
        data: totalPersonData
      }];

      // 添加各设备的数据线
      Object.keys(deviceData).forEach(deviceId => {
        series.push({
          name: deviceNames[deviceId],
          type: 'line',
          smooth: true,
          symbol: 'emptyCircle',
          symbolSize: 6,
          data: deviceData[deviceId]
        });
      });

      // 更新图表配置
      chart.setOption({
        legend: {
          data: ['总人数', ...Object.values(deviceNames)],
          bottom: 0
        },
        series: series
      });
    }
  } catch (error) {
    // console.error('获取历史数据失败', error);
    ElMessage.error('获取历史数据失败');
  } finally {
    historyLoading.value = false;
  }
};

// 按时间间隔采样数据的函数
const sampleDataByInterval = (data, intervalMs) => {
  if (data.length <= 1) return data;
  
  const sampled = [data[0]]; // 保留第一条数据
  let lastSampledTime = new Date(data[0].timestamp).getTime();
  
  for (let i = 1; i < data.length; i++) {
    const currentTime = new Date(data[i].timestamp).getTime();
    if (currentTime - lastSampledTime >= intervalMs) {
      sampled.push(data[i]);
      lastSampledTime = currentTime;
    }
  }
  
  // 确保最后一条数据也被包含
  if (sampled[sampled.length - 1] !== data[data.length - 1]) {
    sampled.push(data[data.length - 1]);
  }
  
  return sampled;
};

const showFullImage = (image) => {
  // 深拷贝对象，避免修改原始数据
  currentImage.value = JSON.parse(JSON.stringify(image));
  fullImageVisible.value = true;
}

const handleCloseFullImage = () => {
  fullImageVisible.value = false;
}

const formatBoxCoordinates = (box) => {
  if (!box || !Array.isArray(box) || box.length < 4) {
    return '未知';
  }
  const [x1, y1, x2, y2] = box.map(coord => Math.round(coord));
  return `左上(${x1}, ${y1}) - 右下(${x2}, ${y2})`;
}

const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) {
    return '#67C23A'; // 高置信度 - 绿色
  } else if (confidence >= 0.6) {
    return '#E6A23C'; // 中等置信度 - 黄色
  } else {
    return '#F56C6C'; // 低置信度 - 红色
  }
}

const refreshHistoryData = async () => {
  try {

    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - 1)
    dateRange.value = [start, end]

    await fetchHistoryData();
  } catch (error) {
    // console.error('刷新历史数据失败', error);
    ElMessage.error('刷新历史数据失败');
  }
}

</script>

<style scoped>
.crowd-analysis-detail {
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.info-card,
.result-card,
.devices-card,
.history-card,
.error-card {
  margin-bottom: 20px;
}

.result-summary {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.total-count {
  text-align: center;
  padding: 20px;
  border-radius: 4px;
  background-color: #f0f9eb;
}

.count-number {
  font-size: 42px;
  font-weight: bold;
  color: #67c23a;
  display: block;
}

.count-label {
  font-size: 16px;
  color: #606266;
}

.sub-title {
  margin: 20px 0 10px;
  font-size: 16px;
  color: #606266;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  margin-top: 20px;
}

.no-data {
  padding: 40px 0;
  text-align: center;
}

.export-button {
  margin-left: 12px;
}

.full-image-container {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.image-info {
  /* margin-bottom: 20px; */
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.image-info h3 {
  margin-top: 0;
  color: #303133;
}

.image-info p {
  margin: 5px 0;
  color: #606266;
}

.person-count {
  font-weight: bold;
  color: #409EFF;
  font-size: 18px;
}

.image-wrapper {
  display: flex;
  justify-content: center;
  margin: 20px 0;
  background-color: #000;
  padding: 10px;
  border-radius: 4px;
  width: 100%;
}

.full-preview-image {
  max-height: 70vh;
  max-width: 100%;
  object-fit: contain;
}

.detection-details {
  margin-bottom: 20px;
  width: 100%;
}

.detection-details h4 {
  margin-bottom: 15px;
  color: #303133;
}

.history-table-view {
  margin-top: 20px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.table-controls {
  display: flex;
  align-items: center;
}

.data-hint {
  margin: 5px 0 0 0;
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.hint,
.cron-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 5px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.model-option,
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

.full-image-dialog {
  z-index: 9999;
}

.edit-dialog {
  z-index: 9999;
}
</style>

<style>
/* 全局样式确保对话框最高优先级 */
.full-image-dialog .el-dialog__wrapper,
.edit-dialog .el-dialog__wrapper {
  z-index: 10000 !important;
}

.full-image-dialog .el-overlay,
.edit-dialog .el-overlay {
  z-index: 9999 !important;
}

.full-image-dialog .el-dialog,
.edit-dialog .el-dialog {
  z-index: 10000 !important;
}

/* 通用对话框优先级保障 */
.el-dialog__wrapper {
  z-index: 9999 !important;
}

.el-overlay {
  z-index: 9998 !important;
}

/* 确保下拉框选项在对话框中正常显示 */
.el-select-dropdown {
  z-index: 10001 !important;
}

.el-popper {
  z-index: 10001 !important;
}

/* 特别针对编辑对话框中的下拉框 */
.edit-dialog .el-select-dropdown {
  z-index: 10002 !important;
}

.edit-dialog .el-popper {
  z-index: 10002 !important;
}

/* 专门针对编辑对话框的下拉框弹出层 */
.edit-dialog-select {
  z-index: 10003 !important;
}

/* 日期选择器等其他popper元素 */
.el-picker-panel {
  z-index: 10001 !important;
}

.edit-dialog .el-picker-panel {
  z-index: 10002 !important;
}
</style>
