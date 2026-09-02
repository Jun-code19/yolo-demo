<template>
  <div class="heatmap-management">
    <div class="page-header">
      <div class="header-content">
        <h1>人数热力图管理</h1>
        <p>管理地图、设置区域、绑定数据源</p>
        <div v-if="currentMapId" class="status-info">
          <el-tag type="success" size="small">
            已选择地图：{{ getMapName(currentMapId) }}
          </el-tag>
          <el-tag v-if="currentAreas.length > 0" type="info" size="small" style="margin-left: 8px;">
            {{ getPolygonAreasCount() }} 个区域
          </el-tag>
          <el-tag v-if="getProjectPointsCount() > 0" type="info" size="small" style="margin-left: 8px;">
            {{ getProjectPointsCount() }} 个项目点
          </el-tag>
          <el-tag v-if="getBoundAreasCount() > 0" type="warning" size="small" style="margin-left: 8px;">
            {{ getBoundAreasCount() }} 个已绑定
          </el-tag>
        </div>
      </div>
      <div class="header-actions">
        <el-button @click="refreshData" icon="Refresh">刷新数据</el-button>
        <el-button @click="$router.back()" icon="ArrowLeft">返回</el-button>
        <el-button type="primary" @click="saveToDisplay" :loading="saving">
          <el-icon><Select /></el-icon>
          保存到展板
        </el-button>
      </div>
    </div>

    <div class="management-content">
      <HeatMapManager 
        ref="heatMapManagerRef"
        :full-page="true"
        @map-selected="handleMapSelected"
        @areas-updated="handleAreasUpdated"
        @maps-changed="handleMapsChanged"
      />
    </div>

    <!-- 配置展板显示对话框 -->
    <Teleport to="body">
      <el-dialog
        v-model="showDisplayConfig"
        title="配置展板显示"
        width="560px"
        align-center
        append-to-body
        destroy-on-close
        lock-scroll
        :close-on-click-modal="false"
        modal-class="heatmap-display-config-overlay"
        class="heatmap-display-config-dialog high-priority-dialog"
      >
      <el-form :model="displayConfig" :rules="displayRules" ref="displayFormRef" label-width="100px">
        <el-form-item label="显示地图" prop="mapId">
          <el-select v-model="displayConfig.mapId" placeholder="选择要在展板显示的地图" style="width: 100%">
            <el-option label="请选择地图" value="" disabled />
            <el-option
              v-for="map in availableMaps"
              :key="map.id"
              :label="map.name"
              :value="map.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="显示模式" prop="displayMode">
          <el-radio-group v-model="displayConfig.displayMode">
            <el-radio value="mini">迷你地图（面板内交互）</el-radio>
            <el-radio value="full">完整地图（底层全屏）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="渲染风格" prop="renderStyle">
          <el-radio-group v-model="displayConfig.renderStyle">
            <el-radio value="block">普通模式</el-radio>
            <el-radio value="fusion">热力融合</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="displayConfig.renderStyle === 'fusion'">
          <el-form-item label="融合模糊">
            <el-slider v-model="displayConfig.fusionConfig.blur" :min="12" :max="80" :step="2" show-input />
          </el-form-item>
          <el-form-item label="融合透明度">
            <el-slider v-model="displayConfig.fusionConfig.opacity" :min="0.5" :max="1" :step="0.01" show-input />
          </el-form-item>
          <el-form-item label="显示边界">
            <el-switch v-model="displayConfig.fusionConfig.showBorders" />
          </el-form-item>
        </template>
        <el-form-item label="刷新间隔" prop="refreshInterval">
          <el-input-number 
            v-model="displayConfig.refreshInterval" 
            :min="10" 
            :max="300"
            :step="10"
          />
          <span style="margin-left: 8px; color: #666;">秒</span>
        </el-form-item>
        <el-form-item label="显示区域数" prop="maxAreas">
          <el-input-number 
            v-model="displayConfig.maxAreas" 
            :min="1" 
            :max="20"
          />
        </el-form-item>
        <el-form-item label="地图标签">
          <el-radio-group v-model="displayConfig.labelMode">
            <el-radio value="smart">智能</el-radio>
            <el-radio value="hover">仅悬停</el-radio>
            <el-radio value="all">全部</el-radio>
            <el-radio value="off">关闭</el-radio>
          </el-radio-group>
          <div style="margin-top: 6px; color: #909399; font-size: 12px; line-height: 1.5;">
            智能模式仅显示人数 Top N（见显示区域数）与当前悬停项，并自动避让重叠
          </div>
        </el-form-item>
        <el-divider content-position="left">园内人数</el-divider>
        <el-form-item label="启用显示">
          <el-switch v-model="displayConfig.parkStats.enabled" />
        </el-form-item>
        <el-form-item v-if="displayConfig.parkStats.enabled" label="标题">
          <el-input v-model="displayConfig.parkStats.title" maxlength="20" />
        </el-form-item>
        <el-form-item v-if="displayConfig.parkStats.enabled" label="订阅监控">
          <el-select
            v-model="displayConfig.parkStats.schemeIds"
            multiple
            filterable
            collapse-tags
            placeholder="选择人数统计订阅（园内 = 各订阅「进入 − 离开」之和，单点可为负）"
            style="width: 100%"
          >
            <el-option v-for="scheme in numberStatSchemes" :key="scheme.id" :label="scheme.label" :value="scheme.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDisplayConfig = false">取消</el-button>
          <el-button type="primary" @click="confirmDisplayConfig" :loading="saving">确定</el-button>
        </span>
      </template>
      </el-dialog>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Select, Refresh } from '@element-plus/icons-vue'
