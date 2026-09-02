<template>
  <div class="dashboard-map-config">
    <el-card class="screen-name-card">
      <div class="screen-name-row">
        <div class="screen-name-label-wrap">
          <div class="panel-title">大屏名称</div>
          <div class="panel-desc">展示在数据大屏顶部的标题，可随时修改</div>
        </div>
        <div class="screen-name-form">
          <el-input
            v-model="displayConfig.screenName"
            maxlength="40"
            show-word-limit
            placeholder="园区 AI 视觉监测大屏"
            clearable
          />
          <el-button type="primary" :loading="savingScreenName" @click="saveScreenName">
            保存名称
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="park-stats-card">
      <div class="park-stats-config">
        <div>
          <div class="panel-title">园内人数统计</div>
          <div class="panel-desc">绑定多个订阅监控（人数统计），汇总当前/进入/离开人数，展示在展板人数分布左上角</div>
        </div>
        <el-form label-width="96px" class="park-stats-form">
          <el-form-item label="启用显示">
            <el-switch v-model="displayConfig.parkStats.enabled" />
          </el-form-item>
          <template v-if="displayConfig.parkStats.enabled">
            <el-form-item label="标题">
              <el-input v-model="displayConfig.parkStats.title" maxlength="20" placeholder="园内人数" />
            </el-form-item>
            <el-form-item label="订阅监控">
              <el-select
                v-model="displayConfig.parkStats.schemeIds"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                placeholder="选择人数统计订阅（可多选）"
                style="width: 100%"
              >
                <el-option
                  v-for="scheme in numberStatSchemes"
                  :key="scheme.id"
                  :label="scheme.label"
                  :value="scheme.id"
                />
              </el-select>
            </el-form-item>
          </template>
        </el-form>
      </div>
    </el-card>

    <el-card class="map-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="panel-title">热力图与区域</div>
            <div class="panel-desc">管理地图、绘制区域、绑定数据源，并保存到数据大屏</div>
            <div v-if="currentMapId" class="status-info">
              <el-tag type="success" size="small">
                已选择地图：{{ getMapName(currentMapId) }}
              </el-tag>
              <el-tag v-if="currentAreas.length > 0" type="info" size="small">
                {{ currentAreas.length }} 个区域
              </el-tag>
              <el-tag v-if="getBoundAreasCount() > 0" type="warning" size="small">
                {{ getBoundAreasCount() }} 个已绑定
              </el-tag>
            </div>
          </div>
          <div class="header-actions">
            <el-button @click="refreshData" :icon="Refresh">刷新</el-button>
            <el-button type="primary" @click="saveToDisplay" :loading="saving" :icon="Select">
              保存到展板
            </el-button>
          </div>
        </div>
      </template>

      <div class="management-content">
        <HeatMapManager
          ref="heatMapManagerRef"
          :full-page="false"
          @map-selected="handleMapSelected"
          @areas-updated="handleAreasUpdated"
          @maps-changed="handleMapsChanged"
        />
      </div>
    </el-card>

    <el-card class="integration-card">
      <el-collapse v-model="integrationExpanded">
        <el-collapse-item name="integration">
          <template #title>
            <div class="integration-collapse-title">
              <span class="panel-title">展板外部接口</span>
              <span class="panel-desc">排队时长与天气接口，密钥由服务端安全代理</span>
            </div>
          </template>
          <DashboardIntegrationConfig compact />
        </el-collapse-item>
      </el-collapse>
    </el-card>

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
        <el-form-item label="大屏名称" prop="screenName">
          <el-input
            v-model="displayConfig.screenName"
            maxlength="40"
            show-word-limit
            placeholder="园区 AI 视觉监测大屏"
            clearable
          />
        </el-form-item>
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
          <span class="field-suffix">秒</span>
        </el-form-item>
        <el-form-item label="显示区域数" prop="maxAreas">
          <el-input-number v-model="displayConfig.maxAreas" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="地图标签">
          <el-radio-group v-model="displayConfig.labelMode">
            <el-radio value="smart">智能</el-radio>
            <el-radio value="hover">仅悬停</el-radio>
            <el-radio value="all">全部</el-radio>
            <el-radio value="off">关闭</el-radio>
          </el-radio-group>
          <div class="form-tip">智能模式仅显示人数 Top N（见显示区域数）与当前悬停项，并自动避让重叠</div>
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
            placeholder="选择人数统计订阅"
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
import { ElMessage } from 'element-plus'
import { Select, Refresh } from '@element-plus/icons-vue'
import HeatMapManager from '@/components/HeatMapManager.vue'
import DashboardIntegrationConfig from '@/components/DashboardIntegrationConfig.vue'
import { dashboardMapApi, DEFAULT_DASHBOARD_SCREEN_NAME, normalizeHeatmapDisplayMode, normalizeHeatmapRenderStyle, normalizeLabelMode, DEFAULT_FUSION_CONFIG } from '@/api/dashboard'
import { smartSchemeApi } from '@/api/smart_scheme'

