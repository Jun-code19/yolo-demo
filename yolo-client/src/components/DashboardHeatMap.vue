<template>
  <div ref="heatmapRootRef" class="dashboard-heatmap">
    <div v-if="!hasConfig" class="no-config">
      <el-icon :size="48">
        <PictureRounded />
      </el-icon>
      <p>暂未配置热力图</p>
      <el-button type="primary" @click="goToManagement">
        <el-icon>
          <Setting />
        </el-icon>
        前往设置
      </el-button>
    </div>

    <div v-else class="map-mode" :class="{ 'map-mode--full': isFullMapMode }">
      <canvas
        ref="mapCanvasRef"
        class="map-canvas interactive-canvas"
        :class="{ 'is-dragging': viewState.isDragging }"
        @click="handleCanvasClick"
        @wheel.prevent="handleCanvasWheel"
        @mousedown="handleCanvasMouseDown"
        @mousemove="handleCanvasMouseMove"
        @mouseup="handleCanvasMouseUp"
        @mouseleave="handleCanvasMouseLeave"
        @dblclick.prevent="resetView"
      />

      <!-- 迷你模式：控件贴面板边缘 -->
      <template v-if="isMiniMapMode">
        <div v-if="parkStats" class="park-stats-panel">
          <div class="park-stats-title">{{ parkStats.title || '园内人数' }}</div>
          <div class="park-stats-grid">
            <div class="park-stat-item"><span class="label">园内</span><span class="value">{{ parkStats.stayingCount ?? 0 }}</span></div>
            <div class="park-stat-item"><span class="label">进入</span><span class="value enter">{{ parkStats.enteredCount ?? 0 }}</span></div>
            <div class="park-stat-item"><span class="label">离开</span><span class="value exit">{{ parkStats.exitedCount ?? 0 }}</span></div>
          </div>
        </div>
        <button v-if="showExpandButton" type="button" class="fullmap-expand-btn" @click="openFullMapDialog">全屏查看</button>
        <div class="map-view-hint">滚轮缩放 · 拖拽平移 · 双击重置</div>
        <div class="full-legend full-color-legend">
          <div class="legend-title">人数色阶</div>
          <div class="legend-gradient" :style="{ background: heatmapLegendGradient }"></div>
          <div class="legend-labels">
            <span>0</span>
            <span>{{ maxCount }}</span>
          </div>
        </div>
        <div class="mini-legend area-overview-legend">
          <div class="mini-legend-title">区域概览</div>
          <div class="mini-legend-list">
            <div class="legend-item" v-for="area in legendAreas" :key="area.id">
              <div class="legend-color" :style="{ backgroundColor: getAreaColor(area) }"></div>
              <span class="legend-text">{{ area.name }}: {{ formatFeatureCount(area) }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 完整地图：控件挂到中栏锚点，避免被 board-content 层遮挡 -->
      <Teleport to="#board-map-ui-anchor" :disabled="!isFullMapMode">
        <div v-if="isFullMapMode" class="map-ui-frame map-ui-frame--anchored">
          <div class="map-ui-row map-ui-row-top">
            <div v-if="parkStats" class="park-stats-panel park-stats-panel--frame">
              <div class="park-stats-title">{{ parkStats.title || '园内人数' }}</div>
              <div class="park-stats-grid">
                <div class="park-stat-item"><span class="label">园内</span><span class="value">{{ parkStats.stayingCount ?? 0 }}</span></div>
                <div class="park-stat-item"><span class="label">进入</span><span class="value enter">{{ parkStats.enteredCount ?? 0 }}</span></div>
                <div class="park-stat-item"><span class="label">离开</span><span class="value exit">{{ parkStats.exitedCount ?? 0 }}</span></div>
              </div>
            </div>
            <div v-else class="map-ui-placeholder" aria-hidden="true"></div>
            <div class="map-title-badge">人数分布</div>
            <div class="full-legend full-color-legend map-ui-legend">
              <div class="legend-title">人数色阶</div>
              <div class="legend-gradient" :style="{ background: heatmapLegendGradient }"></div>
              <div class="legend-labels">
                <span>0</span>
                <span>{{ maxCount }}</span>
              </div>
            </div>
          </div>
          <div class="map-ui-row map-ui-row-bottom">
            <div class="mini-legend area-overview-legend map-ui-overview">
              <div class="mini-legend-title">区域概览</div>
              <div class="mini-legend-list">
                <div class="legend-item" v-for="area in legendAreas" :key="`frame-${area.id}`">
                  <div class="legend-color" :style="{ backgroundColor: getAreaColor(area) }"></div>
                  <span class="legend-text">{{ area.name }}: {{ formatFeatureCount(area) }}</span>
                </div>
              </div>
            </div>
            <div class="map-view-hint map-ui-hint">滚轮缩放 · 拖拽平移 · 双击重置</div>
          </div>
        </div>
      </Teleport>
    </div>

    <Teleport to="body">
      <div v-if="showFullMapDialog" class="fullmap-overlay" @click.self="closeFullMapDialog">
        <div class="fullmap-shell">
          <div class="fullmap-toolbar">
            <div class="fullmap-toolbar-title">完整地图</div>
            <div class="fullmap-toolbar-actions">
              <button type="button" class="toolbar-btn" @click="resetView">重置视图</button>
              <button type="button" class="toolbar-btn primary" @click="closeFullMapDialog">关闭</button>
            </div>
          </div>
          <div class="fullmap-body">
            <canvas
              ref="expandedCanvas"
              class="map-canvas expanded-canvas"
              :class="{ 'is-dragging': viewState.isDragging }"
              @click="handleCanvasClick"
              @wheel.prevent="handleCanvasWheel"
              @mousedown="handleCanvasMouseDown"
              @mousemove="handleCanvasMouseMove"
              @mouseup="handleCanvasMouseUp"
              @mouseleave="handleCanvasMouseLeave"
              @dblclick.prevent="resetView"
            />
            <div class="fullmap-float-layer">
              <div class="map-view-hint expanded-hint">滚轮缩放 · 拖拽平移 · 双击重置</div>
              <div class="full-legend full-color-legend expanded-color-legend">
                <div class="legend-title">人数色阶</div>
                <div class="legend-gradient" :style="{ background: heatmapLegendGradient }"></div>
                <div class="legend-labels">
                  <span>0</span>
                  <span>{{ maxCount }}</span>
                </div>
              </div>
              <div class="mini-legend area-overview-legend expanded-area-overview">
                <div class="mini-legend-title">区域概览</div>
                <div class="mini-legend-list">
                  <div class="legend-item" v-for="area in legendAreas" :key="`expanded-overview-${area.id}`">
                    <div class="legend-color" :style="{ backgroundColor: getAreaColor(area) }"></div>
                    <span class="legend-text">{{ area.name }}: {{ formatFeatureCount(area) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 区域详情（居中浮层，不遮挡整页） -->
    <Teleport to="body" :disabled="!showFullMapDialog">
      <div
        v-if="showAreaDetailDialog && selectedArea"
        class="area-detail-overlay"
        :class="{ 'area-detail-overlay--global': showFullMapDialog }"
        @click.self="closeAreaDetail"
      >
      <div class="area-detail-panel">
        <div class="area-detail-head">
          <span class="area-detail-title">{{ selectedArea.name }}</span>
          <button type="button" class="detail-close-btn" @click="closeAreaDetail">关闭</button>
        </div>
        <div class="area-detail">
          <div class="detail-item">
            <label>当前数量</label>
            <span class="value">{{ selectedArea.stayingCount ?? selectedArea.currentCount ?? 0 }} {{ selectedArea.displayUnit || '人' }}</span>
          </div>
          <div v-if="selectedArea.enteredCount || selectedArea.exitedCount" class="detail-item">
            <label>进入 / 离开</label>
            <span class="value">{{ selectedArea.enteredCount || 0 }} / {{ selectedArea.exitedCount || 0 }}</span>
          </div>
          <!-- <div class="detail-item">
            <label>计量单位</label>
            <span class="value">{{ selectedArea.displayUnit || '人' }}</span>
          </div> -->
          <div class="detail-item">
            <label>区域面积</label>
            <span class="value">{{ selectedArea.shapeType === 'point' ? '—' : `${calculateAreaSize(selectedArea)} m²` }}</span>
          </div>
          <div class="detail-item">
            <label>人口密度</label>
            <span class="value">{{ selectedArea.shapeType === 'point' ? '—' : `${calculateDensity(selectedArea)} ${selectedArea.displayUnit || '人'}/m²` }}</span>
          </div>
          <div class="detail-item">
            <label>绑定任务</label>
            <span class="value">{{ selectedArea.dataSourceName || '未绑定' }}</span>
          </div>
          <div class="detail-item">
            <label>最后更新</label>
            <span class="value">{{ formatTime(lastUpdateTime) }}</span>
          </div>
        </div>
      </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { PictureRounded, Setting } from '@element-plus/icons-vue'
import {
  HEATMAP_LEGEND_GRADIENT,
  computeMaxAreaCount,
  getAreaCount,
  getHeatmapColor,
  getHeatmapStrokeColor,
} from '@/utils/heatmapColors'
import { normalizeHeatmapDisplayMode } from '@/api/dashboard'

const heatmapLegendGradient = HEATMAP_LEGEND_GRADIENT

const router = useRouter()
const mapCanvasRef = ref(null)
const expandedCanvas = ref(null)
const showFullMapDialog = ref(false)
const heatmapRootRef = ref(null)
const showAreaDetailDialog = ref(false)
const selectedArea = ref(null)
const hoveredArea = ref(null)

const MINI_MAP_DEFAULT_SCALE = 1
const FULL_MAP_DEFAULT_SCALE = 0.85

const getDefaultMapScale = (mode) => (mode === 'full' ? FULL_MAP_DEFAULT_SCALE : MINI_MAP_DEFAULT_SCALE)

const viewState = reactive({
  scale: MINI_MAP_DEFAULT_SCALE,
  offsetX: 0,
  offsetY: 0,
  isDragging: false,
  lastMouseX: 0,
  lastMouseY: 0,
  dragMoved: false,
})

const config = ref({})
const areas = ref([])
const parkStats = ref(null)
const crowdJobs = ref([])
const mapImage = ref(null)
const lastUpdateTime = ref(null)
let refreshTimer = null
let resizeObserver = null

// 计算属性
const hasConfig = computed(() => config.value.mapId && areas.value.length > 0)
const normalizeDisplayMode = normalizeHeatmapDisplayMode

const displayMode = computed(() => normalizeDisplayMode(config.value.displayMode))
const defaultMapScale = computed(() => getDefaultMapScale(displayMode.value))
const isFullMapMode = computed(() => displayMode.value === 'full')
const isMiniMapMode = computed(() => displayMode.value === 'mini')
const showExpandButton = computed(() => isMiniMapMode.value)
const maxAreas = computed(() => config.value.maxAreas || 6)
const refreshInterval = computed(() => (config.value.refreshInterval || 30) * 1000)

const displayAreas = computed(() => {
  return areas.value
    .filter(area => area.currentCount !== undefined)
    .sort((a, b) => (b.currentCount || 0) - (a.currentCount || 0))
    .slice(0, maxAreas.value)
})

const legendAreas = computed(() => {
  return [...areas.value]
    .sort((a, b) => getAreaCount(b) - getAreaCount(a))
})

const maxCount = computed(() => computeMaxAreaCount(areas.value, 'polygon'))

onMounted(async () => {
  await loadConfig()
  await loadData()
  startAutoRefresh()

  // 监听配置更新事件
  window.addEventListener('heatmap-config-updated', handleConfigUpdate)

  // 监听窗口大小变化
  window.addEventListener('resize', handleWindowResize)

  // 使用ResizeObserver监听容器大小变化
  initResizeObserver()
})

onUnmounted(() => {
  stopAutoRefresh()
  window.removeEventListener('heatmap-config-updated', handleConfigUpdate)
  window.removeEventListener('resize', handleWindowResize)

  // 清理ResizeObserver
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

// 监听显示模式变化
watch(displayMode, (mode) => {
  viewState.scale = getDefaultMapScale(mode)
  viewState.offsetX = 0
  viewState.offsetY = 0
  scheduleCanvasRedraw()
})

watch(
  () => hasConfig.value,
  () => {
    nextTick(scheduleCanvasRedraw)
  }
)

// 监听悬停区域变化，重绘canvas
watch(hoveredArea, () => {
  scheduleCanvasRedraw()
})

watch(showFullMapDialog, (visible) => {
  if (visible) {
    nextTick(drawExpandedCanvas)
  }
})

// 加载配置
const loadConfig = async () => {
  try {
    // 先尝试从API加载配置
    const response = await fetch('/api/v1/heatmap/dashboard/config')
    const result = await response.json()
    if (result.success && result.data) {
      config.value = {
        mapId: result.data.map_id.toString(),
        displayMode: normalizeDisplayMode(result.data.display_mode),
        maxAreas: result.data.max_areas,
        refreshInterval: result.data.refresh_interval,
        ...result.data.config
      }
    } else {
      // 回退到本地存储
      const savedConfig = localStorage.getItem('dashboard_heatmap_config')
      if (savedConfig) {
        config.value = JSON.parse(savedConfig)
      }
    }
  } catch (error) {
    // console.error('加载配置失败:', error)
    // 回退到本地存储
    try {
      const savedConfig = localStorage.getItem('dashboard_heatmap_config')
      if (savedConfig) {
        config.value = JSON.parse(savedConfig)
      }
    } catch (e) {
      // console.error('加载本地配置失败:', e)
    }
  }
  viewState.scale = getDefaultMapScale(normalizeDisplayMode(config.value.displayMode))
}

// 加载数据
const loadData = async () => {
  if (!config.value.mapId) return

  try {
    // 尝试从API加载完整的热力图数据
    const response = await fetch('/api/v1/heatmap/dashboard/data')
    const result = await response.json()

    if (result.success && result.data) {
      // 处理区域数据
      areas.value = result.data.areas.map(area => ({
        id: area.id.toString(),
        name: area.name,
        shapeType: area.shape_type || 'polygon',
        points: area.points,
        color: area.color,
        jobId: area.data_source_id,
        dataSourceType: area.data_source_type,
        displayUnit: area.display_unit || '人',
        currentCount: area.current_count || 0,
        stayingCount: area.staying_count ?? area.current_count ?? 0,
        enteredCount: area.entered_count || 0,
        exitedCount: area.exited_count || 0,
        maxCapacity: area.max_capacity,
        areaSize: area.area_size,
        dataSourceName: area.data_source_name,
        lastUpdateTime: area.last_update_time
      }))
      parkStats.value = result.data.park_stats || null

      // 处理地图数据
      if (result.data.map) {
        const mapData = result.data.map
        const img = new Image()
        img.onload = () => {
          mapImage.value = img
          scheduleCanvasRedraw()
          setTimeout(scheduleCanvasRedraw, 100)
        }
        img.src = mapData.image_url
      }
    } else {
      // 回退到本地存储
      const savedAreas = localStorage.getItem(`areas_${config.value.mapId}`)
      if (savedAreas) {
        areas.value = JSON.parse(savedAreas)
      }

      // 加载人群分析数据
      await loadCrowdJobs()
      updateAreaCounts()

      // 加载地图图片
      loadMapImage()
    }

    lastUpdateTime.value = new Date()
  } catch (error) {
    // console.error('加载数据失败:', error)
    // 回退到本地数据加载
    try {
      const savedAreas = localStorage.getItem(`areas_${config.value.mapId}`)
      if (savedAreas) {
        areas.value = JSON.parse(savedAreas)
      }

      await loadCrowdJobs()
      updateAreaCounts()
      loadMapImage()
      lastUpdateTime.value = new Date()
    } catch (e) {
      // console.error('加载本地数据失败:', e)
    }
  }
}

// 加载人群分析任务
const loadCrowdJobs = async () => {
  try {
    const response = await fetch('/api/dashboard/crowd-analysis-data')
    const data = await response.json()
    crowdJobs.value = data.data || []
  } catch (error) {
    // console.error('加载人群分析任务失败:', error)
    // 使用模拟数据
    crowdJobs.value = [
      { job_id: 'job1', job_name: 'A车间人数统计', people_count: 25 },
      { job_id: 'job2', job_name: 'B车间人数统计', people_count: 18 },
      { job_id: 'job3', job_name: 'C车间人数统计', people_count: 32 }
    ]
  }
}

// 更新区域人数
const updateAreaCounts = () => {
  areas.value.forEach(area => {
    if (area.jobId) {
      const job = crowdJobs.value.find(j => j.job_id === area.jobId)
      if (job) {
        area.currentCount = job.people_count || 0
      }
    }
  })
}

// 加载地图图片
const loadMapImage = () => {
  if (!config.value.mapId) return

  try {
    const savedMaps = localStorage.getItem('heatmaps')
    if (savedMaps) {
      const maps = JSON.parse(savedMaps)
      const map = maps.find(m => m.id === config.value.mapId)
      if (map) {
        const img = new Image()
        img.onload = () => {
          mapImage.value = img
          scheduleCanvasRedraw()
          setTimeout(scheduleCanvasRedraw, 100)
        }
        img.src = map.imageUrl
      }
    }
  } catch (error) {
    // console.error('加载地图失败:', error)
  }
}

// 设置canvas尺寸的通用函数
const setupCanvasSize = (canvas) => {
  if (!canvas) return null

  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1

  // 设置实际尺寸
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr

  // 设置显示尺寸
  canvas.style.width = rect.width + 'px'
  canvas.style.height = rect.height + 'px'

  // 缩放上下文以匹配设备像素比
  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)

  return { ctx, width: rect.width, height: rect.height }
}

// 绘制地图画布
const isInteractiveCanvas = (canvasEl) => {
  if (!canvasEl) return false
  return canvasEl === mapCanvasRef.value || canvasEl === expandedCanvas.value
}

const getMapTransform = (width, height, canvasEl = null) => {
  if (!mapImage.value || width <= 0 || height <= 0) return null
  const baseScale = Math.min(width / mapImage.value.width, height / mapImage.value.height)
  const interactive = isInteractiveCanvas(canvasEl)
  const scale = interactive ? baseScale * viewState.scale : baseScale
  const mapWidth = mapImage.value.width * scale
  const mapHeight = mapImage.value.height * scale
  const x = (width - mapWidth) / 2 + (interactive ? viewState.offsetX : 0)
  const y = (height - mapHeight) / 2 + (interactive ? viewState.offsetY : 0)
  return { scale, x, y }
}

const drawMapCanvas = (canvasEl) => {
  if (!canvasEl || !mapImage.value) return

  const setup = setupCanvasSize(canvasEl)
  if (!setup) return

  const { ctx, width, height } = setup
  ctx.clearRect(0, 0, width, height)

  const transform = getMapTransform(width, height, canvasEl)
  if (!transform) return

  const { scale, x, y } = transform
  const mapWidth = mapImage.value.width * scale
  const mapHeight = mapImage.value.height * scale
  ctx.drawImage(mapImage.value, x, y, mapWidth, mapHeight)

  if (areas.value?.length) {
    const polygonAreas = areas.value.filter(
      (area) => area.points?.length && (area.shapeType || 'polygon') !== 'point' && area.points.length >= 3
    )
    const projectAreas = areas.value.filter((area) => area.shapeType === 'point' && area.points?.length)

    polygonAreas.forEach((area) => drawAreaOnCanvas(ctx, area, { x, y, scale }))
    projectAreas.forEach((area) => drawProjectOnCanvas(ctx, area, { x, y, scale }))
  }
}

const drawMapCanvasView = () => drawMapCanvas(mapCanvasRef.value)

const drawExpandedCanvas = () => drawMapCanvas(expandedCanvas.value)

const scheduleCanvasRedraw = () => {
  nextTick(() => {
    drawMapCanvasView()
    if (showFullMapDialog.value) {
      drawExpandedCanvas()
    }
  })
}

const resetView = () => {
  viewState.scale = defaultMapScale.value
  viewState.offsetX = 0
  viewState.offsetY = 0
  viewState.isDragging = false
  viewState.dragMoved = false
  scheduleCanvasRedraw()
}

const openFullMapDialog = () => {
  showFullMapDialog.value = true
  nextTick(() => {
    drawExpandedCanvas()
    if (resizeObserver && expandedCanvas.value) {
      resizeObserver.observe(expandedCanvas.value)
    }
  })
}

const closeFullMapDialog = () => {
  showFullMapDialog.value = false
}

// 在画布上绘制区域
const drawAreaOnCanvas = (ctx, area, transform) => {
  if (!area.points || area.points.length < 3) return

  const { x: offsetX, y: offsetY, scale } = transform
  const isHovered = hoveredArea.value && hoveredArea.value.id === area.id
  const count = getAreaCount(area)
  const strokeColor = getHeatmapStrokeColor(count, maxCount.value)

  const canvasPoints = area.points.map(point => ({
    x: point.x * scale + offsetX,
    y: point.y * scale + offsetY,
  }))

  ctx.beginPath()
  ctx.moveTo(canvasPoints[0].x, canvasPoints[0].y)
  canvasPoints.forEach(point => ctx.lineTo(point.x, point.y))
  ctx.closePath()

  const fillColor = getHeatmapColor(count, maxCount.value, isHovered ? 0.62 : 0.52)
  ctx.fillStyle = fillColor
  ctx.fill()

  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = isHovered ? Math.max(4, scale * 4) : Math.max(3, scale * 3)
  ctx.stroke()

  ctx.strokeStyle = strokeColor
  ctx.lineWidth = isHovered ? Math.max(2, scale * 2.5) : Math.max(1.5, scale * 2)
  ctx.stroke()

  const center = calculateAreaCenter(area)
  const centerX = center.x * scale + offsetX
  const centerY = center.y * scale + offsetY
  drawDashboardLabel(ctx, centerX, centerY, area.name, formatFeatureCount(area), isHovered)
}

const formatFeatureCount = (area) => {
  const unit = area.displayUnit || '人'
  const count = area.stayingCount ?? area.currentCount ?? 0
  return `${count} ${unit}`
}

const drawProjectOnCanvas = (ctx, area, transform) => {
  const { x: offsetX, y: offsetY, scale } = transform
  const point = area.points[0]
  const cx = point.x * scale + offsetX
  const cy = point.y * scale + offsetY
  const radius = Math.max(8, scale * 10)
  const isHovered = hoveredArea.value && hoveredArea.value.id === area.id

  ctx.beginPath()
  ctx.arc(cx, cy, radius + Math.max(4, scale * 5), 0, Math.PI * 2)
  ctx.fillStyle = isHovered ? 'rgba(255, 138, 101, 0.3)' : 'rgba(255, 138, 101, 0.18)'
  ctx.fill()

  ctx.beginPath()
  ctx.arc(cx, cy, radius, 0, Math.PI * 2)
  ctx.fillStyle = area.color || 'rgba(255, 138, 101, 0.95)'
  ctx.fill()
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = Math.max(2, scale * 2.5)
  ctx.stroke()

  ctx.beginPath()
  ctx.arc(cx, cy, radius * 0.35, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()

  drawDashboardLabel(ctx, cx, cy + radius + Math.max(14, scale * 12), area.name, formatFeatureCount(area), isHovered, 'rgba(180, 83, 9, 0.9)')
}

const drawDashboardLabel = (ctx, x, y, title, subtitle, isHovered, bgColor = 'rgba(15, 23, 42, 0.86)') => {
  const fontSize = 12
  ctx.font = `bold ${fontSize}px "Microsoft YaHei", Arial`
  const titleWidth = ctx.measureText(title).width
  ctx.font = `${fontSize - 1}px "Microsoft YaHei", Arial`
  const subtitleWidth = ctx.measureText(subtitle).width
  const width = Math.max(titleWidth, subtitleWidth) + 18
  const height = 34
  const left = x - width / 2
  const top = y - height / 2

  ctx.fillStyle = isHovered ? 'rgba(255, 138, 101, 0.92)' : bgColor
  ctx.beginPath()
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(left, top, width, height, 6)
  } else {
    ctx.rect(left, top, width, height)
  }
  ctx.fill()

  ctx.fillStyle = '#ffffff'
  ctx.font = `bold ${fontSize}px "Microsoft YaHei", Arial`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(title, x, y - 6)
  ctx.font = `${fontSize - 1}px "Microsoft YaHei", Arial`
  ctx.fillStyle = '#ffe4d6'
  ctx.fillText(subtitle, x, y + 8)
}

// 自动刷新
const startAutoRefresh = () => {
  if (refreshTimer) return

  refreshTimer = setInterval(() => {
    loadData()
  }, refreshInterval.value)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 处理配置更新
const handleConfigUpdate = (event) => {
  config.value = event.detail
  stopAutoRefresh()
  loadData()
  startAutoRefresh()
}

// 处理窗口大小变化
const handleWindowResize = () => {
  scheduleCanvasRedraw()
}

const initResizeObserver = () => {
  if (typeof ResizeObserver === 'undefined') return

  resizeObserver = new ResizeObserver(() => {
    scheduleCanvasRedraw()
  })

  nextTick(() => {
    if (heatmapRootRef.value) {
      resizeObserver.observe(heatmapRootRef.value)
    }
    scheduleCanvasRedraw()
  })
}

// 工具函数
const getAreaColor = (area) => {
  if (area.shapeType === 'point') {
    return area.color || 'rgba(255, 138, 101, 0.95)'
  }
  return getHeatmapColor(getAreaCount(area), maxCount.value, 0.55)
}

const getAreaBorderColor = (area) => {
  if (area.shapeType === 'point') {
    return area.color ? area.color.replace(/rgba?/, 'rgb').replace(/,\s*[\d.]+\)/, ')') : '#ff8a65'
  }
  return getHeatmapStrokeColor(getAreaCount(area), maxCount.value)
}

const calculateDensity = (area) => {
  const size = calculateAreaSize(area)
  if (size === 0) return 0
  return ((area.currentCount || 0) / size).toFixed(3)
}

const calculateAreaSize = (area) => {
  if (!area.points || area.points.length < 3) return 0

  let area_px = 0
  const points = area.points

  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length
    area_px += points[i].x * points[j].y
    area_px -= points[j].x * points[i].y
  }

  area_px = Math.abs(area_px) / 2
  return Math.round(area_px) // 简化处理，实际应该使用比例尺
}

const calculateAreaCenter = (area) => {
  if (!area.points || area.points.length === 0) return { x: 0, y: 0 }

  const sumX = area.points.reduce((sum, point) => sum + point.x, 0)
  const sumY = area.points.reduce((sum, point) => sum + point.y, 0)

  return {
    x: sumX / area.points.length,
    y: sumY / area.points.length
  }
}

const formatTime = (time) => {
  if (!time) return '无'
  return new Date(time).toLocaleString('zh-CN')
}

const showAreaDetail = (area) => {
  selectedArea.value = area
  showAreaDetailDialog.value = true
}

const closeAreaDetail = () => {
  showAreaDetailDialog.value = false
}

// 鼠标事件处理
const handleCanvasClick = (event) => {
  if (viewState.dragMoved) return
  const area = getAreaAtPoint(event)
  if (area) {
    showAreaDetail(area)
  } else {
    closeAreaDetail()
  }
}

const handleCanvasWheel = (event) => {
  viewState.scale = Math.max(0.5, Math.min(5, viewState.scale * (event.deltaY > 0 ? 0.9 : 1.1)))
  scheduleCanvasRedraw()
}

const handleCanvasMouseDown = (event) => {
  if (event.button !== 0) return
  viewState.isDragging = true
  viewState.dragMoved = false
  viewState.lastMouseX = event.clientX
  viewState.lastMouseY = event.clientY
}

const handleCanvasMouseUp = () => {
  viewState.isDragging = false
}

const handleCanvasMouseMove = (event) => {
  if (viewState.isDragging) {
    const dx = event.clientX - viewState.lastMouseX
    const dy = event.clientY - viewState.lastMouseY
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
      viewState.dragMoved = true
      hoveredArea.value = null
    }
    viewState.offsetX += dx
    viewState.offsetY += dy
    viewState.lastMouseX = event.clientX
    viewState.lastMouseY = event.clientY
    scheduleCanvasRedraw()
    return
  }

  const currentCanvas = event.target
  if (!currentCanvas?.getContext) return

  const area = getAreaAtPoint(event)
  if (area !== hoveredArea.value) {
    hoveredArea.value = area
    scheduleCanvasRedraw()
  }
}

const handleCanvasMouseLeave = () => {
  viewState.isDragging = false
  hoveredArea.value = null
  scheduleCanvasRedraw()
}

// 获取鼠标位置的区域
const getAreaAtPoint = (event) => {
  const canvas = event.target
  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  if (!mapImage.value) return null

  const transform = getMapTransform(rect.width, rect.height, canvas)
  if (!transform) return null

  const mapX = (x - transform.x) / transform.scale
  const mapY = (y - transform.y) / transform.scale

  for (const area of areas.value) {
    if (area.shapeType === 'point' && area.points?.length) {
      const p = area.points[0]
      const radius = Math.max(12, transform.scale * 14) / transform.scale
      const dx = mapX - p.x
      const dy = mapY - p.y
      if (dx * dx + dy * dy <= radius * radius) {
        return area
      }
    }
  }

  for (const area of areas.value) {
    if ((area.shapeType || 'polygon') !== 'point' && area.points && area.points.length >= 3) {
      if (isPointInPolygon(mapX, mapY, area.points)) {
        return area
      }
    }
  }

  return null
}

// 判断点是否在多边形内
const isPointInPolygon = (x, y, polygon) => {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    if ((polygon[i].y > y) !== (polygon[j].y > y) &&
      x < (polygon[j].x - polygon[i].x) * (y - polygon[i].y) / (polygon[j].y - polygon[i].y) + polygon[i].x) {
      inside = !inside
    }
  }
  return inside
}


const goToManagement = () => {
  router.push({ path: '/system', query: { tab: 'map_config' } })
}
</script>

<style scoped>
.dashboard-heatmap {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.no-config {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  gap: 16px;
  padding: 20px;
  text-align: center;
}

@media (max-width: 400px) {
  .no-config {
    gap: 12px;
    padding: 15px;
  }

  .no-config .el-icon {
    font-size: 36px !important;
  }

  .no-config p {
    font-size: 14px;
  }

  .no-config .el-button {
    font-size: 12px;
    padding: 8px 16px;
  }
}

.map-mode {
  flex: 1 1 0;
  min-height: 0;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 完整地图：控件框（Teleport 至中栏锚点） */
.map-ui-frame {
  z-index: 6;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  box-sizing: border-box;
  pointer-events: none;
}

.map-ui-frame--anchored {
  position: absolute;
  inset: 0;
}

.map-ui-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  pointer-events: none;
}

.map-ui-row > * {
  pointer-events: auto;
}

.map-ui-row-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: start;
}

.map-ui-row-bottom {
  align-items: flex-end;
  justify-content: space-between;
}

.park-stats-panel--frame {
  position: static;
  justify-self: start;
  min-width: 0;
  max-width: 100%;
  padding: 8px 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.22);
}

