<template>
  <div class="heatmap-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传地图
        </el-button>
        <el-button @click="addArea" :disabled="!currentMap">
          <el-icon><Plus /></el-icon>
          添加区域
        </el-button>
        <el-button @click="toggleEdit" :disabled="!currentMap">
          <el-icon><Edit /></el-icon>
          {{ isEditing ? '完成编辑' : '编辑区域' }}
        </el-button>
        <el-button @click="refreshData" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-select v-model="selectedMap" placeholder="选择地图" @change="loadMap">
          <el-option
            v-for="map in mapList"
            :key="map.id"
            :label="map.name"
            :value="map.id"
          />
        </el-select>
        <el-button 
          v-if="selectedMap" 
          type="danger" 
          size="small" 
          @click="deleteMap(mapList.find(m => m.id === selectedMap))"
        >
          删除地图
        </el-button>
      </div>
    </div>

    <!-- 地图容器 -->
    <div class="map-container" ref="mapContainer">
      <div v-if="!currentMap" class="empty-map">
        <el-icon :size="48"><PictureRounded /></el-icon>
        <p>请先上传地图文件</p>
      </div>
      <div v-else class="map-canvas-wrapper">
        <canvas 
          v-if="currentMap"
          ref="mapCanvas"
          class="map-canvas"
          @click="handleCanvasClick"
          @mousemove="handleCanvasMouseMove"
          @mousedown="handleCanvasMouseDown"
          @mouseup="handleCanvasMouseUp"
          @dblclick="handleCanvasDoubleClick"
        ></canvas>
        
        <!-- 热力图图例 -->
        <div class="heatmap-legend">
          <div class="legend-title">人数密度</div>
          <div class="legend-bar">
            <div class="legend-gradient"></div>
            <div class="legend-labels">
              <span>0</span>
              <span>{{ maxDensity }}</span>
            </div>
          </div>
        </div>

        <!-- 区域信息面板 -->
        <div v-if="selectedArea" class="area-info-panel">
          <div class="panel-header">
            <h3>{{ selectedArea.name }}</h3>
            <el-button size="small" @click="selectedArea = null">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
          <div class="panel-content">
            <div class="info-item">
              <label>当前人数：</label>
              <span class="count-value">{{ selectedArea.currentCount || 0 }}</span>
            </div>
            <div class="info-item">
              <label>区域面积：</label>
              <span>{{ calculateAreaSize(selectedArea) }} m²</span>
            </div>
            <div class="info-item">
              <label>人口密度：</label>
              <span>{{ calculateDensity(selectedArea) }} 人/m²</span>
            </div>
            <div class="info-item">
              <label>绑定任务：</label>
              <el-select v-model="selectedArea.jobId" size="small" @change="updateAreaBinding">
                <el-option label="未绑定" :value="''" />
                <el-option
                  v-for="job in crowdJobs"
                  :key="job.job_id"
                  :label="job.job_name"
                  :value="job.job_id"
                />
              </el-select>
            </div>
            <div class="info-actions">
              <el-button size="small" @click="editArea(selectedArea)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteArea(selectedArea)">删除</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传地图对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传地图" width="500px">
      <el-form :model="uploadForm" :rules="uploadRules" ref="uploadFormRef" label-width="80px">
        <el-form-item label="地图名称" prop="name">
          <el-input v-model="uploadForm.name" placeholder="请输入地图名称" />
        </el-form-item>
        <el-form-item label="地图文件" prop="file">
          <el-upload
            class="upload-demo"
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            accept="image/*"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 jpg/png/gif 格式，文件大小不超过 10MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="比例尺" prop="scale">
          <el-input v-model.number="uploadForm.scale" placeholder="1像素 = ? 米">
            <template #append>米/像素</template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showUploadDialog = false">取消</el-button>
          <el-button type="primary" @click="uploadMap" :loading="uploading">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 区域编辑对话框 -->
    <el-dialog v-model="showAreaDialog" :title="editingArea ? '编辑区域' : '新建区域'" width="400px">
      <el-form :model="areaForm" :rules="areaRules" ref="areaFormRef" label-width="80px">
        <el-form-item label="区域名称" prop="name">
          <el-input v-model="areaForm.name" placeholder="请输入区域名称" />
        </el-form-item>
        <el-form-item label="绑定任务" prop="jobId">
          <el-select v-model="areaForm.jobId" placeholder="选择人群分析任务">
            <el-option label="未绑定" :value="''" />
            <el-option
              v-for="job in crowdJobs"
              :key="job.job_id"
              :label="job.job_name"
              :value="job.job_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="区域颜色" prop="color">
          <el-color-picker v-model="areaForm.color" show-alpha />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAreaDialog = false">取消</el-button>
          <el-button type="primary" @click="saveArea">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Plus, Edit, Refresh, PictureRounded, Close, UploadFilled } from '@element-plus/icons-vue'