const heatMapManagerRef = ref(null)
const displayFormRef = ref(null)
const integrationExpanded = ref([])

const saving = ref(false)
const savingScreenName = ref(false)
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

const displayConfig = reactive({
  mapId: '',
  displayMode: 'mini',
  renderStyle: 'block',
  fusionConfig: { ...DEFAULT_FUSION_CONFIG },
  labelMode: 'smart',
  refreshInterval: 30,
  maxAreas: 6,
  screenName: DEFAULT_DASHBOARD_SCREEN_NAME,
  parkStats: defaultParkStats(),
})

const displayRules = {
  mapId: [
    { required: true, message: '请选择要显示的地图', trigger: 'change' },
    {
      validator: (_rule, value, callback) => {
        if (!value || value === '') {
          callback(new Error('请选择要显示的地图'))
        } else {
          callback()
        }
      },
      trigger: 'change'
    }
  ],
  displayMode: [{ required: true, message: '请选择显示模式', trigger: 'change' }]
}

onMounted(async () => {
  await loadAvailableMaps()
  await loadNumberStatSchemes()
  await loadCurrentDisplayConfig()
  await initHeatMapView()
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

const initHeatMapView = async () => {
  await nextTick()
  const manager = heatMapManagerRef.value
  if (!manager) return

  await manager.loadMapList?.()

  const mapId = displayConfig.mapId || availableMaps.value[0]?.id
  if (mapId) {
    await manager.selectMap(mapId)
    currentMapId.value = mapId.toString()
  }
  manager.refreshView?.()
}

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
      displayConfig.screenName = config.screen_name || DEFAULT_DASHBOARD_SCREEN_NAME
      const park = config.config?.park_stats
      if (park) {
        displayConfig.parkStats.enabled = !!park.enabled
        displayConfig.parkStats.title = park.title || '园内人数'
        displayConfig.parkStats.schemeIds = [...(park.scheme_ids || [])]
      }
    }
  } catch (error) {
    console.error('加载展板配置失败:', error)
  }
}

const dispatchScreenNameUpdated = (screenName) => {
  window.dispatchEvent(new CustomEvent('heatmap-config-updated', {
    detail: { screenName },
  }))
}

const saveScreenName = async () => {
  const name = displayConfig.screenName?.trim() || DEFAULT_DASHBOARD_SCREEN_NAME
  savingScreenName.value = true
  try {
    const response = await dashboardMapApi.saveDashboardScreenName(name)
    if (response.data?.success) {
      displayConfig.screenName = response.data.data?.screen_name || name
      dispatchScreenNameUpdated(displayConfig.screenName)
      ElMessage.success('大屏名称已保存')
    } else {
      throw new Error(response.data?.message || '保存失败')
    }
  } catch (error) {
    console.error('保存大屏名称失败:', error)
    ElMessage.error(error.message || '保存大屏名称失败')
  } finally {
    savingScreenName.value = false
  }
}

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

