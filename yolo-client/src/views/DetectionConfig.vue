<template>
  <div class="detection-config-page">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>检测配置管理</span>
          <el-button type="primary" @click="showAddModal">
            <el-icon><plus /></el-icon>创建配置
          </el-button>
        </div>
      </template>
      
      <!-- 配置列表 -->
      <el-table
        :data="configList"
        v-loading="loading"
        style="width: 100%"
      >
        <!-- 设备名称列 -->
        <el-table-column label="设备" prop="device_id">
          <template #default="scope">
            {{ getDeviceName(scope.row.device_id) }}
          </template>
        </el-table-column>
        
        <!-- 模型名称列 -->
        <el-table-column label="模型" prop="models_id">
          <template #default="scope">
            {{ getModelName(scope.row.models_id) }}
          </template>
        </el-table-column>
        
        <!-- 状态列 -->
        <el-table-column label="状态" prop="enabled">
          <template #default="scope">
            <el-tag :type="scope.row.enabled ? 'success' : 'danger'">
              {{ scope.row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 灵敏度列 -->
        <el-table-column label="灵敏度" prop="sensitivity">
        </el-table-column>
        
        <!-- 检测频率列 -->
        <el-table-column label="检测频率" prop="frequency">
          <template #default="scope">
            <el-tag :type="getFrequencyType(scope.row.frequency)">
              {{ getFrequencyLabel(scope.row.frequency) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 保存模式列 -->
        <el-table-column label="保存模式" prop="save_mode">
          <template #default="scope">
            <el-tag :type="getSaveModeType(scope.row.save_mode)">
              {{ getSaveModeLabel(scope.row.save_mode) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 操作列 -->
        <el-table-column label="操作">
          <template #default="scope">
            <el-space>
              <el-button type="primary" size="small" @click="editConfig(scope.row)">
                编辑
              </el-button>
              <el-button
                :type="scope.row.enabled ? 'danger' : 'success'"
                size="small"
                @click="toggleEnabled(scope.row)"
              >
                {{ scope.row.enabled ? '禁用' : '启用' }}
              </el-button>
              <el-popconfirm
                title="确定要删除这个配置吗?"
                @confirm="deleteConfig(scope.row.config_id)"
              >
                <template #reference>
                  <el-button type="danger" size="small">
                    删除
                  </el-button>
                </template>
              </el-popconfirm>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 添加/编辑配置的模态框 -->
    <el-dialog
      v-model="modalVisible"
      :title="isEdit ? '编辑检测配置' : '创建检测配置'"
      width="700px"
    >
      <el-form
        ref="formRef"
        :model="formState"
        :rules="rules"
        label-position="top"
      >
        <!-- 设备选择 -->
        <el-form-item label="设备" prop="device_id">
          <el-select
            v-model="formState.device_id"
            placeholder="请选择设备"
            :disabled="isEdit"
            style="width: 100%"
          >
            <el-option
              v-for="device in deviceList"
              :key="device.device_id"
              :label="`${device.device_name} (${device.device_id})`"
              :value="device.device_id"
            />
          </el-select>
        </el-form-item>
        
        <!-- 模型选择 -->
        <el-form-item label="检测模型" prop="models_id">
          <el-select
            v-model="formState.models_id"
            placeholder="请选择检测模型"
            style="width: 100%"
          >
            <el-option
              v-for="model in modelList"
              :key="model.models_id"
              :label="`${model.models_name} (${getModelTypeName(model.models_type)})`"
              :value="model.models_id"
            />
          </el-select>
        </el-form-item>
        
        <!-- 是否启用 -->
        <el-form-item label="状态" prop="enabled">
          <el-switch v-model="formState.enabled" />
        </el-form-item>
        
        <!-- 检测灵敏度 -->
        <el-form-item label="检测灵敏度" prop="sensitivity">
          <el-slider
            v-model="formState.sensitivity"
            :min="0.1"
            :max="0.9"
            :step="0.05"
            :show-tooltip="true"
            :marks="{
              0.1: '低',
              0.5: '中',
              0.9: '高'
            }"
          />
        </el-form-item>
        
        <!-- 目标类别 -->
        <el-form-item label="目标类别" prop="target_classes">
          <el-select
            v-model="formState.target_classes"
            multiple
            placeholder="请选择要检测的目标类别"
            style="width: 100%"
            collapse-tags
            collapse-tags-tooltip
          >
            <el-option
              v-for="cls in commonClasses"
              :key="cls"
              :label="cls"
              :value="cls"
            />
          </el-select>
        </el-form-item>
        
        <!-- 检测频率 -->
        <el-form-item label="检测频率" prop="frequency">
          <el-radio-group v-model="formState.frequency">
            <el-radio value="realtime">实时检测</el-radio>
            <el-radio value="scheduled">定时检测</el-radio>
            <el-radio value="manual">手动触发</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- 保存模式 -->
        <el-form-item label="保存模式" prop="save_mode">
          <el-radio-group v-model="formState.save_mode">
            <el-radio value="screenshot">仅截图</el-radio>
            <el-radio value="video">仅视频</el-radio>
            <el-radio value="both">截图和视频</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- 高级配置 -->
        <el-collapse>
          <el-collapse-item title="高级配置" name="1">
            <!-- 视频片段时长 -->
            <el-form-item
              label="视频片段时长(秒)"
              prop="save_duration"
              v-if="formState.save_mode !== 'screenshot'"
            >
              <el-input-number
                v-model="formState.save_duration"
                :min="5"
                :max="60"
                :step="5"
              />
            </el-form-item>
            
            <!-- 事件保留天数 -->
            <el-form-item label="事件保留天数" prop="max_storage_days">
              <el-input-number
                v-model="formState.max_storage_days"
                :min="1"
                :max="90"
                :step="1"
              />
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="cancelModal">取消</el-button>
          <el-button type="primary" @click="submitForm" :loading="submitLoading">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Plus } from '@element-plus/icons-vue';
import deviceApi from '@/api/device'
import { detectionConfigApi, detectionServiceApi } from '@/api/detection';
import { startDetection, stopDetection } from '@/api/detection_server';

export default defineComponent({
  name: 'DetectionConfig',
  components: {
    Plus
  },
  setup() {
    // 数据加载状态
    const loading = ref(false);
    const submitLoading = ref(false);
    
    // 表格数据
    const configList = ref([]);
    const deviceList = ref([]);
    const modelList = ref([]);
    
    // 模态框状态
    const modalVisible = ref(false);
    const isEdit = ref(false);
    const formRef = ref(null);
    
    // 表单状态
    const formState = reactive({
      config_id: null,
      device_id: null,
      models_id: null,
      enabled: true,
      sensitivity: 0.5,
      target_classes: [],
      frequency: 'realtime',
      save_mode: 'screenshot',
      save_duration: 10,
      max_storage_days: 30
    });
    
    // 表单校验规则
    const rules = {
      device_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
      models_id: [{ required: true, message: '请选择检测模型', trigger: 'change' }],
      sensitivity: [{ required: true, message: '请设置检测灵敏度', trigger: 'change' }],
      frequency: [{ required: true, message: '请选择检测频率', trigger: 'change' }],
      save_mode: [{ required: true, message: '请选择保存模式', trigger: 'change' }]
    };
    
    // 常见目标类别
    const commonClasses = ref([
      'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
      'dog', 'cat', 'bottle', 'chair', 'laptop', 'cell phone'
    ]);

    // 获取模型类型名称
    const getModelTypeName = (type) => {
      const typeMap = {
        'object_detection': '目标检测',
        'segmentation': '图像分割',
        'keypoint': '关键点检测',
        'pose': '姿态估计',
        'face': '人脸识别',
        'other': '其他类型'
      }
      return typeMap[type] || type
    }

    // 获取设备名称
    const getDeviceName = (deviceId) => {
      const device = deviceList.value.find(d => d.device_id === deviceId);
      return device ? device.device_name : deviceId;
    };
    
    // 获取模型名称
    const getModelName = (modelId) => {
      const model = modelList.value.find(m => m.models_id === modelId);
      return model ? model.models_name : modelId;
    };
    
    // 获取检测频率标签
    const getFrequencyLabel = (frequency) => {
      const map = {
        'realtime': '实时',
        'scheduled': '定时',
        'manual': '手动'
      };
      return map[frequency] || frequency;
    };
    
    // 获取检测频率标签类型
    const getFrequencyType = (frequency) => {
      const map = {
        'realtime': 'primary',
        'scheduled': 'warning',
        'manual': 'info'
      };
      return map[frequency] || '';
    };
    
    // 获取保存模式标签
    const getSaveModeLabel = (saveMode) => {
      const map = {
        'screenshot': '截图',
        'video': '视频',
        'both': '截图+视频'
      };
      return map[saveMode] || saveMode;
    };
    
    // 获取保存模式标签类型
    const getSaveModeType = (saveMode) => {
      const map = {
        'screenshot': 'success',
        'video': 'primary',
        'both': 'info'
      };
      return map[saveMode] || '';
    };
    
    // 加载配置列表
    const loadConfigList = async () => {
      loading.value = true;
      try {
        const response = await detectionConfigApi.getConfigs();
        configList.value = response.data;
      } catch (error) {
        ElMessage.error('获取配置列表失败: ' + error.message);
      } finally {
        loading.value = false;
      }
    };
    
    // 加载设备列表
    const loadDeviceList = async () => {
      try {
        const response = await deviceApi.getDevices();
        deviceList.value = response.data;
      } catch (error) {
        ElMessage.error('获取设备列表失败: ' + error.message);
      }
    };
    
    // 加载模型列表
    const loadModelList = async () => {
      try {
        const response = await deviceApi.getModels();
        modelList.value = response.data.filter(model => model.is_active);
      } catch (error) {
        ElMessage.error('获取模型列表失败: ' + error.message);
      }
    };
    
    // 初始化
    onMounted(() => {
      loadConfigList();
      loadDeviceList();
      loadModelList();
    });
    
    // 显示添加模态框
    const showAddModal = () => {
      isEdit.value = false;
      resetForm();
      modalVisible.value = true;
    };
    
    // 重置表单
    const resetForm = () => {
      Object.assign(formState, {
        config_id: null,
        device_id: null,
        models_id: null,
        enabled: true,
        sensitivity: 0.5,
        target_classes: [],
        frequency: 'realtime',
        save_mode: 'screenshot',
        save_duration: 10,
        max_storage_days: 30
      });
      
      if (formRef.value) {
        formRef.value.resetFields();
      }
    };
    
    // 编辑配置
    const editConfig = (record) => {
      isEdit.value = true;
      
      Object.assign(formState, {
        config_id: record.config_id,
        device_id: record.device_id,
        models_id: record.models_id,
        enabled: record.enabled,
        sensitivity: record.sensitivity,
        target_classes: record.target_classes || [],
        frequency: record.frequency,
        save_mode: record.save_mode,
        save_duration: record.save_duration,
        max_storage_days: record.max_storage_days
      });
      
      modalVisible.value = true;
    };
    
    // 提交表单
    const submitForm = async () => {
      if (formRef.value) {
        await formRef.value.validate(async (valid, fields) => {
          if (valid) {
            submitLoading.value = true;
            
            try {
              if (isEdit.value) {
                // 更新配置
                await detectionConfigApi.updateConfig(formState.config_id, {
                  models_id: formState.models_id,
                  enabled: formState.enabled,
                  sensitivity: formState.sensitivity,
                  target_classes: formState.target_classes,
                  frequency: formState.frequency,
                  save_mode: formState.save_mode,
                  save_duration: formState.save_duration,
                  max_storage_days: formState.max_storage_days
                });
                ElMessage.success('配置更新成功');
              } else {
                // 创建配置
                await detectionConfigApi.createConfig(formState);
                ElMessage.success('配置创建成功');
              }
              
              modalVisible.value = false;
              loadConfigList();
            } catch (error) {
              ElMessage.error('提交失败: ' + (error.response?.data?.detail || error.message));
            } finally {
              submitLoading.value = false;
            }
          }
        });
      }
    };
    
    // 取消模态框
    const cancelModal = () => {
      modalVisible.value = false;
    };
    
    // 切换启用状态
    const toggleEnabled = async (record) => {
      try {
        if(!record.enabled) {
          // 启动任务
          const response = await startDetection(record.config_id)         
          if (response.status === 'success') {
            ElMessage.success('检测任务已启动')
          } else {
            ElMessage.error(response.message || '启动任务失败')
          }
        } else {
          // 停止任务
          const response = await stopDetection(record.config_id)
          if (response.status === 'success') {
            ElMessage.success('检测任务已停止')
          } else {
            ElMessage.error(response.message || '停止任务失败')
          }
        }
        loadConfigList();
      } catch (error) {
        ElMessage.error('操作失败: ' + error.message);
      }
    };
    
    // 删除配置
    const deleteConfig = async (configId) => {
      try {
        await detectionConfigApi.deleteConfig(configId);
        ElMessage.success('配置删除成功');
        loadConfigList();
      } catch (error) {
        ElMessage.error('删除失败: ' + error.message);
      }
    };
    
    return {
      loading,
      submitLoading,
      configList,
      deviceList,
      modelList,
      modalVisible,
      isEdit,
      formRef,
      formState,
      rules,
      commonClasses,
      getModelTypeName,
      getDeviceName,
      getModelName,
      getFrequencyLabel,
      getFrequencyType,
      getSaveModeLabel,
      getSaveModeType,
      showAddModal,
      editConfig,
      submitForm,
      cancelModal,
      toggleEnabled,
      deleteConfig
    };
  }
});
</script>

<style scoped>
.detection-config-page {
  padding: 24px;
}

.main-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style> 