import { dashboardMapApi } from '@/api/dashboard'
import { crowdAnalysisApi } from '@/api/crowd_analysis'

// Props
const props = defineProps({
  fullPage: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['map-selected', 'areas-updated'])

// 响应式数据
const mapContainer = ref(null)
const mapCanvas = ref(null)
const uploadFormRef = ref(null)
const areaFormRef = ref(null)

const showUploadDialog = ref(false)
const showAreaDialog = ref(false)
const uploading = ref(false)
const refreshing = ref(false)
const isEditing = ref(false)

const selectedMap = ref(null)
const currentMap = ref(null)
const selectedArea = ref(null)
const editingArea = ref(null)

const mapList = ref([])
const areas = ref([])
const crowdJobs = ref([])
const fileList = ref([])

let canvas = null
let ctx = null
let mapImage = null
let isDrawing = false
let currentPath = []

// 表单数据
const uploadForm = reactive({
  name: '',
  file: null,
  scale: 1,
  preview: ''
})

const areaForm = reactive({
  name: '',
  jobId: '',
  color: 'rgba(74, 144, 226, 0.3)',
  points: []
})

// 表单验证规则
const uploadRules = {
  name: [
    { required: true, message: '请输入地图名称', trigger: 'blur' }
  ],
  file: [
    { required: true, message: '请选择地图文件', trigger: 'change' }
  ]
}

const areaRules = {
  name: [
    { required: true, message: '请输入区域名称', trigger: 'blur' }
  ]
}

// 计算属性
const maxDensity = computed(() => {
  if (!areas.value.length) return 100
  return Math.max(...areas.value.map(area => area.currentCount || 0), 100)
})

// 初始化
onMounted(async () => {
  await loadMapList()
  await loadCrowdJobs()
  // 不在这里初始化canvas，等到有地图时再初始化
})

// 加载地图列表
const loadMapList = async () => {
  try {
    const response = await dashboardMapApi.getDashboardMaps()
    const maps = response.data || response
    
    if (maps && maps.length > 0) {
      mapList.value = maps.map(map => ({
        id: map.id.toString(),
        name: map.name,
        imageUrl: map.image_url,
        scale: map.scale_factor,
        createdAt: map.created_at,
        width: map.width,
        height: map.height,
        description: map.description
      }))
    } else {
      mapList.value = []
    }
  } catch (error) {
    console.error('加载地图列表失败:', error)
    // 回退到本地存储
    // const savedMaps = localStorage.getItem('heatmaps')
    // if (savedMaps) {
    //   mapList.value = JSON.parse(savedMaps)
    // }
  }
}

const loadCrowdJobs = async () => {
  try {
    const response = await crowdAnalysisApi.getAnalysisJobs()
    crowdJobs.value = response.data || []
  } catch (error) {
    console.error('加载人群分析任务失败:', error)
    crowdJobs.value = [
      { job_id: 'job1', job_name: 'A车间人数统计', people_count: 25 },
      { job_id: 'job2', job_name: 'B车间人数统计', people_count: 18 },
      { job_id: 'job3', job_name: 'C车间人数统计', people_count: 32 }
    ]
  }
}

const initCanvas = () => {
  nextTick(() => {
    tryInitCanvas()
  })
}

const tryInitCanvas = (retryCount = 0) => {
  if (mapCanvas.value && currentMap.value) {
    canvas = mapCanvas.value
    ctx = canvas.getContext('2d')
    resizeCanvas()
    
    // 避免重复添加事件监听器
    if (!canvas.hasResizeListener) {
      window.addEventListener('resize', resizeCanvas)
      canvas.hasResizeListener = true
    }
    
    console.log('Canvas initialized successfully')
  } else if (retryCount < 5) {
    // 最多重试5次，每次间隔递增
    const delay = (retryCount + 1) * 100
    setTimeout(() => {
      tryInitCanvas(retryCount + 1)
    }, delay)
  } else {
    if (!currentMap.value) {
      console.log('Canvas initialization skipped - no map selected')
    } else {
      console.warn('Canvas element not found after multiple retries')
    }
  }
}

const resizeCanvas = () => {
  if (!canvas || !mapContainer.value) return
  
  const container = mapContainer.value
  canvas.width = container.clientWidth
  canvas.height = container.clientHeight - 60
  
  drawCanvas()
}

const loadMap = (mapId) => {
  const map = mapList.value.find(m => m.id === mapId)
  if (map) {
    currentMap.value = map
    loadAreas(mapId)
    loadMapImage()
    emit('map-selected', mapId)
    
    // 确保canvas在地图加载后初始化
    nextTick(() => {
      if (!canvas) {
        initCanvas()
      }
    })
  }
}

const loadMapImage = () => {
  if (!currentMap.value) return
  
  mapImage = new Image()
  mapImage.onload = () => {
    drawCanvas()
  }
  mapImage.src = currentMap.value.imageUrl
}

const loadAreas = async (mapId) => {
  try {
    const response = await dashboardMapApi.getDashboardMapAreas(mapId)
    const areasData = response.data || response
    
    if (areasData && areasData.length > 0) {
      areas.value = areasData.map(area => ({
        id: area.id.toString(),
        name: area.name,
        points: area.points,
        color: area.color,
        jobId: area.data_source_id || '',
        currentCount: area.current_count || 0,
        maxCapacity: area.max_capacity,
        areaSize: area.area_size,
        dataSourceType: area.data_source_type,
        dataSourceName: area.data_source_name,
        lastUpdateTime: area.last_update_time
      }))
    } else {
      areas.value = []
    }
  } catch (error) {
    console.error('加载区域失败:', error)
    // 回退到本地存储
    // const savedAreas = localStorage.getItem(`areas_${mapId}`)
    // if (savedAreas) {
    //   areas.value = JSON.parse(savedAreas)
    // }
  }
}

const updateAreaCounts = () => {
  areas.value.forEach(area => {
    if (area.jobId && area.jobId !== '') {
      const job = crowdJobs.value.find(j => j.job_id === area.jobId)
      if (job && job.last_result) {
        try {
          area.currentCount = parseInt(job.last_result.total_person_count) || 0
        } catch (error) {
          console.error('解析人数数据失败:', error)
          area.currentCount = 0
        }
      }
    } else {
      area.currentCount = 0
    }
  })
}

// 计算地图显示的缩放参数
const getMapTransform = () => {
  if (!mapImage || !canvas) return null
  
  const scale = Math.min(canvas.width / mapImage.width, canvas.height / mapImage.height)
  const width = mapImage.width * scale
  const height = mapImage.height * scale
  const x = (canvas.width - width) / 2
  const y = (canvas.height - height) / 2
  
  return { scale, width, height, x, y }
}

// 将canvas坐标转换为地图坐标
const canvasToMapCoords = (canvasX, canvasY) => {
  const transform = getMapTransform()
  if (!transform) return { x: canvasX, y: canvasY }
  
  const mapX = (canvasX - transform.x) / transform.scale
  const mapY = (canvasY - transform.y) / transform.scale
  
  return { x: mapX, y: mapY }
}

// 将地图坐标转换为canvas坐标
const mapToCanvasCoords = (mapX, mapY) => {
  const transform = getMapTransform()
  if (!transform) return { x: mapX, y: mapY }
  
  const canvasX = mapX * transform.scale + transform.x
  const canvasY = mapY * transform.scale + transform.y
  
  return { x: canvasX, y: canvasY }
}

// 检查坐标是否在地图范围内
const isValidMapCoords = (mapX, mapY) => {
  if (!mapImage) return false
  
  return mapX >= 0 && mapX <= mapImage.width && 
         mapY >= 0 && mapY <= mapImage.height
}

const drawCanvas = () => {
  if (!canvas || !ctx) return
  
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  if (mapImage) {
    const transform = getMapTransform()
    if (transform) {
      ctx.drawImage(mapImage, transform.x, transform.y, transform.width, transform.height)
    }
  }
  
  areas.value.forEach(area => {
    drawArea(area)
  })
  
  if (isDrawing && currentPath.length > 0) {
    drawPath(currentPath, 'rgba(74, 144, 226, 0.5)', true) // 传入true表示是地图坐标
  }
}

const drawArea = (area) => {
  if (!area.points || area.points.length < 3) return
  
  // 转换地图坐标到canvas坐标
  const canvasPoints = area.points.map(point => mapToCanvasCoords(point.x, point.y))
  
  ctx.beginPath()
  ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y)
  canvasPoints.forEach(point => {
    ctx.lineTo(point.x, point.y)
  })
  ctx.closePath()
  
  const density = calculateDensity(area)
  const intensity = Math.min(density / 0.1, 1)
  const alpha = 0.3 + intensity * 0.4
  
  ctx.fillStyle = area.color.replace(/[\d\.]+\)$/g, `${alpha})`)
  ctx.fill()
  
  ctx.strokeStyle = area.color.replace(/rgba?/, 'rgb').replace(/,\s*[\d\.]+\)/, ')')
  ctx.lineWidth = 2
  ctx.stroke()
  
  const center = calculateAreaCenter(area)
  const canvasCenter = mapToCanvasCoords(center.x, center.y)
  ctx.fillStyle = '#333'
  ctx.font = '14px Arial'
  ctx.textAlign = 'center'
  ctx.fillText(area.name, canvasCenter.x, canvasCenter.y - 10)
  ctx.fillText(`${area.currentCount || 0}人`, canvasCenter.x, canvasCenter.y + 10)
}

