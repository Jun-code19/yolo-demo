<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑监听器配置' : '新建监听器配置'"
    width="1000px"
    :close-on-click-modal="false"
    @close="handleClose"
    class="listener-config-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="140px"
      v-loading="loading"
    >
      <!-- 基本信息 -->
      <el-divider content-position="left">基本信息</el-divider>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="配置名称" prop="name">
            <el-input
              v-model="form.name"
              placeholder="请输入监听器配置名称"
              maxlength="100"
              show-word-limit
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="监听器类型" prop="listener_type">
            <el-select
              v-model="form.listener_type"
              placeholder="请选择监听器类型"
              style="width: 100%"
              @change="handleTypeChange"
              :disabled="isEdit"
            >
              <el-option value="tcp" label="TCP Socket">
                <span>TCP Socket - TCP服务器/客户端连接</span>
              </el-option>
              <el-option value="mqtt" label="MQTT">
                <span>MQTT - MQTT消息订阅</span>
              </el-option>
              <el-option value="http" label="HTTP">
                <span>HTTP - Webhook接收或轮询</span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="请输入描述信息"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>

      <!-- 连接配置 -->
      <el-divider content-position="left">连接配置</el-divider>
      
      <!-- TCP配置 -->
      <template v-if="form.listener_type === 'tcp'">
        <el-form-item label="运行模式" prop="connection_config.mode">
          <el-radio-group v-model="form.connection_config.mode">
            <el-radio value="server">服务器模式（监听端口）</el-radio>
            <el-radio value="client">客户端模式（连接远程）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item
              :label="form.connection_config.mode === 'server' ? '监听地址' : '远程地址'"
              prop="connection_config.host"
            >
              <el-input
                v-model="form.connection_config.host"
                placeholder="IP地址"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item
              :label="form.connection_config.mode === 'server' ? '监听端口' : '远程端口'"
              prop="connection_config.port"
            >
              <el-input-number
                v-model="form.connection_config.port"
                :min="1"
                :max="65535"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="数据格式" prop="connection_config.data_format">
              <el-select v-model="form.connection_config.data_format" style="width: 100%">
                <el-option value="json" label="JSON格式" />
                <el-option value="line" label="行分隔" />
                <el-option value="binary" label="二进制" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="编码格式" prop="connection_config.encoding">
              <el-select v-model="form.connection_config.encoding" style="width: 100%">
                <el-option value="utf-8" label="UTF-8" />
                <el-option value="gbk" label="GBK" />
                <el-option value="ascii" label="ASCII" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- MQTT配置 -->
      <template v-if="form.listener_type === 'mqtt'">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="MQTT代理" prop="connection_config.host">
              <el-input
                v-model="form.connection_config.host"
                placeholder="MQTT代理地址"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="端口" prop="connection_config.port">
              <el-input-number
                v-model="form.connection_config.port"
                :min="1"
                :max="65535"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户名">
              <el-input
                v-model="form.connection_config.username"
                placeholder="MQTT用户名（可选）"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码">
              <el-input
                v-model="form.connection_config.password"
                type="password"
                placeholder="MQTT密码（可选）"
                show-password
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="订阅主题" prop="connection_config.topics">
          <el-select
            v-model="form.connection_config.topics"
            multiple
            filterable
            allow-create
            placeholder="输入MQTT主题，支持通配符"
            style="width: 100%"
            popper-class="listener-dialog-select"
          >
            <el-option value="#" label="# (所有主题)" />
            <el-option value="+/alarm" label="+/alarm (设备报警)" />
            <el-option value="+/detection" label="+/detection (检测事件)" />
            <el-option value="+/status" label="+/status (状态信息)" />
          </el-select>
        </el-form-item>
      </template>

      <!-- HTTP配置 -->
      <template v-if="form.listener_type === 'http'">
        <el-form-item label="运行模式" prop="connection_config.mode">
          <el-radio-group v-model="form.connection_config.mode">
            <el-radio value="webhook">Webhook接收</el-radio>
            <el-radio value="polling">轮询获取</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- Webhook模式 -->
        <template v-if="form.connection_config.mode === 'webhook'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="监听地址" prop="connection_config.host">
                <el-input
                  v-model="form.connection_config.host"
                  placeholder="监听地址"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="监听端口" prop="connection_config.port">
                <el-input-number
                  v-model="form.connection_config.port"
                  :min="1"
                  :max="65535"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="Webhook路径" prop="connection_config.path">
            <el-input
              v-model="form.connection_config.path"
              placeholder="/webhook"
            />
          </el-form-item>
        </template>

        <!-- 轮询模式 -->
        <template v-if="form.connection_config.mode === 'polling'">
          <el-form-item label="轮询URL" prop="connection_config.poll_url">
            <el-input
              v-model="form.connection_config.poll_url"
              placeholder="https://api.example.com/events"
            />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="HTTP方法">
                <el-select v-model="form.connection_config.poll_method" style="width: 100%">
                  <el-option value="GET" />
                  <el-option value="POST" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="轮询间隔">
                <el-input-number
                  v-model="form.connection_config.poll_interval"
                  :min="5"
                  :max="3600"
                  style="width: 100%"
                />
                <span style="color: #999; font-size: 12px;">秒</span>
              </el-form-item>
            </el-col>
          </el-row>
        </template>
      </template>

      <!-- 数据字段映射配置 -->
      <el-divider content-position="left">数据字段映射</el-divider>
      
      <!-- 通用基础字段映射 -->
      <el-card class="field-config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>通用基础字段</span>
            <el-tooltip content="用于事件存储、页面显示和数据统计的基础字段" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="设备SN码字段">
              <el-input
                v-model="form.data_mapping.sn_field"
                placeholder="如：sn"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="视频通道字段">
              <el-input
                v-model="form.data_mapping.channel_field"
                placeholder="如：chid"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="算法引擎字段">
              <el-input
                v-model="form.data_mapping.engine_field"
                placeholder="如：geid"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="位置字段">
              <el-input
                v-model="form.data_mapping.location_field"
                placeholder="如：location"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="时间戳字段">
              <el-input
                v-model="form.data_mapping.timestamp_field"
                placeholder="如：timestamp"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="描述字段">
              <el-input
                v-model="form.data_mapping.description_field"
                placeholder="如：desc"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <!-- 算法特定字段配置 -->
      <el-card class="field-config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>算法特定字段配置</span>
            <el-tooltip content="根据选择的边缘设备和算法引擎配置特定字段" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>

        <!-- 边缘设备选择 -->
        <el-form-item label="关联边缘设备">
          <el-select
            v-model="form.edge_device_mappings"
            multiple
            filterable
            placeholder="选择边缘设备（可多选）"
            style="width: 100%"
            popper-class="listener-dialog-select"
            @change="onEdgeDeviceChange"
          >
            <el-option
              v-for="device in availableEdgeDevices"
              :key="device.id"
              :label="`${device.name} (${device.ip_address})`"
              :value="device.id"
            >
              <div class="device-option">
                <span>{{ device.name }}</span>
                <el-tag size="small" :type="device.status === 'online' ? 'success' : 'danger'">
                  {{ device.status === 'online' ? '在线' : '离线' }}
                </el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <!-- 算法引擎配置 -->
        <div v-if="selectedDeviceEngines != null" class="algorithm-configs">
          <div
            v-for="(engineGroup, deviceId) in selectedDeviceEngines"
            :key="deviceId"
            class="device-engine-group"
          >
            <h4>{{ getDeviceName(deviceId) }} - 算法引擎</h4>
            <el-checkbox-group v-model="form.algorithm_field_mappings[deviceId]">
              <div class="engine-list">
                <div
                  v-for="engine in engineGroup"
                  :key="engine.engineId"
                  class="engine-item"
                >
                  <el-checkbox :value="engine.engineId">
                    <div class="engine-info">
                      <span class="engine-name">{{ engine.engineName }}</span>
                      <el-tag size="small" type="info">{{ engine.engineTypes.join(', ') }}</el-tag>
                    </div>
                  </el-checkbox>
                  
                  <!-- 当算法被选中时显示字段配置 -->
                  <div
                    v-if="form.algorithm_field_mappings[deviceId]?.includes(engine.engineId)"
                    class="engine-fields"
                  >
                    <div class="field-mappings-header">
                      <span>算法字段映射配置</span>
                      <el-button 
                        type="primary" 
                        size="small" 
                        @click="addAlgorithmField(deviceId, engine.engineId)"
                      >
                        添加字段
                      </el-button>
                    </div>
                    
                    <div class="algorithm-field-list">
                      <div
                        v-for="(fieldMapping, fieldIndex) in getAlgorithmFields(deviceId, engine.engineId)"
                        :key="fieldIndex"
                        class="algorithm-field-item"
                      >
                        <el-input
                          v-model="fieldMapping.source_field"
                          placeholder="源字段名"
                          style="width: 150px"
                        />
                        <span class="mapping-arrow">→</span>
                        <el-input
                          v-model="fieldMapping.target_field"
                          placeholder="目标字段名"
                          style="width: 150px"
                        />
                        <el-select v-model="fieldMapping.field_type" style="width: 100px">
                          <el-option value="string" label="文本" />
                          <el-option value="number" label="数字" />
                          <el-option value="boolean" label="布尔" />
                          <el-option value="array" label="数组" />
                          <el-option value="object" label="对象" />
                        </el-select>
                        <el-input
                          v-model="fieldMapping.description"
                          placeholder="字段说明"
                          style="width: 120px"
                        />
                        <el-button
                          type="danger"
                          size="small"
                          @click="removeAlgorithmField(deviceId, engine.engineId, fieldIndex)"
                        >
                          删除
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </el-checkbox-group>
          </div>
        </div>
      </el-card>

      <!-- 自定义字段映射 -->
      <el-card class="field-config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>自定义字段映射</span>
            <el-tooltip content="接收其他字段作为通用字段" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        
        <div class="mapping-container">
          <div
            v-for="(mapping, index) in customFieldMappings"
            :key="index"
            class="mapping-item"
          >
            <el-input
              v-model="mapping.source_field"
              placeholder="源字段名"
              style="width: 150px"
            />
            <span class="mapping-arrow">→</span>
            <el-input
              v-model="mapping.target_field"
              placeholder="目标字段名"
              style="width: 150px"
            />
            <el-select v-model="mapping.field_type" style="width: 120px" placeholder="类型">
              <el-option value="string" label="文本" />
              <el-option value="number" label="数字" />
              <el-option value="boolean" label="布尔" />
              <el-option value="json" label="JSON" />
            </el-select>
            <el-button
              type="danger"
              size="small"
              @click="removeCustomFieldMapping(index)"
            >
              删除
            </el-button>
          </div>
          <el-button type="primary" size="small" @click="addCustomFieldMapping">
            添加自定义字段
          </el-button>
        </div>
      </el-card>

      <!-- 图片字段配置 -->
      <el-card class="field-config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>图片字段配置</span>
            <el-tooltip content="配置图片字段的存储和处理方式" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </template>
        
        <div class="mapping-container">
          <div
            v-for="(imageField, index) in imageFieldConfigs"
            :key="index"
            class="mapping-item image-field-item"
          >
            <el-input
              v-model="imageField.field_name"
              placeholder="图片字段名"
              style="width: 140px"
            />
            <el-select v-model="imageField.encoding" style="width: 120px">
              <el-option value="base64" label="Base64编码" />
              <el-option value="url" label="图片URL" />
              <el-option value="binary" label="二进制数据" />
            </el-select>
            <el-input
              v-model="imageField.save_path"
              placeholder="保存路径前缀，如：images/events"
              style="width: 200px"
            />
            <div class="image-options">
              <el-switch
                v-model="imageField.generate_thumbnail"
                active-text="缩略图"
              />
              <el-input-number
                v-if="imageField.generate_thumbnail"
                v-model="imageField.thumbnail_size"
                :min="50"
                :max="500"
                placeholder="尺寸"
                style="width: 120px; margin-left: 8px"
              />
            </div>
            <el-button
              type="danger"
              size="small"
              @click="removeImageFieldConfig(index)"
            >
              删除
            </el-button>
          </div>
          <el-button type="primary" size="small" @click="addImageFieldConfig">
            添加图片字段
          </el-button>
        </div>
      </el-card>

      <!-- 存储和推送配置 -->
      <el-divider content-position="left">存储和推送配置</el-divider>
      
      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="存储到数据库">
            <el-switch v-model="form.storage_enabled" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="启用数据推送">
            <el-switch v-model="form.push_enabled" @change="onPushEnabledChange" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="启用监听器">
            <el-switch v-model="form.enabled" />
            <div class="form-tip">启用后将自动启动监听</div>
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 数据推送配置 -->
      <el-card v-if="form.push_enabled" class="field-config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>数据推送配置</span>
          </div>
        </template>

        <el-form-item label="推送标签">
          <el-select
            v-model="form.push_config.tags"
            multiple
            filterable
            allow-create
            placeholder="设置推送数据的标签"
            style="width: 100%"
            popper-class="listener-dialog-select"
          >
            <el-option value="real-time" label="实时数据" >
              <div class="option-content">
                <span>实时数据</span>
                <el-tag size="small" effect="plain">real-time</el-tag>
              </div>
            </el-option>
            <el-option value="alarm" label="告警数据" >
              <div class="option-content">
                <span>告警数据</span>
                <el-tag size="small" effect="plain">alarm</el-tag>
              </div>
            </el-option>
            <el-option value="analysis" label="分析数据" >
              <div class="option-content">
                <span>分析数据</span>
                <el-tag size="small" effect="plain">analysis</el-tag>
              </div>
            </el-option>
            <el-option value="statistics" label="统计数据" >
              <div class="option-content">
                <span>统计数据</span>
                <el-tag size="small" effect="plain">statistics</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="推送模板">
          <el-input
            v-model="form.push_config.template"
            type="textarea"
            :rows="4"
            placeholder="推送数据模板，支持变量：{device_sn}, {location}, {timestamp}, {event_type} , {confidence}, {description}等"
          />
        </el-form-item>
      </el-card>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button @click="loadTemplate" v-if="!isEdit && templates[form.listener_type]">
          载入模板
        </el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import { dataListenerApi } from '../api/dataListener'