.park-stats-panel--frame .park-stats-title {
  margin-bottom: 4px;
  font-size: 11px;
}

.park-stats-panel--frame .park-stat-item .value {
  font-size: 14px;
}

.map-title-badge {
  justify-self: center;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #ffd4b8;
  background: rgba(11, 20, 36, 0.82);
  border: 1px solid rgba(255, 138, 101, 0.35);
  letter-spacing: 0.5px;
  white-space: nowrap;
  line-height: 1.4;
}

.map-ui-legend {
  position: static;
  justify-self: end;
  top: auto;
  right: auto;
  min-width: 92px;
  max-width: 120px;
  padding: 8px;
}

.map-ui-overview {
  position: static;
  bottom: auto;
  left: auto;
  flex: 1 1 auto;
  min-width: 0;
  max-width: min(480px, 70%);
  max-height: 92px;
}

.map-ui-overview .mini-legend-list {
  max-height: 68px;
}

.map-ui-hint {
  position: static;
  flex-shrink: 0;
  white-space: nowrap;
}

.map-ui-placeholder {
  min-width: 0;
  min-height: 1px;
}

.interactive-canvas {
  flex: 1 1 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
  position: relative;
  z-index: 1;
}

.interactive-canvas.is-dragging {
  cursor: grabbing;
}

