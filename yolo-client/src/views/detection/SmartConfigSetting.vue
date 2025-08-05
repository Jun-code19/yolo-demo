<template>
  <div class="smart-config-setting-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" class="back-btn">
          <el-icon>
            <ArrowLeft />
          </el-icon>
          返回
        </el-button>
        <div class="header-info">
          <h2>智能方案设置</h2>
          <p v-if="deviceInfo">设备：{{ deviceInfo.device_name }} ({{ deviceInfo.device_id }})</p>
        </div>
      </div>
      <div class="header-right">
        <el-button @click="resetConfig">重置</el-button>
        <el-button type="primary" @click="saveConfig" :loading="saveLoading" :disabled="!canSave()">
          保存配置
        </el-button>
      </div>
    </div>

    <div class="page-content">
      <!-- 左侧：画线设置 -->
      <div class="left-panel">
        <el-card class="drawing-card">
          <template #header>
            <div class="card-header">
              <span>画线设置</span>
              <div class="drawing-status">
                <el-tag v-if="configForm.coordinates.behaviorType" type="success">
                  当前模式：{{ getDrawingModeLabel() }}
                </el-tag>
              </div>
            </div>
          </template>

          <!-- 设备画面预览和绘制区域 -->
          <div class="image-preview-container">
            <div v-if="imageLoading" class="loading-wrapper">
              <el-skeleton animated :rows="8" />
              <div class="loading-text">正在加载设备画面...</div>
            </div>
            <div v-else-if="imageError" class="error-wrapper">
              <el-icon :size="64">
                <CircleClose />
              </el-icon>
              <p>{{ imageError }}</p>
              <el-button @click="loadDeviceImage">重试</el-button>
            </div>
            <div v-else-if="!deviceImage" class="image-placeholder">
              <el-icon :size="64">
                <VideoCamera />
              </el-icon>
              <p>暂无设备画面图片</p>
            </div>
            <div v-else class="image-wrapper">
              <img ref="deviceImageRef" :src="deviceImage" class="device-image" @load="onImageLoaded" />
              <canvas ref="drawingCanvas" class="drawing-canvas" @mousedown="handleMouseDown"
                @mousemove="handleMouseMove" @contextmenu.prevent="handleRightClick">
              </canvas>
              <div class="drawing-controls">
                <el-button type="primary" @click="startDrawing"
                  :disabled="!configForm.analysisType || configForm.analysisType === 'none'">
                  开始绘制
                </el-button>
                <el-button @click="clearDrawing" :disabled="configForm.analysisType === 'none'">清除</el-button>
              </div>
            </div>
          </div>

          <div class="drawing-hints">
            <el-alert title="绘制提示" type="info" :closable="false"
              v-if="configForm.analysisType && configForm.analysisType !== 'none'">
              <p>• 左键点击添加顶点</p>
              <p>• 右键点击完成绘制</p>
              <p>• 请先在右侧选择智能方案类型</p>
            </el-alert>
            <el-alert title="当前配置" type="success" :closable="false" v-else-if="configForm.analysisType === 'none'">
              <p>• 已选择"无智能方案"</p>
              <p>• 系统将进行普通目标检测</p>
              <p>• 无需绘制区域或拌线</p>
            </el-alert>
            <el-alert title="绘制提示" type="warning" :closable="false" v-else>
              <p>• 请先在右侧选择智能方案类型</p>
            </el-alert>
          </div>
        </el-card>
      </div>

      <!-- 右侧：智能方案设置 -->
      <div class="right-panel">
        <el-form :model="configForm" label-position="top" class="smart-config-form">
          <!-- 智能方案选择 -->
          <el-card class="config-card">
            <template #header>
              <div class="card-header">
                <el-icon>
                  <Operation />
                </el-icon>
                <span>智能方案</span>
              </div>
            </template>

            <el-radio-group v-model="configForm.analysisType" @change="handleAnalysisTypeChange"
              class="analysis-type-selector">
              <div class="analysis-option" :class="{ active: configForm.analysisType === 'behavior' }">
                <el-radio value="behavior">
                  <div class="option-content">
                    <div class="option-header">
                      <el-icon>
                        <VideoCamera />
                      </el-icon>
                      <span class="option-title">通用行为分析</span>
                    </div>
                    <div class="option-desc">检测区域内的行为活动和拌线穿越事件</div>
                  </div>
                </el-radio>
              </div>
              <div class="analysis-option" :class="{ active: configForm.analysisType === 'counting' }">
                <el-radio value="counting">
                  <div class="option-content">
                    <div class="option-header">
                      <el-icon>
                        <Files />
                      </el-icon>
                      <span class="option-title">人数统计分析</span>
                    </div>
                    <div class="option-desc">统计区域内人数变化和人流通过数量</div>
                  </div>
                </el-radio>
              </div>
              <div class="analysis-option" :class="{ active: configForm.analysisType === 'none' }">
                <el-radio value="none">
                  <div class="option-content">
                    <div class="option-header">
                      <el-icon>
                        <CircleClose />
                      </el-icon>
                      <span class="option-title">无智能方案</span>
                    </div>
                    <div class="option-desc">普通目标检测功能</div>
                  </div>
                </el-radio>
              </div>
            </el-radio-group>
          </el-card>

          <!-- 通用行为分析配置 -->
          <el-card v-if="configForm.analysisType === 'behavior'" class="config-card">
            <template #header>
              <div class="card-header">
                <el-icon>
                  <Setting />
                </el-icon>
                <span>行为分析配置</span>
              </div>
            </template>

            <!-- 检测类型选择 -->
            <el-form-item label="检测类型">
              <el-radio-group v-model="configForm.coordinates.behaviorType" @change="handleDetectionTypeChange">
                <div class="type-options">
                  <div class="type-card" :class="{ active: configForm.coordinates.behaviorType === 'area' }">
                    <el-radio value="area">
                      <div class="type-content">
                        <div class="type-header">
                          <el-icon>
                            <Operation />
                          </el-icon>
                          <span class="type-title">区域检测</span>
                        </div>
                        <div class="type-desc">检测区域内的行为活动</div>
                      </div>
                    </el-radio>
                  </div>
                  <div class="type-card" :class="{ active: configForm.coordinates.behaviorType === 'line' }">
                    <el-radio value="line">
                      <div class="type-content">
                        <div class="type-header">
                          <el-icon>
                            <Edit />
                          </el-icon>
                          <span class="type-title">拌线检测</span>
                        </div>
                        <div class="type-desc">检测穿越拌线的行为</div>
                      </div>
                    </el-radio>
                  </div>
                </div>
              </el-radio-group>
            </el-form-item>

            <!-- 检测模式选择 -->
            <el-form-item label="检测模式" v-if="configForm.coordinates.behaviorType">
              <el-radio-group v-model="configForm.coordinates.behaviorSubtype">
                <el-radio value="simple">普通检测</el-radio>
                <el-radio value="directional">方向检测</el-radio>
              </el-radio-group>
            </el-form-item>

            <!-- 方向选择 -->
            <el-form-item label="检测方向" v-if="configForm.coordinates.behaviorSubtype === 'directional'">
              <el-radio-group v-model="configForm.coordinates.behaviorDirection">
                <el-radio value="in">进入区域/线</el-radio>
                <el-radio value="out">离开区域/线</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-card>

          <!-- 人数统计分析配置 -->
          <el-card v-if="configForm.analysisType === 'counting'" class="config-card">
            <template #header>
              <div class="card-header">
                <el-icon>
                  <Setting />
                </el-icon>
                <span>人数统计配置</span>
              </div>
            </template>

            <!-- 统计类型选择 -->
            <el-form-item label="统计类型">
              <el-radio-group v-model="configForm.coordinates.countingType" @change="handleCountingTypeChange">
                <div class="type-options">
                  <div class="type-card" :class="{ active: configForm.coordinates.countingType === 'occupancy' }">
                    <el-radio value="occupancy">
                      <div class="type-content">
                        <div class="type-header">
                          <el-icon>
                            <Operation />
                          </el-icon>
                          <span class="type-title">区域人数统计</span>
                        </div>
                        <div class="type-desc">统计区域内当前人数</div>
                      </div>
                    </el-radio>
                  </div>
                  <div class="type-card" :class="{ active: configForm.coordinates.countingType === 'flow' }">
                    <el-radio value="flow">
                      <div class="type-content">
                        <div class="type-header">
                          <el-icon>
                            <Edit />
                          </el-icon>
                          <span class="type-title">人流统计</span>
                        </div>
                        <div class="type-desc">统计通过的人数流量</div>
                      </div>
                    </el-radio>
                  </div>
                </div>
              </el-radio-group>
            </el-form-item>

            <!-- 区域人数统计配置 -->
            <div v-if="configForm.coordinates.countingType === 'occupancy'" class="counting-config">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="统计间隔">
                    <div class="input-with-unit">
                      <el-input-number v-model="configForm.coordinates.countingInterval" :min="1" :max="60" :step="1" />
                      <span class="unit-label">秒</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="最大容量">
                    <div class="input-with-unit">
                      <el-input-number v-model="configForm.coordinates.maxCapacity" :min="1" :max="1000" :step="1" />
                      <span class="unit-label">人</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

            <!-- 人流统计配置 -->
            <div v-if="configForm.coordinates.countingType === 'flow'" class="counting-config">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="统计方向">
                    <el-select v-model="configForm.coordinates.flowDirection" style="width: 100%">
                      <el-option label="双向统计" value="bidirectional" />
                      <el-option label="仅进入" value="in" />
                      <el-option label="仅离开" value="out" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="统计周期">
                    <el-select v-model="configForm.coordinates.flowPeriod" style="width: 100%">
                      <el-option label="实时" value="realtime" />
                      <el-option label="每分钟" value="minute" />
                      <el-option label="每5分钟" value="5minute" />
                      <el-option label="每小时" value="hour" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

            <!-- 设置绘制类型提示 -->
            <div class="auto-draw-type">
              <el-alert :title="getCountingDrawingTypeHint()" type="info" :closable="false" show-icon />
            </div>
          </el-card>

          <!-- 高级设置 -->
          <el-card v-if="configForm.analysisType" class="config-card">
            <template #header>
              <div class="card-header">
                <el-icon>
                  <Setting />
                </el-icon>
                <span>高级设置</span>
              </div>
            </template>

            <el-row :gutter="20">
              <el-col :span="10">
                <el-form-item label="推送标签">
                  <el-input v-model="configForm.coordinates.pushLabel" placeholder="请输入推送标签" maxlength="50"
                    show-word-limit />
                </el-form-item>
              </el-col>
              <el-col :span="14">
                <el-form-item label="推送间隔(秒)">
                  <el-input-number v-model="configForm.coordinates.alarm_interval" :min="0" :max="3600" :step="1" style="width: 50%;" />
                </el-form-item>
              </el-col>
            </el-row>

            <div class="form-hint">
              推送标签将在事件数据中标识该智能方案的来源；推送间隔为事件推送的间隔时间，单位为秒。
            </div>

            <el-form-item label="报警设置" v-if="configForm.analysisType === 'counting'">
              <el-switch v-model="configForm.coordinates.enableAlert" active-text="启用报警" inactive-text="关闭报警" />
            </el-form-item>

            <div v-if="configForm.coordinates.enableAlert" class="alert-config">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="报警阈值">
                    <div class="input-with-unit">
                      <el-input-number v-model="configForm.coordinates.alertThreshold" :min="1" :max="1000" />
                      <span class="unit-label">人</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

          </el-card>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Operation, Setting, Edit, VideoCamera, Files, CircleClose } from '@element-plus/icons-vue';