import edgeServerAPI from '../api/edge-server'

// Props & Emits
const props = defineProps({
  modelValue: Boolean,
  config: Object,
  templates: Object
})

const emit = defineEmits(['update:modelValue', 'saved'])

// 响应式数据
const formRef = ref()
const loading = ref(false)
const saving = ref(false)
const availableEdgeDevices = ref([])
const selectedDeviceEngines = ref({})

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const isEdit = computed(() => !!props.config)

// 表单数据
const defaultForm = () => ({
  name: '',
  description: '',
  listener_type: '',
  connection_config: {},
  data_mapping: {
    // 通用基础字段
    sn_field: 'sn',
    channel_field: 'chid',
    engine_field: 'geid',
    location_field: 'location',
    timestamp_field: 'timestamp',
    description_field: 'desc'
  },
  // 边缘设备映射
  edge_device_mappings: [],
  // 算法字段映射
  algorithm_field_mappings: {},
  algorithm_specific_fields: {},
  storage_enabled: true,
  push_enabled: false,
  push_config: {
    tags: [],
    template: ''
  },
  enabled: false
})

const form = reactive(defaultForm())

// 自定义字段映射数组
const customFieldMappings = ref([])

// 图片字段配置数组
const imageFieldConfigs = ref([])

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入配置名称', trigger: 'blur' },
    { min: 1, max: 100, message: '长度在 1 到 100 个字符', trigger: 'blur' }
  ],
  listener_type: [
    { required: true, message: '请选择监听器类型', trigger: 'change' }
  ],
  'connection_config.host': [
    { required: true, message: '请输入地址', trigger: 'blur' }
  ],
  'connection_config.port': [
    { required: true, message: '请输入端口', trigger: 'blur' },
    { type: 'number', min: 1, max: 65535, message: '端口范围 1-65535', trigger: 'blur' }
  ]
}

