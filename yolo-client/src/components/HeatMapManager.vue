<template>
  <div class="heatmap-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传地图
        </el-button>
        <el-button @click="startEditArea" :disabled="!currentMap" :type="editMode === 'area' ? 'primary' : 'default'">
          <el-icon><Edit /></el-icon>
          {{ editMode === 'area' ? '完成区域' : '编辑区域' }}
        </el-button>
        <el-button @click="startEditProject" :disabled="!currentMap" :type="editMode === 'project' ? 'primary' : 'default'">
          <el-icon><Location /></el-icon>
          {{ editMode === 'project' ? '完成项目' : '编辑项目' }}
        </el-button>
        <el-button @click="refreshData" :loading="refreshing">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-select v-model="selectedMap" class="map-select" placeholder="选择地图" @change="loadMap">
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
          <div class="legend-title">人数分级</div>
          <div class="legend-bar">
            <div class="legend-gradient" :style="{ background: heatmapLegendGradient }"></div>
            <div class="legend-labels">
              <span>0</span>
              <span>{{ maxAreaCount }}</span>
            </div>
          </div>
        </div>

        <!-- 编辑模式提示 -->
        <div v-if="editMode" class="edit-mode-hint">
          {{ editMode === 'area' ? '点击绘制区域边界，双击完成' : '点击地图设置项目位置' }}
        </div>

        <!-- 编辑框（地图内居中浮层） -->
        <div v-if="showAreaDialog" class="feature-edit-overlay" @click.self="closeAreaPanel">
          <div class="feature-edit-panel">
            <div class="panel-head">
              <div>
                <div class="panel-type-tag">{{ areaForm.shapeType === 'point' ? '项目点' : '区域' }}</div>
                <h3>{{ dialogTitle }}</h3>
              </div>
              <el-button text circle @click="closeAreaPanel">
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
            <el-form :model="areaForm" :rules="areaRules" ref="areaFormRef" label-position="top" class="panel-form">
              <el-form-item :label="areaForm.shapeType === 'point' ? '项目名称' : '区域名称'" prop="name">
                <el-input v-model="areaForm.name" :placeholder="areaForm.shapeType === 'point' ? '请输入项目名称' : '请输入区域名称'" />
              </el-form-item>
              <el-form-item label="计量单位">
                <el-input v-model="areaForm.displayUnit" placeholder="默认：人，可改为辆、台等" maxlength="8" />
              </el-form-item>
              <el-form-item label="数据源类型">
                <el-radio-group v-model="areaForm.dataSourceType" @change="handleDataSourceTypeChange">
                  <el-radio value="crowd_analysis">人群分析</el-radio>
                  <el-radio value="smart_scheme">订阅监控</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="areaForm.dataSourceType === 'crowd_analysis'" label="绑定任务" prop="sourceId">
                <el-select
                  :key="'crowd-' + (editingArea?.id || 'new')"
                  v-model="areaForm.sourceId"
                  placeholder="选择人群分析任务"
                  teleported
                  filterable
                  style="width: 100%"
                  @change="handleSourceChange"
                >
                  <el-option label="未绑定" :value="''" />
                  <el-option
                    v-for="job in crowdJobs"
                    :key="job.job_id"
                    :label="job.job_name"
                    :value="job.job_id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-else label="绑定订阅" prop="sourceId">
                <el-select
                  :key="'scheme-' + (editingArea?.id || 'new')"
                  v-model="areaForm.sourceId"
                  placeholder="选择人数统计订阅"
                  teleported
                  filterable
                  style="width: 100%"
                  @change="handleSourceChange"
                >
                  <el-option label="未绑定" :value="''" />
                  <el-option
                    v-for="scheme in numberStatSchemes"
                    :key="scheme.id"
                    :label="scheme.label"
                    :value="scheme.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-if="areaForm.shapeType === 'point'" label="标记颜色" prop="color">
                <el-color-picker v-model="areaForm.color" show-alpha />
              </el-form-item>
              <el-form-item v-else label="区域着色">
                <span class="color-auto-hint">按绑定人数自动分级着色（低→高：蓝→黄→红）</span>
              </el-form-item>
            </el-form>
            <div class="panel-foot">
              <el-button v-if="editingArea" type="danger" plain @click="deleteAreaFromDialog">删除</el-button>
              <span class="dialog-footer-spacer" />
              <el-button @click="closeAreaPanel">取消</el-button>
              <el-button type="primary" @click="saveArea">保存</el-button>
            </div>
          </div>
        </div>

        <!-- 图例说明 -->
        <div class="map-feature-legend">
          <div class="legend-row">
            <span class="legend-area-icon" />
            <span>区域（多边形）</span>
          </div>
          <div class="legend-row">
            <span class="legend-point-icon" />
            <span>项目点</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传地图对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传地图"
      width="500px"
      top="8vh"
      align-center
      append-to-body
      destroy-on-close
      :z-index="999999"
      class="high-priority-dialog"
    >
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Edit, Refresh, PictureRounded, UploadFilled, Location, Close } from '@element-plus/icons-vue'
import { dashboardMapApi } from '@/api/dashboard'
import { crowdAnalysisApi } from '@/api/crowd_analysis'
import { smartSchemeApi } from '@/api/smart_scheme'
import {
  HEATMAP_LEGEND_GRADIENT,
  computeMaxFeatureCount,
  getAreaCount,
  getHeatmapColor,
  getHeatmapRatio,
  getHeatmapRgbAtRatio,
  getHeatmapStrokeColor,
} from '@/utils/heatmapColors'