.full-mode .map-view-hint,
.full-mode .full-color-legend,
.full-mode .area-overview-legend,
.map-mode .map-view-hint,
.map-mode .full-color-legend,
.map-mode .area-overview-legend {
  pointer-events: none;
}

.map-mode .area-overview-legend .mini-legend-list {
  pointer-events: auto;
}

.park-stats-panel {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 8;
  min-width: 180px;
  padding: 10px 12px;
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(11, 20, 36, 0.94) 0%, rgba(21, 42, 74, 0.94) 100%);
  border: 1px solid rgba(255, 138, 101, 0.35);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
}

.park-stats-title {
  font-size: 12px;
  font-weight: 600;
  color: #ffd4b8;
  margin-bottom: 8px;
}

.park-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.park-stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.park-stat-item .label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.62);
}

.park-stat-item .value {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
}

.park-stat-item .value.enter {
  color: #7dd3fc;
}

.park-stat-item .value.exit {
  color: #fdba74;
}

.map-canvas {
  flex: 1 1 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.expanded-canvas {
  cursor: grab;
}

.expanded-canvas.is-dragging {
  cursor: grabbing;
}

.fullmap-expand-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 7;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 138, 101, 0.45);
  background: rgba(11, 20, 36, 0.88);
  color: #ffd4b8;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.fullmap-expand-btn:hover {
  background: rgba(255, 138, 101, 0.22);
  border-color: rgba(255, 138, 101, 0.65);
}