// 生命周期
onMounted(() => {
  loadAvailableEdgeDevices()
})

// 监听对话框打开
watch(visible, (newVal) => {
  if (newVal) {
    initForm()
  }
})

// 方法
const initForm = async () => {
  // 重置表单
  Object.assign(form, defaultForm())
  
  // 重置数组
  customFieldMappings.value = []
  imageFieldConfigs.value = []
  selectedDeviceEngines.value = {}
  
  if (isEdit.value && props.config) {
    try {
      loading.value = true
      
      // 编辑模式，通过API获取完整的配置数据
      const response = await dataListenerApi.getConfig(props.config.config_id)
      const configData = response.data.data
      
      // 填充表单数据
      Object.assign(form, {
        ...configData,
        connection_config: { ...configData.connection_config },
        data_mapping: { 
          sn_field: 'sn',
          channel_field: 'chid',
          engine_field: 'geid',
          location_field: 'location',
          timestamp_field: 'timestamp',
          description_field: 'desc',
          ...configData.data_mapping 
        },
        // 新增字段
        edge_device_mappings: configData.edge_device_mappings || [],
        algorithm_field_mappings: configData.algorithm_field_mappings || {},
        algorithm_specific_fields: configData.algorithm_specific_fields || {},
        push_config: { 
          tags: [],
          template: '',
          ...configData.push_config 
        }
      })
      
      // 填充自定义字段映射
      if (configData.data_mapping?.custom_fields) {
        customFieldMappings.value = Object.entries(configData.data_mapping.custom_fields)
          .map(([source_field, config]) => ({
            source_field,
            target_field: config.target_field || source_field,
            field_type: config.field_type || 'string'
          }))
      }
      
      // 填充图片字段配置
      if (configData.data_mapping?.image_fields) {
        imageFieldConfigs.value = Object.entries(configData.data_mapping.image_fields)
          .map(([field_name, config]) => ({
            field_name,
            encoding: config.encoding || 'base64',
            save_path: config.save_path || 'images/events',
            generate_thumbnail: config.generate_thumbnail !== false,
            thumbnail_size: config.thumbnail_size || 200
          }))
      }
      
      // 如果有边缘设备映射，重新加载对应的算法引擎信息
      if (form.edge_device_mappings.length > 0) {
        await loadEdgeDevicesAndEngines(form.edge_device_mappings)
      }
      
    } catch (error) {
      // console.error('加载配置数据失败:', error)
      ElMessage.error('加载配置数据失败')
    } finally {
      loading.value = false
    }
  } else {
    // 新建模式，设置默认值
    initConnectionConfig()
  }
}