const drawPath = (points, color, isMapCoords = false) => {
  if (points.length < 2) return
  
  // 如果是地图坐标，需要转换为canvas坐标
  const canvasPoints = isMapCoords ? 
    points.map(point => mapToCanvasCoords(point.x, point.y)) : 
    points
  
  ctx.beginPath()
  ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y)
  canvasPoints.forEach(point => {
    ctx.lineTo(point.x, point.y)
  })
  
  ctx.strokeStyle = color
  ctx.lineWidth = 2
  ctx.stroke()
}

const handleFileChange = (file) => {
  uploadForm.file = file
  fileList.value = [file]
  
  const reader = new FileReader()
  reader.onload = (e) => {
    uploadForm.preview = e.target.result
  }
  reader.readAsDataURL(file.raw)
}

const uploadMap = async () => {
  if (!uploadFormRef.value) return
  
  try {
    await uploadFormRef.value.validate()
    
    if (!uploadForm.file) {
      ElMessage.error('请选择要上传的文件')
      return
    }
    
    uploading.value = true
    
    const formData = new FormData()
    formData.append('file', uploadForm.file.raw)
    formData.append('name', uploadForm.name)
    formData.append('description', uploadForm.description || '')
    formData.append('scale_factor', uploadForm.scale)
    formData.append('created_by', 'user')
    
    const response = await dashboardMapApi.uploadDashboardMap(formData)
    
    if (response.data && response.data.success) {
      // 重新加载地图列表
      await loadMapList()
      
      selectedMap.value = response.data.data.id.toString()
      const newMap = mapList.value.find(m => m.id === selectedMap.value)
      if (newMap) {
        currentMap.value = newMap
        await loadAreas(selectedMap.value)
        loadMapImage()
      }
      
      showUploadDialog.value = false
      resetUploadForm()
      ElMessage.success('地图上传成功')
    } else {
      throw new Error(response.data?.message || '上传失败')
    }
  } catch (error) {
    // console.error('上传地图失败:', error)
    ElMessage.error(error.message || '上传地图失败')
  } finally {
    uploading.value = false
  }
}

