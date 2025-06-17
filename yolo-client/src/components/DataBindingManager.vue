<template>
  <div class="data-binding-manager">
    <div class="manager-header">
      <h2>大屏数据绑定管理</h2>
      <div class="header-controls">
        <button @click="refreshAllModules" class="btn-primary" :disabled="isRefreshing">
          <span v-if="isRefreshing">刷新中...</span>
          <span v-else>全部刷新</span>
        </button>
        <button @click="showGlobalConfig = !showGlobalConfig" class="btn-secondary">
          全局配置
        </button>
      </div>
    </div>

    <!-- 全局配置面板 -->
    <div v-if="showGlobalConfig" class="global-config-panel">
      <h3>全局配置</h3>
      <div class="config-grid">
        <div class="config-item">
          <label>自动刷新</label>
          <input 
            type="checkbox" 
            v-model="globalConfig.autoRefresh"
            @change="updateGlobalConfig"
          />
        </div>
        <div class="config-item">
          <label>刷新间隔(秒)</label>
          <input 
            type="number" 
            v-model="globalConfig.refreshInterval"
            @change="updateGlobalConfig"
            min="5"
            max="300"
          />
        </div>
        <div class="config-item">
          <label>启用缓存</label>
          <input 
            type="checkbox" 
            v-model="globalConfig.enableCache"
            @change="updateGlobalConfig"
          />
        </div>
        <div class="config-item">
          <label>启用降级</label>
          <input 
            type="checkbox" 
            v-model="globalConfig.enableFallback"
            @change="updateGlobalConfig"
          />
        </div>
      </div>
    </div>

    <!-- 模块状态总览 -->
    <div class="modules-overview">
      <h3>模块状态总览</h3>
      <div class="status-cards">
        <div 
          v-for="(status, moduleId) in modulesStatus" 
          :key="moduleId"
          class="status-card"
          :class="getStatusClass(status)"
        >
          <div class="card-header">
            <h4>{{ getModuleName(moduleId) }}</h4>
            <div class="status-indicator" :class="status.error ? 'error' : status.loading ? 'loading' : 'success'">
              <span v-if="status.loading">●</span>
              <span v-else-if="status.error">⚠</span>
              <span v-else>✓</span>
            </div>
          </div>
          <div class="card-content">
            <p class="status-text">
              <span v-if="status.loading">加载中...</span>
              <span v-else-if="status.error">{{ status.error.message || '加载失败' }}</span>
              <span v-else-if="status.hasData">数据已加载</span>
              <span v-else>无数据</span>
            </p>
            <p v-if="status.lastUpdate" class="last-update">
              最后更新: {{ formatTime(status.lastUpdate) }}
            </p>
          </div>
          <div class="card-actions">
            <button 
              @click="refreshSingleModule(moduleId)" 
              class="btn-refresh"
              :disabled="status.loading"
            >
              刷新
            </button>
            <button 
              @click="showModuleConfig(moduleId)" 
              class="btn-config"
            >
              配置
            </button>
            <button 
              @click="viewModuleData(moduleId)" 
              class="btn-view"
            >
              查看数据
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 模块配置对话框 -->
    <div v-if="selectedModule" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ getModuleName(selectedModule) }} - 数据源配置</h3>
          <button @click="closeModal" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="module-info">
            <p><strong>描述:</strong> {{ getModuleConfig(selectedModule)?.description }}</p>
            <p><strong>数据源数量:</strong> {{ getModuleConfig(selectedModule)?.dataSources?.length }}</p>
          </div>
          
          <div class="data-sources">
            <h4>数据源配置</h4>
            <div 
              v-for="(source, index) in getModuleConfig(selectedModule)?.dataSources" 
              :key="index"
              class="data-source-item"
            >
              <div class="source-header">
                <h5>{{ source.name }}</h5>
                <span class="source-type">{{ source.type }}</span>
              </div>
              <div class="source-details">
                <div v-if="source.type === 'api'" class="api-config">
                  <div class="config-row">
                    <label>接口地址:</label>
                    <input 
                      v-model="source.endpoint" 
                      type="text"
                      @change="updateSourceConfig(selectedModule, index, source)"
                    />
                  </div>
                  <div class="config-row">
                    <label>请求参数:</label>
                    <textarea 
                      :value="JSON.stringify(source.params, null, 2)"
                      @change="updateSourceParams(selectedModule, index, $event)"
                      rows="3"
                    ></textarea>
                  </div>
                  <div class="config-row">
                    <label>数据路径:</label>
                    <input 
                      v-model="source.dataPath" 
                      type="text"
                      @change="updateSourceConfig(selectedModule, index, source)"
                    />
                  </div>
                </div>
                <div v-else-if="source.type === 'static'" class="static-config">
                  <div class="config-row">
                    <label>静态数据:</label>
                    <textarea 
                      :value="JSON.stringify(source.data, null, 2)"
                      @change="updateSourceData(selectedModule, index, $event)"
                      rows="5"
                    ></textarea>
                  </div>
                </div>
              </div>
              <div class="source-actions">
                <button @click="testDataSource(selectedModule, index)" class="btn-test">
                  测试数据源
                </button>
              </div>
            </div>
          </div>

          <div class="transform-config">
            <h4>数据转换配置</h4>
            <div class="config-row">
              <label>自定义转换函数:</label>
              <textarea 
                :value="getTransformFunction(selectedModule)"
                @change="updateTransformFunction(selectedModule, $event)"
                rows="8"
                placeholder="输入数据转换函数..."
              ></textarea>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="saveModuleConfig" class="btn-primary">保存配置</button>
          <button @click="resetModuleConfig" class="btn-secondary">重置</button>
          <button @click="closeModal" class="btn-default">取消</button>
        </div>
      </div>
    </div>

    <!-- 数据查看对话框 -->
    <div v-if="viewingData" class="modal-overlay" @click="closeDataView">
      <div class="modal-content data-view-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ getModuleName(viewingData.moduleId) }} - 数据预览</h3>
          <button @click="closeDataView" class="btn-close">&times;</button>
        </div>
        <div class="modal-body">
          <div class="data-view">
            <pre>{{ JSON.stringify(viewingData.data, null, 2) }}</pre>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeDataView" class="btn-default">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { dataBindingManager, DASHBOARD_MODULES } from '@/utils/dataBinding.js'