const initConnectionConfig = () => {
  switch (form.listener_type) {
    case 'tcp':
      form.connection_config = {
        mode: 'server',
        host: '0.0.0.0',
        port: 8080,
        encoding: 'utf-8',
        data_format: 'json'
      }
      break
    case 'mqtt':
      form.connection_config = {
        host: 'localhost',
        port: 1883,
        username: '',
        password: '',
        topics: ['#']
      }
      break
    case 'http':
      form.connection_config = {
        mode: 'webhook',
        host: '0.0.0.0',
        port: 8080,
        path: '/webhook',
        poll_method: 'GET',
        poll_interval: 30
      }
      break
  }
}

const handleTypeChange = (type) => {
  if (type) {
    initConnectionConfig()
  }
}

const loadTemplate = () => {
  const template = props.templates[form.listener_type]
  if (template) {
    Object.assign(form, template)
    ElMessage.success('模板已载入')
  }
}

// 加载可用边缘设备
const loadAvailableEdgeDevices = async () => {
  try {
    const response = await edgeServerAPI.getOnlineServers()
    availableEdgeDevices.value = response || []
  } catch (error) {
    // console.error('加载边缘设备失败:', error)
    ElMessage.warning('加载边缘设备列表失败')
  }
}

// 边缘设备选择变化
const onEdgeDeviceChange = async (deviceIds) => {
  selectedDeviceEngines.value = {}
  
  if (!form.algorithm_field_mappings) {
    form.algorithm_field_mappings = {}
  }
  if (!form.algorithm_specific_fields) {
    form.algorithm_specific_fields = {}
  }
  
  await loadEdgeDevicesAndEngines(deviceIds)
}