const resetUploadForm = () => {
  uploadForm.name = ''
  uploadForm.file = null
  uploadForm.scale = 1
  uploadForm.preview = ''
  fileList.value = []
}

const addArea = () => {
  if (!currentMap.value) {
    ElMessage.warning('请先选择地图')
    return
  }
  
  editingArea.value = null
  areaForm.name = ''
  areaForm.jobId = ''
  areaForm.color = 'rgba(74, 144, 226, 0.3)'
  areaForm.points = []
  showAreaDialog.value = true
}

const toggleEdit = () => {
  isEditing.value = !isEditing.value
  if (isEditing.value) {
    ElMessage.info('请在地图上点击绘制区域边界，双击完成绘制')
  }
}

const refreshData = async () => {
  refreshing.value = true
  try {
    await loadCrowdJobs()
    updateAreaCounts()
    drawCanvas()
    ElMessage.success('数据刷新成功')
  } finally {
    refreshing.value = false
  }
}

const handleCanvasClick = (event) => {
  if (!canvas) return
  
  const rect = canvas.getBoundingClientRect()
  const canvasX = event.clientX - rect.left
  const canvasY = event.clientY - rect.top
  
  // 转换为地图坐标
  const mapCoords = canvasToMapCoords(canvasX, canvasY)
  
  // 检查是否在地图范围内
  if (!isValidMapCoords(mapCoords.x, mapCoords.y)) {
    return
  }
  
  if (!isEditing.value) {
    // 点击选择区域时，需要使用地图坐标进行判断
    const clickedArea = areas.value.find(area => isPointInArea(mapCoords.x, mapCoords.y, area))
    selectedArea.value = clickedArea || null
    return
  }
  
  // 编辑模式下，存储地图坐标
  if (!isDrawing) {
    isDrawing = true
    currentPath = [mapCoords]
  } else {
    currentPath.push(mapCoords)
  }
  
  drawCanvas()
}

