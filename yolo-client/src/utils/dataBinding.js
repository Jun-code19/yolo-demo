import { reactive, ref } from 'vue'
import { apiClient_v1, apiClient_v2 } from '@/api/dashboard.js'

// 数据源类型枚举
export const DATA_SOURCE_TYPES = {
  API: 'api',
  WEBSOCKET: 'websocket', 
  STATIC: 'static',
  COMPUTED: 'computed'
}

// 大屏模块枚举
export const DASHBOARD_MODULES = {
  FACTORY_OVERVIEW: 'factoryOverview',
  ALERT_DATA: 'alertData',
  STAFF_DISTRIBUTION: 'staffDistribution',
  MONITORING_POINTS: 'monitoringPoints',
  ALERT_HISTORY: 'alertHistory',
  BEHAVIOR_STATS: 'behaviorStats',
  LIVE_MONITORS: 'liveMonitors',
  PROJECT_QUEUE: 'projectQueue',
  HISTORICAL_STATS: 'historicalStats'
}

// 数据转换器
export class DataTransformer {
  // 数据映射
  static mapData(data, mapping) {
    if (!mapping) return data
    
    const result = {}
    for (const [targetKey, sourceKey] of Object.entries(mapping)) {
      result[targetKey] = this.getNestedValue(data, sourceKey)
    }
    return result
  }

  // 获取嵌套属性值
  static getNestedValue(obj, path) {
    return path.split('.').reduce((current, key) => current?.[key], obj)
  }

  // 数据聚合
  static aggregateData(dataArray, aggregateRules) {
    if (!aggregateRules) return dataArray
    
    const result = {}
    for (const [key, rule] of Object.entries(aggregateRules)) {
      switch (rule.type) {
        case 'count':
          result[key] = dataArray.length
          break
        case 'sum':
          result[key] = dataArray.reduce((sum, item) => sum + (this.getNestedValue(item, rule.field) || 0), 0)
          break
        case 'group':
          result[key] = this.groupBy(dataArray, rule.field)
          break
        case 'filter':
          result[key] = dataArray.filter(item => this.evaluateCondition(item, rule.condition))
          break
        default:
          result[key] = dataArray
      }
    }
    return result
  }

  // 数据分组
  static groupBy(array, field) {
    return array.reduce((groups, item) => {
      const key = this.getNestedValue(item, field) || 'unknown'
      if (!groups[key]) groups[key] = []
      groups[key].push(item)
      return groups
    }, {})
  }

  // 条件评估
  static evaluateCondition(item, condition) {
    const value = this.getNestedValue(item, condition.field)
    switch (condition.operator) {
      case 'equals': return value === condition.value
      case 'contains': return String(value).includes(condition.value)
      case 'greater': return value > condition.value
      case 'less': return value < condition.value
      default: return true
    }
  }

  // 数据格式化
  static formatData(data, formatRules) {
    if (!formatRules) return data
    
    const result = { ...data }
    for (const [key, rule] of Object.entries(formatRules)) {
      if (result[key] !== undefined) {
        switch (rule.type) {
          case 'percentage':
            result[key] = Math.round((result[key] / rule.total) * 100)
            break
          case 'currency':
            result[key] = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(result[key])
            break
          case 'date':
            result[key] = new Date(result[key]).toLocaleString()
            break
          case 'number':
            result[key] = Number(result[key]).toLocaleString()
            break
        }
      }
    }
    return result
  }
}

// 数据源适配器
export class DataSourceAdapter {
  constructor(config) {
    this.config = config
    this.cache = new Map()
    this.cacheTimeout = config.cacheTimeout || 30000 // 30秒缓存
  }

  async fetchData() {
    const cacheKey = JSON.stringify(this.config)
    const cached = this.cache.get(cacheKey)
    
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data
    }

    let data
    switch (this.config.type) {
      case DATA_SOURCE_TYPES.API:
        data = await this.fetchApiData()
        break
      case DATA_SOURCE_TYPES.STATIC:
        data = this.config.data
        break
      case DATA_SOURCE_TYPES.COMPUTED:
        data = await this.computeData()
        break
      default:
        throw new Error(`不支持的数据源类型: ${this.config.type}`)
    }

    // 缓存数据
    this.cache.set(cacheKey, {
      data,
      timestamp: Date.now()
    })

    return data
  }

  async fetchApiData() {
    const { endpoint, params, method = 'GET', apiVersion = 'v1' } = this.config
    
    try {
      let response
      const client = apiVersion === 'v2' ? apiClient_v2 : apiClient_v1
      
      switch (method.toUpperCase()) {
        case 'GET':
          response = await client.get(endpoint, { params })
          break
        case 'POST':
          response = await client.post(endpoint, params)
          break
        default:
          throw new Error(`不支持的HTTP方法: ${method}`)
      }
      
      return this.extractResponseData(response)
    } catch (error) {
      // console.error(`API数据获取失败 (${endpoint}):`, error)
      return this.config.fallbackData || null
    }
  }

  extractResponseData(response) {
    const { dataPath = 'data' } = this.config
    return DataTransformer.getNestedValue(response, dataPath)
  }

  async computeData() {
    const { computation } = this.config
    if (typeof computation === 'function') {
      return await computation()
    }
    throw new Error('计算数据源需要提供computation函数')
  }

  clearCache() {
    this.cache.clear()
  }
}

