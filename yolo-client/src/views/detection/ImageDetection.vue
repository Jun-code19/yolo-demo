<template>
  <div class="detection-container">
    <div class="page-header">
      <h2>图片检测</h2>
      <div class="header-actions">
        <el-select
          v-model="selectedModel"
          placeholder="选择检测模型"
          class="model-select"
          :disabled="isDetecting"
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
        <el-upload
          class="upload-image"
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          accept=".jpg,.jpeg,.png,.bmp,.webp"
          :on-change="handleImageChange"
          :before-upload="() => false"
          multiple
        >
          <el-button type="primary">选择图片</el-button>
        </el-upload>
        <el-button 
          type="success" 
          :disabled="!imageList.length || !selectedModel" 
          @click="startBatchDetection"
        >
          {{ isDetecting ? '停止检测' : '开始检测' }}
        </el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="image-card">
          <div class="image-preview">
            <div v-if="!currentImage" class="placeholder">
              <el-icon :size="64"><Picture /></el-icon>
              <p>选择图片开始检测</p>
            </div>
            <div v-else class="preview-container">
              <img :src="currentImage.url" class="preview-image" />
              <canvas ref="canvasRef" class="detection-canvas"></canvas>
            </div>
          </div>

          <div class="image-list" v-if="imageList.length">
            <el-scrollbar>
              <div class="thumbnail-list">
                <div
                  v-for="(image, index) in imageList"
                  :key="index"
                  class="thumbnail-item"
                  :class="{ active: currentImageIndex === index }"
                  @click="selectImage(index)"
                >
                  <el-image
                    :src="image.url"
                    fit="cover"
                    :loading="loading"
                  >
                    <template #placeholder>
                      <div class="image-placeholder">
                        <el-icon><Picture /></el-icon>
                      </div>
                    </template>
                  </el-image>
                  <el-tag
                    size="small"
                    :type="image.status === 'done' ? 'success' : image.status === 'processing' ? 'warning' : ''"
                  >
                    {{ getStatusText(image.status) }}
                  </el-tag>
                </div>
              </div>
            </el-scrollbar>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="detection-info">
          <template #header>
            <div class="card-header">
              <span>检测信息</span>
              <el-button-group v-if="currentImage">
                <el-button type="primary" link @click="downloadResult">导出结果</el-button>
                <el-button type="primary" link @click="downloadImage">导出图片</el-button>
              </el-button-group>
            </div>
          </template>
          
          <template v-if="currentImage">
            <div class="image-info">
              <div class="info-item">
                <label>文件名：</label>
                <span>{{ currentImage.name }}</span>
              </div>
              <div class="info-item">
                <label>大小：</label>
                <span>{{ getFileSize(currentImage.size) }}</span>
              </div>
              <div class="info-item">
                <label>分辨率：</label>
                <span>{{ currentImage.resolution || '未知' }}</span>
              </div>
            </div>

            <div class="detection-stats">
              <div class="stat-item">
                <label>检测状态：</label>
                <el-tag :type="getStatusType(currentImage.status)">
                  {{ getStatusText(currentImage.status) }}
                </el-tag>
              </div>
              <div class="stat-item">
                <label>目标数量：</label>
                <span>{{ currentImage.detectedCount || 0 }}</span>
              </div>
            </div>

            <div class="detection-results">
              <h4>检测结果</h4>
              <el-empty 
                v-if="!currentImage.results?.length" 
                description="暂无检测结果" 
              />
              <el-table
                v-else
                :data="currentImage.results"
                style="width: 100%"
                size="small"
              >
                <el-table-column prop="class" label="类别" />
                <el-table-column prop="confidence" label="置信度">
                  <template #default="{ row }">
                    {{ (row.confidence * 100).toFixed(2) }}%
                  </template>
                </el-table-column>
                <el-table-column prop="position" label="位置" />
              </el-table>
            </div>
          </template>
          <el-empty v-else description="请选择图片" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// WebSocket 连接
let ws = null
let canvasContext = null

// 响应式变量
const imageList = ref([])
const currentImage = ref(null)
const isDetecting = ref(false)
const detectionResults = ref([])
const selectedModel = ref('')
const canvasRef = ref(null)

// 计算属性
const currentImageIndex = computed(() => {
  if (currentImage.value) return imageList.value.findIndex(img => img.url === currentImage.value.url)
  return -1
})

