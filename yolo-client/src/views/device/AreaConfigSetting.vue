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
          <h2>区域设置</h2>
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
                <el-tag type="success">
                  当前：区域绘制
                </el-tag>
              </div>
            </div>
          </template>

          <!-- 设备画面预览和绘制区域 -->
          <div class="image-preview-container">
            <div v-if="imageLoading" class="loading-wrapper">
              <el-skeleton animated :rows="8" />
              <div class="loading-text">正在获取设备画面...</div>
            </div>
            <div v-else-if="imageError" class="error-wrapper">
              <el-icon :size="64">
                <CircleClose />
              </el-icon>
              <p>{{ imageError }}</p>
              <div class="error-actions">
                <el-button @click="loadDeviceImage" type="primary">重试</el-button>
              </div>
              <div class="error-tips">
                <p><strong>设备抓图失败的可能原因：</strong></p>
                <ul>
                  <li>设备离线或网络不通</li>
                  <li>设备用户名或密码错误</li>
                  <li>设备不支持抓图API</li>
                  <li>后端服务未启动或配置错误</li>
                  <li>网络防火墙阻止后端访问设备</li>
                </ul>
                <p>建议：检查设备连接状态和后端服务状态</p>
              </div>
            </div>
            <div v-else-if="!deviceImage" class="image-placeholder">
              <el-icon :size="64">
                <VideoCamera />
              </el-icon>
              <p>暂无设备画面</p>
            </div>
            <div v-else class="image-wrapper">
              <img ref="deviceImageRef" :src="deviceImage" class="device-image" @load="onImageLoaded" />
              <canvas ref="drawingCanvas" class="drawing-canvas" @mousedown="handleMouseDown"
                @mousemove="handleMouseMove" @contextmenu.prevent="handleRightClick">
              </canvas>
              <div class="drawing-controls">
                <el-button type="primary" @click="startDrawing">开始绘制</el-button>
                <el-button @click="clearDrawing">清除</el-button>
              </div>
            </div>
          </div>

          <div class="drawing-hints">
            <el-alert title="绘制提示" type="info" :closable="false">
              <p>• 左键点击添加顶点</p>
              <p>• 右键点击完成绘制</p>
            </el-alert> 
          </div>
        </el-card>
      </div>
    
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, VideoCamera, CircleClose } from '@element-plus/icons-vue';
import deviceApi from '@/api/device';

export default defineComponent({
  name: 'AreaConfigSetting',
  components: {
    ArrowLeft,
    VideoCamera,
    CircleClose
  },
  setup() {
    const router = useRouter();
    const route = useRoute();

    // 获取路由参数
    const deviceId = route.params.deviceId;

    // 响应式数据
    const saveLoading = ref(false);
    const deviceInfo = ref(null);

    // 配置表单数据
    const configForm = reactive({
      coordinates: {
        points: [],
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

    // 设备抓图相关
    const isSnapshotLoading = ref(false);

    // 页面操作方法
    const goBack = () => {
      router.go(-1);
    };

    const resetConfig = () => {
      configForm.coordinates = {
        points: [],
      };
      clearDrawing();
      ElMessage.success('配置已重置');
    };

    const saveConfig = async () => {
      try {
        // 智能方案的验证逻辑
        if (!configForm.coordinates.points || configForm.coordinates.points.length < 3) {
          throw new Error('请绘制有效的区域，至少需要3个点');
        }

        saveLoading.value = true;

        await deviceApi.updateDevice(deviceId, {
          area_coordinates: configForm.coordinates
        });

        ElMessage.success('区域配置保存成功');
        goBack();
      } catch (error) {
        ElMessage.error(`保存失败: ${error.message}`);
      } finally {
        saveLoading.value = false;
      }
    };

    const canSave = () => {
      return configForm.coordinates.points.length > 2;
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

    const loadDeviceImage = async () => {
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

      // 使用设备API实时抓图
      loadDeviceSnapshot(ipAddress, channel);
    };

    // 通过设备API实时抓图
    const loadDeviceSnapshot = async (ipAddress, channel) => {
      try {
        isSnapshotLoading.value = true;
        imageLoading.value = true;
        imageError.value = null;
              
        // 通过后端API获取设备抓图，避免CORS问题
        const response = await fetch('/api/v1/devices/snapshot', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            device_id: deviceInfo.value.device_id,
            ip_address: ipAddress,
            device_type: deviceInfo.value.device_type,
            channel: channel || 1,
            username: deviceInfo.value.username,
            password: deviceInfo.value.password
          })
        });
        
        if (response.ok) {
          
          // 获取图像数据并转换为blob URL
          const blob = await response.blob();
          const imageUrl = window.URL.createObjectURL(blob);
          
          // 更新设备图片
          deviceImage.value = imageUrl;
          imageLoading.value = false;
          imageError.value = null;
          
          ElMessage.success('设备画面刷新成功');
        } else {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (error) {
        imageError.value = `设备抓图失败: ${error.message}`;
        imageLoading.value = false;
        
      } finally {
        isSnapshotLoading.value = false;
      }
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

        ctx.closePath();
        ctx.fillStyle = 'rgba(0, 255, 0, 0.15)';
        ctx.fill();

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
      isDrawing.value = true;
      points.value = [];
      configForm.coordinates.points = [];
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

      if (!isDrawing.value || points.value.length < 3) return;

      configForm.coordinates.points = [...points.value];
      drawPolygon(points.value);
      isDrawing.value = false;

      ElMessage.success('区域绘制完成');
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

          if (!isDrawing.value && points.value.length >= 3) {
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
        const response = await deviceApi.getDevice(deviceId);
        deviceInfo.value = response.data;
        deviceInfo.value = deviceInfo.value || { device_id: deviceId, device_name: '未知设备' };

        Object.assign(configForm.coordinates, deviceInfo.value.area_coordinates);

        // 加载设备图片
        setTimeout(() => {
            loadDeviceImage();
          }, 100);
      } catch (error) {
        console.error('获取设备列表失败:', error);
      }
    };

    // 初始化
    onMounted(async () => {
      await loadDeviceList();
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
      isSnapshotLoading,
      goBack,
      resetConfig,
      saveConfig,
      canSave,
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
  flex: 0.5; 
  display: flex;
  flex-direction: column;
}

.drawing-card {
  height: 100%;
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

.error-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.error-tips {
  margin-top: 15px;
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
  padding: 10px;
  background-color: #fde2e2;
  border: 1px solid #faeced;
  border-radius: 4px;
}

.error-tips p {
  margin-bottom: 5px;
}

.error-tips ul {
  margin-bottom: 10px;
  padding-left: 20px;
}

.error-tips li {
  list-style: disc;
  margin-bottom: 3px;
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

</style> 