// 加载边缘设备和算法引擎信息
const loadEdgeDevicesAndEngines = async (deviceIds) => {
  for (const deviceId of deviceIds) {
    try {
      const device = availableEdgeDevices.value.find(d => d.id === deviceId)
      if (device && device.status === 'online') {
        const serverAPI = edgeServerAPI.createServerAPI(device.ip_address, device.port)
        const response = await serverAPI.getAlgorithmEngines()
        
        if (response.code === 0 && response.result?.engines) {
          selectedDeviceEngines.value[deviceId] = response.result.engines.map(engine => ({
            engineId: engine.id,
            engineName: engine.name,
            engineTypes: engine.model?.class?.value ? 
              engine.model.class.value.map(c => c.name || '未知').filter(Boolean) : 
              ['未知类型']
          }))
          
          // 在编辑模式下保留现有配置，否则初始化空配置
          if (!form.algorithm_field_mappings[deviceId]) {
            form.algorithm_field_mappings[deviceId] = []
          }
          if (!form.algorithm_specific_fields[deviceId]) {
            form.algorithm_specific_fields[deviceId] = {}
          }
          
          // 为每个引擎初始化空配置（如果不存在）
          response.result.engines.forEach(engine => {
            if (!form.algorithm_specific_fields[deviceId][engine.id]) {
              form.algorithm_specific_fields[deviceId][engine.id] = []
            }
          })
        }
        // console.log(selectedDeviceEngines.value)
      }
    } catch (error) {
      // console.error(`加载设备${deviceId}算法引擎失败:`, error)
    }
  }
}

