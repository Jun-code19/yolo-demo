<template>
  <div class="detection-container">
    <div class="page-header">
      <h2>实时检测</h2>
      <div class="header-controls">
        <el-select
          v-model="selectedModel"
          placeholder="选择检测模型"
          class="model-select"
          filterable
        >
          <el-option-group
            v-for="group in models"
            :key="group.type"
            :label="group.type"
          >
            <el-option
              v-for="model in group.models"
              :key="model.value"
              :label="model.label"
              :value="model.value"
            >
              <div class="model-option">
                <span class="model-name">{{ model.label }}</span>
                <span class="model-desc">{{ model.description }}</span>
              </div>
            </el-option>
          </el-option-group>
        </el-select>
        <el-select
          v-model="selectedDevice"
          placeholder="选择摄像头"
          :disabled="isDetecting"
        >
          <el-option
            v-for="device in devices"
            :key="device.deviceId"
            :label="device.label"
            :value="device.deviceId"
          />
        </el-select>
        <el-button-group>
          <el-button
            type="primary"
            :disabled="!selectedDevice || !selectedModel"
            @click="toggleDetection"
          >
            {{ isDetecting ? '停止检测' : '开始检测' }}
          </el-button>
          <el-button
            type="info"
            :disabled="!selectedModel"
            @click="showModelInfo"
          >
            模型信息
          </el-button>
        </el-button-group>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="video-card">
          <template #header>
            <div class="video-header">
              <div class="video-status">
                <el-tag :type="isDetecting ? 'success' : 'info'" effect="dark">
                  {{ isDetecting ? '检测中' : '未开始' }}
                </el-tag>
                <span class="fps" v-if="isDetecting">30 FPS</span>
              </div>
              <div class="video-controls">
                <el-button-group>
                  <el-button 
                    type="primary" 
                    :icon="isFullscreen ? 'FullscreenExit' : 'FullScreen'"
                    @click="toggleFullscreen"
                  >
                    {{ isFullscreen ? '退出全屏' : '全屏' }}
                  </el-button>
                  <el-button 
                    type="primary"
                    :icon="isRecording ? 'VideoPause' : 'VideoPlay'"
                    @click="toggleRecording"
                  >
                    {{ isRecording ? '停止录制' : '开始录制' }}
                  </el-button>
                  <el-button 
                    type="primary"
                    icon="Camera"
                    @click="takeSnapshot"
                  >
                    截图
                  </el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          <div class="video-container" ref="videoContainer">
            <div v-if="!isDetecting" class="placeholder">
              <el-icon :size="64"><VideoCamera /></el-icon>
              <p>选择设备并开始检测</p>
            </div>
            <div v-else class="video-wrapper">
              <video ref="videoRef" class="video-player"></video>
              <canvas ref="canvasRef" class="detection-canvas"></canvas>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="detection-info">
          <template #header>
            <div class="card-header">
              <span>检测信息</span>
              <div class="header-actions">
                <el-button-group>
                  <el-button 
                    type="primary" 
                    link 
                    :icon="isAutoScroll ? 'Lock' : 'Unlock'"
                    @click="toggleAutoScroll"
                  >
                    {{ isAutoScroll ? '自动滚动' : '手动滚动' }}
                  </el-button>
                  <el-button 
                    type="primary" 
                    link
                    icon="Delete"
                    @click="clearRecords"
                  >
                    清空记录
                  </el-button>
                </el-button-group>
              </div>
            </div>
          </template>
          
          <div class="info-content">
            <div class="detection-stats">
              <div class="stat-group">
                <div class="stat-item">
                  <label>检测模型</label>
                  <span>{{ selectedModel ? models.find(m => m.value === selectedModel)?.label : '未选择' }}</span>
                </div>
                <div class="stat-item">
                  <label>目标数量</label>
                  <span class="highlight">{{ detectedCount }}</span>
                </div>
              </div>
              <div class="stat-group">
                <div class="stat-item">
                  <label>检测时长</label>
                  <span>{{ detectionTime }}</span>
                </div>
                <div class="stat-item">
                  <label>检测速度</label>
                  <span>{{ fps }} FPS</span>
                </div>
              </div>
            </div>

            <div class="detection-list">
              <div class="list-header">
                <h4>实时检测记录</h4>
                <div class="list-controls">
                  <el-radio-group v-model="logFilter" size="small">
                    <el-radio-button label="all">全部</el-radio-button>
                    <el-radio-button label="detection">检测</el-radio-button>
                    <el-radio-button label="system">系统</el-radio-button>
                  </el-radio-group>
                  <el-button type="primary" link @click="exportRecords">
                    <el-icon><Download /></el-icon>
                    导出记录
                  </el-button>
                </div>
              </div>
              
              <div class="records-container" ref="recordsContainer">
                <el-scrollbar ref="scrollbar" :always="true">
                  <el-timeline>
                    <el-timeline-item
                      v-for="(record, index) in filteredRecords"
                      :key="index"
                      :timestamp="record.time"
                      :type="record.type"
                      :hollow="record.category === 'system'"
                      :size="record.category === 'detection' ? 'large' : 'normal'"
                    >
                      <div class="record-content">
                        <div class="record-header">
                          <el-tag 
                            :type="getRecordTagType(record.type)"
                            size="small"
                            effect="plain"
                          >
                            {{ getRecordTypeText(record.type) }}
                          </el-tag>
                          <span v-if="record.objectCount" class="object-count">
                            检测到 {{ record.objectCount }} 个目标
                          </span>
                        </div>
                        <p class="record-message">{{ record.message }}</p>
                        <div v-if="record.details" class="record-details">
                          <el-collapse>
                            <el-collapse-item>
                              <template #title>
                                <el-icon><InfoFilled /></el-icon>
                                详细信息
                              </template>
                              <div class="details-content">
                                <pre>{{ record.details }}</pre>
                              </div>
                            </el-collapse-item>
                          </el-collapse>
                        </div>
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                </el-scrollbar>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { VideoCamera, Download, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { parse, unparse } from 'papaparse'

// 检测模型列表
const models = [
  {
    type: 'YOLO系列',
    models: [
      { label: 'YOLOv8-n', value: 'yolov8n', description: '速度最快，适合实时检测' },
      { label: 'YOLOv8-s', value: 'yolov8s', description: '速度和精度的平衡' },
      { label: 'YOLOv8-m', value: 'yolov8m', description: '中等精度' },
      { label: 'YOLOv8-l', value: 'yolov8l', description: '高精度' },
      { label: 'YOLOv8-x', value: 'yolov8x', description: '最高精度' },
      { label: 'YOLOv5-n', value: 'yolov5n', description: '轻量级模型' },
      { label: 'YOLOv5-s', value: 'yolov5s', description: '小型模型' },
      { label: 'YOLOv5-m', value: 'yolov5m', description: '中型模型' },
      { label: 'YOLOv5-l', value: 'yolov5l', description: '大型模型' },
      { label: 'YOLOv5-x', value: 'yolov5x', description: '超大模型' }
    ]
  },
  {
    type: 'Faster R-CNN系列',
    models: [
      { label: 'Faster R-CNN (ResNet50)', value: 'faster_rcnn_r50', description: '经典两阶段检测器' },
      { label: 'Faster R-CNN (ResNet101)', value: 'faster_rcnn_r101', description: '高精度两阶段检测器' }
    ]
  },
  {
    type: 'SSD系列',
    models: [
      { label: 'SSD-300', value: 'ssd300', description: '单次检测器(300x300)' },
      { label: 'SSD-512', value: 'ssd512', description: '单次检测器(512x512)' }
    ]
  }
]

const selectedModel = ref('')
const selectedDevice = ref('')
const devices = ref([])
const isDetecting = ref(false)
const videoRef = ref(null)
const detectedCount = ref(0)
const detectionTime = ref('00:00:00')
const detectionRecords = ref([])
const logFilter = ref('all')

// 新增的响应式变量
const isFullscreen = ref(false)
const isRecording = ref(false)
const isAutoScroll = ref(true)
const fps = ref(0)
const videoContainer = ref(null)
const canvasRef = ref(null)
const recordsContainer = ref(null)
const scrollbar = ref(null)

// WebSocket 连接
let ws = null
let canvasContext = null

// 修改WebSocket初始化函数
const initWebSocket = () => {
  ws = new WebSocket('ws://localhost:8765/ws')
  
  ws.onopen = () => {
    console.log('WebSocket connected')
    // 发送模型配置
    if (selectedModel.value) {
      ws.send(JSON.stringify({
        type: 'config',
        model: selectedModel.value
      }))
    }
  }
  
  ws.onclose = () => {
    console.log('WebSocket disconnected')
    if (isDetecting.value) {
      stopDetection()
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    ElMessage.error('WebSocket连接错误')
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleDetectionResult(data)
    } catch (error) {
      console.error('Error processing detection result:', error)
      ElMessage.error('处理检测结果时出错')
    }
  }
}

// 修改发送帧函数
const sendFrame = async () => {
  if (!isDetecting.value || !videoRef.value) {
    return
  }

  if (!ws || ws.readyState !== WebSocket.OPEN) {
    handleDisconnection()
    return
  }

  const currentTime = Date.now()
  if (currentTime - lastFrameTime.value < frameInterval) {
    return
  }

  try {
    const video = videoRef.value
    if (video.readyState < 2) {
      return
    }

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    
    const imageData = canvas.toDataURL('image/jpeg', 0.6)
    
    ws.send(JSON.stringify({
      type: 'frame',
      frame_id: frameId.value++,
      timestamp: currentTime,
      width: video.videoWidth,
      height: video.videoHeight,
      data: imageData
    }))

    lastFrameTime.value = currentTime
  } catch (error) {
    console.error('Error sending frame:', error)
    handleDisconnection()
  }
}

// 获取设备列表
const fetchDevices = async () => {
  try {
    // 这里替换为实际的API调用
    const response = await fetch('/api/devices')
    devices.value = await response.json()
  } catch (error) {
    ElMessage.error('获取设备列表失败')
  }
}

// 更新检测时间
const updateDetectionTime = () => {
  if (!detectionStartTime.value) return
  
  const now = new Date()
  const diff = now - detectionStartTime.value
  const hours = Math.floor(diff / 3600000)
  const minutes = Math.floor((diff % 3600000) / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  
  detectionTime.value = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

// 检测状态变量
const detectionStartTime = ref(null)
const lastFrameTime = ref(0)
const frameCount = ref(0)
const detectedObjects = ref([])

// 修改处理检测结果函数
const handleDetectionResult = (data) => {
  if (!data || !data.objects) return
  
  detectedCount.value = data.objects.length
  
  // 计算延迟
  const latency = Date.now() - data.timestamp
  if (latency > maxLatency) {
    console.log(`Skipping frame due to high latency: ${latency}ms`)
    return
  }
  
  // 更新FPS
  const currentTime = performance.now()
  if (lastFrameTime.value) {
    const timeDiff = currentTime - lastFrameTime.value
    fps.value = Math.round(1000 / timeDiff)
  }
  lastFrameTime.value = currentTime
  
  // 绘制检测框
  drawDetectionBoxes(data.objects)
  
  // 更新检测记录
  if (data.objects.length > 0) {
    const message = `检测到 ${data.objects.length} 个目标`
    addDetectionRecord('success', message)
  }
}

// 绘制检测框
const drawDetectionBoxes = (objects) => {
  const canvas = canvasRef.value
  const video = videoRef.value
  const ctx = canvas.getContext('2d')
  
  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  // 设置画布尺寸与视频一致
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  
  objects.forEach(obj => {
    // 设置检测框样式
    ctx.strokeStyle = getObjectColor(obj.class)
    ctx.lineWidth = 2
    ctx.fillStyle = `${ctx.strokeStyle}80` // 添加50%透明度
    
    // 绘制检测框
    const [x, y, w, h] = obj.bbox
    ctx.strokeRect(x, y, w, h)
    ctx.fillRect(x, y, w, h)
    
    // 绘制标签
    ctx.font = '14px Arial'
    ctx.fillStyle = '#fff'
    const label = `${obj.class} ${Math.round(obj.confidence * 100)}%`
    const textWidth = ctx.measureText(label).width
    
    ctx.fillStyle = ctx.strokeStyle
    ctx.fillRect(x, y - 20, textWidth + 10, 20)
    
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x + 5, y - 5)
  })
}

// 获取目标类别对应的颜色
const getObjectColor = (className) => {
  const colors = {
    person: '#ff0000',
    car: '#00ff00',
    truck: '#0000ff',
    // 添加更多类别的颜色
    default: '#ff9900'
  }
  return colors[className] || colors.default
}

// 开始检测
const startDetection = async () => {
  try {
    // 获取视频流
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { deviceId: selectedDevice.value }
    })
    
    // 设置视频源
    videoRef.value.srcObject = stream
    await videoRef.value.play()
    
    // 设置画布尺寸
    canvasRef.value.width = videoRef.value.videoWidth
    canvasRef.value.height = videoRef.value.videoHeight
    
    // 初始化检测状态
    detectionStartTime.value = new Date()
    frameCount.value = 0
    detectedCount.value = 0
    
    // 开始发送视频帧
    startFrameCapture()
    
    // 开始时间更新
    timeUpdateInterval = setInterval(updateDetectionTime, 1000)
    
    isDetecting.value = true
    addDetectionRecord('success', `开始使用 ${models.find(m => m.value === selectedModel.value).label} 模型检测`)
  } catch (error) {
    ElMessage.error('启动检测失败')
    console.error('Error starting detection:', error)
  }
}