// 模块数据绑定配置
export class ModuleBinding {
  constructor(moduleId, config) {
    this.moduleId = moduleId
    this.config = reactive(config)
    this.data = ref(null)
    this.loading = ref(false)
    this.error = ref(null)
    this.adapters = []
    this.setupAdapters()
  }

  setupAdapters() {
    this.adapters = this.config.dataSources.map(sourceConfig => 
      new DataSourceAdapter(sourceConfig)
    )
  }

  async loadData() {
    this.loading.value = true
    this.error.value = null

    try {
      // 并发获取所有数据源
      const dataResults = await Promise.allSettled(
        this.adapters.map(adapter => adapter.fetchData())
      )

      // 处理数据结果
      const successfulData = dataResults
        .filter(result => result.status === 'fulfilled')
        .map(result => result.value)

      // 合并数据
      let mergedData

      // 应用数据转换
      if (this.config.transform) {
        mergedData = this.applyTransformations(successfulData)
      }

      this.data.value = mergedData
      return mergedData
    } catch (error) {
      this.error.value = error
      // console.error(`模块 ${this.moduleId} 数据加载失败:`, error)
      return this.config.fallbackData || null
    } finally {
      this.loading.value = false
    }
  }

  mergeData(dataArray) {
    if (dataArray.length === 0) return null
    if (dataArray.length === 1) return dataArray[0]

    // 根据合并策略合并数据
    const strategy = this.config.mergeStrategy || 'assign'
    switch (strategy) {
      case 'assign':
        return Object.assign({}, ...dataArray)
      case 'concat':
        return dataArray.flat()
      case 'custom':
        return this.config.customMerge(dataArray)
      default:
        return dataArray[0]
    }
  }

  applyTransformations(data) {
    let result = data

    // 应用映射
    if (this.config.transform.mapping) {
      result = DataTransformer.mapData(result, this.config.transform.mapping)
    }

    // 应用聚合
    if (this.config.transform.aggregate) {
      result = DataTransformer.aggregateData(
        Array.isArray(result) ? result : [result],
        this.config.transform.aggregate
      )
    }

    // 应用格式化
    if (this.config.transform.format) {
      result = DataTransformer.formatData(result, this.config.transform.format)
    }

    // 应用自定义转换
    if (this.config.transform.custom) {
      result = this.config.transform.custom(result)
    }

    return result
  }

  updateConfig(newConfig) {
    Object.assign(this.config, newConfig)
    this.setupAdapters()
  }

  clearCache() {
    this.adapters.forEach(adapter => adapter.clearCache())
  }
}

// 数据绑定管理器
export class DataBindingManager {
  constructor() {
    this.modules = new Map()
    this.globalConfig = reactive({
      autoRefresh: true,
      refreshInterval: 30000,
      enableCache: true,
      enableFallback: true
    })
    this.refreshTimer = null
  }

  // 注册模块
  registerModule(moduleId, config) {
    const binding = new ModuleBinding(moduleId, config)
    this.modules.set(moduleId, binding)
    return binding
  }

  // 获取模块
  getModule(moduleId) {
    return this.modules.get(moduleId)
  }

  // 获取模块数据
  getModuleData(moduleId) {
    const module = this.modules.get(moduleId)
    return module?.data.value
  }

  // 加载所有模块数据
  async loadAllModules() {
    const loadPromises = Array.from(this.modules.values()).map(module => 
      module.loadData().catch(error => {
        // console.error(`模块 ${module.moduleId} 加载失败:`, error)
        return null
      })
    )

    return await Promise.allSettled(loadPromises)
  }

  // 加载指定模块
  async loadModule(moduleId) {
    const module = this.modules.get(moduleId)
    if (!module) {
      throw new Error(`模块 ${moduleId} 不存在`)
    }
    return await module.loadData()
  }

  // 启动自动刷新
  startAutoRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }

    if (this.globalConfig.autoRefresh) {
      this.refreshTimer = setInterval(() => {
        this.loadAllModules()
      }, this.globalConfig.refreshInterval)
    }
  }

  // 停止自动刷新
  stopAutoRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
      this.refreshTimer = null
    }
  }

  // 更新全局配置
  updateGlobalConfig(config) {
    Object.assign(this.globalConfig, config)
    if (config.autoRefresh !== undefined || config.refreshInterval !== undefined) {
      this.startAutoRefresh()
    }
  }

  // 清除所有缓存
  clearAllCache() {
    this.modules.forEach(module => module.clearCache())
  }

  // 获取所有模块状态
  getModulesStatus() {
    const status = {}
    this.modules.forEach((module, moduleId) => {
      status[moduleId] = {
        loading: module.loading.value,
        error: module.error.value,
        hasData: module.data.value !== null,
        lastUpdate: module.data.value ? new Date().toISOString() : null
      }
    })
    return status
  }

  // 销毁管理器
  destroy() {
    this.stopAutoRefresh()
    this.modules.clear()
  }
}

// 创建全局数据绑定管理器实例
export const dataBindingManager = new DataBindingManager()

// 导出常用函数
// export {
//   DataTransformer,
//   DataSourceAdapter,
//   ModuleBinding
// } 