const handleCanvasDoubleClick = () => {
  if (isDrawing && currentPath.length >= 3) {
    // currentPath已经是地图坐标，直接使用
    areaForm.points = [...currentPath]
    isDrawing = false
    currentPath = []
    showAreaDialog.value = true
    drawCanvas()
  }
}

const handleCanvasMouseMove = (event) => {
  if (!canvas || !isDrawing) return
  
  const rect = canvas.getBoundingClientRect()
  const canvasX = event.clientX - rect.left
  const canvasY = event.clientY - rect.top
  
  // 转换为地图坐标
  const mapCoords = canvasToMapCoords(canvasX, canvasY)
  
  // 检查是否在地图范围内
  if (!isValidMapCoords(mapCoords.x, mapCoords.y)) {
    return
  }
  
  const tempPath = [...currentPath, mapCoords]
  
  drawCanvas()
  drawPath(tempPath, 'rgba(74, 144, 226, 0.5)', true) // 传入true表示是地图坐标
}

const handleCanvasMouseDown = () => {}
const handleCanvasMouseUp = () => {}

const editArea = (area) => {
  editingArea.value = area
  areaForm.name = area.name
  areaForm.jobId = area.jobId || ''
  areaForm.color = area.color
  areaForm.points = [...area.points]
  showAreaDialog.value = true
}

