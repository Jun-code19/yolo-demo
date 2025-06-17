<template>
  <div class="dashboard-heatmap">
    <div v-if="!hasConfig" class="no-config">
      <el-icon :size="48"><PictureRounded /></el-icon>
      <p>暂未配置热力图</p>
      <el-button type="primary" @click="goToManagement">
        <el-icon><Setting /></el-icon>
        前往设置
      </el-button>
    </div>
    
    <div v-else-if="displayMode === 'preview'" class="preview-mode">
      <div class="preview-grid">
        <div 
          v-for="area in displayAreas" 
          :key="area.id"
          class="area-card"
          :style="{ 
            backgroundColor: getAreaColor(area),
            borderColor: getAreaBorderColor(area)
          }"
          @click="showAreaDetail(area)"
        >
          <div class="area-name">{{ area.name }}</div>
          <div class="area-count">{{ area.currentCount || 0 }}</div>
          <div class="area-unit">人</div>
          <div class="area-density">{{ calculateDensity(area) }} 人/m²</div>
        </div>
      </div>
    </div>
    
    <div v-else-if="displayMode === 'mini'" class="mini-mode">
      <canvas 
        ref="miniCanvas" 
        class="mini-canvas"
        @click="handleCanvasClick"
        @mousemove="handleCanvasMouseMove"
        @mouseleave="handleCanvasMouseLeave"
      ></canvas>
      <div class="mini-legend">
        <div class="legend-item" v-for="area in displayAreas.slice(0, 5)" :key="area.id">
          <div class="legend-color" :style="{ backgroundColor: getAreaColor(area) }"></div>
          <span class="legend-text">{{ area.name }}: {{ area.currentCount || 0 }}人</span>
        </div>
      </div>
    </div>
    
    <div v-else-if="displayMode === 'full'" class="full-mode">
      <canvas 
        ref="fullCanvas" 
        class="full-canvas"
        @click="handleCanvasClick"
        @mousemove="handleCanvasMouseMove"
        @mouseleave="handleCanvasMouseLeave"
      ></canvas>
      <div class="full-legend">
        <div class="legend-title">人数分布</div>
        <div class="legend-gradient"></div>
        <div class="legend-labels">
          <span>0</span>
          <span>{{ maxCount }}</span>
        </div>
      </div>
    </div>

    <!-- 悬停提示框 -->
    <div 
      v-if="hoveredArea && showTooltip" 
      class="area-tooltip"
      :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
    >
      <div class="tooltip-title">{{ hoveredArea.name }}</div>
      <div class="tooltip-content">
        <div class="tooltip-item">
          <span class="tooltip-label">当前人数：</span>
          <span class="tooltip-value">{{ hoveredArea.currentCount || 0 }}人</span>
        </div>
        <div class="tooltip-item">
          <span class="tooltip-label">密度：</span>
          <span class="tooltip-value">{{ calculateDensity(hoveredArea) }} 人/m²</span>
        </div>
      </div>
    </div>

    <!-- 区域详情弹窗 -->
    <el-dialog v-model="showAreaDetailDialog" :title="selectedArea?.name" width="250px">
      <div v-if="selectedArea" class="area-detail">
        <div class="detail-item">
          <label>当前人数：</label>
          <span class="value">{{ selectedArea.currentCount || 0 }} 人</span>
        </div>
        <div class="detail-item">
          <label>区域面积：</label>
          <span class="value">{{ calculateAreaSize(selectedArea) }} m²</span>
        </div>
        <div class="detail-item">
          <label>人口密度：</label>
          <span class="value">{{ calculateDensity(selectedArea) }} 人/m²</span>
        </div>
        <div class="detail-item">
          <label>绑定任务：</label>
          <span class="value">{{ selectedArea.dataSourceName }}</span>
        </div>
        <div class="detail-item">
          <label>最后更新：</label>
          <span class="value">{{ formatTime(lastUpdateTime) }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PictureRounded, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const emit = defineEmits(['open-map-zoom'])
const miniCanvas = ref(null)
const fullCanvas = ref(null)
const showAreaDetailDialog = ref(false)
const selectedArea = ref(null)
const hoveredArea = ref(null)
const showTooltip = ref(false)
const tooltipPosition = ref({ x: 0, y: 0 })

const config = ref({})
const areas = ref([])
const crowdJobs = ref([])
const mapImage = ref(null)
const lastUpdateTime = ref(null)
let refreshTimer = null
let resizeObserver = null

// 计算属性
const hasConfig = computed(() => config.value.mapId && areas.value.length > 0)
const displayMode = computed(() => config.value.displayMode || 'preview')
const maxAreas = computed(() => config.value.maxAreas || 6)
const refreshInterval = computed(() => (config.value.refreshInterval || 30) * 1000)

const displayAreas = computed(() => {
  return areas.value
    .filter(area => area.currentCount !== undefined)
    .sort((a, b) => (b.currentCount || 0) - (a.currentCount || 0))
    .slice(0, maxAreas.value)
})

const maxCount = computed(() => {
  if (!displayAreas.value.length) return 100
  return Math.max(...displayAreas.value.map(area => area.currentCount || 0), 1)
})

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
watch(displayMode, (newMode) => {
  nextTick(() => {
    // 重新设置ResizeObserver
    if (resizeObserver) {
      resizeObserver.disconnect()
      
      if (newMode === 'mini' && miniCanvas.value) {
        resizeObserver.observe(miniCanvas.value)
        drawMiniCanvas()
      } else if (newMode === 'full' && fullCanvas.value) {
        resizeObserver.observe(fullCanvas.value)
        drawFullCanvas()
      }
    }
  })
})

// 监听悬停区域变化，重绘canvas
watch(hoveredArea, () => {
  if (displayMode.value === 'mini') {
    drawMiniCanvas()
  } else if (displayMode.value === 'full') {
    drawFullCanvas()
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
        displayMode: result.data.display_mode,
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
        points: area.points,
        color: area.color,
        jobId: area.data_source_id,
        currentCount: area.current_count || 0,
        maxCapacity: area.max_capacity,
        areaSize: area.area_size,
        dataSourceType: area.data_source_type,
        dataSourceName: area.data_source_name,
        lastUpdateTime: area.last_update_time
      }))
      
      // 处理地图数据
      if (result.data.map) {
        const mapData = result.data.map
        const img = new Image()
        img.onload = () => {
          mapImage.value = img
          nextTick(() => {
            if (displayMode.value === 'mini') {
              drawMiniCanvas()
            } else if (displayMode.value === 'full') {
              drawFullCanvas()
            }
          })
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
          nextTick(() => {
            if (displayMode.value === 'mini') {
              drawMiniCanvas()
            } else if (displayMode.value === 'full') {
              drawFullCanvas()
            }
          })
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

// 绘制迷你画布
const drawMiniCanvas = () => {
  if (!miniCanvas.value || !mapImage.value) return
  
  const setup = setupCanvasSize(miniCanvas.value)
  if (!setup) return
  
  const { ctx, width, height } = setup
  
  // 清除画布
  ctx.clearRect(0, 0, width, height)
  
  // 绘制地图背景
  const scale = Math.min(width / mapImage.value.width, height / mapImage.value.height)
  const mapWidth = mapImage.value.width * scale
  const mapHeight = mapImage.value.height * scale
  const x = (width - mapWidth) / 2
  const y = (height - mapHeight) / 2
  
  ctx.drawImage(mapImage.value, x, y, mapWidth, mapHeight)
  
  // 绘制区域
  if (areas.value && areas.value.length > 0) {
    areas.value.forEach(area => {
      if (area.points && area.points.length >= 3) {
        drawAreaOnCanvas(ctx, area, { x, y, scale })
      }
    })
  }
}

// 绘制完整画布
const drawFullCanvas = () => {
  if (!fullCanvas.value || !mapImage.value) return
  
  const setup = setupCanvasSize(fullCanvas.value)
  if (!setup) return
  
  const { ctx, width, height } = setup
  
  // 清除画布
  ctx.clearRect(0, 0, width, height)
  
  // 绘制地图背景
  const scale = Math.min(width / mapImage.value.width, height / mapImage.value.height)
  const mapWidth = mapImage.value.width * scale
  const mapHeight = mapImage.value.height * scale
  const x = (width - mapWidth) / 2
  const y = (height - mapHeight) / 2
  
  ctx.drawImage(mapImage.value, x, y, mapWidth, mapHeight)
  
  // 绘制区域
  if (areas.value && areas.value.length > 0) {
    areas.value.forEach(area => {
      if (area.points && area.points.length >= 3) {
        drawAreaOnCanvas(ctx, area, { x, y, scale })
      }
    })
  }
}

// 在画布上绘制区域
const drawAreaOnCanvas = (ctx, area, transform) => {
  if (!area.points || area.points.length < 3) return
  
  const { x: offsetX, y: offsetY, scale } = transform
  const isHovered = hoveredArea.value && hoveredArea.value.id === area.id
  
  ctx.beginPath()
  const firstPoint = area.points[0]
  ctx.moveTo(firstPoint.x * scale + offsetX, firstPoint.y * scale + offsetY)
  
  area.points.forEach(point => {
    ctx.lineTo(point.x * scale + offsetX, point.y * scale + offsetY)
  })
  ctx.closePath()
  
  // 悬停时的特殊效果
  if (isHovered) {
    // 绘制光晕效果
    ctx.save()
    ctx.shadowColor = getAreaBorderColor(area)
    ctx.shadowBlur = 20
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 0
    
    // 填充半透明背景
    const hoverColor = getAreaColor(area).replace(/[\d\.]+\)$/g, '0.6)')
    ctx.fillStyle = hoverColor
    ctx.fill()
    
    ctx.restore()
  }
  
  // 填充颜色
  ctx.fillStyle = getAreaColor(area)
  ctx.fill()
  
  // 绘制边框
  ctx.strokeStyle = getAreaBorderColor(area)
  ctx.lineWidth = isHovered ? Math.max(2, scale * 3) : Math.max(1, scale * 2)
  
  // 悬停时边框发光效果
  if (isHovered) {
    ctx.save()
    ctx.shadowColor = getAreaBorderColor(area)
    ctx.shadowBlur = 10
    ctx.shadowOffsetX = 0
    ctx.shadowOffsetY = 0
  }
  
  ctx.stroke()
  
  if (isHovered) {
    ctx.restore()
  }
  
  // 绘制标签 - 动态调整字体大小
  const center = calculateAreaCenter(area)
  const centerX = center.x * scale + offsetX
  const centerY = center.y * scale + offsetY
  
  // 根据缩放比例调整字体大小
  const fontSize = Math.max(8, Math.min(16, scale * 12))
  
  ctx.fillStyle = isHovered ? '#fff' : '#333'
  ctx.font = `${isHovered ? 'bold ' : ''}${fontSize}px Arial`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  
  // 添加文字阴影效果
  ctx.shadowColor = isHovered ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.8)'
  ctx.shadowBlur = isHovered ? 4 : 2
  ctx.shadowOffsetX = 1
  ctx.shadowOffsetY = 1
  
  ctx.fillText(area.name, centerX, centerY - fontSize * 0.6)
  ctx.fillText(`${area.currentCount || 0}人`, centerX, centerY + fontSize * 0.6)
  
  // 重置阴影
  ctx.shadowColor = 'transparent'
  ctx.shadowBlur = 0
  ctx.shadowOffsetX = 0
  ctx.shadowOffsetY = 0
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
  nextTick(() => {
    if (displayMode.value === 'mini') {
      drawMiniCanvas()
    } else if (displayMode.value === 'full') {
      drawFullCanvas()
    }
  })
}

// 初始化ResizeObserver
const initResizeObserver = () => {
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        if (entry.target === miniCanvas.value || entry.target === fullCanvas.value) {
          nextTick(() => {
            if (displayMode.value === 'mini' && miniCanvas.value) {
              drawMiniCanvas()
            } else if (displayMode.value === 'full' && fullCanvas.value) {
              drawFullCanvas()
            }
          })
          break
        }
      }
    })
    
    // 观察canvas元素
    nextTick(() => {
      if (miniCanvas.value) {
        resizeObserver.observe(miniCanvas.value)
      }
      if (fullCanvas.value) {
        resizeObserver.observe(fullCanvas.value)
      }
    })
  }
}