const handleAreasUpdated = (areas) => {
  currentAreas.value = areas
}

const refreshData = async () => {
  try {
    await loadAvailableMaps()
    await loadCurrentDisplayConfig()
    await initHeatMapView()
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

const saveToDisplay = () => {
  if (!currentMapId.value) {
    ElMessage.warning('请先选择地图')
    return
  }

  if (currentAreas.value.length === 0) {
    ElMessage.warning('请先设置区域')
    return
  }

  const hasBinding = currentAreas.value.some(area => (area.sourceId || area.jobId) && (area.sourceId || area.jobId) !== '')
  if (!hasBinding) {
    ElMessage.warning('请至少为一个区域绑定数据源')
    return
  }

  displayConfig.mapId = currentMapId.value
  openDisplayConfigDialog()
}

const confirmDisplayConfig = async () => {
  if (!displayFormRef.value) return

  try {
    await displayFormRef.value.validate()
    saving.value = true

    const configData = {
      map_id: parseInt(displayConfig.mapId),
      display_mode: normalizeHeatmapDisplayMode(displayConfig.displayMode),
      refresh_interval: displayConfig.refreshInterval,
      max_areas: displayConfig.maxAreas,
      screen_name: displayConfig.screenName?.trim() || DEFAULT_DASHBOARD_SCREEN_NAME,
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

    const response = await dashboardMapApi.saveDashboardConfig(configData)

    if (response.data && response.data.success) {
      window.dispatchEvent(new CustomEvent('heatmap-config-updated', {
        detail: {
          mapId: displayConfig.mapId,
          displayMode: displayConfig.displayMode,
          renderStyle: displayConfig.renderStyle,
          labelMode: displayConfig.labelMode,
          fusionConfig: { ...displayConfig.fusionConfig },
          refreshInterval: displayConfig.refreshInterval,
          maxAreas: displayConfig.maxAreas,
          screenName: displayConfig.screenName?.trim() || DEFAULT_DASHBOARD_SCREEN_NAME,
          areas: currentAreas.value,
          parkStats: displayConfig.parkStats.enabled ? {
            title: displayConfig.parkStats.title,
            schemeIds: [...displayConfig.parkStats.schemeIds],
          } : null,
          lastUpdated: new Date().toISOString()
        }
      }))

      showDisplayConfig.value = false
      ElMessage.success('展板配置保存成功')
      await nextTick()
      heatMapManagerRef.value?.refreshView?.()
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

const getMapName = (mapId) => {
  const map = availableMaps.value.find(m => m.id === mapId)
  return map ? map.name : '未知地图'
}

const getBoundAreasCount = () => {
  return currentAreas.value.filter(area => (area.sourceId || area.jobId) && (area.sourceId || area.jobId) !== '').length
}
</script>

<style scoped>
.screen-name-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.park-stats-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.park-stats-config .panel-desc {
  margin-bottom: 12px;
}

.park-stats-form {
  max-width: 720px;
}

.screen-name-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.screen-name-form {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 320px;
  max-width: 560px;
}

.screen-name-form .el-input {
  flex: 1;
}

.dashboard-map-config {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 140px);
}

.map-card {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.map-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0;
}

.integration-card :deep(.el-card__body) {
  padding-top: 0;
  padding-bottom: 8px;
}

.integration-collapse-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.4;
}

.integration-collapse-title .panel-desc {
  margin-top: 0;
  font-weight: normal;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.panel-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}

.status-info {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.management-content {
  flex: 1 1 0;
  min-height: 760px;
  height: calc(100vh - 200px);
}

.integration-card :deep(.dashboard-integration-config) {
  padding-top: 0;
}

.field-suffix {
  margin-left: 8px;
  color: #909399;
}

.form-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