// 停止检测
const stopDetection = () => {
  // 停止视频流
  if (videoRef.value?.srcObject) {
    videoRef.value.srcObject.getTracks().forEach(track => track.stop())
    videoRef.value.srcObject = null
  }
  
  // 清理画布
  const ctx = canvasRef.value?.getContext('2d')
  if (ctx) {
    ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  }
  
  // 重置状态
  isDetecting.value = false
  detectionStartTime.value = null
  clearInterval(timeUpdateInterval)
  
  addDetectionRecord('info', '检测已停止')
}

// 发送视频帧进行检测
const startFrameCapture = () => {
  const captureFrame = () => {
    if (!isDetecting.value) return
    
    const canvas = document.createElement('canvas')
    const video = videoRef.value
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)
    
    // 将帧数据发送到服务器
    if (ws && ws.readyState === WebSocket.OPEN) {
      canvas.toBlob(blob => {
        ws.send(JSON.stringify({
          type: 'frame',
          model: selectedModel.value,
          data: blob
        }))
      }, 'image/jpeg', 0.8)
    }
    
    // 请求下一帧
    requestAnimationFrame(captureFrame)
  }
  
  captureFrame()
}

// 修改toggleDetection函数
const toggleDetection = async () => {
  if (!selectedDevice.value || !selectedModel.value) {
    ElMessage.warning('请选择摄像头和检测模型')
    return
  }

  if (isDetecting.value) {
    stopDetection()
  } else {
    startDetection()
  }
}