import dashboardModulesConfig from '@/config/dashboardModules.js'

// 响应式数据
const isRefreshing = ref(false)
const showGlobalConfig = ref(false)
const selectedModule = ref(null)
const viewingData = ref(null)
const originalConfigs = ref({})

// 全局配置
const globalConfig = reactive({
  autoRefresh: true,
  refreshInterval: 30, // 以秒为单位显示
  enableCache: true,
  enableFallback: true
})

// 计算属性
const modulesStatus = computed(() => dataBindingManager.getModulesStatus())

// 方法
const getModuleName = (moduleId) => {
  return dashboardModulesConfig[moduleId]?.name || moduleId
}

const getModuleConfig = (moduleId) => {
  return dashboardModulesConfig[moduleId]
}

const getStatusClass = (status) => {
  if (status.loading) return 'status-loading'
  if (status.error) return 'status-error'
  if (status.hasData) return 'status-success'
  return 'status-empty'
}

const formatTime = (timeString) => {
  return new Date(timeString).toLocaleString()
}

const refreshAllModules = async () => {
  isRefreshing.value = true
  try {
    await dataBindingManager.loadAllModules()
    // console.log('所有模块刷新成功')
  } catch (error) {
    // console.error('模块刷新失败:', error)
  } finally {
    isRefreshing.value = false
  }
}

const refreshSingleModule = async (moduleId) => {
  try {
    await dataBindingManager.loadModule(moduleId)
    // console.log(`模块 ${moduleId} 刷新成功`)
  } catch (error) {
    // console.error(`模块 ${moduleId} 刷新失败:`, error)
  }
}

const updateGlobalConfig = () => {
  dataBindingManager.updateGlobalConfig({
    autoRefresh: globalConfig.autoRefresh,
    refreshInterval: globalConfig.refreshInterval * 1000, // 转换为毫秒
    enableCache: globalConfig.enableCache,
    enableFallback: globalConfig.enableFallback
  })
}

const showModuleConfig = (moduleId) => {
  selectedModule.value = moduleId
  // 保存原始配置用于重置
  originalConfigs.value[moduleId] = JSON.parse(JSON.stringify(dashboardModulesConfig[moduleId]))
}

const closeModal = () => {
  selectedModule.value = null
}

const viewModuleData = (moduleId) => {
  const data = dataBindingManager.getModuleData(moduleId)
  viewingData.value = {
    moduleId,
    data
  }
}

const closeDataView = () => {
  viewingData.value = null
}

const updateSourceConfig = (moduleId, sourceIndex, newSource) => {
  const config = dashboardModulesConfig[moduleId]
  if (config && config.dataSources[sourceIndex]) {
    Object.assign(config.dataSources[sourceIndex], newSource)
  }
}

const updateSourceParams = (moduleId, sourceIndex, event) => {
  try {
    const params = JSON.parse(event.target.value)
    const config = dashboardModulesConfig[moduleId]
    if (config && config.dataSources[sourceIndex]) {
      config.dataSources[sourceIndex].params = params
    }
  } catch (error) {
    // console.error('参数格式错误:', error)
  }
}

const updateSourceData = (moduleId, sourceIndex, event) => {
  try {
    const data = JSON.parse(event.target.value)
    const config = dashboardModulesConfig[moduleId]
    if (config && config.dataSources[sourceIndex]) {
      config.dataSources[sourceIndex].data = data
    }
  } catch (error) {
    // console.error('数据格式错误:', error)
  }
}

const getTransformFunction = (moduleId) => {
  const config = dashboardModulesConfig[moduleId]
  if (config?.transform?.custom) {
    return config.transform.custom.toString()
  }
  return ''
}