// 工具函数
const getAreaColor = (area) => {
  const density = calculateDensity(area)
  const intensity = Math.min(density / 0.1, 1)
  const alpha = 0.3 + intensity * 0.4
  return area.color ? area.color.replace(/[\d\.]+\)$/g, `${alpha})`) : `rgba(74, 144, 226, ${alpha})`
}

const getAreaBorderColor = (area) => {
  return area.color ? area.color.replace(/rgba?/, 'rgb').replace(/,\s*[\d\.]+\)/, ')') : '#4a90e2'
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

// 鼠标事件处理
const handleCanvasClick = (event) => {
  const area = getAreaAtPoint(event)
  if (area) {
    showAreaDetail(area)
  } else {
    // 向父组件发送事件，传递当前组件的地图数据
    emit('open-map-zoom', {
      mapImage: mapImage.value,
      areas: areas.value,
      config: config.value
    })
  }
}

const handleCanvasMouseMove = (event) => {
  const area = getAreaAtPoint(event)
  if (area !== hoveredArea.value) {
    hoveredArea.value = area
    if (area) {
      showTooltip.value = true
      updateTooltipPosition(event)
    } else {
      showTooltip.value = false
    }
  } else if (area) {
    updateTooltipPosition(event)
  }
}

const handleCanvasMouseLeave = () => {
  hoveredArea.value = null
  showTooltip.value = false
}