import HeatMapManager from '@/components/HeatMapManager.vue'
import { dashboardMapApi, normalizeHeatmapDisplayMode, normalizeHeatmapRenderStyle, normalizeLabelMode, DEFAULT_FUSION_CONFIG } from '@/api/dashboard'
import { smartSchemeApi } from '@/api/smart_scheme'

const router = useRouter()
const heatMapManagerRef = ref(null)
const displayFormRef = ref(null)

const saving = ref(false)
const showDisplayConfig = ref(false)
const availableMaps = ref([])
const currentMapId = ref(null)
const currentAreas = ref([])
const numberStatSchemes = ref([])

const defaultParkStats = () => ({
  enabled: false,
  title: '园内人数',
  schemeIds: [],
})

// 展板显示配置
const displayConfig = reactive({
  mapId: '',
  displayMode: 'mini',
  renderStyle: 'block',
  fusionConfig: { ...DEFAULT_FUSION_CONFIG },
  labelMode: 'smart',
  refreshInterval: 30,
  maxAreas: 6,
  parkStats: defaultParkStats(),
})

// 表单验证规则
const displayRules = {
  mapId: [
    { required: true, message: '请选择要显示的地图', trigger: 'change' },
    { 
      validator: (rule, value, callback) => {
        if (!value || value === '') {
          callback(new Error('请选择要显示的地图'))
        } else {
          callback()
        }
      }, 
      trigger: 'change' 
    }
  ],
  displayMode: [
    { required: true, message: '请选择显示模式', trigger: 'change' }
  ]
}

onMounted(async () => {
  await loadAvailableMaps()
  await loadNumberStatSchemes()
  await loadCurrentDisplayConfig()
})

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
    numberStatSchemes.value = []
  }
}