const updateTransformFunction = (moduleId, event) => {
  try {
    // 这里需要小心处理函数字符串，实际项目中可能需要更安全的方式
    const funcString = event.target.value
    const config = dashboardModulesConfig[moduleId]
    if (config) {
      if (!config.transform) config.transform = {}
      // 注意：实际应用中应该使用更安全的方式来处理函数
      config.transform.custom = new Function('data', `return (${funcString})(data)`)
    }
  } catch (error) {
    // console.error('函数格式错误:', error)
  }
}

const testDataSource = async (moduleId, sourceIndex) => {
  try {
    const module = dataBindingManager.getModule(moduleId)
    if (module && module.adapters[sourceIndex]) {
      const result = await module.adapters[sourceIndex].fetchData()
      // console.log(`数据源测试结果:`, result)
      alert('数据源测试成功，查看控制台获取详细信息')
    }
  } catch (error) {
    // console.error('数据源测试失败:', error)
    alert('数据源测试失败: ' + error.message)
  }
}

const saveModuleConfig = () => {
  if (selectedModule.value) {
    const module = dataBindingManager.getModule(selectedModule.value)
    if (module) {
      module.updateConfig(dashboardModulesConfig[selectedModule.value])
      // console.log(`模块 ${selectedModule.value} 配置已保存`)
      closeModal()
    }
  }
}

const resetModuleConfig = () => {
  if (selectedModule.value && originalConfigs.value[selectedModule.value]) {
    Object.assign(dashboardModulesConfig[selectedModule.value], originalConfigs.value[selectedModule.value])
    // console.log(`模块 ${selectedModule.value} 配置已重置`)
  }
}

// 初始化
onMounted(() => {
  // 同步全局配置
  const currentGlobalConfig = dataBindingManager.globalConfig
  globalConfig.autoRefresh = currentGlobalConfig.autoRefresh
  globalConfig.refreshInterval = currentGlobalConfig.refreshInterval / 1000
  globalConfig.enableCache = currentGlobalConfig.enableCache
  globalConfig.enableFallback = currentGlobalConfig.enableFallback
})
</script>

<style scoped>
.data-binding-manager {
  padding: 20px;
  background: #f5f5f5;
  min-height: 100vh;
}

.manager-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-controls {
  display: flex;
  gap: 10px;
}

.btn-primary, .btn-secondary, .btn-default, .btn-refresh, .btn-config, .btn-view, .btn-test {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s ease;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

.btn-default {
  background: #e9ecef;
  color: #495057;
}

.btn-default:hover {
  background: #dee2e6;
}

.global-config-panel {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 15px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.config-item label {
  font-weight: 500;
  color: #495057;
}

.config-item input {
  padding: 8px;
  border: 1px solid #ced4da;
  border-radius: 4px;
}

.modules-overview {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 15px;
}

.status-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 15px;
  background: white;
  transition: all 0.3s ease;
}

.status-card:hover {
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.status-card.status-loading {
  border-left: 4px solid #ffc107;
}

.status-card.status-error {
  border-left: 4px solid #dc3545;
}

.status-card.status-success {
  border-left: 4px solid #28a745;
}

.status-card.status-empty {
  border-left: 4px solid #6c757d;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.card-header h4 {
  margin: 0;
  color: #495057;
}

.status-indicator {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
}

.status-indicator.success {
  background: #28a745;
  color: white;
}

.status-indicator.error {
  background: #dc3545;
  color: white;
}

.status-indicator.loading {
  background: #ffc107;
  color: white;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.card-content {
  margin-bottom: 15px;
}

.status-text {
  margin: 5px 0;
  color: #495057;
}

.last-update {
  margin: 5px 0;
  color: #6c757d;
  font-size: 12px;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.btn-refresh {
  background: #17a2b8;
  color: white;
}

.btn-config {
  background: #6f42c1;
  color: white;
}

.btn-view {
  background: #20c997;
  color: white;
}

.btn-test {
  background: #fd7e14;
  color: white;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
  width: 90%;
}

.data-view-modal {
  max-width: 1000px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
}

.modal-header h3 {
  margin: 0;
  color: #495057;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #6c757d;
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #dee2e6;
}

.module-info {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.data-sources {
  margin-bottom: 20px;
}

.data-source-item {
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 15px;
}

.source-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.source-header h5 {
  margin: 0;
  color: #495057;
}

.source-type {
  background: #e9ecef;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #495057;
}

.source-details {
  margin-bottom: 15px;
}

.config-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 15px;
}

.config-row label {
  font-weight: 500;
  color: #495057;
  margin-bottom: 5px;
}

.config-row input,
.config-row textarea {
  padding: 8px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-family: monospace;
}

.config-row textarea {
  resize: vertical;
  min-height: 80px;
}

.source-actions {
  display: flex;
  justify-content: flex-end;
}

.data-view {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  padding: 15px;
  max-height: 500px;
  overflow: auto;
}

.data-view pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: #495057;
}
</style> 