import deviceApi from '@/api/device';
import { detectionConfigApi } from '@/api/detection';

export default defineComponent({
  name: 'SmartConfigSetting',
  components: {
    ArrowLeft,
    Operation,
    Setting,
    Edit,
    VideoCamera,
    Files,
    CircleClose
  },
  setup() {
    const router = useRouter();
    const route = useRoute();

    // 获取路由参数
    const configId = route.params.configId;

    // 响应式数据
    const saveLoading = ref(false);
    const deviceInfo = ref(null);
    const deviceList = ref([]);

    // 配置表单数据
    const configForm = reactive({
      analysisType: null,
      coordinates: {
        behaviorType: null,
        points: [],
        behaviorSubtype: "simple",
        behaviorDirection: "in",
        countingType: null,
        countingInterval: 5,
        maxCapacity: 100,
        flowDirection: 'bidirectional',
        flowPeriod: 'realtime',
        alarm_interval: 0,
        pushLabel: '',
        enableAlert: false,
        alertThreshold: 50,
      }
    });

    // 图片预览相关
    const imageLoading = ref(false);
    const imageError = ref(null);
    const deviceImage = ref(null);
    const deviceImageRef = ref(null);
    const drawingCanvas = ref(null);

    // 绘制相关状态
    const isDrawing = ref(false);
    const points = ref([]);

    // 页面操作方法
    const goBack = () => {
      router.go(-1);
    };

    const resetConfig = () => {
      configForm.analysisType = null;
      configForm.coordinates = {
        behaviorType: null,
        points: [],
        behaviorSubtype: "simple",
        behaviorDirection: "in",
        countingType: null,
        countingInterval: 5,
        maxCapacity: 100,
        flowDirection: 'bidirectional',
        flowPeriod: 'realtime',
        alarm_interval: 0,
        pushLabel: '',
        enableAlert: false,
        alertThreshold: 50,
      };
      clearDrawing();
      ElMessage.success('配置已重置');
    };

    const saveConfig = async () => {
      try {
        if (!configForm.analysisType) {
          throw new Error('请选择智能方案类型');
        }

        // 如果选择了"无智能方案"，直接保存空配置
        if (configForm.analysisType === 'none') {
          saveLoading.value = true;

          await detectionConfigApi.updateConfig(configId, {
            area_coordinates: {
              analysisType: null,
              points: [],
              behaviorType: null,
              countingType: null,
              behaviorSubtype: 'simple',
              behaviorDirection: 'in',
              countingInterval: 5,
              maxCapacity: 100,
              flowDirection: 'bidirectional',
              flowPeriod: 'realtime',
              alarm_interval: configForm.coordinates.alarm_interval || 0,
              pushLabel: configForm.coordinates.pushLabel || '',
              enableAlert: false,
              alertThreshold: 50
            }
          });

          ElMessage.success('已清空智能方案配置');
          goBack();
          return;
        }

        // 智能方案的验证逻辑
        if (!configForm.coordinates.points || configForm.coordinates.points.length === 0) {
          throw new Error('请绘制有效的区域或拌线');
        }

        if (configForm.analysisType === 'behavior') {
          if (!configForm.coordinates.behaviorType) {
            throw new Error('请选择检测类型（区域检测或拌线检测）');
          }
        } else if (configForm.analysisType === 'counting') {
          if (!configForm.coordinates.countingType) {
            throw new Error('请选择统计类型（区域人数统计或人流统计）');
          }
        }

        const shouldClose = getShouldCloseArea();
        const minPoints = shouldClose ? 3 : 2;
        if (configForm.coordinates.points.length < minPoints) {
          const typeLabel = shouldClose ? '区域' : '拌线';
          throw new Error(`请绘制有效的${typeLabel}（至少需要${minPoints}个点）`);
        }

        saveLoading.value = true;

        const configData = {
          ...configForm.coordinates,
          analysisType: configForm.analysisType,
        };

        await detectionConfigApi.updateConfig(configId, {
          area_coordinates: configData
        });

        ElMessage.success('智能方案配置保存成功');
        goBack();
      } catch (error) {
        ElMessage.error(`保存失败: ${error.message}`);
      } finally {
        saveLoading.value = false;
      }
    };

    const canSave = () => {
      if (!configForm.analysisType) return false;

      // 如果选择了"无智能方案"，总是可以保存
      if (configForm.analysisType === 'none') {
        return true;
      }

      if (configForm.analysisType === 'behavior') {
        return configForm.coordinates.behaviorType && configForm.coordinates.points.length > 0;
      } else if (configForm.analysisType === 'counting') {
        return configForm.coordinates.countingType && configForm.coordinates.points.length > 0;
      }

      return false;
    };

    // 辅助方法
    const getShouldCloseArea = () => {
      if (configForm.analysisType === 'none') {
        return false;
      } else if (configForm.analysisType === 'behavior') {
        // 行为分析：区域闭合，拌线不闭合
        return configForm.coordinates.behaviorType === 'area';
      } else if (configForm.analysisType === 'counting') {
        // 人数统计：区域人数统计闭合，人流统计不闭合
        return configForm.coordinates.countingType === 'occupancy';
      }
      return false;
    };

    const getDrawingModeLabel = () => {
      if (!configForm.coordinates.behaviorType) return '';

      const typeLabel = configForm.coordinates.behaviorType === 'area' ? '区域' : '拌线';
      const subtypeLabel = configForm.coordinates.behaviorSubtype === 'directional' ? '方向检测' : '普通检测';

      return `${typeLabel}${subtypeLabel}`;
    };

    const getCountingDrawingTypeHint = () => {
      if (configForm.coordinates.countingType === 'occupancy') {
        return '区域人数统计需要绘制封闭区域，用于统计区域内的人数';
      } else if (configForm.coordinates.countingType === 'flow') {
        return '人流统计需要绘制拌线，用于统计穿越该线的人数';
      }
      return '';
    };

    // 事件处理方法
    const handleAnalysisTypeChange = (type) => {
      clearDrawing();
      configForm.coordinates.behaviorType = null;
      configForm.coordinates.countingType = null;
      configForm.coordinates.behaviorSubtype = 'simple';
      configForm.coordinates.behaviorDirection = 'in';
      configForm.coordinates.enableAlert = false;

      if (type === 'counting') {
        configForm.coordinates.countingType = 'occupancy';
        configForm.coordinates.behaviorType = 'area';
      } else if (type === 'none') {
        // 清空所有智能分析相关设置
        configForm.coordinates.points = [];
        // configForm.coordinates.pushLabel = '';
        // configForm.coordinates.alarm_interval = 0;
        configForm.coordinates.alertThreshold = 50;
      }
    };

    const handleDetectionTypeChange = (type) => {
      clearDrawing();
      configForm.coordinates.behaviorSubtype = 'simple';
      configForm.coordinates.behaviorDirection = 'in';
    };

    const handleCountingTypeChange = (type) => {
      clearDrawing();
      if (type === 'occupancy') {
        configForm.coordinates.behaviorType = 'area';
      } else if (type === 'flow') {
        configForm.coordinates.behaviorType = 'line';
      }
    };

    // 绘制相关方法
    const initCanvas = () => {
      if (!drawingCanvas.value || !deviceImageRef.value) return;

      const canvas = drawingCanvas.value;
      const image = deviceImageRef.value;
      const ctx = canvas.getContext('2d');

      const devicePixelRatio = window.devicePixelRatio || 1;
      const displayWidth = image.clientWidth;
      const displayHeight = image.clientHeight;

      canvas.width = displayWidth * devicePixelRatio;
      canvas.height = displayHeight * devicePixelRatio;
      canvas.style.width = displayWidth + 'px';
      canvas.style.height = displayHeight + 'px';

      ctx.scale(devicePixelRatio, devicePixelRatio);
      ctx.imageSmoothingEnabled = false;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
    };

    const onImageLoaded = () => {
      setTimeout(() => {
        initCanvas();
        if (configForm.coordinates.points && configForm.coordinates.points.length > 0) {
          drawPolygon(configForm.coordinates.points);
        }
      }, 100);
    };

    const getDeviceImageUrl = (ipAddress, channel) => {
      const imagePath = `storage/devices/${ipAddress}_ch${channel}.jpg`;
      return `/api/v2/data-listeners/images/${encodeURIComponent(imagePath)}`;
    };

    const loadDeviceImage = () => {
      if (!deviceInfo.value) {
        imageError.value = '设备信息不完整';
        return;
      }

      imageLoading.value = true;
      imageError.value = null;
      deviceImage.value = null;

      const ipAddress = deviceInfo.value.ip_address;
      const channel = deviceInfo.value.channel;
      if (!ipAddress) {
        imageLoading.value = false;
        imageError.value = '无法获取设备IP地址';
        return;
      }

      const imageUrl = getDeviceImageUrl(ipAddress, channel);
      const img = new Image();

      img.onload = () => {
        deviceImage.value = imageUrl;
        imageLoading.value = false;
      };

      img.onerror = () => {
        imageLoading.value = false;
        imageError.value = '设备画面图片不存在，请先进行设备预览以生成画面快照';
      };

      img.src = `${imageUrl}?t=${Date.now()}`;
    };

    const drawPolygon = (points) => {
      if (!drawingCanvas.value || !points || points.length === 0) return;

      const canvas = drawingCanvas.value;
      const ctx = canvas.getContext('2d');
      const displayWidth = canvas.clientWidth;
      const displayHeight = canvas.clientHeight;

      ctx.clearRect(0, 0, displayWidth, displayHeight);

      if (points.length > 0) {
        ctx.save();
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        ctx.beginPath();
        const firstPoint = points[0];
        const startX = Math.round(firstPoint.x * displayWidth) + 0.5;
        const startY = Math.round(firstPoint.y * displayHeight) + 0.5;
        ctx.moveTo(startX, startY);

        points.forEach((point, index) => {
          if (index > 0) {
            const x = Math.round(point.x * displayWidth) + 0.5;
            const y = Math.round(point.y * displayHeight) + 0.5;
            ctx.lineTo(x, y);
          }
        });

        // 判断是否需要闭合区域
        const shouldClose = getShouldCloseArea();
        if (shouldClose) {
          ctx.closePath();
          ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
          ctx.fill();
        }

        ctx.stroke();

        points.forEach(point => {
          const x = Math.round(point.x * displayWidth);
          const y = Math.round(point.y * displayHeight);

          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#ff4444';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();
        });

        ctx.restore();
      }
    };

    const startDrawing = () => {
      if (configForm.coordinates.behaviorType || configForm.coordinates.countingType) {
        isDrawing.value = true;
        points.value = [];
        configForm.coordinates.points = [];
      } else {
        ElMessage.info('请选择检测类型');
      }
    };

    const clearDrawing = () => {
      const canvas = drawingCanvas.value;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        const displayWidth = canvas.clientWidth;
        const displayHeight = canvas.clientHeight;
        ctx.clearRect(0, 0, displayWidth, displayHeight);
      }
      points.value = [];
      configForm.coordinates.points = [];
      isDrawing.value = false;
    };

    const handleMouseDown = (e) => {
      if (!isDrawing.value) return;

      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();

      const normalizedX = (e.clientX - rect.left) / rect.width;
      const normalizedY = (e.clientY - rect.top) / rect.height;

      if (normalizedX < 0 || normalizedX > 1 || normalizedY < 0 || normalizedY > 1) return;

      points.value.push({ x: normalizedX, y: normalizedY });
      redrawCanvas();
    };

    const handleMouseMove = (e) => {
      if (!isDrawing.value || points.value.length === 0) return;

      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();

      const normalizedX = (e.clientX - rect.left) / rect.width;
      const normalizedY = (e.clientY - rect.top) / rect.height;

      if (normalizedX < 0 || normalizedX > 1 || normalizedY < 0 || normalizedY > 1) return;

      redrawCanvas({ x: normalizedX, y: normalizedY });
    };

    const handleRightClick = () => {
      const shouldClose = getShouldCloseArea();
      const minPoints = shouldClose ? 3 : 2;

      if (!isDrawing.value || points.value.length < minPoints) return;

      configForm.coordinates.points = [...points.value];
      drawPolygon(points.value);
      isDrawing.value = false;

      const message = shouldClose ? '区域绘制完成' : '拌线绘制完成';
      ElMessage.success(message);
    };

    const redrawCanvas = (previewPoint = null) => {
      if (!drawingCanvas.value) return;

      const canvas = drawingCanvas.value;
      const ctx = canvas.getContext('2d');
      const displayWidth = canvas.clientWidth;
      const displayHeight = canvas.clientHeight;

      ctx.clearRect(0, 0, displayWidth, displayHeight);

      if (points.value.length === 0 && !previewPoint) return;

      ctx.save();

      if (points.value.length > 0) {
        points.value.forEach(point => {
          const x = Math.round(point.x * displayWidth);
          const y = Math.round(point.y * displayHeight);

          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#ff4444';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();
        });

        if (points.value.length > 1) {
          ctx.beginPath();
          ctx.strokeStyle = '#00ff00';
          ctx.lineWidth = 2;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

          const firstPoint = points.value[0];
          ctx.moveTo(
            Math.round(firstPoint.x * displayWidth) + 0.5,
            Math.round(firstPoint.y * displayHeight) + 0.5
          );

          for (let i = 1; i < points.value.length; i++) {
            const point = points.value[i];
            ctx.lineTo(
              Math.round(point.x * displayWidth) + 0.5,
              Math.round(point.y * displayHeight) + 0.5
            );
          }

          const shouldClose = getShouldCloseArea();
          if (shouldClose && !isDrawing.value && points.value.length >= 3) {
            ctx.closePath();
            ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
            ctx.fill();
          }

          ctx.stroke();
        }

        if (previewPoint && points.value.length > 0) {
          ctx.beginPath();
          ctx.strokeStyle = '#00ff00';
          ctx.lineWidth = 1;

          const lastPoint = points.value[points.value.length - 1];
          ctx.moveTo(
            Math.round(lastPoint.x * displayWidth) + 0.5,
            Math.round(lastPoint.y * displayHeight) + 0.5
          );
          ctx.lineTo(
            Math.round(previewPoint.x * displayWidth) + 0.5,
            Math.round(previewPoint.y * displayHeight) + 0.5
          );
          ctx.stroke();
        }
      }

      ctx.restore();
    };

    // 数据加载方法
    const loadDeviceList = async () => {
      try {
        const response = await deviceApi.getDevices();
        deviceList.value = response.data.data;
      } catch (error) {
        console.error('获取设备列表失败:', error);
      }
    };

    const loadConfigData = async () => {
      try {
        const response = await detectionConfigApi.getConfigs();
        const config = response.data.data.find(c => c.config_id === configId);

        if (config) {
          // 设置设备信息
          deviceInfo.value = deviceList.value.find(d => d.device_id === config.device_id) ||
            { device_id: config.device_id, device_name: '未知设备' };

          // 设置配置数据
          if (config.area_coordinates && Object.keys(config.area_coordinates).length > 0) {
            const coordinates = config.area_coordinates;
            
            configForm.analysisType = coordinates.analysisType || 'none';
            
            Object.assign(configForm.coordinates, coordinates);
          } else {
            // 如果没有配置数据，默认选择"无智能方案"
            configForm.analysisType = 'none';
          }
          
          // 加载设备图片
          setTimeout(() => {
            loadDeviceImage();
          }, 100);
        }
      } catch (error) {
        ElMessage.error('加载配置数据失败: ' + error.message);
      }
    };

    // 初始化
    onMounted(async () => {
      await loadDeviceList();
      await loadConfigData();
    });

    return {
      configForm,
      deviceInfo,
      saveLoading,
      imageLoading,
      imageError,
      deviceImage,
      deviceImageRef,
      drawingCanvas,
      goBack,
      resetConfig,
      saveConfig,
      canSave,
      getShouldCloseArea,
      getDrawingModeLabel,
      getCountingDrawingTypeHint,
      handleAnalysisTypeChange,
      handleDetectionTypeChange,
      handleCountingTypeChange,
      startDrawing,
      clearDrawing,
      handleMouseDown,
      handleMouseMove,
      handleRightClick,
      onImageLoaded,
      loadDeviceImage
    };
  }
});
</script>

