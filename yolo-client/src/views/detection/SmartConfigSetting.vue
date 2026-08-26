<template>
  <div class="smart-config-setting-page">
    <header class="page-header">
      <div class="header-left">
        <el-button @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="header-info">
          <h2>智能方案设置</h2>
          <p v-if="deviceInfo">{{ deviceInfo.device_name }} · {{ deviceInfo.device_id }}</p>
        </div>
      </div>
      <div class="header-right">
        <el-button @click="resetConfig">重置</el-button>
        <el-button type="primary" @click="saveConfig" :loading="saveLoading">保存配置</el-button>
      </div>
    </header>

    <div class="page-body">
      <!-- 场景列表 -->
      <el-card class="section-card scenario-table-card" shadow="never">
        <template #header>
          <div class="card-title-row card-title-row--start">
            <el-dropdown trigger="click" @command="addScenario">
              <el-button type="primary">添加场景</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <template v-for="group in scenarioGroups" :key="group.key">
                    <el-dropdown-item disabled class="menu-group-label">{{ group.label }}</el-dropdown-item>
                    <el-dropdown-item v-for="item in group.items" :key="item.type" :command="item.type">
                      {{ item.label }}
                    </el-dropdown-item>
                  </template>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <!-- <span class="section-title">场景列表</span> -->
          </div>
        </template>
        <div class="scenario-table-wrap">
          <el-table
            :data="multiConfig.scenarios"
            row-key="id"
            height="200"
            table-layout="fixed"
            highlight-current-row
            :current-row-key="activeScenarioId"
            empty-text="暂无场景"
            :row-class-name="getRowClassName"
            @row-click="(row) => selectScenario(row.id)"
            class="scenario-table"
          >
            <el-table-column label="序号" align="center">
              <template #default="{ $index }">{{ $index + 1 }}</template>
            </el-table-column>
            <el-table-column label="名称" align="center">
              <template #default="{ row }">
                <el-input v-model="row.name" class="table-input" @click.stop />
              </template>
            </el-table-column>
            <el-table-column label="类型" align="center" show-overflow-tooltip>
              <template #default="{ row }">{{ getRuleDisplayType(row) }}</template>
            </el-table-column>
            <el-table-column label="启用" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" @click.stop />
              </template>
            </el-table-column>
            <el-table-column label="操作" align="center">
              <template #default="{ row }">
                <el-button type="danger" link @click.stop="removeScenario(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <!-- 画线 + 参数 -->
      <div class="workspace">
        <el-card class="section-card preview-card" shadow="never">
          <template #header>
            <div class="card-title-row card-title-row--start">
              <span class="section-title">画线设置</span>
              <el-tag v-if="activeScenario" size="small" type="success" class="section-subtitle-tag">
                {{ activeScenario.name }}
              </el-tag>
            </div>
          </template>

          <div class="preview-body">
            <div class="image-preview-container">
              <div v-if="imageLoading" class="state-box">
                <el-skeleton animated :rows="5" />
              </div>
              <div v-else-if="imageError" class="state-box error">
                <p>{{ imageError }}</p>
                <el-button type="primary" @click="loadDeviceImage">重试</el-button>
              </div>
              <div v-else-if="!deviceImage" class="state-box">
                <el-icon :size="40"><VideoCamera /></el-icon>
                <p>暂无画面</p>
              </div>
              <div v-else class="image-wrapper">
                <img ref="deviceImageRef" :src="deviceImage" class="device-image" @load="onImageLoaded" />
                <canvas
                  ref="drawingCanvas"
                  class="drawing-canvas"
                  @mousedown="handleMouseDown"
                  @mousemove="handleMouseMove"
                  @contextmenu.prevent="handleRightClick"
                />
              </div>
            </div>
            <div class="draw-actions">
              <el-button type="primary" @click="startDrawing" :disabled="!activeScenario">
                {{ isMultiAreaOccupancy() ? '绘制区域' : '开始绘制' }}
              </el-button>
              <el-button v-if="isMultiAreaOccupancy() && isDrawing" @click="finishDrawingAll">
                完成全部
              </el-button>
              <el-button @click="clearDrawing" :disabled="!activeScenario">清除</el-button>
              <el-button @click="loadDeviceImage" :loading="isSnapshotLoading">刷新画面</el-button>
            </div>
          </div>
        </el-card>

        <el-card class="section-card config-card" shadow="never">
          <template #header>
            <span class="section-title">场景配置</span>
          </template>
          <div class="config-layout">
            <div class="config-main">
              <div class="config-block">
                <div class="block-title">
                  {{ activeScenario ? activeScenario.name : '场景参数' }}
                  <span v-if="activeScenario" class="block-subtitle">{{ getRuleDisplayType(activeScenario) }}</span>
                </div>

                <el-empty v-if="!activeScenario" description="请选择场景" :image-size="56" />

                <el-form v-else label-position="top" class="param-form">
            <!-- 聚集 / 离岗 / 徘徊 -->
            <template v-if="isDurationScenario(activeScenario)">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item :label="activeScenario.type === 'leave_post' ? '最少在岗人数' : '人数阈值'">
                    <el-input-number v-model="activeScenario.params.minPersons" :min="1" :max="100" controls-position="right" class="ctrl-full" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="持续时长">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.params.durationSec" :min="5" :max="3600" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">秒</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </template>

            <!-- 绊线 / 人流 -->
            <template v-if="isLineScenario(activeScenario)">
              <el-form-item label="检测模式">
                <el-radio-group v-model="activeScenario.behaviorSubtype" v-if="activeScenario.type === 'behavior'">
                  <el-radio value="simple">普通检测</el-radio>
                  <el-radio value="directional">方向检测</el-radio>
                </el-radio-group>
                <el-select
                  v-else-if="activeScenario.catalogType === 'flow_count' || activeScenario.countingType === 'flow'"
                  v-model="activeScenario.flowDirection"
                  class="ctrl-full"
                >
                  <el-option label="双向统计" value="bidirectional" />
                  <el-option label="仅进入" value="in" />
                  <el-option label="仅离开" value="out" />
                </el-select>
                <el-radio-group v-else v-model="activeScenario.behaviorSubtype">
                  <el-radio value="simple">双向穿越</el-radio>
                  <el-radio value="directional">单向穿越</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item
                v-if="activeScenario.behaviorSubtype === 'directional' || activeScenario.flowDirection === 'in' || activeScenario.flowDirection === 'out'"
                label="穿越方向"
              >
                <el-radio-group
                  v-if="activeScenario.catalogType !== 'flow_count' && activeScenario.countingType !== 'flow'"
                  v-model="activeScenario.behaviorDirection"
                >
                  <el-radio value="in">进入</el-radio>
                  <el-radio value="out">离开</el-radio>
                </el-radio-group>
                <el-select v-else v-model="activeScenario.flowPeriod" class="ctrl-full">
                  <el-option label="向下为进入" value="detect_in" />
                  <el-option label="向上为进入" value="detect_out" />
                </el-select>
              </el-form-item>
            </template>

            <!-- 区域入侵 -->
            <template v-if="activeScenario.catalogType === 'area_intrusion'">
              <el-form-item label="检测模式">
                <el-radio-group v-model="activeScenario.behaviorSubtype">
                  <el-radio value="simple">进入/离开</el-radio>
                  <el-radio value="directional">指定方向</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="activeScenario.behaviorSubtype === 'directional'" label="触发方向">
                <el-radio-group v-model="activeScenario.behaviorDirection">
                  <el-radio value="in">进入区域</el-radio>
                  <el-radio value="out">离开区域</el-radio>
                </el-radio-group>
              </el-form-item>
            </template>

            <!-- 区域人数 -->
            <template v-if="isOccupancyScenario(activeScenario)">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="统计间隔">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.countingInterval" :min="1" :max="60" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">秒</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="最大容量">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.maxCapacity" :min="1" :max="1000" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">人</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="平滑窗口">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.smoothWindow" :min="1" :max="10" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">帧</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="下降延迟">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.decreaseHoldFrames" :min="0" :max="10" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">次</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="校正偏移">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.countBias" :min="-50" :max="50" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">人</span>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="校正系数">
                    <el-input-number v-model="activeScenario.countScale" :min="0.5" :max="2" :step="0.05" :precision="2" controls-position="right" class="ctrl-full" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-form-item label="判定点">
                    <el-select v-model="activeScenario.countPointMode" class="ctrl-full">
                      <el-option label="脚点（推荐）" value="foot" />
                      <el-option label="框中心" value="center" />
                      <el-option label="底边三点" value="bottom_edge" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="稳定帧数">
                    <div class="input-with-unit">
                      <el-input-number v-model="activeScenario.countMinHits" :min="1" :max="10" controls-position="right" class="ctrl-full" />
                      <span class="unit-label">帧</span>
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="超限报警">
                <el-switch v-model="activeScenario.enableAlert" />
              </el-form-item>
              <el-form-item v-if="activeScenario.enableAlert" label="报警阈值">
                <div class="input-with-unit">
                  <el-input-number v-model="activeScenario.alertThreshold" :min="1" :max="1000" controls-position="right" />
                  <span class="unit-label">人</span>
                </div>
              </el-form-item>
              <div v-if="activeScenario.occupancyAreas?.length" class="occupancy-area-list">
                <div class="area-list-title">已绘制区域（{{ activeScenario.occupancyAreas.length }}）</div>
                <div v-for="(area, index) in activeScenario.occupancyAreas" :key="area.id" class="occupancy-area-item">
                  <span class="area-color-dot" :style="{ backgroundColor: getAreaColor(index).stroke }"></span>
                  <el-input v-model="area.name" class="area-name-input" />
                  <el-button type="danger" link @click="removeOccupancyArea(index)">删除</el-button>
                </div>
              </div>
            </template>
                </el-form>
              </div>

              <div class="config-block config-block-muted">
                <div class="block-title">推送设置</div>
                <el-form label-position="top" class="param-form">
                  <el-row :gutter="12">
                    <el-col :span="14">
                      <el-form-item label="推送标签">
                        <el-input v-model="multiConfig.pushLabel" placeholder="可选" maxlength="50" show-word-limit />
                      </el-form-item>
                    </el-col>
                    <el-col :span="10">
                      <el-form-item label="推送间隔">
                        <div class="input-with-unit">
                          <el-input-number v-model="multiConfig.alarm_interval" :min="0" :max="3600" controls-position="right" class="ctrl-full" />
                          <span class="unit-label">秒</span>
                        </div>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-form>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, VideoCamera } from '@element-plus/icons-vue';