.mini-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 6;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 10px;
  max-width: min(240px, calc(100% - 16px));
  background: linear-gradient(160deg, rgba(11, 20, 36, 0.92) 0%, rgba(21, 42, 74, 0.92) 100%);
  border: 1px solid rgba(255, 138, 101, 0.24);
  backdrop-filter: blur(8px);
}

.mini-legend-title {
  font-size: 11px;
  font-weight: 600;
  color: #ffd4b8;
  margin-bottom: 6px;
}

.mini-legend-list,
.area-overview-legend .mini-legend-list {
  max-height: 120px;
  overflow-y: auto;
}

.expanded-area-overview .mini-legend-list {
  max-height: min(360px, 42vh);
}

.mini-legend-list .legend-text,
.area-overview-legend .legend-text {
  color: rgba(255, 255, 255, 0.82);
  font-size: 10px;
  line-height: 1.3;
}

@media (max-width: 400px) {
  .mini-legend {
    padding: 4px;
    font-size: 8px;
    bottom: 4px;
    left: 4px;
  }
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 6px;
}

.full-legend.full-color-legend {
  position: absolute;
  top: 44px;
  right: 12px;
  z-index: 6;
  background: linear-gradient(160deg, rgba(11, 20, 36, 0.92) 0%, rgba(21, 42, 74, 0.92) 100%);
  border: 1px solid rgba(255, 138, 101, 0.28);
  padding: 10px;
  border-radius: 8px;
  min-width: 100px;
  max-width: min(160px, calc(100% - 32px));
  backdrop-filter: blur(8px);
}