const saveArea = async () => {
  if (!areaFormRef.value) return
  
  try {
    await areaFormRef.value.validate()
    
    if (areaForm.points.length < 3) {
      ElMessage.warning('请在地图上绘制区域')
      return
    }
    
    const areaData = {
      map_id: parseInt(currentMap.value.id),
      name: areaForm.name,
      points: areaForm.points,
      color: areaForm.color,
      max_capacity: areaForm.maxCapacity,
      description: areaForm.description,
      scale_factor: currentMap.value.scale || 1
    }
    
    let response
    if (editingArea.value) {
      // 更新区域
      response = await dashboardMapApi.updateDashboardMapArea(editingArea.value.id, areaData)
    } else {
      // 创建新区域
      response = await dashboardMapApi.createDashboardMapArea(areaData)
    }
    
    if (response.data.success) {
      // 如果有数据绑定，创建绑定关系
      if (areaForm.jobId && areaForm.jobId !== '') {
        const bindingData = {
          area_id: response.data.data.id || editingArea.value.id,
          data_source_type: 'crowd_analysis',
          data_source_id: areaForm.jobId,
          data_source_name: getJobName(areaForm.jobId),
          refresh_interval: 30
        }
        
        await dashboardMapApi.createDashboardMapBinding(bindingData)
      }
      
      // 重新加载区域数据
      await loadAreas(currentMap.value.id)
      
      showAreaDialog.value = false
      isEditing.value = false
      
      // 触发区域更新事件
      emit('areas-updated', areas.value)
      
      ElMessage.success('区域保存成功')
    } else {
      throw new Error(response.message || '保存失败')
    }
  } catch (error) {
    console.error('保存区域失败:', error)
    ElMessage.error(error.message || '保存区域失败')
    
    // 回退到本地存储
    const areaDataLocal = {
      id: editingArea.value?.id || Date.now().toString(),
      name: areaForm.name,
      jobId: areaForm.jobId || '',
      color: areaForm.color,
      points: [...areaForm.points],
      currentCount: 0
    }
    
    if (editingArea.value) {
      const index = areas.value.findIndex(a => a.id === editingArea.value.id)
      if (index >= 0) {
        areas.value[index] = areaDataLocal
      }
    } else {
      areas.value.push(areaDataLocal)
    }
    
    // localStorage.setItem(`areas_${currentMap.value.id}`, JSON.stringify(areas.value))
    showAreaDialog.value = false
    isEditing.value = false
    emit('areas-updated', areas.value)
  }
}

const deleteArea = async (area) => {
  try {
    await ElMessageBox.confirm('确定要删除这个区域吗？', '确认删除', {
      type: 'warning'
    })
    
    try {
      const response = await dashboardMapApi.deleteDashboardMapArea(area.id)
      
      if (response.success) {
        await loadAreas(currentMap.value.id)
        selectedArea.value = null
        ElMessage.success('区域删除成功')
      } else {
        throw new Error(response.message || '删除失败')
      }
    } catch (error) {
      console.error('删除区域失败:', error)
      // 回退到本地删除
      // const index = areas.value.findIndex(a => a.id === area.id)
      // if (index >= 0) {
      //   areas.value.splice(index, 1)
      //   localStorage.setItem(`areas_${currentMap.value.id}`, JSON.stringify(areas.value))
      //   selectedArea.value = null
      //   ElMessage.success('区域删除成功')
      // }
    }
  } catch (error) {
    // 用户取消删除
  }
}

const updateAreaBinding = async () => {
  if (selectedArea.value) {
    const area = areas.value.find(a => a.id === selectedArea.value.id)
    if (area) {
      area.jobId = selectedArea.value.jobId || ''
      
      // 如果有绑定，创建或更新绑定关系
      if (selectedArea.value.jobId && selectedArea.value.jobId !== '') {
        try {
          const bindingData = {
            area_id: area.id,
            data_source_type: 'crowd_analysis',
            data_source_id: selectedArea.value.jobId,
            data_source_name: getJobName(selectedArea.value.jobId),
            refresh_interval: 30
          }
          
          await dashboardMapApi.createDashboardMapBinding(bindingData)
        } catch (error) {
          console.error('创建绑定失败:', error)
        }
      } else {
        // 如果选择了"未绑定"，删除现有绑定
        try {
          await dashboardMapApi.deleteDashboardMapAreaBindings(area.id)
        } catch (error) {
          console.error('删除绑定失败:', error)
        }
      }
      
      updateAreaCounts()
      // localStorage.setItem(`areas_${currentMap.value.id}`, JSON.stringify(areas.value))
    }
  }
}