<style scoped>
.smart-config-setting-page {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  margin: 0 24px;
  background: white;
  border-bottom: 1px solid #ebeef5;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-info h2 {
  margin: 0 0 4px 0;
  font-size: 18px;
  color: #303133;
}

.header-info p {
  margin: 0;
  font-size: 14px;
  color: #606266;
}

.header-right {
  display: flex;
  gap: 12px;
}

.page-content {
  flex: 1;
  display: flex;
  gap: 20px;
  padding: 20px 24px;
  overflow: hidden;
}

.left-panel {
  flex: 0.9;
  display: flex;
  flex-direction: column;
}

.right-panel {
  flex: 1;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}

.drawing-card {
  /* height: 100%; */
  display: flex;
  flex-direction: column;
}

.drawing-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.drawing-status {
  margin-left: auto;
}

.image-preview-container {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 16px;
  min-height: 400px;
}

.loading-wrapper {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
}

.loading-text {
  margin-top: 10px;
  color: #909399;
}

.error-wrapper {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #f56c6c;
  gap: 10px;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 6px;
}

.device-image,
.drawing-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.drawing-canvas {
  z-index: 1;
  cursor: crosshair;
}

.drawing-controls {
  position: absolute;
  bottom: 16px;
  left: 16px;
  z-index: 2;
  display: flex;
  gap: 8px;
}