// 检测模型列表
const models = [
  {
    type: 'YOLO系列',
    models: [
      { label: 'YOLOv8-n', value: 'yolov8n', description: '速度最快，适合实时检测' },
      { label: 'YOLOv8-s', value: 'yolov8s', description: '速度和精度的平衡' },
      { label: 'YOLOv8-m', value: 'yolov8m', description: '中等精度' },
      { label: 'YOLOv8-l', value: 'yolov8l', description: '高精度' },
      { label: 'YOLOv8-x', value: 'yolov8x', description: '最高精度' }
    ]
  }
]

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

// 修改开始检测函数
const startBatchDetection = async () => {
  if (!imageList.value.length || !selectedModel.value) {
    ElMessage.warning('请选择图片和检测模型')
    return
  }

  try {
    isDetecting.value = true
    
    // 初始化WebSocket连接
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      initWebSocket()
    }
    
    // 等待WebSocket连接建立
    while (ws.readyState === WebSocket.CONNECTING) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    
    if (ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket连接失败')
    }
    
    // 处理每张图片
    for (let i = 0; i < imageList.value.length; i++) {
      const image = imageList.value[i]
      if (image.status === 'done') continue
      
      try {
        image.status = 'processing'
        
        // 创建canvas并绘制图片
        const canvas = document.createElement('canvas')
        const img = new Image()
        img.src = image.url
        
        await new Promise((resolve, reject) => {
          img.onload = resolve
          img.onerror = reject
        })
        
        canvas.width = img.width
        canvas.height = img.height
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0)
        
        // 转换为base64并发送
        const imageData = canvas.toDataURL('image/jpeg', 0.6)
        
        ws.send(JSON.stringify({
          type: 'image',
          image_id: i,
          timestamp: Date.now(),
          width: img.width,
          height: img.height,
          data: imageData
        }))
      } catch (error) {
        console.error('Error processing image:', error)
        image.status = 'error'
      }
    }
  } catch (error) {
    console.error('Error starting batch detection:', error)
    ElMessage.error('启动检测失败：' + error.message)
    stopDetection()
  }
}

// 修改处理检测结果函数
const handleDetectionResult = (result) => {
  const image = imageList.value[result.image_id]
  if (!image) return
  
  image.status = 'done'
  image.detectedCount = result.objects.length
  image.results = result.objects.map(obj => ({
    class: obj.class,
    confidence: obj.confidence,
    position: `(${obj.bbox[0]}, ${obj.bbox[1]}, ${obj.bbox[2]}, ${obj.bbox[3]})`
  }))
  
  if (currentImage.value === image) {
    drawDetectionBoxes(result.objects)
  }
}

// 绘制检测框
const drawDetectionBoxes = (objects) => {
  if (!canvasContext || !currentImage.value) return
  
  const canvas = canvasRef.value
  const image = new Image()
  image.src = currentImage.value.url
  
  image.onload = () => {
    // 设置画布尺寸
    canvas.width = image.width
    canvas.height = image.height
    
    // 绘制原始图像
    canvasContext.drawImage(image, 0, 0)
    
    objects.forEach(obj => {
      // 设置检测框样式
      canvasContext.strokeStyle = getObjectColor(obj.class)
      canvasContext.lineWidth = 2
      canvasContext.fillStyle = `${canvasContext.strokeStyle}80`
      
      // 绘制检测框
      const [x, y, w, h] = obj.bbox
      canvasContext.strokeRect(x, y, w, h)
      canvasContext.fillRect(x, y, w, h)
      
      // 绘制标签
      canvasContext.font = '14px Arial'
      canvasContext.fillStyle = '#fff'
      const label = `${obj.class} ${Math.round(obj.confidence * 100)}%`
      const textWidth = canvasContext.measureText(label).width
      
      canvasContext.fillStyle = canvasContext.strokeStyle
      canvasContext.fillRect(x, y - 20, textWidth + 10, 20)
      
      canvasContext.fillStyle = '#fff'
      canvasContext.fillText(label, x + 5, y - 5)
    })
  }
}

// 获取目标类别对应的颜色
const getObjectColor = (className) => {
  const colors = {
    person: '#ff0000',
    car: '#00ff00',
    truck: '#0000ff',
    default: '#ff9900'
  }
  return colors[className] || colors.default
}