.area-overview-legend {
  max-width: min(260px, calc(100% - 120px));
}

.full-color-legend.expanded-color-legend {
  top: 12px;
  right: 12px;
}

.fullmap-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(5, 12, 24, 0.78);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.fullmap-shell {
  width: min(96vw, 1400px);
  height: min(92vh, 900px);
  display: flex;
  flex-direction: column;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(255, 138, 101, 0.28);
  background: linear-gradient(160deg, rgba(11, 20, 36, 0.98) 0%, rgba(21, 42, 74, 0.98) 100%);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.45);
}

.fullmap-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.fullmap-toolbar-title {
  font-size: 15px;
  font-weight: 600;
  color: #ffd4b8;
}

.fullmap-toolbar-actions {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.86);
  font-size: 12px;
  cursor: pointer;
}

.toolbar-btn.primary {
  border-color: rgba(255, 138, 101, 0.45);
  background: rgba(255, 138, 101, 0.18);
  color: #ffd4b8;
}

.fullmap-body {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.fullmap-float-layer {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
}

.fullmap-float-layer .mini-legend-list {
  pointer-events: auto;
}

.expanded-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
}

.expanded-hint {
  bottom: 12px;
  right: 12px;
}

.map-view-hint {
  position: absolute;
  right: 10px;
  bottom: 10px;
  z-index: 6;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.72);
  background: rgba(11, 20, 36, 0.72);
  border: 1px solid rgba(255, 138, 101, 0.22);
  pointer-events: none;
}