.drawing-hints {
  margin-top: auto;
}

.config-card {
  margin-bottom: 20px;
}

.config-card .card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: #409eff;
}

.analysis-type-selector {
  /* display: flex; */
  /* flex-direction: column; */
  gap: 12px;
}

.analysis-option {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px;
  transition: all 0.3s;
  /* overflow: hidden; */
}

.analysis-option:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.analysis-option.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.analysis-option .el-radio {
  width: 100%;
  margin: 0;
  height: auto;
}

.analysis-option .el-radio__input {
  position: absolute;
  top: 16px;
  right: 16px;
}

.analysis-option .el-radio__label {
  width: 100%;
  padding: 16px 50px 16px 16px;
}

.option-content {
  width: 100%;
}

.option-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.option-header .el-icon {
  margin-right: 10px;
  font-size: 18px;
  color: #409eff;
}

.option-title {
  font-weight: 500;
  font-size: 15px;
  color: #303133;
}

.option-desc {
  font-size: 13px;
  color: #606266;
  line-height: 1.4;
}

.type-options {
  display: flex;
  /* flex-direction: column; */
  gap: 10px;
}

.type-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 8px 12px;
  transition: all 0.3s;
  /* overflow: hidden; */
}

.type-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.type-card.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.type-card .el-radio {
  width: 100%;
  margin: 0;
  height: auto;
}