const updateTooltipPosition = (event) => {
  const rect = event.target.getBoundingClientRect()
  tooltipPosition.value = {
    x: event.clientX - rect.left + 10,
    y: event.clientY - rect.top - 10
  }
}

// 获取鼠标位置的区域
const getAreaAtPoint = (event) => {
  const canvas = event.target
  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  if (!mapImage.value) return null
  
  // 计算地图变换
  const scale = Math.min(rect.width / mapImage.value.width, rect.height / mapImage.value.height)
  const mapWidth = mapImage.value.width * scale
  const mapHeight = mapImage.value.height * scale
  const offsetX = (rect.width - mapWidth) / 2
  const offsetY = (rect.height - mapHeight) / 2
  
  // 转换为地图坐标
  const mapX = (x - offsetX) / scale
  const mapY = (y - offsetY) / scale
  
  // 检查哪个区域包含这个点
  for (const area of areas.value) {
    if (area.points && area.points.length >= 3) {
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
  router.push('/heatmap-management')
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

.preview-mode {
  flex: 1;
  padding: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
  flex: 1;
  overflow: auto;
  align-content: start;
}

/* 响应式网格布局 */
@media (max-width: 400px) {
  .preview-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
  }
}

@media (min-width: 401px) and (max-width: 600px) {
  .preview-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
}

@media (min-width: 601px) {
  .preview-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
  }
}

.area-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 8px;
  border-radius: 8px;
  border: 2px solid;
  cursor: pointer;
  transition: all 0.3s ease;
  min-height: 80px;
  aspect-ratio: 1;
  position: relative;
  overflow: hidden;
}