// 获取设备名称
const getDeviceName = (deviceId) => {
  const device = availableEdgeDevices.value.find(d => d.id === deviceId)
  return device ? device.name : `设备${deviceId}`
}

// 推送启用状态变化
const onPushEnabledChange = (enabled) => {
  if (!enabled) {
    form.push_config = {
      tags: [],
      template: ''
    }
  }
}

// 算法字段配置方法
const getAlgorithmFields = (deviceId, engineId) => {
  if (!form.algorithm_specific_fields[deviceId] || !form.algorithm_specific_fields[deviceId][engineId]) {
    return []
  }
  const fields = form.algorithm_specific_fields[deviceId][engineId]
  if (Array.isArray(fields)) {
    return fields
  }
  // 如果是对象格式，转换为数组格式
  return Object.entries(fields).map(([key, value]) => ({
    source_field: key,
    target_field: value.target_field || key,
    field_type: value.field_type || 'string',
    description: value.description || ''
  }))
}

const addAlgorithmField = (deviceId, engineId) => {
  if (!form.algorithm_specific_fields[deviceId]) {
    form.algorithm_specific_fields[deviceId] = {}
  }
  if (!form.algorithm_specific_fields[deviceId][engineId]) {
    form.algorithm_specific_fields[deviceId][engineId] = []
  }
  
  form.algorithm_specific_fields[deviceId][engineId].push({
    source_field: '',
    target_field: '',
    field_type: 'string',
    description: ''
  })
}

const removeAlgorithmField = (deviceId, engineId, fieldIndex) => {
  if (form.algorithm_specific_fields[deviceId] && 
      form.algorithm_specific_fields[deviceId][engineId] &&
      Array.isArray(form.algorithm_specific_fields[deviceId][engineId])) {
    form.algorithm_specific_fields[deviceId][engineId].splice(fieldIndex, 1)
  }
}

// 自定义字段映射方法
const addCustomFieldMapping = () => {
  customFieldMappings.value.push({
    source_field: '',
    target_field: '',
    field_type: 'string'
  })
}

const removeCustomFieldMapping = (index) => {
  customFieldMappings.value.splice(index, 1)
}

// 图片字段配置方法
const addImageFieldConfig = () => {
  imageFieldConfigs.value.push({
    field_name: '',
    encoding: 'base64',
    save_path: 'images/events',
    generate_thumbnail: false,
    thumbnail_size: 200
  })
}