.type-card .el-radio__input {
  position: absolute;
  top: 12px;
  right: 12px;
}

.type-card .el-radio__label {
  width: 100%;
  padding: 12px 40px 12px 12px;
}

.type-content {
  width: 100%;
}

.type-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.type-content .el-icon {
  font-size: 16px;
  color: #409eff;
}

.type-title {
  font-weight: 500;
  /* margin-bottom: 4px; */
  color: #303133;
}

.type-desc {
  font-size: 13px;
  color: #909399;
  line-height: 1.4;
}

.counting-config {
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
  margin-top: 15px;
  border: 1px solid #e9ecef;
}

.auto-draw-type {
  margin-top: 15px;
}

.input-with-unit {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit-label {
  color: #606266;
  font-size: 14px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-bottom: 15px;
  line-height: 1.4;
}

.alert-config {
  margin-top: 10px;
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
  border-left: 3px solid #409eff;
}

.smart-config-form .el-form-item {
  margin-bottom: 16px;
}

.smart-config-form .el-input-number {
  width: 120px;
}

/* 响应式设计 */
@media screen and (max-width: 1024px) {
  .page-content {
    flex-direction: column;
    gap: 15px;
  }

  .left-panel,
  .right-panel {
    flex: none;
  }

  .right-panel {
    order: -1;
    max-height: none;
  }
}

@media screen and (max-width: 768px) {
  .page-header {
    padding: 12px 16px;
  }

  .page-content {
    padding: 16px;
  }
  
  .header-left {
    gap: 12px;
  }
  
  .header-info h2 {
    font-size: 16px;
  }
  
  .analysis-option .el-radio__label,
  .type-card .el-radio__label {
    padding: 10px 35px 10px 10px;
  }
}
</style> 