.full-legend .legend-title,
.full-legend .legend-labels {
  color: rgba(255, 255, 255, 0.78);
}

@media (max-width: 400px) {
  .full-legend {
    top: 8px;
    right: 8px;
    padding: 6px;
    min-width: 60px;
    font-size: 10px;
  }

  .legend-title {
    font-size: 10px !important;
  }

  .legend-labels {
    font-size: 8px !important;
  }
}

.legend-title {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 8px;
  text-align: center;
}

.legend-gradient {
  height: 20px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #666;
}

.area-detail-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(5, 12, 24, 0.42);
}

.area-detail-overlay--global {
  position: fixed;
  inset: 0;
  z-index: 4000;
}

.area-detail-panel {
  position: relative;
  width: min(300px, 90%);
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(11, 20, 36, 0.98) 0%, rgba(21, 42, 74, 0.98) 100%);
  border: 1px solid rgba(255, 138, 101, 0.35);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
  overflow: hidden;
}

.area-detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 138, 101, 0.22);
  background: rgba(10, 20, 40, 0.55);
}

.area-detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #f8fafc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-close-btn {
  flex-shrink: 0;
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 138, 101, 0.45);
  background: rgba(255, 138, 101, 0.12);
  color: #ffd4b8;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
}

.detail-close-btn:hover {
  background: rgba(255, 138, 101, 0.28);
  color: #fff;
}

.area-detail {
  padding: 10px 12px 12px;
}

.area-detail .detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.area-detail .detail-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.area-detail label {
  flex-shrink: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
}

.area-detail .value {
  font-size: 12px;
  color: #ffd4b8;
  text-align: right;
  word-break: break-all;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style> 