// 生命周期钩子
onMounted(() => {
  fetchDevices()
  initWebSocket()
})

onUnmounted(() => {
  if (isDetecting.value) {
    stopDetection()
  }
  if (ws) {
    ws.close()
  }
})

// 添加检测记录
const addDetectionRecord = (type, message, details = null, objectCount = null) => {
  detectionRecords.value.unshift({
    time: new Date().toLocaleTimeString(),
    type,
    message,
    details,
    objectCount,
    category: type === 'success' && objectCount ? 'detection' : 'system'
  })
}

// 过滤记录
const filteredRecords = computed(() => {
  if (logFilter.value === 'all') return detectionRecords.value
  return detectionRecords.value.filter(record => record.category === logFilter.value)
})

// 获取记录类型标签样式
const getRecordTagType = (type) => {
  const typeMap = {
    success: 'success',
    warning: 'warning',
    error: 'danger',
    info: 'info'
  }
  return typeMap[type]
}

// 获取记录类型文本
const getRecordTypeText = (type) => {
  const textMap = {
    success: '成功',
    warning: '警告',
    error: '错误',
    info: '信息'
  }
  return textMap[type]
}

// 导出记录
const exportRecords = () => {
  if (detectionRecords.value.length === 0) {
    ElMessage.warning('没有可导出的记录')
    return
  }

  try {
    const records = detectionRecords.value.map(record => ({
      时间: record.time,
      类型: getRecordTypeText(record.type),
      消息: record.message,
      目标数量: record.objectCount || '-',
      详细信息: record.details ? JSON.stringify(record.details) : '-'
    }))
    
    const csv = unparse(records, {
      quotes: true, // 在所有字段周围添加引号
      delimiter: ',', // 使用逗号作为分隔符
      header: true // 包含表头
    })
    
    // 添加 BOM 以确保 Excel 正确显示中文
    const csvContent = '\ufeff' + csv
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    
    // 创建下载链接
    const link = document.createElement('a')
    const now = new Date()
    const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19)
    link.download = `detection_records_${timestamp}.csv`
    link.href = URL.createObjectURL(blob)
    
    // 触发下载
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // 清理 URL 对象
    URL.revokeObjectURL(link.href)
    
    ElMessage.success('记录导出成功')
  } catch (error) {
    console.error('Error exporting records:', error)
    ElMessage.error('导出记录失败：' + (error.message || '未知错误'))
  }
}