// 加载可用地图列表
const loadAvailableMaps = async () => {
  try {
    const response = await dashboardMapApi.getDashboardMaps()
    const maps = response.data || response
    
    if (maps && maps.length > 0) {
      availableMaps.value = maps.map(map => ({
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
      availableMaps.value = []
    }
  } catch (error) {
    console.error('加载地图列表失败:', error)
    ElMessage.error('加载地图列表失败')
    availableMaps.value = []
  }
}

// 加载当前展板配置
const loadCurrentDisplayConfig = async () => {
  try {
    const response = await dashboardMapApi.getDashboardConfig()
    if (response.data && response.data.success && response.data.data) {
      const config = response.data.data
      displayConfig.mapId = config.map_id ? config.map_id.toString() : ''
      displayConfig.displayMode = normalizeHeatmapDisplayMode(config.display_mode || 'mini')
      displayConfig.renderStyle = normalizeHeatmapRenderStyle(config.config?.render_style)
      displayConfig.fusionConfig = {
        ...DEFAULT_FUSION_CONFIG,
        ...(config.config?.fusion_config || {}),
      }
      displayConfig.labelMode = normalizeLabelMode(
        config.config?.label_mode,
        config.config?.fusion_config?.showLabels,
      )
      displayConfig.refreshInterval = config.refresh_interval || 30
      displayConfig.maxAreas = config.max_areas || 6
      const park = config.config?.park_stats
      if (park) {
        displayConfig.parkStats.enabled = !!park.enabled
        displayConfig.parkStats.title = park.title || '园内人数'
        displayConfig.parkStats.schemeIds = [...(park.scheme_ids || [])]
      }
    }
  } catch (error) {
    console.error('加载展板配置失败:', error)
    // 如果加载失败，保持默认配置
  }
}

// 处理地图选择
const handleMapSelected = (mapId) => {
  currentMapId.value = mapId
  if (!mapId) {
    currentAreas.value = []
    return
  }
  if (!displayConfig.mapId || displayConfig.mapId === '') {
    displayConfig.mapId = mapId
  }
}

const handleMapsChanged = async () => {
  await loadAvailableMaps()
  if (currentMapId.value && !availableMaps.value.some(m => m.id === currentMapId.value)) {
    currentMapId.value = availableMaps.value[0]?.id || null
    currentAreas.value = []
    if (currentMapId.value) {
      displayConfig.mapId = currentMapId.value
    } else {
      displayConfig.mapId = ''
    }
  }
}

// 处理区域更新
const handleAreasUpdated = (areas) => {
  currentAreas.value = areas
}

// 刷新数据
const refreshData = async () => {
  try {
    await loadAvailableMaps()
    await loadCurrentDisplayConfig()
    ElMessage.success('数据刷新成功')
  } catch (error) {
    console.error('刷新数据失败:', error)
    ElMessage.error('刷新数据失败')
  }
}

const resetPageScroll = () => {
  window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  document.documentElement.scrollTop = 0
  document.body.scrollTop = 0
  document.querySelector('.el-main')?.scrollTo?.({ top: 0, left: 0, behavior: 'instant' })
}

const openDisplayConfigDialog = () => {
  showDisplayConfig.value = true
  nextTick(resetPageScroll)
}

// 保存到展板
const saveToDisplay = () => {
  if (!currentMapId.value) {
    ElMessage.warning('请先选择地图')
    return
  }
  
  if (currentAreas.value.length === 0) {
    ElMessage.warning('请先设置区域')
    return
  }
  
  // 检查是否有区域绑定了数据源
  const hasBinding = currentAreas.value.some(area => (area.sourceId || area.jobId) && (area.sourceId || area.jobId) !== '')
  if (!hasBinding) {
    ElMessage.warning('请至少为一个区域绑定数据源')
    return
  }
  
  displayConfig.mapId = currentMapId.value
  openDisplayConfigDialog()
}

// 确认展板配置
const confirmDisplayConfig = async () => {
  if (!displayFormRef.value) return
  
  try {
    await displayFormRef.value.validate()
    saving.value = true
    
    // 构建API请求数据
    const configData = {
      map_id: parseInt(displayConfig.mapId),
      display_mode: normalizeHeatmapDisplayMode(displayConfig.displayMode),
      refresh_interval: displayConfig.refreshInterval,
      max_areas: displayConfig.maxAreas,
      config: {
        lastUpdated: new Date().toISOString(),
        areas: currentAreas.value,
        render_style: normalizeHeatmapRenderStyle(displayConfig.renderStyle),
        label_mode: displayConfig.labelMode,
        fusion_config: { ...displayConfig.fusionConfig },
        park_stats: {
          enabled: displayConfig.parkStats.enabled,
          title: displayConfig.parkStats.title?.trim() || '园内人数',
          scheme_ids: displayConfig.parkStats.enabled ? [...displayConfig.parkStats.schemeIds] : [],
        },
      }
    }
    
    // 调用API保存配置
    const response = await dashboardMapApi.saveDashboardConfig(configData)
    
    if (response.data && response.data.success) {
      // 触发展板刷新事件
      window.dispatchEvent(new CustomEvent('heatmap-config-updated', {
        detail: {
          mapId: displayConfig.mapId,
          displayMode: displayConfig.displayMode,
          renderStyle: displayConfig.renderStyle,
          labelMode: displayConfig.labelMode,
          fusionConfig: { ...displayConfig.fusionConfig },
          refreshInterval: displayConfig.refreshInterval,
          maxAreas: displayConfig.maxAreas,
          areas: currentAreas.value,
          lastUpdated: new Date().toISOString()
        }
      }))
      
      showDisplayConfig.value = false
      ElMessage.success('展板配置保存成功')
      
      // 可选择返回Dashboard
      setTimeout(() => {
        router.push('/dashboard')
      }, 1000)
    } else {
      throw new Error(response.data?.message || '保存配置失败')
    }
    
  } catch (error) {
    console.error('保存展板配置失败:', error)
    ElMessage.error(error.message || '保存配置失败')
  } finally {
    saving.value = false
  }
}

// 获取地图名称
const getMapName = (mapId) => {
  const map = availableMaps.value.find(m => m.id === mapId)
  return map ? map.name : '未知地图'
}

// 获取已绑定区域数量
const getBoundAreasCount = () => {
  return currentAreas.value.filter(area => (area.sourceId || area.jobId) && (area.sourceId || area.jobId) !== '').length
}

const getPolygonAreasCount = () => {
  return currentAreas.value.filter(area => (area.shapeType || 'polygon') === 'polygon').length
}

const getProjectPointsCount = () => {
  return currentAreas.value.filter(area => area.shapeType === 'point').length
}

</script>

<style scoped>
.heatmap-management {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-content h1 {
  margin: 0 0 5px 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.header-content p {
  margin: 0;
  color: #606266;
  font-size: 14px;
}

.status-info {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.management-content {
  flex: 1;
  overflow: hidden;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

<style>
.el-overlay.heatmap-display-config-overlay {
  position: fixed !important;
  inset: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
}

.heatmap-display-config-dialog.el-dialog {
  max-width: calc(100vw - 32px);
  margin: auto;
}

.heatmap-display-config-dialog .el-dialog__body {
  max-height: min(72vh, calc(100vh - 180px));
  overflow-x: hidden;
  overflow-y: auto;
}
</style> 