const removeImageFieldConfig = (index) => {
  imageFieldConfigs.value.splice(index, 1)
}

const handleSave = async () => {
  try {
    await formRef.value.validate()
    
    saving.value = true
    
    // 转换自定义字段映射
    const custom_fields = {}
    customFieldMappings.value.forEach(mapping => {
      if (mapping.source_field && mapping.target_field) {
        custom_fields[mapping.source_field] = {
          target_field: mapping.target_field,
          field_type: mapping.field_type
        }
      }
    })
    
    // 转换图片字段配置
    const image_fields = {}
    imageFieldConfigs.value.forEach(config => {
      if (config.field_name) {
        image_fields[config.field_name] = {
          encoding: config.encoding,
          save_path: config.save_path,
          generate_thumbnail: config.generate_thumbnail,
          thumbnail_size: config.thumbnail_size
        }
      }
    })
    
    // 构建设备和引擎名称映射
    const device_name_mappings = {}
    const engine_name_mappings = {}
    
    // 遍历选择的设备，构建设备ID到名称的映射
    form.edge_device_mappings.forEach(deviceId => {
      const device = availableEdgeDevices.value.find(d => d.id === deviceId)
      if (device) {
        device_name_mappings[device.device_info.deviceSN] = device.name
      }
    })
    
    // 遍历算法引擎，构建引擎ID到名称的映射
    Object.keys(selectedDeviceEngines.value).forEach(deviceId => {
      const engines = selectedDeviceEngines.value[deviceId] || []
      engines.forEach(engine => {
        if (form.algorithm_field_mappings[deviceId]?.includes(engine.engineId)) {
          engine_name_mappings[engine.engineId] = engine.engineName
        }
      })
    })
    
    // 准备保存的数据
    const saveData = {
      ...form,
      data_mapping: {
        ...form.data_mapping,
        custom_fields,
        image_fields
      },
      device_name_mappings,
      engine_name_mappings
    }
    
    let response
    if (isEdit.value) {
      response = await dataListenerApi.updateConfig(props.config.config_id, saveData)
    } else {
      response = await dataListenerApi.createConfig(saveData)
    }
    
    if (response.data.status === 'success') {
      ElMessage.success(isEdit.value ? '配置更新成功' : '配置创建成功')
      emit('saved')
    } else {
      ElMessage.error(response.data.message || '保存失败')
    }
  } catch (error) {
    // console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败')
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  formRef.value?.resetFields()
  visible.value = false
}
</script>

<style scoped>
.listener-config-dialog {
  z-index: 9999;
}

.field-config-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #303133;
}

.mapping-container {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 16px;
  background-color: #fafafa;
}

.mapping-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.mapping-item:last-child {
  margin-bottom: 0;
}

.mapping-arrow {
  font-weight: bold;
  color: #409eff;
  margin: 0 8px;
}

.image-field-item {
  padding: 12px;
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  background-color: white;
  margin-bottom: 12px;
}

.image-options {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.option-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.algorithm-configs {
  margin-top: 16px;
}

.device-engine-group {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background-color: #fafafa;
}

.device-engine-group h4 {
  margin: 0 0 16px 0;
  color: #303133;
  font-size: 16px;
}

.engine-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.engine-item {
  padding: 12px;
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  background-color: white;
}

.engine-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.engine-name {
  font-weight: 500;
}

.engine-fields {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.field-mappings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.algorithm-field-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.algorithm-field-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.dialog-footer {
  text-align: right;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
}

/* 响应式 */
@media (max-width: 768px) {
  .mapping-item {
    flex-direction: column;
    align-items: stretch;
  }
  
  .mapping-arrow {
    align-self: center;
    margin: 4px 0;
  }
  
  .device-engine-group {
    padding: 12px;
  }
  
  .field-mappings-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

<style>
/* 全局样式确保下拉框正常显示 */
.listener-dialog-select {
  z-index: 10003 !important;
}

.listener-config-dialog .el-dialog__wrapper {
  z-index: 10000 !important;
}

.listener-config-dialog .el-overlay {
  z-index: 9999 !important;
}
</style>