// 更新检测记录示例
const updateDetectionExample = () => {
  addDetectionRecord('success', '检测到行人和汽车', {
    persons: 2,
    cars: 1,
    confidence: 0.92
  }, 3)
}

// 全屏控制
const toggleFullscreen = async () => {
  if (!isFullscreen.value) {
    try {
      await videoContainer.value.requestFullscreen()
      isFullscreen.value = true
    } catch (error) {
      ElMessage.error('无法进入全屏模式')
    }
  } else {
    try {
      await document.exitFullscreen()
      isFullscreen.value = false
    } catch (error) {
      ElMessage.error('无法退出全屏模式')
    }
  }
}

// 录制控制
const toggleRecording = () => {
  if (!isDetecting.value) {
    ElMessage.warning('请先开始检测')
    return
  }
  isRecording.value = !isRecording.value
  if (isRecording.value) {
    addDetectionRecord('info', '开始录制视频')
  } else {
    addDetectionRecord('info', '停止录制视频')
  }
}

// 截图功能
const takeSnapshot = () => {
  if (!isDetecting.value) {
    ElMessage.warning('请先开始检测')
    return
  }
  
  try {
    const canvas = document.createElement('canvas')
    const video = videoRef.value
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    
    const link = document.createElement('a')
    link.download = `snapshot_${new Date().toISOString().slice(0, 19).replace(/[:.]/g, '-')}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
    
    addDetectionRecord('success', '截图已保存')
  } catch (error) {
    ElMessage.error('截图失败')
    console.error('Error taking snapshot:', error)
  }
}

// 自动滚动控制
const toggleAutoScroll = () => {
  isAutoScroll.value = !isAutoScroll.value
}

// 清空记录
const clearRecords = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有检测记录吗？此操作不可恢复。',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    detectionRecords.value = []
    ElMessage.success('记录已清空')
  } catch {
    // 用户取消操作
  }
}

// 监听记录变化，自动滚动
watch(filteredRecords, () => {
  if (isAutoScroll.value && scrollbar.value) {
    nextTick(() => {
      scrollbar.value.setScrollTop(0)
    })
  }
})
</script>

<style scoped>
.detection-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #2c3e50;
}

.header-controls {
  display: flex;
  gap: 16px;
  align-items: center;
}

.model-select {
  width: 240px;
}

.video-card {
  margin-bottom: 20px;
}

.video-container {
  width: 100%;
  height: 600px;
  background-color: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  overflow: hidden;
}

.placeholder {
  text-align: center;
  color: #606266;
}

.placeholder .el-icon {
  margin-bottom: 16px;
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.detection-info {
  height: 600px;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detection-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background-color: #f8fafc;
  border-radius: 8px;
  margin-bottom: 16px;
}

.stat-group {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background-color: #ffffff;
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stat-item label {
  color: #64748b;
  font-size: 13px;
}

.stat-item span {
  color: #1e293b;
  font-size: 16px;
  font-weight: 500;
}

.stat-item span.highlight {
  color: #409EFF;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.detection-list {
  flex: 1;
  overflow-y: auto;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 0 8px;
}

.list-controls {
  display: flex;
  gap: 16px;
  align-items: center;
}

.records-container {
  flex: 1;
  overflow: hidden;
  padding: 0 8px;
}

.record-content {
  padding: 8px;
  background-color: #f8fafc;
  border-radius: 6px;
}

.record-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.object-count {
  font-size: 13px;
  color: #409EFF;
  font-weight: 500;
}

.record-message {
  margin: 0;
  color: #2c3e50;
  font-size: 14px;
  line-height: 1.4;
}

.record-details {
  margin-top: 8px;
}

.details-content {
  padding: 8px;
  background-color: #ffffff;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

:deep(.el-timeline-item__node--normal) {
  left: -1px;
}

:deep(.el-timeline-item__node--large) {
  left: -2px;
}

:deep(.el-timeline-item__content) {
  margin-left: 28px;
}

:deep(.el-timeline-item__timestamp) {
  font-size: 12px;
  color: #909399;
}

:deep(.el-radio-button__inner) {
  padding: 4px 12px;
}

.model-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-name {
  font-weight: 500;
  color: #2c3e50;
}

.model-desc {
  font-size: 12px;
  color: #909399;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.video-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fps {
  font-size: 14px;
  color: #409EFF;
  font-weight: 500;
}

.video-controls {
  display: flex;
  gap: 12px;
}

.video-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.detection-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.info-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

@media (max-width: 1400px) {
  .stat-group {
    grid-template-columns: 1fr;
  }
}
</style> 