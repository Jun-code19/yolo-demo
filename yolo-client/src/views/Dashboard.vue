<template>
  <div class="dashboard-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>实时监控</span>
              <el-button-group>
                <el-button type="primary" :icon="VideoCameraFilled">开始检测</el-button>
                <el-button type="danger" :icon="VideoPlay">录制</el-button>
                <el-button :icon="Camera">截图</el-button>
              </el-button-group>
            </div>
          </template>
          <div class="video-container">
            <div class="video-wrapper">
              <div class="video-placeholder">
                <el-icon :size="64"><VideoCameraFilled /></el-icon>
                <p>等待视频输入</p>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-4">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>检测结果</span>
              <el-radio-group v-model="resultType" size="small">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="warning">警告</el-radio-button>
                <el-radio-button label="danger">危险</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="detectionResults" height="400" style="width: 100%">
            <el-table-column prop="time" label="时间" width="180" />
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.type">{{ row.typeText }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.confidence"
                  :status="row.confidence > 90 ? 'success' : ''"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统状态</span>
              <el-tag type="success">运行中</el-tag>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="CPU使用率">
              <el-progress :percentage="45" />
            </el-descriptions-item>
            <el-descriptions-item label="内存使用率">
              <el-progress :percentage="62" type="warning" />
            </el-descriptions-item>
            <el-descriptions-item label="GPU使用率">
              <el-progress :percentage="28" type="success" />
            </el-descriptions-item>
            <el-descriptions-item label="磁盘使用率">
              <el-progress :percentage="85" type="danger" />
            </el-descriptions-item>
          </el-descriptions>
          <div class="mt-4">
            <h4>系统日志</h4>
            <el-scrollbar height="200px">
              <div v-for="(log, index) in systemLogs" :key="index" class="log-item">
                <el-tag size="small" :type="log.type">{{ log.level }}</el-tag>
                <span class="log-time">{{ log.time }}</span>
                <span class="log-content">{{ log.content }}</span>
              </div>
            </el-scrollbar>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  VideoCameraFilled,
  VideoPlay,
  Camera
} from '@element-plus/icons-vue'

const resultType = ref('all')

const detectionResults = ref([
  {
    time: '2024-03-03 10:00:00',
    type: 'warning',
    typeText: '警告',
    description: '检测到可疑行为',
    confidence: 85
  },
  {
    time: '2024-03-03 10:01:30',
    type: 'danger',
    typeText: '危险',
    description: '检测到危险行为',
    confidence: 95
  },
  {
    time: '2024-03-03 10:02:45',
    type: 'info',
    typeText: '正常',
    description: '正常行为',
    confidence: 78
  }
])

const systemLogs = ref([
  {
    level: 'INFO',
    type: 'info',
    time: '10:00:00',
    content: '系统启动成功'
  },
  {
    level: 'WARN',
    type: 'warning',
    time: '10:01:30',
    content: 'GPU温度较高'
  },
  {
    level: 'ERROR',
    type: 'danger',
    time: '10:02:45',
    content: '视频流连接断开'
  }
])
</script>

<style scoped>
.dashboard-container {
  height: 100%;
  min-width: 0;
}

.el-row {
  margin-bottom: 20px;
  &:last-child {
    margin-bottom: 0;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.video-container {
  width: 100%;
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
}

.video-wrapper {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%; /* 16:9 aspect ratio */
}

.video-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
}

.mt-4 {
  margin-top: 20px;
}

.log-item {
  padding: 8px;
  border-bottom: 1px solid #ebeef5;
  &:last-child {
    border-bottom: none;
  }
}

.log-time {
  margin: 0 10px;
  color: #909399;
}

.log-content {
  color: #606266;
}

.el-card {
  height: 100%;
}

@media screen and (max-width: 1200px) {
  .el-col {
    width: 100% !important;
    margin-bottom: 20px;
  }
}
</style> 