// 删除地图
const deleteMap = async (map) => {
  try {
    await ElMessageBox.confirm('确定要删除这个地图吗？删除后将无法恢复。', '确认删除', {
      type: 'warning'
    })
    
    try {
      const response = await dashboardMapApi.deleteDashboardMap(map.id)
      
      if (response.success) {
        await loadMapList()
        if (selectedMap.value === map.id) {
          selectedMap.value = ''
          currentMap.value = null
          areas.value = []
        }
        ElMessage.success('地图删除成功')
      } else {
        throw new Error(response.message || '删除失败')
      }
    } catch (error) {
      // console.error('删除地图失败:', error)
      // 回退到本地删除
      // const index = mapList.value.findIndex(m => m.id === map.id)
      // if (index >= 0) {
      //   mapList.value.splice(index, 1)
      //   localStorage.setItem('heatmaps', JSON.stringify(mapList.value))
      //   if (selectedMap.value === map.id) {
      //     selectedMap.value = ''
      //     currentMap.value = null
      //     areas.value = []
      //   }
      //   ElMessage.success('地图删除成功')
      // }
    }
  } catch (error) {
    // 用户取消删除
  }
}

// 辅助函数
const isPointInArea = (x, y, area) => {
  if (!area.points || area.points.length < 3) return false
  
  let inside = false
  const points = area.points
  
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    if (((points[i].y > y) !== (points[j].y > y)) &&
        (x < (points[j].x - points[i].x) * (y - points[i].y) / (points[j].y - points[i].y) + points[i].x)) {
      inside = !inside
    }
  }
  
  return inside
}

const calculateAreaCenter = (area) => {
  if (!area.points || area.points.length === 0) return { x: 0, y: 0 }
  
  let x = 0, y = 0
  area.points.forEach(point => {
    x += point.x
    y += point.y
  })
  
  return {
    x: x / area.points.length,
    y: y / area.points.length
  }
}

const calculateAreaSize = (area) => {
  // 如果已经有计算好的面积，直接返回
  if (area.areaSize) {
    return Math.round(area.areaSize * 100) / 100
  }
  
  // 如果没有面积数据但有坐标点，计算面积
  if (!area.points || area.points.length < 3) return 0
  
  let area_px = 0
  const points = area.points
  
  // 使用鞋带公式计算多边形面积
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length
    area_px += points[i].x * points[j].y
    area_px -= points[j].x * points[i].y
  }
  
  area_px = Math.abs(area_px) / 2
  
  // 转换为实际面积（平方米）
  const scale = currentMap.value?.scale || 1
  return Math.round(area_px * scale * scale * 100) / 100
}

const calculateDensity = (area) => {
  const size = calculateAreaSize(area)
  if (size === 0) return 0
  return Math.round(((area.currentCount || 0) / size) * 1000) / 1000 // 保留3位小数
}

const getJobName = (jobId) => {
  const job = crowdJobs.value.find(j => j.job_id === jobId)
  return job ? job.job_name : '未知任务'
}

// 监听地图选择变化
watch(selectedMap, (newMapId) => {
  if (newMapId) {
    emit('map-selected', newMapId)
  }
})

// 监听区域数据变化
watch(areas, (newAreas) => {
  emit('areas-updated', newAreas)
}, { deep: true })

// 监听当前地图变化，确保canvas在有地图时初始化
watch(currentMap, (newMap) => {
  if (newMap && !canvas) {
    nextTick(() => {
      initCanvas()
    })
  }
})
</script>

<style scoped>
.heatmap-manager {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  min-width: 150px;
  gap: 8px;
}

.map-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  min-height: v-bind('props.fullPage ? "calc(100vh - 120px)" : "400px"');
}

.empty-map {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.map-canvas-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.map-canvas {
  display: block;
  cursor: crosshair;
  background: white;
}

.heatmap-legend {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.9);
  padding: 12px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.legend-title {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 8px;
  text-align: center;
}

.legend-bar {
  width: 100px;
}

.legend-gradient {
  height: 20px;
  background: linear-gradient(to right, 
    rgba(74, 144, 226, 0.3) 0%, 
    rgba(74, 144, 226, 0.7) 100%);
  border-radius: 4px;
  margin-bottom: 4px;
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #666;
}

.area-info-panel {
  position: absolute;
  top: 16px;
  left: 16px;
  width: 280px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #409eff;
  color: white;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.panel-content {
  padding: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.info-item label {
  font-size: 14px;
  color: #666;
}

.count-value {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
}

.info-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.upload-demo {
  width: 100%;
}
</style> 