import deviceApi from '@/api/device';
import { detectionConfigApi } from '@/api/detection';
import {
  SCENARIO_GROUPS,
  createScenario,
  migrateAreaCoordinates,
  buildAreaCoordinatesPayload,
  getRuleDisplayType,
  shouldCloseScenarioArea,
  validateScenario,
  createDefaultRuleName,
  isDurationScenario,
  isLineScenario,
  isOccupancyScenario,
} from '@/utils/smartScenarios';

export default defineComponent({
  name: 'SmartConfigSetting',
  components: { ArrowLeft, VideoCamera },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const configId = route.params.configId;

    const saveLoading = ref(false);
    const deviceInfo = ref(null);
    const deviceList = ref([]);
    const activeScenarioId = ref(null);
    const scenarioGroups = SCENARIO_GROUPS;

    const multiConfig = reactive({
      version: 2,
      alarm_interval: 15,
      pushLabel: '',
      scenarios: [],
    });

    const activeScenario = computed(() =>
      multiConfig.scenarios.find((item) => item.id === activeScenarioId.value) || null
    );

    const imageLoading = ref(false);
    const imageError = ref(null);
    const deviceImage = ref(null);
    const deviceImageRef = ref(null);
    const drawingCanvas = ref(null);
    let canvasResizeObserver = null;
    const isDrawing = ref(false);
    const points = ref([]);
    const isSnapshotLoading = ref(false);

    const AREA_COLORS = [
      { stroke: '#00ff00', fill: 'rgba(0, 255, 0, 0.15)' },
      { stroke: '#00aaff', fill: 'rgba(0, 170, 255, 0.15)' },
      { stroke: '#ff9900', fill: 'rgba(255, 153, 0, 0.15)' },
      { stroke: '#ff44aa', fill: 'rgba(255, 68, 170, 0.15)' },
      { stroke: '#aa44ff', fill: 'rgba(170, 68, 255, 0.15)' },
    ];

    const isMultiAreaOccupancy = () => isOccupancyScenario(activeScenario.value);

    const createAreaId = () => `area-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const getOccupancyAreaDevicePrefix = () => deviceInfo.value?.device_id || 'device';
    const formatOccupancyAreaName = (index) => `${getOccupancyAreaDevicePrefix()}-${index}`;

    const getNextOccupancyAreaIndex = () => {
      const prefix = getOccupancyAreaDevicePrefix();
      const areas = activeScenario.value?.occupancyAreas || [];
      const usedIndexes = new Set();
      for (const area of areas) {
        const name = area?.name;
        if (typeof name === 'string' && name.startsWith(`${prefix}-`)) {
          const suffix = parseInt(name.slice(prefix.length + 1), 10);
          if (!Number.isNaN(suffix) && suffix > 0) usedIndexes.add(suffix);
        }
      }
      let next = 1;
      while (usedIndexes.has(next)) next += 1;
      return next;
    };

    const getAreaColor = (index) => AREA_COLORS[index % AREA_COLORS.length];

    const normalizeOccupancyAreas = (scenario) => {
      if (!scenario || scenario.countingType !== 'occupancy') return;
      if (Array.isArray(scenario.occupancyAreas) && scenario.occupancyAreas.length > 0) return;
      if (scenario.points?.length >= 3) {
        scenario.occupancyAreas = [{ id: createAreaId(), name: formatOccupancyAreaName(1), points: [...scenario.points] }];
      } else if (!scenario.occupancyAreas) {
        scenario.occupancyAreas = [];
      }
    };

    const syncOccupancyPoints = () => {
      if (!isMultiAreaOccupancy() || !activeScenario.value) return;
      const areas = activeScenario.value.occupancyAreas || [];
      activeScenario.value.points = areas.length > 0 ? [...areas[0].points] : [];
    };

    const getOccupancyAreaCount = () => (activeScenario.value?.occupancyAreas || []).length;

    const getRowClassName = ({ row }) => (row.id === activeScenarioId.value ? 'is-active-row' : '');

    const selectScenario = (scenarioId) => {
      activeScenarioId.value = scenarioId;
      points.value = [];
      isDrawing.value = false;
      redrawCanvas();
    };

    const addScenario = (type) => {
      try {
        const scenario = createScenario(type);
        scenario.name = createDefaultRuleName(multiConfig.scenarios.length + 1);
        multiConfig.scenarios.push(scenario);
        selectScenario(scenario.id);
      } catch (error) {
        ElMessage.warning(error.message);
      }
    };

    const removeScenario = (scenarioId) => {
      const index = multiConfig.scenarios.findIndex((item) => item.id === scenarioId);
      if (index === -1) return;
      multiConfig.scenarios.splice(index, 1);
      if (activeScenarioId.value === scenarioId) {
        activeScenarioId.value = multiConfig.scenarios[0]?.id || null;
      }
      redrawCanvas();
    };

    const goBack = () => router.go(-1);

    const resetConfig = () => {
      multiConfig.alarm_interval = 15;
      multiConfig.pushLabel = '';
      multiConfig.scenarios = [];
      activeScenarioId.value = null;
      clearDrawing();
      ElMessage.success('已重置');
    };

    const syncOccupancyPointsForScenario = (scenario) => {
      const areas = scenario.occupancyAreas || [];
      scenario.points = areas.length > 0 ? [...areas[0].points] : [];
    };

    const saveConfig = async () => {
      try {
        const enabledScenarios = multiConfig.scenarios.filter((item) => item.enabled !== false);
        for (let i = 0; i < enabledScenarios.length; i += 1) {
          if (isOccupancyScenario(enabledScenarios[i])) {
            normalizeOccupancyAreas(enabledScenarios[i]);
            syncOccupancyPointsForScenario(enabledScenarios[i]);
          }
          validateScenario(enabledScenarios[i], i);
        }
        saveLoading.value = true;
        const payload = buildAreaCoordinatesPayload(multiConfig);
        await detectionConfigApi.updateConfig(configId, {
          area_coordinates: payload.scenarios.length ? payload : {
            version: 2, scenarios: [], alarm_interval: payload.alarm_interval, pushLabel: payload.pushLabel,
          },
        });
        ElMessage.success('保存成功');
        goBack();
      } catch (error) {
        ElMessage.error(error.message || '保存失败');
      } finally {
        saveLoading.value = false;
      }
    };

    const getShouldCloseArea = () => shouldCloseScenarioArea(activeScenario.value);

    const handleDetectionTypeChange = () => {
      clearDrawing();
      if (!activeScenario.value) return;
      activeScenario.value.behaviorSubtype = 'simple';
      activeScenario.value.behaviorDirection = 'in';
      activeScenario.value.points = [];
    };

    const handleCountingTypeChange = () => {
      clearDrawing();
      if (!activeScenario.value) return;
      activeScenario.value.occupancyAreas = [];
      activeScenario.value.points = [];
    };

    const getImageDisplayRect = () => {
      const image = deviceImageRef.value;
      const wrapper = image?.parentElement;
      if (!image || !wrapper || !image.naturalWidth || !image.naturalHeight) return null;
      const containerWidth = wrapper.clientWidth;
      const containerHeight = wrapper.clientHeight;
      if (!containerWidth || !containerHeight) return null;
      const imageRatio = image.naturalWidth / image.naturalHeight;
      const containerRatio = containerWidth / containerHeight;
      let displayWidth, displayHeight, offsetX, offsetY;
      if (imageRatio > containerRatio) {
        displayWidth = containerWidth;
        displayHeight = containerWidth / imageRatio;
        offsetX = 0;
        offsetY = (containerHeight - displayHeight) / 2;
      } else {
        displayHeight = containerHeight;
        displayWidth = containerHeight * imageRatio;
        offsetX = (containerWidth - displayWidth) / 2;
        offsetY = 0;
      }
      return { displayWidth, displayHeight, offsetX, offsetY };
    };

    const syncCanvasLayout = () => {
      if (!drawingCanvas.value || !deviceImageRef.value) return false;
      const rect = getImageDisplayRect();
      if (!rect) return false;
      const canvas = drawingCanvas.value;
      const { displayWidth, displayHeight, offsetX, offsetY } = rect;
      const dpr = window.devicePixelRatio || 1;
      canvas.style.left = `${offsetX}px`;
      canvas.style.top = `${offsetY}px`;
      canvas.style.width = `${displayWidth}px`;
      canvas.style.height = `${displayHeight}px`;
      canvas.width = Math.round(displayWidth * dpr);
      canvas.height = Math.round(displayHeight * dpr);
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return true;
    };

    const refreshCanvasDrawing = () => { if (syncCanvasLayout()) redrawCanvas(); };

    const setupCanvasResizeObserver = () => {
      if (canvasResizeObserver) { canvasResizeObserver.disconnect(); canvasResizeObserver = null; }
      const wrapper = deviceImageRef.value?.parentElement;
      if (!wrapper || typeof ResizeObserver === 'undefined') return;
      canvasResizeObserver = new ResizeObserver(() => refreshCanvasDrawing());
      canvasResizeObserver.observe(wrapper);
    };

    const onImageLoaded = () => {
      requestAnimationFrame(() => { refreshCanvasDrawing(); setupCanvasResizeObserver(); });
    };

    const getDeviceImageUrl = (ipAddress, channel) =>
      `/api/v2/data-listeners/images/${encodeURIComponent(`storage/devices/${ipAddress}_ch${channel}.jpg`)}`;

    const loadDeviceImage = async () => {
      if (!deviceInfo.value) return;
      const ipAddress = deviceInfo.value.ip_address || deviceInfo.value.device_ip;
      const channel = deviceInfo.value.channel || 1;
      if (!ipAddress) { imageError.value = '设备 IP 不可用'; return; }
      await loadDeviceSnapshot(ipAddress, channel);
    };

    const loadDeviceList = async () => {
      try {
        const response = await deviceApi.getDevices();
        deviceList.value = response.data.data;
      } catch (error) {
        console.error('获取设备列表失败:', error);
      }
    };

    const loadDeviceSnapshot = async (ipAddress, channel) => {
      try {
        isSnapshotLoading.value = true;
        imageLoading.value = true;
        imageError.value = null;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const response = await fetch('/api/v1/devices/snapshot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: deviceInfo.value.device_id,
            ip_address: ipAddress,
            device_type: deviceInfo.value.device_type,
            channel: channel || 1,
            username: deviceInfo.value.username,
            password: deviceInfo.value.password,
          }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          deviceImage.value = window.URL.createObjectURL(await response.blob());
          imageLoading.value = false;
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch {
        const fallbackImageUrl = getDeviceImageUrl(ipAddress, channel);
        const img = new Image();
        img.onload = () => { deviceImage.value = fallbackImageUrl; imageLoading.value = false; imageError.value = null; };
        img.onerror = () => { imageLoading.value = false; imageError.value = '无法获取设备画面'; };
        img.src = `${fallbackImageUrl}?t=${Date.now()}`;
      } finally {
        isSnapshotLoading.value = false;
      }
    };

    const drawPolygonShape = (ctx, polygonPoints, displayWidth, displayHeight, options = {}) => {
      const { strokeStyle = '#00ff00', fillStyle = 'rgba(0, 255, 0, 0.15)', shouldClose = false } = options;
      if (!polygonPoints?.length) return;
      ctx.save();
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 2;
      if (polygonPoints.length > 1) {
        ctx.beginPath();
        ctx.moveTo(Math.round(polygonPoints[0].x * displayWidth) + 0.5, Math.round(polygonPoints[0].y * displayHeight) + 0.5);
        for (let i = 1; i < polygonPoints.length; i++) {
          ctx.lineTo(Math.round(polygonPoints[i].x * displayWidth) + 0.5, Math.round(polygonPoints[i].y * displayHeight) + 0.5);
        }
        if (shouldClose && polygonPoints.length >= 3) { ctx.closePath(); ctx.fillStyle = fillStyle; ctx.fill(); }
        ctx.stroke();
      }
      polygonPoints.forEach((point) => {
        ctx.beginPath();
        ctx.arc(Math.round(point.x * displayWidth), Math.round(point.y * displayHeight), 4, 0, Math.PI * 2);
        ctx.fillStyle = '#ff4444';
        ctx.fill();
      });
      ctx.restore();
    };

    const startDrawing = () => {
      if (!activeScenario.value) return;
      isDrawing.value = true;
      points.value = [];
      if (!isMultiAreaOccupancy()) activeScenario.value.points = [];
    };

    const finishDrawingAll = () => {
      points.value = [];
      isDrawing.value = false;
      redrawCanvas();
    };

    const removeOccupancyArea = (index) => {
      activeScenario.value?.occupancyAreas?.splice(index, 1);
      syncOccupancyPoints();
      redrawCanvas();
    };

    const clearDrawing = () => {
      points.value = [];
      isDrawing.value = false;
      if (activeScenario.value) {
        if (isMultiAreaOccupancy()) activeScenario.value.occupancyAreas = [];
        activeScenario.value.points = [];
      }
      redrawCanvas();
    };

    const handleMouseDown = (e) => {
      if (!isDrawing.value) return;
      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      if (x < 0 || x > 1 || y < 0 || y > 1) return;
      points.value.push({ x, y });
      redrawCanvas();
    };

    const handleMouseMove = (e) => {
      if (!isDrawing.value || !points.value.length) return;
      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      if (x < 0 || x > 1 || y < 0 || y > 1) return;
      redrawCanvas({ x, y });
    };

    const handleRightClick = () => {
      const shouldClose = getShouldCloseArea();
      const minPoints = shouldClose ? 3 : 2;
      if (!isDrawing.value || points.value.length < minPoints) return;
      if (isMultiAreaOccupancy()) {
        const areaIndex = getNextOccupancyAreaIndex();
        if (!activeScenario.value.occupancyAreas) activeScenario.value.occupancyAreas = [];
        activeScenario.value.occupancyAreas.push({
          id: createAreaId(),
          name: formatOccupancyAreaName(areaIndex),
          points: [...points.value],
        });
        syncOccupancyPoints();
        points.value = [];
        redrawCanvas();
        return;
      }
      activeScenario.value.points = [...points.value];
      isDrawing.value = false;
      redrawCanvas();
    };

    const redrawCanvas = (previewPoint = null) => {
      if (!drawingCanvas.value) return;
      const canvas = drawingCanvas.value;
      const ctx = canvas.getContext('2d');
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      const scenario = activeScenario.value;
      if (!scenario) return;

      const scenarioIndex = multiConfig.scenarios.findIndex((item) => item.id === scenario.id);
      const color = getAreaColor(scenarioIndex >= 0 ? scenarioIndex : 0);

      if (isOccupancyScenario(scenario)) {
        (scenario.occupancyAreas || []).forEach((area, areaIndex) => {
          const areaColor = getAreaColor(areaIndex);
          drawPolygonShape(ctx, area.points, w, h, {
            strokeStyle: areaColor.stroke,
            fillStyle: areaColor.fill,
            shouldClose: true,
          });
        });
      } else if (scenario.points?.length > 0 && !isDrawing.value) {
        drawPolygonShape(ctx, scenario.points, w, h, {
          strokeStyle: color.stroke,
          fillStyle: color.fill,
          shouldClose: shouldCloseScenarioArea(scenario),
        });
      }

      if (points.value.length > 0) {
        const drawColor = isMultiAreaOccupancy() ? getAreaColor(getOccupancyAreaCount()) : color;
        drawPolygonShape(ctx, points.value, w, h, {
          strokeStyle: drawColor.stroke,
          fillStyle: drawColor.fill,
          shouldClose: false,
        });
        if (previewPoint && points.value.length) {
          const last = points.value[points.value.length - 1];
          ctx.beginPath();
          ctx.strokeStyle = drawColor.stroke;
          ctx.moveTo(last.x * w, last.y * h);
          ctx.lineTo(previewPoint.x * w, previewPoint.y * h);
          ctx.stroke();
        }
      }
    };

    const loadConfigData = async () => {
      try {
        const response = await detectionConfigApi.getConfig(configId);
        const config = response.data?.data ?? response.data;
        if (!config) return;
        deviceInfo.value = deviceList.value.find((d) => d.device_id === config.device_id)
          || { device_id: config.device_id, device_name: config.device_name || '未知设备' };
        if (config.area_coordinates && Object.keys(config.area_coordinates).length > 0) {
          const migrated = migrateAreaCoordinates(config.area_coordinates);
          multiConfig.alarm_interval = migrated.alarm_interval;
          multiConfig.pushLabel = migrated.pushLabel;
          multiConfig.scenarios.splice(0, multiConfig.scenarios.length, ...migrated.scenarios);
          multiConfig.scenarios.forEach((s) => {
            if (isOccupancyScenario(s)) normalizeOccupancyAreas(s);
            if (s.params == null) s.params = {};
            if (s.enabled == null) s.enabled = true;
          });
          activeScenarioId.value = multiConfig.scenarios[0]?.id || null;
        }
        setTimeout(loadDeviceImage, 100);
      } catch (error) {
        ElMessage.error('加载配置失败');
      }
    };

    onMounted(async () => {
      await loadDeviceList();
      await loadConfigData();
      window.addEventListener('resize', refreshCanvasDrawing);
    });

    watch(activeScenarioId, () => {
      points.value = [];
      isDrawing.value = false;
      redrawCanvas();
    });

    onUnmounted(() => {
      window.removeEventListener('resize', refreshCanvasDrawing);
      canvasResizeObserver?.disconnect();
    });

    return {
      multiConfig, activeScenario, activeScenarioId, scenarioGroups,
      getRuleDisplayType, isDurationScenario, isLineScenario, isOccupancyScenario,
      addScenario, removeScenario, selectScenario, getRowClassName,
      deviceInfo, saveLoading, imageLoading, imageError, deviceImage, deviceImageRef, drawingCanvas,
      isDrawing, isSnapshotLoading, isMultiAreaOccupancy, getAreaColor,
      finishDrawingAll, removeOccupancyArea, goBack, resetConfig, saveConfig,
      getShouldCloseArea, handleDetectionTypeChange, handleCountingTypeChange,
      startDrawing, clearDrawing, handleMouseDown, handleMouseMove, handleRightClick,
      onImageLoaded, loadDeviceImage,
    };
  },
});
</script>

<style scoped>
.smart-config-setting-page {
  --page-margin-x: 16px;
  --page-padding-x: 20px;
  --page-padding-y: 14px;
  --title-size: 17px;
  --body-size: 13px;
  --ctrl-height: 32px;

  min-height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  padding: var(--page-margin-x) var(--page-margin-x) var(--page-margin-x);
  background: #f0f2f5;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--page-padding-y) var(--page-padding-x);
  margin: 0 0 12px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--body-size);
}

.header-info h2 {
  margin: 0 0 2px;
  font-size: var(--title-size);
  font-weight: 600;
  color: #303133;
  line-height: 1.3;
}

.header-info p {
  margin: 0;
  font-size: var(--body-size);
  color: #909399;
  line-height: 1.4;
}

.header-right {
  display: flex;
  gap: 8px;
}

.page-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0;
  margin: 0;
}

.section-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  font-size: var(--body-size);
}

.section-card :deep(.el-card__header) {
  padding: var(--page-padding-y) var(--page-padding-x);
  border-bottom: 1px solid #f0f0f0;
  min-height: var(--ctrl-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
}

.section-card :deep(.el-card__body) {
  padding: var(--page-padding-y) var(--page-padding-x);
}

.section-title {
  font-size: var(--title-size);
  font-weight: 600;
  color: #303133;
  line-height: 1.3;
}

.section-subtitle-tag {
  font-size: var(--body-size);
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.card-title-row--start {
  justify-content: flex-start;
  gap: 12px;
}

.device-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
}

.drawing-canvas {
  position: absolute;
  top: 0;
  left: 0;
  cursor: crosshair;
  z-index: 1;
}

.scenario-table-card :deep(.el-card__body) {
  padding: 0 var(--page-padding-x) var(--page-padding-y);
}

.scenario-table-wrap {
  min-height: 200px;
}

.scenario-table :deep(.el-table__cell) {
  padding: 10px 0;
  font-size: var(--body-size);
}

.scenario-table :deep(.el-input__wrapper) {
  min-height: 32px;
}

.scenario-table :deep(.el-table__header .cell) {
  font-size: var(--body-size);
  color: #606266;
}

.scenario-table :deep(.table-input .el-input__wrapper) {
  box-shadow: none;
  background: transparent;
}

.scenario-table :deep(.table-input .el-input__inner) {
  text-align: center;
  font-size: var(--body-size);
}

.scenario-table :deep(.table-input .el-input__wrapper:hover),
.scenario-table :deep(.table-input .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
  background: #fff;
}

.scenario-table-card :deep(.is-active-row) {
  background-color: #ecf5ff !important;
}

.workspace {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 12px;
  align-items: start;
}

.preview-card,
.config-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.preview-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  padding: var(--page-padding-y) var(--page-padding-x);
}

.config-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  padding: 0;
}

.config-layout {
  display: flex;
  flex-direction: column;
}

.config-main {
  padding: var(--page-padding-y) var(--page-padding-x);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.image-preview-container {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  background: #111;
  border-radius: 6px;
  overflow: hidden;
}

.state-box {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #909399;
  padding: 16px;
  font-size: var(--body-size);
}

.state-box.error { color: #f56c6c; }

.image-wrapper {
  position: absolute;
  inset: 0;
}

.draw-actions {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: var(--ctrl-height);
  align-items: center;
}

.draw-actions :deep(.el-button) {
  font-size: var(--body-size);
}

.config-block {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: var(--page-padding-y) var(--page-padding-x);
  background: #fff;
  font-size: var(--body-size);
}

.config-block-muted {
  background: #fafafa;
}

.block-title {
  font-size: var(--title-size);
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  line-height: 1.3;
}

.block-subtitle {
  font-size: var(--body-size);
  font-weight: 400;
  color: #909399;
}

.ctrl-full {
  width: 100%;
}

.param-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.param-form :deep(.el-form-item__label) {
  font-size: var(--body-size);
  color: #606266;
  padding-bottom: 2px;
  line-height: 1.4;
}

.param-form :deep(.el-input-number),
.param-form :deep(.el-select),
.param-form :deep(.el-input),
.param-form :deep(.el-radio__label) {
  font-size: var(--body-size);
}

.param-form :deep(.el-input-number),
.param-form :deep(.el-select),
.param-form :deep(.el-input) {
  width: 100%;
}

.param-form :deep(.el-input__wrapper),
.param-form :deep(.el-select__wrapper) {
  min-height: var(--ctrl-height);
}

.param-form :deep(.el-input-number .el-input__wrapper) {
  min-height: var(--ctrl-height);
}

.param-form :deep(.el-radio-group) {
  min-height: var(--ctrl-height);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.input-with-unit {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.input-with-unit .el-input-number {
  flex: 1;
}

.unit-label {
  flex-shrink: 0;
  font-size: var(--body-size);
  color: #909399;
}

.occupancy-area-list { margin-top: 4px; }

.area-list-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.occupancy-area-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.area-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.area-name-input { flex: 1; }

.menu-group-label {
  font-size: 12px !important;
  color: #909399 !important;
  cursor: default !important;
}

@media (max-width: 960px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