/* 区域卡片响应式调整 */
@media (max-width: 400px) {
  .area-card {
    padding: 8px 4px;
    min-height: 60px;
  }
  
  .area-name {
    font-size: 10px !important;
  }
  
  .area-count {
    font-size: 18px !important;
  }
  
  .area-unit {
    font-size: 10px !important;
  }
  
  .area-density {
    font-size: 8px !important;
  }
}

@media (min-width: 401px) and (max-width: 600px) {
  .area-card {
    padding: 10px 6px;
    min-height: 70px;
  }
  
  .area-name {
    font-size: 11px !important;
  }
  
  .area-count {
    font-size: 20px !important;
  }
}

.area-card:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.area-name {
  font-size: 12px;
  font-weight: bold;
  color: #333;
  margin-bottom: 8px;
  text-align: center;
}

.area-count {
  font-size: 24px;
  font-weight: bold;
  color: #333;
  line-height: 1;
}

.area-unit {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.area-density {
  font-size: 10px;
  color: #999;
}

.mini-mode, .full-mode {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mini-canvas, .full-canvas {
  width: 100%;
  height: 100%;
  cursor: pointer;
  display: block;
  object-fit: contain;
}

.mini-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  /* background: rgba(255, 255, 255, 0.9); */
  padding: 6px;
  border-radius: 4px;
  font-size: 10px;
  max-width: calc(100% - 16px);
  backdrop-filter: blur(5px);
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

.full-legend {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 6px;
  min-width: 80px;
  max-width: calc(100% - 32px);
  backdrop-filter: blur(5px);
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

.area-detail .detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.area-detail .detail-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.area-detail label {
  font-weight: 500;
  color: #666;
}

.area-detail .value {
  /* font-weight: bold; */
  color: #333;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* 悬停提示框样式 */
.area-tooltip {
  position: fixed;
  background: linear-gradient(135deg, 
    rgba(30, 60, 114, 0.95) 0%, 
    rgba(15, 26, 46, 0.98) 100%
  );
  border: 1px solid rgba(255, 138, 101, 0.6);
  border-radius: 8px;
  padding: 12px;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 0 20px rgba(255, 138, 101, 0.3);
  backdrop-filter: blur(15px);
  z-index: 9999;
  pointer-events: none;
  max-width: 200px;
  animation: tooltipFadeIn 0.2s ease;
}

@keyframes tooltipFadeIn {
  0% { 
    opacity: 0; 
    transform: translate(-50%, -50%) scale(0.8); 
  }
  100% { 
    opacity: 1; 
    transform: translate(-50%, -50%) scale(1); 
  }
}

.tooltip-title {
  font-size: 14px;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 138, 101, 0.4);
  text-align: center;
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tooltip-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tooltip-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

.tooltip-value {
  font-size: 12px;
  font-weight: bold;
  color: #ff8a65;
  text-shadow: 0 0 8px rgba(255, 138, 101, 0.6);
}



/* 添加canvas鼠标悬停样式 */
.mini-canvas,
.full-canvas {
  cursor: pointer;
  transition: filter 0.3s ease;
}

.mini-canvas:hover,
.full-canvas:hover {
  filter: brightness(1.05);
}
</style> 