<template>
  <div class="home-container">
    <el-row :gutter="20">
      <el-col :span="6" v-for="card in cards" :key="card.title">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>{{ card.title }}</span>
              <el-tag :type="card.type">{{ card.tag }}</el-tag>
            </div>
          </template>
          <div class="card-content">
            <el-statistic :value="card.value">
              <template #prefix>
                <el-icon><component :is="card.icon" /></el-icon>
              </template>
            </el-statistic>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-4">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>检测结果趋势</span>
            </div>
          </template>
          <div class="chart-container">
            <!-- 这里将添加图表组件 -->
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近检测</span>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="(activity, index) in activities"
              :key="index"
              :type="activity.type"
              :timestamp="activity.timestamp"
            >
              {{ activity.content }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  VideoCameraFilled,
  Warning,
  DataLine,
  Timer
} from '@element-plus/icons-vue'

const cards = ref([
  {
    title: '今日检测',
    value: 234,
    type: '',
    tag: '实时',
    icon: 'VideoCameraFilled'
  },
  {
    title: '异常数量',
    value: 12,
    type: 'danger',
    tag: '需处理',
    icon: 'Warning'
  },
  {
    title: '检测准确率',
    value: 98.5,
    type: 'success',
    tag: '良好',
    icon: 'DataLine'
  },
  {
    title: '平均耗时',
    value: 0.85,
    type: 'warning',
    tag: '秒',
    icon: 'Timer'
  }
])

const activities = ref([
  {
    content: '检测到异常行为',
    timestamp: '10 分钟前',
    type: 'danger'
  },
  {
    content: '系统自动处理完成',
    timestamp: '30 分钟前',
    type: 'success'
  },
  {
    content: '开始新的检测任务',
    timestamp: '1 小时前',
    type: 'primary'
  }
])
</script>

<style scoped>
.home-container {
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

.card-content {
  text-align: center;
  padding: 20px 0;
}

.chart-container {
  height: 350px;
  width: 100%;
}

.mt-4 {
  margin-top: 20px;
}

.el-card {
  margin-bottom: 20px;
  height: 100%;
}

@media screen and (max-width: 1200px) {
  .el-col {
    margin-bottom: 20px;
  }
}

@media screen and (max-width: 768px) {
  .el-col {
    width: 100%;
  }
}
</style> 