// 处理图片选择
const handleImageChange = async (file) => {
  console.log('Selected image file:', file)
  
  // 检查文件类型和大小
  const allowedTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp']
  const isImage = allowedTypes.includes(file.raw.type) || /\.(jpg|jpeg|png|bmp|webp)$/i.test(file.name)
  const isLt5M = file.size / 1024 / 1024 < 5

  if (!isImage) {
    ElMessage.error('请选择正确的图片格式（支持jpg、png、bmp、webp）！')
    return
  }

  if (!isLt5M) {
    ElMessage.error('图片大小不能超过 5MB！')
    return
  }

  try {
    const url = URL.createObjectURL(file.raw)
    const resolution = await getImageResolution(url)
    
    // 添加到图片列表
    const imageInfo = {
      file: file.raw,
      url,
      name: file.name,
      size: file.size,
      resolution,
      status: 'pending',
      results: []
    }

    console.log('Image info created:', imageInfo)
    imageList.value.push(imageInfo)
    if (currentImageIndex.value === -1) {
      currentImageIndex.value = 0
    }
  } catch (error) {
    console.error('Error processing image file:', error)
    ElMessage.error('处理图片文件时出错：' + error.message)
  }
}

// 选择图片
const selectImage = (index) => {
  currentImage.value = imageList.value[index]
  
  // 初始化画布
  const canvas = canvasRef.value
  canvasContext = canvas.getContext('2d')
  
  // 加载图片并绘制
  const img = new Image()
  img.onload = () => {
    canvas.width = img.width
    canvas.height = img.height
    canvasContext.drawImage(img, 0, 0)
  }
  img.src = imageList.value[index].url
}

// 停止检测
const stopDetection = () => {
  isDetecting.value = false
}

// 下载结果
const downloadResult = () => {
  if (!currentImage.value) return
  // 实现导出检测结果的逻辑
}

// 下载图片
const downloadImage = () => {
  if (!currentImage.value) return
  // 实现导出检测后图片的逻辑
}

// 工具函数
const getFileSize = (size) => {
  return (size / 1024 / 1024).toFixed(2) + ' MB'
}

const getStatusText = (status) => {
  const statusMap = {
    pending: '待检测',
    processing: '检测中',
    done: '已完成',
    error: '失败'
  }
  return statusMap[status] || status
}

const getStatusType = (status) => {
  const typeMap = {
    pending: 'info',
    processing: 'warning',
    done: 'success',
    error: 'danger'
  }
  return typeMap[status]
}

// 获取图片分辨率
const getImageResolution = (url) => {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      resolve(`${img.naturalWidth} × ${img.naturalHeight}`)
    }
    img.src = url
  })
}

// 添加检测记录
const addDetectionRecord = (type, message, details = null, objectCount = null) => {
  detectionResults.value.unshift({
    time: new Date().toLocaleTimeString(),
    type,
    message,
    details,
    objectCount
  })
}

// 生命周期钩子
onMounted(() => {
  initWebSocket()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
  // 清理图片URL
  imageList.value.forEach(image => {
    URL.revokeObjectURL(image.url)
  })
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

.header-actions {
  display: flex;
  gap: 12px;
}

.image-card {
  margin-bottom: 20px;
}

.image-preview {
  width: 100%;
  height: 500px;
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

.preview-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.detection-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.image-list {
  margin-top: 20px;
  height: 120px;
}

.thumbnail-list {
  display: flex;
  gap: 12px;
  padding: 4px;
}

.thumbnail-item {
  position: relative;
  width: 100px;
  height: 100px;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.3s ease;
}

.thumbnail-item.active {
  border-color: #409EFF;
}

.thumbnail-item .el-image {
  width: 100%;
  height: 100%;
}

.thumbnail-item .el-tag {
  position: absolute;
  bottom: 4px;
  right: 4px;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f7fa;
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

.image-info {
  padding: 16px;
  background-color: #f8fafc;
  border-radius: 4px;
  margin-bottom: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-item label {
  color: #606266;
}

.detection-stats {
  padding: 16px;
  background-color: #f8fafc;
  border-radius: 4px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stat-item:last-child {
  margin-bottom: 0;
}

.detection-results {
  flex: 1;
  overflow-y: auto;
}

.detection-results h4 {
  margin: 0 0 16px;
  color: #2c3e50;
}

.model-select {
  width: 240px;
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
</style> 