const heatmapLegendGradient = HEATMAP_LEGEND_GRADIENT

// Props
const props = defineProps({
  fullPage: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['map-selected', 'areas-updated', 'maps-changed'])

// 响应式数据
const mapContainer = ref(null)
const mapCanvas = ref(null)
const uploadFormRef = ref(null)
const areaFormRef = ref(null)

const showUploadDialog = ref(false)
const showAreaDialog = ref(false)
const uploading = ref(false)
const refreshing = ref(false)
const editMode = ref(null) // null | 'area' | 'project'

const selectedMap = ref(null)
const currentMap = ref(null)
const editingArea = ref(null)

const mapList = ref([])
const areas = ref([])
const crowdJobs = ref([])
const numberStatSchemes = ref([])
const fileList = ref([])

let canvas = null
let ctx = null
let mapImage = null
let isDrawing = false
let currentPath = []
let containerObserver = null

// 表单数据
const uploadForm = reactive({
  name: '',
  file: null,
  scale: 1,
  preview: ''
})

const areaForm = reactive({
  name: '',
  sourceId: '',
  dataSourceType: 'crowd_analysis',
  displayUnit: '人',
  color: 'rgba(74, 144, 226, 0.3)',
  shapeType: 'polygon',
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
const maxAreaCount = computed(() => computeMaxFeatureCount(areas.value))

const dialogTitle = computed(() => {
  const isPoint = areaForm.shapeType === 'point'
  const label = isPoint ? '项目' : '区域'
  return editingArea.value ? `编辑${label}` : `新建${label}`
})

// 初始化
onMounted(async () => {
  await loadMapList()
  await loadCrowdJobs()
  await loadNumberStatSchemes()
})

onUnmounted(() => {
  containerObserver?.disconnect()
  containerObserver = null
  if (canvas?.hasResizeListener) {
    window.removeEventListener('resize', resizeCanvas)
  }
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

const loadNumberStatSchemes = async () => {
  try {
    const response = await smartSchemeApi.getSchemes({ page: 1, page_size: 100, event_type: 'number_stat' })
    const items = response.data?.items || response.data?.data?.items || response.data?.data || []
    numberStatSchemes.value = (Array.isArray(items) ? items : []).map((scheme) => ({
      id: scheme.id,
      label: scheme.camera_name
        ? `${scheme.camera_name}${scheme.remarks ? ` · ${scheme.remarks}` : ''}`
        : (scheme.remarks || scheme.id),
    }))
  } catch (error) {
    console.error('加载订阅监控失败:', error)
    numberStatSchemes.value = []
    ElMessage.warning('加载订阅监控列表失败，请检查数据服务是否正常')
  }
}

const loadCrowdJobs = async () => {
  try {
    const response = await crowdAnalysisApi.getAllAnalysisJobs()
    crowdJobs.value = response.data?.data || []
  } catch (error) {
    console.error('加载人群分析任务失败:', error)
    crowdJobs.value = []
    ElMessage.warning('加载人群分析任务失败')
  }
}

const initCanvas = () => {
  nextTick(() => {
    tryInitCanvas()
  })
}

const observeContainer = () => {
  if (!mapContainer.value || containerObserver) return
  containerObserver = new ResizeObserver(() => {
    if (!canvas || !mapContainer.value) return
    const { clientWidth, clientHeight } = mapContainer.value
    if (clientWidth > 0 && clientHeight > 0) {
      resizeCanvas()
    }
  })
  containerObserver.observe(mapContainer.value)
}

const tryInitCanvas = (retryCount = 0) => {
  if (mapCanvas.value && currentMap.value && mapContainer.value) {
    const { clientWidth, clientHeight } = mapContainer.value
    if (clientWidth <= 0 || clientHeight <= 0) {
      observeContainer()
      if (retryCount < 30) {
        setTimeout(() => tryInitCanvas(retryCount + 1), 100)
      }
      return
    }

    canvas = mapCanvas.value
    ctx = canvas.getContext('2d')
    observeContainer()
    resizeCanvas()

    if (!canvas.hasResizeListener) {
      window.addEventListener('resize', resizeCanvas)
      canvas.hasResizeListener = true
    }
    return
  }

  if (retryCount < 10) {
    setTimeout(() => tryInitCanvas(retryCount + 1), (retryCount + 1) * 100)
  }
}

const resizeCanvas = () => {
  if (!canvas || !mapContainer.value) return

  const container = mapContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  if (width <= 0 || height <= 0) return

  canvas.width = width
  canvas.height = height

  drawCanvas()
}

const loadMap = async (mapId) => {
  const map = mapList.value.find(m => m.id === mapId)
  if (!map) return

  selectedMap.value = mapId
  currentMap.value = map
  await loadAreas(mapId)
  updateAreaCounts()
  loadMapImage()
  emit('map-selected', mapId)

  nextTick(() => {
    if (!canvas) {
      initCanvas()
    } else {
      resizeCanvas()
    }
  })
}

const loadMapImage = () => {
  if (!currentMap.value) return

  mapImage = new Image()
  mapImage.onload = () => {
    if (canvas && ctx) {
      drawCanvas()
    } else {
      initCanvas()
    }
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
        shapeType: area.shape_type || 'polygon',
        points: area.points,
        color: area.color,
        dataSourceType: area.data_source_type || 'crowd_analysis',
        sourceId: area.data_source_id || '',
        jobId: area.data_source_id || '',
        displayUnit: area.display_unit || '人',
        currentCount: area.current_count || 0,
        enteredCount: area.entered_count || 0,
        exitedCount: area.exited_count || 0,
        stayingCount: area.staying_count ?? area.current_count ?? 0,
        maxCapacity: area.max_capacity,
        areaSize: area.area_size,
        dataSourceName: area.data_source_name,
        lastUpdateTime: area.last_update_time
      }))
    } else {
      areas.value = []
    }
    drawCanvas()
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
    if (!area.sourceId && !area.jobId) {
      area.currentCount = 0
      area.enteredCount = 0
      area.exitedCount = 0
      area.stayingCount = 0
      return
    }
    const sourceId = area.sourceId || area.jobId
    if (area.dataSourceType === 'smart_scheme') {
      return
    }
    const job = crowdJobs.value.find(j => j.job_id === sourceId)
    if (job && job.last_result) {
      try {
        area.currentCount = parseInt(job.last_result.total_person_count) || 0
        area.stayingCount = area.currentCount
      } catch (error) {
        area.currentCount = 0
        area.stayingCount = 0
      }
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
  
  const polygonAreas = areas.value.filter(area => (area.shapeType || 'polygon') !== 'point')
  const projectAreas = areas.value.filter(area => area.shapeType === 'point')
  polygonAreas.forEach(area => drawArea(area))
  projectAreas.forEach(area => drawProject(area))
  
  if (isDrawing && currentPath.length > 0) {
    drawPath(currentPath, 'rgba(74, 144, 226, 0.5)', true) // 传入true表示是地图坐标
  }
}

const drawArea = (area) => {
  if (!area.points || area.points.length < 3) return

  const canvasPoints = area.points.map(point => mapToCanvasCoords(point.x, point.y))
  const highlighted = isFeatureHighlighted(area)
  const count = getAreaCount(area)
  const strokeColor = getHeatmapStrokeColor(count, maxAreaCount.value)

  ctx.beginPath()
  ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y)
  canvasPoints.forEach(point => ctx.lineTo(point.x, point.y))
  ctx.closePath()

  const fillAlpha = highlighted ? 0.62 : 0.52
  ctx.fillStyle = getHeatmapColor(count, maxAreaCount.value, fillAlpha)
  ctx.fill()

  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = highlighted ? 5 : 4
  ctx.stroke()

  ctx.strokeStyle = strokeColor
  ctx.lineWidth = highlighted ? 3 : 2
  ctx.setLineDash(highlighted ? [8, 4] : [])
  ctx.stroke()
  ctx.setLineDash([])

  canvasPoints.forEach((point) => {
    ctx.beginPath()
    ctx.arc(point.x, point.y, highlighted ? 5 : 4, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.strokeStyle = strokeColor
    ctx.lineWidth = 2
    ctx.stroke()
  })

  const center = calculateAreaCenter(area)
  const canvasCenter = mapToCanvasCoords(center.x, center.y)
  drawFeatureLabel(
    canvasCenter.x,
    canvasCenter.y,
    area.name,
    formatFeatureCount(area),
    highlighted ? 'rgba(255, 138, 101, 0.92)' : 'rgba(15, 23, 42, 0.86)'
  )
}

const drawProject = (area) => {
  if (!area.points?.length) return

  const point = mapToCanvasCoords(area.points[0].x, area.points[0].y)
  const highlighted = isFeatureHighlighted(area)
  const ratio = getHeatmapRatio(getAreaCount(area), maxAreaCount.value)
  const { r, g, b } = getHeatmapRgbAtRatio(ratio)
  const baseRadius = highlighted ? 13 : 11
  const glowRadius = baseRadius * (highlighted ? 3.4 : 2.8)

  const outerGlow = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, glowRadius)
  outerGlow.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${highlighted ? 0.62 : 0.46})`)
  outerGlow.addColorStop(0.35, `rgba(${r}, ${g}, ${b}, ${highlighted ? 0.24 : 0.16})`)
  outerGlow.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
  ctx.fillStyle = outerGlow
  ctx.beginPath()
  ctx.arc(point.x, point.y, glowRadius, 0, Math.PI * 2)
  ctx.fill()

  const midGlow = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, baseRadius * 0.95)
  midGlow.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${highlighted ? 0.95 : 0.82})`)
  midGlow.addColorStop(0.65, `rgba(${r}, ${g}, ${b}, ${highlighted ? 0.42 : 0.28})`)
  midGlow.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
  ctx.fillStyle = midGlow
  ctx.beginPath()
  ctx.arc(point.x, point.y, baseRadius * 0.95, 0, Math.PI * 2)
  ctx.fill()

  ctx.beginPath()
  ctx.arc(point.x, point.y, baseRadius * 0.55, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${highlighted ? 0.98 : 0.88})`
  ctx.fill()
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = highlighted ? 2.5 : 2
  ctx.stroke()

  ctx.beginPath()
  ctx.arc(point.x, point.y, baseRadius * 0.22, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  drawFeatureLabel(
    point.x,
    point.y + baseRadius + 10,
    area.name,
    formatFeatureCount(area),
    `rgba(${Math.max(r - 18, 0)}, ${Math.max(g - 18, 0)}, ${Math.max(b - 18, 0)}, 0.92)`
  )
}

const formatFeatureCount = (area) => {
  const unit = area.displayUnit || '人'
  const count = area.stayingCount ?? area.currentCount ?? 0
  return `${count} ${unit}`
}

const setColorAlpha = (color, alpha) => {
  if (!color) return `rgba(64, 158, 255, ${alpha})`
  if (color.startsWith('rgba')) {
    return color.replace(/[\d.]+\)$/g, `${alpha})`)
  }
  if (color.startsWith('rgb')) {
    return color.replace('rgb', 'rgba').replace(')', `, ${alpha})`)
  }
  return color
}

const getFeatureStrokeColor = (color) => {
  if (!color) return '#409eff'
  return color.replace(/rgba?/, 'rgb').replace(/,\s*[\d.]+\)/, ')')
}

const isFeatureHighlighted = (area) =>
  showAreaDialog.value && editingArea.value && editingArea.value.id === area.id

const drawFeatureLabel = (x, y, title, subtitle, bgColor) => {
  ctx.font = 'bold 13px "Microsoft YaHei", Arial'
  const titleWidth = ctx.measureText(title).width
  ctx.font = '12px "Microsoft YaHei", Arial'
  const subtitleWidth = ctx.measureText(subtitle).width
  const width = Math.max(titleWidth, subtitleWidth) + 20
  const height = 40
  const left = x - width / 2
  const top = y - height / 2

  ctx.fillStyle = bgColor
  ctx.beginPath()
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(left, top, width, height, 8)
  } else {
    ctx.rect(left, top, width, height)
  }
  ctx.fill()

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)'
  ctx.lineWidth = 1
  ctx.stroke()

  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 13px "Microsoft YaHei", Arial'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(title, x, y - 7)
  ctx.font = '12px "Microsoft YaHei", Arial'
  ctx.fillStyle = '#ffe4d6'
  ctx.fillText(subtitle, x, y + 11)
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
        nextTick(() => initCanvas())
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

const startEditArea = () => {
  if (editMode.value === 'area') {
    finishEdit()
    return
  }
  editMode.value = 'area'
  isDrawing = false
  currentPath = []
  ElMessage.info('请在地图上点击绘制区域边界，双击完成绘制')
}

const startEditProject = () => {
  if (editMode.value === 'project') {
    finishEdit()
    return
  }
  editMode.value = 'project'
  isDrawing = false
  currentPath = []
  ElMessage.info('请在地图上点击设置项目位置')
}

const finishEdit = () => {
  editMode.value = null
  isDrawing = false
  currentPath = []
  drawCanvas()
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
  
  if (!editMode.value) {
    const clicked = findFeatureAtPoint(mapCoords.x, mapCoords.y)
    if (clicked) {
      openEditDialog(clicked)
    }
    return
  }

  if (editMode.value === 'project') {
    editingArea.value = null
    areaForm.name = ''
    areaForm.sourceId = ''
    areaForm.dataSourceType = 'crowd_analysis'
    areaForm.displayUnit = '人'
    areaForm.color = 'rgba(255, 138, 101, 0.92)'
    areaForm.shapeType = 'point'
    areaForm.points = [mapCoords]
    showAreaDialog.value = true
    return
  }
  
  // 区域编辑模式下，存储地图坐标
  if (!isDrawing) {
    isDrawing = true
    currentPath = [mapCoords]
  } else {
    currentPath.push(mapCoords)
  }
  
  drawCanvas()
}

const handleCanvasDoubleClick = () => {
  if (editMode.value !== 'area') return
  if (isDrawing && currentPath.length >= 3) {
    editingArea.value = null
    areaForm.name = ''
    areaForm.sourceId = ''
    areaForm.dataSourceType = 'crowd_analysis'
    areaForm.displayUnit = '人'
    areaForm.color = 'rgba(64, 158, 255, 0.55)'
    areaForm.shapeType = 'polygon'
    areaForm.points = [...currentPath]
    isDrawing = false
    currentPath = []
    showAreaDialog.value = true
    drawCanvas()
  }
}

const handleCanvasMouseMove = (event) => {
  if (!canvas || !isDrawing || editMode.value !== 'area') return
  
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

const openEditDialog = (feature) => {
  editingArea.value = feature
  areaForm.name = feature.name
  areaForm.sourceId = feature.sourceId || feature.jobId || ''
  areaForm.dataSourceType = feature.dataSourceType || 'crowd_analysis'
  areaForm.displayUnit = feature.displayUnit || '人'
  areaForm.color = feature.color
  areaForm.shapeType = feature.shapeType || 'polygon'
  areaForm.points = [...(feature.points || [])]
  showAreaDialog.value = true
  drawCanvas()
}

const closeAreaPanel = () => {
  showAreaDialog.value = false
  editingArea.value = null
  drawCanvas()
}

const deleteAreaFromDialog = async () => {
  if (!editingArea.value) return
  const target = editingArea.value
  closeAreaPanel()
  await deleteArea(target)
}

const saveArea = async () => {
  if (!areaFormRef.value) return
  
  try {
    await areaFormRef.value.validate()

    const isPointType = areaForm.shapeType === 'point'
    if (!isPointType && areaForm.points.length < 3) {
      ElMessage.warning('请在地图上绘制区域')
      return
    }
    if (isPointType && areaForm.points.length < 1) {
      ElMessage.warning('请在地图上点击设置项目位置')
      return
    }
    
    const areaData = {
      map_id: parseInt(currentMap.value.id),
      name: areaForm.name,
      shape_type: areaForm.shapeType,
      points: areaForm.points,
      color: areaForm.color,
      max_capacity: areaForm.maxCapacity,
      display_unit: areaForm.displayUnit || '人',
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
      const savedAreaId = response.data.data.id || editingArea.value?.id

      if (areaForm.sourceId) {
        const bindingData = {
          area_id: savedAreaId,
          data_source_type: areaForm.dataSourceType,
          data_source_id: areaForm.sourceId,
          data_source_name: getSourceName(areaForm.dataSourceType, areaForm.sourceId),
          refresh_interval: 30,
          config: {
            display_unit: areaForm.displayUnit || '人',
          },
        }
        await dashboardMapApi.createDashboardMapBinding(bindingData)
      } else if (editingArea.value) {
        await dashboardMapApi.deleteDashboardMapAreaBindings(editingArea.value.id)
      }
      
      await loadAreas(currentMap.value.id)
      updateAreaCounts()
      drawCanvas()

      showAreaDialog.value = false
      editingArea.value = null
      finishEdit()
      
      emit('areas-updated', areas.value)
      
      ElMessage.success(areaForm.shapeType === 'point' ? '项目保存成功' : '区域保存成功')
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
      sourceId: areaForm.sourceId || '',
      jobId: areaForm.sourceId || '',
      dataSourceType: areaForm.dataSourceType,
      displayUnit: areaForm.displayUnit,
      color: areaForm.color,
      shapeType: areaForm.shapeType,
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
    finishEdit()
    drawCanvas()
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
      const result = getApiResult(response)

      if (!result?.success) {
        throw new Error(result?.message || '删除失败')
      }

      await loadAreas(currentMap.value.id)
      drawCanvas()
      emit('areas-updated', areas.value)
      ElMessage.success(result.message || (area.shapeType === 'point' ? '项目删除成功' : '区域删除成功'))
    } catch (error) {
      console.error('删除区域失败:', error)
      ElMessage.error(error?.message || '删除区域失败')
    }
  } catch (error) {
    // 用户取消删除
  }
}

const getApiResult = (response) => response?.data ?? response

const resetMapView = () => {
  selectedMap.value = ''
  currentMap.value = null
  areas.value = []
  editMode.value = null
  mapImage = null
  isDrawing = false
  currentPath = []
  if (canvas && ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
  emit('map-selected', null)
  emit('areas-updated', [])
}

// 删除地图
const deleteMap = async (map) => {
  if (!map) return

  try {
    await ElMessageBox.confirm('确定要删除这个地图吗？删除后将无法恢复。', '确认删除', {
      type: 'warning'
    })

    const response = await dashboardMapApi.deleteDashboardMap(map.id)
    const result = getApiResult(response)

    if (!result?.success) {
      throw new Error(result?.message || '删除失败')
    }

    const deletedId = map.id.toString()
    const wasSelected = selectedMap.value === deletedId || selectedMap.value === map.id

    await loadMapList()
    emit('maps-changed', mapList.value)

    if (wasSelected) {
      resetMapView()
      if (mapList.value.length > 0) {
        await loadMap(mapList.value[0].id)
      }
    }

    ElMessage.success(result.message || '地图删除成功')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除地图失败:', error)
      ElMessage.error(error?.message || '删除地图失败')
    }
  }
}

// 辅助函数
const PROJECT_HIT_RADIUS = 14

const isPointNearProject = (x, y, area) => {
  if (area.shapeType !== 'point' || !area.points?.length) return false
  const p = area.points[0]
  const transform = getMapTransform()
  const radius = transform ? PROJECT_HIT_RADIUS / transform.scale : PROJECT_HIT_RADIUS
  const dx = x - p.x
  const dy = y - p.y
  return dx * dx + dy * dy <= radius * radius
}

const findFeatureAtPoint = (x, y) => {
  const project = [...areas.value]
    .reverse()
    .find(area => area.shapeType === 'point' && isPointNearProject(x, y, area))
  if (project) return project

  return areas.value.find(
    area => (area.shapeType || 'polygon') === 'polygon' && isPointInArea(x, y, area)
  ) || null
}

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

const getSchemeName = (schemeId) => {
  const scheme = numberStatSchemes.value.find(s => s.id === schemeId)
  return scheme ? scheme.label : '未知订阅'
}

const getSourceName = (sourceType, sourceId) => {
  if (sourceType === 'smart_scheme') return getSchemeName(sourceId)
  return getJobName(sourceId)
}

const handleSourceChange = (sourceId) => {
  if (!areaForm.name?.trim() && sourceId) {
    areaForm.name = getSourceName(areaForm.dataSourceType, sourceId)
  }
}

const handleDataSourceTypeChange = () => {
  areaForm.sourceId = ''
}

const selectMap = async (mapId) => {
  if (!mapId) return
  const id = mapId.toString()
  if (!mapList.value.some(m => m.id === id)) {
    await loadMapList()
  }
  if (mapList.value.some(m => m.id === id)) {
    await loadMap(id)
  }
}

const refreshView = () => {
  nextTick(() => {
    if (currentMap.value && canvas && mapContainer.value) {
      resizeCanvas()
    } else if (currentMap.value) {
      initCanvas()
    }
  })
}

defineExpose({ selectMap, refreshView, loadMapList })

// 监听编辑面板开关，重绘高亮
watch(showAreaDialog, () => {
  nextTick(() => drawCanvas())
})

// 监听地图选择变化
watch(selectedMap, (newMapId) => {
  if (newMapId) {
    emit('map-selected', newMapId)
  }
})

// 监听区域数据变化
watch(areas, (newAreas) => {
  emit('areas-updated', newAreas)
  nextTick(() => drawCanvas())
}, { deep: true })

// 监听当前地图变化，确保 canvas 在有地图时初始化
watch(currentMap, (newMap) => {
  if (newMap) {
    nextTick(() => {
      if (!canvas) initCanvas()
      else resizeCanvas()
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
  flex: 1 1 auto;
  justify-content: flex-end;
  min-width: 0;
  gap: 8px;
}

.toolbar-right .map-select {
  flex: 1 1 280px;
  min-width: 280px;
  max-width: 420px;
}

.map-container {
  flex: 1 1 0;
  position: relative;
  overflow: hidden;
  min-height: v-bind('props.fullPage ? "calc(100vh - 120px)" : "0"');
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
  cursor: v-bind("editMode ? 'crosshair' : 'pointer'");
  background: white;
}

.edit-mode-hint {
  position: absolute;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(64, 158, 255, 0.92);
  color: #fff;
  font-size: 13px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  pointer-events: none;
  z-index: 5;
}

.heatmap-legend {
  position: absolute;
  top: 16px;
  left: 16px;
  background: rgba(255, 255, 255, 0.9);
  padding: 12px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 6;
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
  border-radius: 4px;
  margin-bottom: 4px;
}

.color-auto-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #666;
}

.feature-edit-overlay {
  position: absolute;
  inset: 0;
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.28);
  padding: 16px;
}

.feature-edit-panel {
  position: relative;
  width: min(340px, 100%);
  max-height: calc(100% - 32px);
  z-index: 13;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.feature-edit-panel .panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #ebeef5;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.feature-edit-panel .panel-head h3 {
  margin: 6px 0 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.panel-type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: #409eff;
  background: rgba(64, 158, 255, 0.12);
}

.panel-form {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px 0;
}

.panel-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px 16px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}

.map-feature-legend {
  position: absolute;
  left: 16px;
  bottom: 16px;
  z-index: 6;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  color: #606266;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-row + .legend-row {
  margin-top: 6px;
}

.legend-area-icon {
  width: 18px;
  height: 12px;
  border: 2px solid #409eff;
  background: rgba(64, 158, 255, 0.35);
  border-radius: 2px;
}

.legend-point-icon {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: rgba(255, 138, 101, 0.95);
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(255, 138, 101, 0.8);
}

.area-info-panel {
  display: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.dialog-footer-spacer {
  flex: 1;
}

.upload-demo {
  width: 100%;
}
</style> 