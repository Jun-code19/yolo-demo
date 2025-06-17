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
            {{ currentAreas.length }} 个区域
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
      />
    </div>

    <!-- 配置展板显示对话框 -->
    <el-dialog v-model="showDisplayConfig" title="配置展板显示" width="500px">
      <el-form :model="displayConfig" :rules="displayRules" ref="displayFormRef" label-width="100px">
        <el-form-item label="显示地图" prop="mapId">
          <el-select v-model="displayConfig.mapId" placeholder="选择要在展板显示的地图">
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
            <el-radio value="preview">预览模式（色块）</el-radio>
            <el-radio value="mini">迷你地图</el-radio>
            <el-radio value="full">完整地图</el-radio>
          </el-radio-group>
        </el-form-item>
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
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDisplayConfig = false">取消</el-button>
          <el-button type="primary" @click="confirmDisplayConfig" :loading="saving">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Select, Refresh } from '@element-plus/icons-vue'
import HeatMapManager from '@/components/HeatMapManager.vue'
import { dashboardMapApi } from '@/api/dashboard'

const router = useRouter()
const heatMapManagerRef = ref(null)
const displayFormRef = ref(null)

const saving = ref(false)
const showDisplayConfig = ref(false)
const availableMaps = ref([])
const currentMapId = ref(null)
const currentAreas = ref([])

// 展板显示配置
const displayConfig = reactive({
  mapId: '',
  displayMode: 'preview',
  refreshInterval: 30,
  maxAreas: 6
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
  await loadCurrentDisplayConfig()
})

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
      displayConfig.displayMode = config.display_mode || 'preview'
      displayConfig.refreshInterval = config.refresh_interval || 30
      displayConfig.maxAreas = config.max_areas || 6
    }
  } catch (error) {
    console.error('加载展板配置失败:', error)
    // 如果加载失败，保持默认配置
  }
}

// 处理地图选择
const handleMapSelected = (mapId) => {
  currentMapId.value = mapId
  if (!displayConfig.mapId || displayConfig.mapId === '') {
    displayConfig.mapId = mapId
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
  const hasBinding = currentAreas.value.some(area => area.jobId && area.jobId !== '')
  if (!hasBinding) {
    ElMessage.warning('请至少为一个区域绑定数据源')
    return
  }
  
  displayConfig.mapId = currentMapId.value
  showDisplayConfig.value = true
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
      display_mode: displayConfig.displayMode,
      refresh_interval: displayConfig.refreshInterval,
      max_areas: displayConfig.maxAreas,
      config: {
        lastUpdated: new Date().toISOString(),
        areas: currentAreas.value
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
  return currentAreas.value.filter(area => area.jobId && area.jobId !== '').length
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