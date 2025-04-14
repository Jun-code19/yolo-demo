<template>
  <div class="detection-config-page">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>检测配置管理</span>
          <el-button type="primary" @click="showAddModal">
            <el-icon>
              <plus />
            </el-icon>创建配置
          </el-button>
        </div>
      </template>

      <!-- 配置列表 -->
      <el-table :data="configList" v-loading="loading" style="width: 100%">
        <!-- 设备名称列 -->
        <el-table-column label="设备" prop="device_id" min-width="80">
          <template #default="scope">
            {{ getDeviceName(scope.row.device_id) }}
          </template>
        </el-table-column>

        <!-- 模型名称列 -->
        <el-table-column label="模型" prop="models_id" min-width="80">
          <template #default="scope">
            {{ getModelName(scope.row.models_id) }}
          </template>
        </el-table-column>

        <!-- 状态列 -->
        <el-table-column label="状态" prop="enabled" min-width="80">
          <template #default="scope">
            <el-tag :type="scope.row.enabled ? 'success' : 'danger'">
              {{ scope.row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 灵敏度列 -->
        <el-table-column label="灵敏度" prop="sensitivity" min-width="80">
        </el-table-column>

        <!-- 检测频率列 -->
        <el-table-column label="检测频率" prop="frequency" min-width="80">
          <template #default="scope">
            <el-tag :type="getFrequencyType(scope.row.frequency)">
              {{ getFrequencyLabel(scope.row.frequency) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 保存模式列 -->
        <el-table-column label="保存模式" prop="save_mode" min-width="80">
          <template #default="scope">
            <el-tag :type="getSaveModeType(scope.row.save_mode)">
              {{ getSaveModeLabel(scope.row.save_mode) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 区域设置列 -->
        <el-table-column label="区域设置" prop="area_coordinates" min-width="80">
          <template #default="scope">
            <el-tag>
              {{ getAreaTypeLabel(scope.row.area_coordinates) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 操作列 -->
        <el-table-column label="操作" min-width="120">
          <template #default="scope">
            <el-space>
              <el-button type="warning" size="small" @click="scope.row.enabled ? null : setInterestArea(scope.row)"
                :disabled="scope.row.enabled"> <!-- 禁用按钮 -->
                区域
              </el-button><!-- 设置感兴趣区域按钮 -->
              <el-button type="primary" size="small" @click="scope.row.enabled ? null : editConfig(scope.row)"
                :disabled="scope.row.enabled"> <!-- 禁用按钮 -->
                编辑
              </el-button>
              <el-button :type="scope.row.enabled ? 'danger' : 'success'" size="small"
                @click="toggleEnabled(scope.row)">
                {{ scope.row.enabled ? '禁用' : '启用' }}
              </el-button>
              <el-popconfirm title="确定要删除这个配置吗?" @confirm="deleteConfig(scope.row.config_id)">
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
    <el-dialog v-model="modalVisible" :title="isEdit ? '编辑检测配置' : '创建检测配置'" width="700px">
      <el-form ref="formRef" :model="formState" :rules="rules" label-position="top">
        <!-- 设备选择 -->
        <el-form-item label="设备" prop="device_id">
          <el-select v-model="formState.device_id" placeholder="请选择设备" :disabled="isEdit" style="width: 100%">
            <el-option v-for="device in deviceList" :key="device.device_id"
              :label="`${device.device_name} (${device.device_id})`" :value="device.device_id" />
          </el-select>
        </el-form-item>

        <!-- 模型选择 -->
        <el-form-item label="检测模型" prop="models_id">
          <el-select v-model="formState.models_id" placeholder="请选择检测模型" @change="updateTargetClasses"
            style="width: 100%">
            <el-option v-for="model in modelList" :key="model.models_id"
              :label="`${model.models_name} (${getModelTypeName(model.models_type)})`" :value="model.models_id" />
          </el-select>
        </el-form-item>

        <!-- 是否启用 -->
        <el-form-item label="状态" prop="enabled">
          <el-switch v-model="formState.enabled" />
        </el-form-item>

        <!-- 检测灵敏度 -->
        <el-form-item label="检测灵敏度" prop="sensitivity">
          <el-slider v-model="formState.sensitivity" :min="0.1" :max="0.9" :step="0.05" :show-tooltip="true" :marks="{
            0.1: '低',
            0.5: '中',
            0.9: '高'
          }" />
        </el-form-item>

        <!-- 目标类别 -->
        <el-form-item label="目标类别" prop="target_classes">
          <el-select v-model="formState.target_classes" multiple placeholder="请选择要检测的目标类别" style="width: 100%"
            collapse-tags collapse-tags-tooltip :max-collapse-tags="4">
            <el-option v-for="(classItem, index) in targetClasses" :key="classItem.value" :label="classItem.label"
              :value="classItem.value" />
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
            <el-radio value="none">暂无</el-radio>
            <el-radio value="screenshot">仅截图</el-radio>
            <el-radio value="video">仅视频</el-radio>
            <el-radio value="both">截图和视频</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 高级配置 -->
        <el-collapse>
          <el-collapse-item title="高级配置" name="1">
            <!-- 视频片段时长 -->
            <el-form-item label="视频片段时长(秒)" prop="save_duration" v-if="formState.save_mode !== 'screenshot'">
              <el-input-number v-model="formState.save_duration" :min="5" :max="60" :step="5" />
            </el-form-item>

            <!-- 事件保留天数 -->
            <el-form-item label="事件保留天数" prop="max_storage_days">
              <el-input-number v-model="formState.max_storage_days" :min="1" :max="90" :step="1" />
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

    <!-- 区域设置对话框 -->
    <el-dialog v-model="areaModalVisible" title="感兴趣区域设置" width="800px" destroy-on-close @close="stopPreview">
      <el-form :model="areaForm" label-position="top">
        <!-- 配置类型 -->
        <el-form-item label="配置类型">
          <el-radio-group v-model="areaForm.coordinates.type">
            <el-radio value="area">区域设置</el-radio>
            <el-radio value="line">拌线设置</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 新增检测模式选择 -->
        <el-form-item label="检测模式">
          <el-radio-group v-model="areaForm.coordinates.subtype" @change="handleSubtypeChange">
            <el-radio value="simple">普通检测</el-radio>
            <el-radio value="directional">方向检测</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 新增方向选择 -->
        <el-form-item label="检测方向" v-if="areaForm.coordinates.subtype === 'directional'">
          <el-radio-group v-model="areaForm.coordinates.direction" @change="updateDirectionArrow">
            <el-radio value="in">入方向</el-radio>
            <el-radio value="out">出方向</el-radio>
            <el-radio value="both">双向</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 视频预览和绘制区域 -->
        <div class="video-preview-container">
          <div v-if="previewLoading" class="loading-wrapper">
            <el-skeleton animated :rows="8" />
            <div class="loading-text">正在连接设备，请稍候...</div>
          </div>
          <div v-else-if="previewError" class="error-wrapper">
            <el-icon :size="64">
              <CircleClose />
            </el-icon>
            <p>{{ previewError }}</p>
            <el-button @click="retryPreview">重试</el-button>
          </div>
          <div v-else-if="!previewStream" class="video-placeholder">
            <el-icon :size="64">
              <VideoCamera />
            </el-icon>
            <p>等待视频流连接...</p>
          </div>
          <div v-else class="video-wrapper">
            <video ref="videoRef" class="preview-video" autoplay muted @loadedmetadata="onVideoLoaded">
            </video>
            <!-- 备用图像显示 -->
            <img v-if="currentFrame" :src="currentFrame" class="fallback-image"
              :style="{ display: showFallbackImage ? 'block' : 'none' }" />
            <canvas ref="drawingCanvas" class="drawing-canvas" @mousedown="handleMouseDown" @mousemove="handleMouseMove"
              @contextmenu.prevent="handleRightClick">
            </canvas>
            <div class="drawing-controls">
              <el-button type="primary" @click="startDrawing">开始绘制</el-button>
              <el-button @click="clearDrawing">清除</el-button>
            </div>
          </div>
        </div>

        <el-form-item label="区域坐标">
          <el-input v-model="coordinatesDisplay" placeholder="绘制完成后自动生成坐标" readonly />
        </el-form-item>
        <div class="coordinate-hint">提示：左键添加顶点，右键完成绘制</div>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button type="primary" @click="loadArea">查看</el-button>
          <el-button @click="areaModalVisible = false">取消</el-button>
          <el-button type="primary" @click="saveAreaConfig">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted, computed } from 'vue';
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
    const targetClasses = ref([]); // 用于存储目标类别

    // 模态框状态
    const modalVisible = ref(false);
    const isEdit = ref(false);
    const formRef = ref(null);

    // 区域对话框状态
    const areaModalVisible = ref(false);
    const currentConfigId = ref(null);

    // 区域表单数据
    const areaForm = reactive({
      coordinates: {
        type: 'area',           // "line"或 "area"
        points: [],                // 归一化坐标
        subtype: "simple",    // 可选值：directional（方向检测）、simple（普通检测）
        direction: "in",   // 方向：in(入方向), out(出方向), both(双向)
      }
    });

    // 坐标显示计算属性
    const coordinatesDisplay = computed(() => {
      if (!areaForm.coordinates || !areaForm.coordinates.points) return '';
      return JSON.stringify(areaForm.coordinates.points.map(p => [p.x, p.y]));
    });

    // 绘制相关状态
    const isDrawing = ref(false);
    const points = ref([]);
    const drawingCanvas = ref(null);

    // 预览相关
    const previewLoading = ref(false)
    const previewError = ref(null)
    const previewStream = ref(null)
    const currentDevice = ref(null)
    const videoRef = ref(null)
    const currentFrame = ref(null)
    const streamResolution = ref('')
    const ws = ref(null)
    const showFallbackImage = ref(false)

    // 视频加载完成
    const onVideoLoaded = () => {
      if (!videoRef.value) return

      const { videoWidth, videoHeight } = videoRef.value
      streamResolution.value = `${videoWidth}x${videoHeight}`
    }
    // 重试预览
    const retryPreview = () => {
      previewError.value = null
      previewLoading.value = true
      startPreview()
    }
    // 停止预览
    const stopPreview = () => {
      // 关闭WebSocket连接
      if (ws.value) {
        if (ws.value.readyState === WebSocket.OPEN) {
          ws.value.send(JSON.stringify({ type: 'stop' }))
        }
        ws.value.close()
        ws.value = null
      }

      // 停止视频流
      if (videoRef.value && videoRef.value.srcObject) {
        const tracks = videoRef.value.srcObject.getTracks()
        tracks.forEach(track => track.stop())
        videoRef.value.srcObject = null
      }

      // 重置状态
      previewStream.value = null
      streamResolution.value = ''
    }
    // 设置感兴趣区域方法
    const setInterestArea = (config) => {
      currentConfigId.value = config.config_id;
      // 检查 area_coordinates 是否有效
      if (config.area_coordinates && Object.keys(config.area_coordinates).length > 0) {
        areaForm.coordinates = config.area_coordinates; // 直接使用对象
        if (drawingCanvas.value) {
          drawPolygon(areaForm.coordinates.points);
        }
      } else {
        areaForm.coordinates = {
          type: 'area',
          points: [],
          subtype: "simple",
          direction: "in"
        };
      }

      areaModalVisible.value = true;

      currentDevice.value = config
      previewLoading.value = true
      previewError.value = null
      previewStream.value = null
      currentFrame.value = null
      showFallbackImage.value = true
      streamResolution.value = ''

      // 清除之前的预览状态
      if (videoRef.value && videoRef.value.srcObject) {
        const tracks = videoRef.value.srcObject.getTracks()
        tracks.forEach(track => track.stop())
        videoRef.value.srcObject = null
      }

      // 延迟一帧，确保DOM加载完成再开始预览
      setTimeout(() => {
        startPreview()
      }, 0)
    };

    const drawPolygon = (points) => {
      if (!drawingCanvas.value) {
        console.error('Canvas 未初始化')
        return
      }
      try {
        // 使用 Canvas 或其他绘图库绘制多边形
        const canvas = drawingCanvas.value;
        const ctx = canvas.getContext('2d');
        // 先清除画布，然后重新绘制所有内容
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.beginPath();
        ctx.moveTo(points[0].x * drawingCanvas.value.width, points[0].y * drawingCanvas.value.height);
        points.forEach(point => {
          // console.log(point.x * drawingCanvas.value.offsetWidth, point.y * drawingCanvas.value.offsetHeight)
          ctx.lineTo(point.x * drawingCanvas.value.width, point.y * drawingCanvas.value.height);
        });
        ctx.closePath();
        ctx.strokeStyle = '#00ff00';
        ctx.stroke();
      } catch { }
    };

    // 开始预览
    const startPreview = async () => {
      try {
        if (!currentDevice.value) {
          throw new Error('设备信息不完整')
        }

        // 构建流地址
        const { device_type, ip_address, port, username, password } = currentDevice.value

        if (device_type === 'camera') {
          // 构建RTSP URL（根据摄像头类型可能需要调整URL格式）
          const rtspUrl = `rtsp://${username}:${password}@${ip_address}:${port}/cam/realmonitor?channel=1&subtype=0`

          // 使用WebSocket连接服务器请求代理流
          await connectToWebSocket(rtspUrl)
        } else {
          throw new Error('不支持的设备类型')
        }

        previewLoading.value = false
      } catch (error) {
        // console.error('预览失败:', error)
        previewLoading.value = false
        previewError.value = `连接设备失败: ${error.message}`
      }
    }
    // 连接WebSocket服务器
    const connectToWebSocket = async (streamUrl) => {
      return new Promise((resolve, reject) => {
        try {
          // 关闭已有的连接
          if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            ws.value.close()
          }

          // 创建新的WebSocket连接
          ws.value = new WebSocket('ws://localhost:8765/ws')

          // 连接超时
          const connectionTimeout = setTimeout(() => {
            reject(new Error('连接超时'))
          }, 10000)

          ws.value.onopen = () => {
            clearTimeout(connectionTimeout)
            // console.log('WebSocket已连接，正在发送连接请求...')

            // 发送连接请求
            ws.value.send(JSON.stringify({
              type: 'connect',
              client_type: 'preview_client'
            }))
          }

          ws.value.onmessage = handleWsMessage

          ws.value.onerror = (error) => {
            clearTimeout(connectionTimeout)
            // console.error('WebSocket错误:', error)
            reject(new Error('WebSocket连接错误'))
          }

          ws.value.onclose = () => {
            // console.log('WebSocket已关闭')
            if (areaModalVisible.value && !previewError.value) {
              previewError.value = '视频流连接已断开'
            }
          }
        } catch (error) {
          // console.error('创建WebSocket连接失败:', error)
          reject(error)
        }
      })
    }
    // 处理WebSocket消息
    const handleWsMessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        // console.log('接收到WebSocket消息:', message.type)

        // 根据消息类型处理
        switch (message.type) {
          case 'connect_confirm':
            // console.log('WebSocket连接确认')

            // 发送预览请求
            if (ws.value && ws.value.readyState === WebSocket.OPEN && currentDevice.value) {
              // console.log('发送预览请求')
              ws.value.send(
                JSON.stringify({
                  type: 'preview_request',
                  device_id: currentDevice.value.device_id,
                  stream_url: buildRtspUrl()
                })
              )
            }
            break

          case 'preview_start':
            // console.log('预览流已开始', message)
            previewLoading.value = false

            // 如果预览流还未开始，则启动
            if (!previewStream.value) {
              // 确保状态被正确设置
              startVideoStream()
            }
            break

          case 'stream_data':
            // 处理流数据
            handleStreamData(message)
            break

          case 'error':
            // console.error('服务器错误:', message.message)
            previewLoading.value = false
            previewError.value = `服务器错误: ${message.message}`
            break

          default:
            break
          // console.log('未处理的消息类型:', message.type)
        }
      } catch (error) {
        // console.error('处理WebSocket消息错误:', error)
      }
    }
    // 开始视频流播放
    const startVideoStream = () => {
      // console.log('开始初始化视频流播放...');

      try {
        // 无论videoRef是否存在，都先将预览状态设置为true
        previewLoading.value = false;
        previewStream.value = true;
        // console.log('视频预览状态已更新: previewStream =', previewStream.value);

        // 检查浏览器支持
        if (!window.MediaSource) {
          // console.warn('浏览器不支持MediaSource API，将使用备用显示模式');
          showFallbackImage.value = true;
        }

        // 如果videoRef已存在，可以进行其他初始化
        // if (videoRef.value) {
        //   console.log('videoRef已存在，可以初始化视频元素');
        // } else {
        //   console.log('videoRef尚未就绪，将在收到第一帧时初始化');
        // }
      } catch (error) {
        // console.error('启动视频流失败:', error);
        previewError.value = `启动视频流失败: ${error.message}`;
      }
    }
    // 处理流数据
    const handleStreamData = (data) => {
      // console.log('收到流数据:', data.type, data.format || '(无格式信息)');

      // 确保预览状态已初始化（双重保险）
      if (!previewStream.value) {
        // console.log('预览流状态未初始化，自动初始化');
        previewLoading.value = false;
        previewStream.value = true;
      }

      try {
        // 检查数据格式
        if (data.format === 'jpeg' && data.data) {
          // console.log(`处理JPEG图像数据: ${data.width}x${data.height}, 帧ID:${data.frame_id}`);

          // 基于Base64图像创建图像URL
          const imageData = `data:image/jpeg;base64,${data.data}`;

          // 更新当前帧，用于备用显示方式
          currentFrame.value = imageData;

          // 更新分辨率信息（无论显示模式如何）
          if (!streamResolution.value && data.width && data.height) {
            streamResolution.value = `${data.width}x${data.height}`;
          }

          // 默认使用备用图像显示方式，简单可靠
          if (!videoRef.value || !videoRef.value.parentElement) {
            // console.log('使用备用图像显示模式 - videoRef不可用');
            showFallbackImage.value = true;
            return;
          }

          // 如果明确使用备用图像显示方式，则直接返回
          if (showFallbackImage.value) {
            return;
          }

          // 使用IMG元素更新视频帧
          const img = new Image();
          img.onload = () => {
            // 确保videoRef仍然存在
            if (!videoRef.value) {
              // console.warn('videoRef在图像加载过程中消失，切换到备用模式');
              showFallbackImage.value = true;
              return;
            }

            try {
              // 使用Canvas绘制图像
              const canvas = document.createElement('canvas');
              canvas.width = data.width;
              canvas.height = data.height;
              const ctx = canvas.getContext('2d');
              ctx.drawImage(img, 0, 0);

              // 直接将canvas内容显示在video元素上
              if (!videoRef.value.srcObject) {
                // 首次创建流
                // console.log('创建新的Canvas流');
                try {
                  const canvasStream = canvas.captureStream(15); // 15fps
                  videoRef.value.srcObject = canvasStream;
                  // console.log('视频流已连接到video元素');
                } catch (e) {
                  // console.error('创建Canvas流失败，切换到备用模式:', e);
                  showFallbackImage.value = true;
                }
              } else {
                // 更新现有流的图像 - 使用简化的方法
                try {
                  const newStream = canvas.captureStream(15);
                  const oldStream = videoRef.value.srcObject;
                  videoRef.value.srcObject = newStream;

                  // 停止旧流的轨道
                  if (oldStream && oldStream.getTracks) {
                    oldStream.getTracks().forEach(track => track.stop());
                  }
                } catch (e) {
                  // console.warn('更新Canvas流失败，切换到备用模式:', e);
                  showFallbackImage.value = true;
                }
              }
            } catch (e) {
              // console.error('Canvas操作失败，切换到备用模式:', e);
              showFallbackImage.value = true;
            }
          };

          img.onerror = (err) => {
            // console.error('图像加载失败:', err);
            previewError.value = '图像加载失败，请检查网络连接';
          };

          img.src = imageData;
        } else if (data.data && !data.format) {
          // console.log('收到二进制数据，尝试作为MP4片段处理');
          // 二进制数据处理 (PyAV版本的后端)
          if (window.appendVideoData) {
            try {
              const videoData = new Uint8Array(data.data);
              window.appendVideoData(videoData);
              // console.log('成功处理视频数据片段');
            } catch (e) {
              // console.error('处理视频片段失败:', e);
              previewError.value = '视频解码失败';
            }
          } else {
            // console.warn('window.appendVideoData未定义，无法处理MP4片段，切换到备用模式');
            showFallbackImage.value = true;
          }
        } else {
          // console.warn('收到未知格式的数据:', data);
        }
      } catch (error) {
        // console.error('处理视频数据错误:', error);
        previewError.value = `视频处理错误: ${error.message}`;
        showFallbackImage.value = true;  // 出错时默认使用备用模式
      }
    }
    // 构建RTSP URL
    const buildRtspUrl = () => {
      if (!currentDevice.value) return '';

      return `rtsp://${currentDevice.value.username}:${currentDevice.value.password}@${currentDevice.value.ip_address}:${currentDevice.value.port}/cam/realmonitor?channel=1&subtype=0`
    }
    // 绘制相关方法
    const startDrawing = () => {
      if (areaForm.coordinates.type) {
        isDrawing.value = true;
        points.value = [];
        areaForm.coordinates.points = [];
      } else {
        ElMessage.info('请选择画线类型');
      }

    };

    const clearDrawing = () => {
      const canvas = drawingCanvas.value;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      points.value = [];
      areaForm.coordinates.points = [];
    };

    const handleMouseDown = (e) => {
      if (!isDrawing.value) return;

      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;

      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;

      points.value.push({ x, y });

      // 绘制点
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#00FF00';
      ctx.beginPath();
      ctx.arc(x, y, 1, 0, Math.PI * 2);
      ctx.fill();

      // 绘制连线
      if (points.value.length > 1) {
        ctx.strokeStyle = '#00FF00';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(points.value[points.value.length - 2].x, points.value[points.value.length - 2].y);
        ctx.lineTo(x, y);
        ctx.stroke();
      }
    };

    const handleMouseMove = (e) => {
      if (!isDrawing.value || points.value.length === 0) return;

      const canvas = drawingCanvas.value;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;

      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;

      // 绘制临时线
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 重绘所有点
      points.value.forEach(point => {
        ctx.fillStyle = '#00FF00';
        ctx.beginPath();
        ctx.arc(point.x, point.y, 1, 0, Math.PI * 2);
        ctx.fill();
      });

      // 重绘所有线
      if (points.value.length > 1) {
        ctx.strokeStyle = '#00FF00';
        ctx.lineWidth = 1;
        for (let i = 1; i < points.value.length; i++) {
          ctx.beginPath();
          ctx.moveTo(points.value[i - 1].x, points.value[i - 1].y);
          ctx.lineTo(points.value[i].x, points.value[i].y);
          ctx.stroke();
        }
      }

      // 绘制临时线
      if (points.value.length > 0) {
        ctx.strokeStyle = '#00FF00';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(points.value[points.value.length - 1].x, points.value[points.value.length - 1].y);
        ctx.lineTo(x, y);
        ctx.stroke();
      }
    };

    const handleRightClick = () => {
      if (!isDrawing.value || points.value.length < (areaForm.coordinates.type === 'area' ? 3 : 2)) return;

      const ctx = drawingCanvas.value.getContext('2d');
      ctx.strokeStyle = '#00FF00';
      ctx.lineWidth = 1;
      ctx.beginPath();

      // 绘制路径
      points.value.forEach((p, index) => {
        if (index === 0) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      });

      // 自动闭合多边形
      if (areaForm.coordinates.type === 'area') {
        ctx.lineTo(points.value[0].x, points.value[0].y);
      }
      ctx.stroke();

      // 生成标准化坐标
      areaForm.coordinates = {
        type: areaForm.coordinates.type,
        points: points.value.map(p => ({
          x: p.x / drawingCanvas.value.width,
          y: p.y / drawingCanvas.value.height
        })),
        subtype: areaForm.coordinates.subtype || "simple",
        direction: areaForm.coordinates.direction || "in",
      };

      // 如果是方向检测，绘制箭头
      if (areaForm.coordinates.subtype === 'directional') {
        updateDirectionArrow();
      }

      isDrawing.value = false;
    };

    // 保存区域配置
    const saveAreaConfig = async () => {
      try {
        if (!areaForm.coordinates) { //|| !areaForm.coordinates.points
          throw new Error('无效的坐标数据');
        }

        if (areaForm.coordinates.subtype === 'directional' && !areaForm.coordinates.direction) {
          ElMessage.error('请选择有效的检测方向');
          return;
        }
        // 几何有效性验证
        // if (areaForm.coordinates.points.length < (areaForm.coordinates.type === 'area' ? 3 : 2)) {
        //   ElMessage.error('请绘制有效的多边形区域');
        //   return;
        // }
        console.log(areaForm.coordinates);

        if (areaForm.coordinates.points.length == 0) {
          // 调用API保存区域配置
          await detectionConfigApi.updateConfig(currentConfigId.value, {
            area_coordinates: {}
          });
        } else {
          // 调用API保存区域配置
          await detectionConfigApi.updateConfig(currentConfigId.value, {
            area_coordinates: areaForm.coordinates
          });
        }



        ElMessage.success('区域配置保存成功');
        areaModalVisible.value = false;
        loadConfigList();
      } catch (error) {
        ElMessage.error(`保存失败: ${error.message}`);
      }
    };
    // 表单状态
    const formState = reactive({
      config_id: null,
      device_id: null,
      models_id: null,
      enabled: true,
      sensitivity: 0.5,
      target_classes: [],
      frequency: 'realtime',
      save_mode: 'none',
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

    // 更新目标类别
    const updateTargetClasses = (modelId) => {
      const selectedModel = modelList.value.find(model => model.models_id === modelId);
      if (selectedModel && selectedModel.models_classes) {
        // 将 models_classes 字典转换为数组，格式为 { label: name, value: key }
        targetClasses.value = Object.entries(selectedModel.models_classes).map(([key, name]) => ({
          label: name, // 显示的名称
          value: key   // 对应的键
        }));
      } else {
        targetClasses.value = []; // 如果没有选择模型，清空目标类别
      }
    }

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

    const getAreaTypeLabel = (areaType) => {
      const typeMap = {
        'area': '区域',
        'line': '拌线'
      }
      if (typeMap[areaType.type]) {
        if (areaType.subtype === 'directional') {
          return typeMap[areaType.type] + '(方向检测:' + (areaType.direction === 'in' ? '进入' : areaType.direction === 'out' ? '离开' : '双向') + ')'
        } else {
          return typeMap[areaType.type] + '(普通检测)'
        }
      } else {
        return '未设置'
      }
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
        'none': '暂无',
        'screenshot': '截图',
        'video': '视频',
        'both': '截图+视频'
      };
      return map[saveMode] || saveMode;
    };

    // 获取保存模式标签类型
    const getSaveModeType = (saveMode) => {
      const map = {
        'none': 'warning',
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
        save_mode: 'none',
        save_duration: 10,
        max_storage_days: 30
      });

      if (formRef.value) {
        formRef.value.clearValidate();
        // formRef.value.resetFields();
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
      updateTargetClasses(record.models_id);
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
                  enabled: false,
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
      isEdit.value = false;
    };

    // 切换启用状态
    const toggleEnabled = async (record) => {
      try {
        if (!record.enabled) {
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

    const loadArea = () => {
      if (drawingCanvas.value) {
        // areaForm.config_type = areaForm.coordinates.type;
        drawPolygon(areaForm.coordinates.points);
      }
    }

    // 检查是否已绘制内容
    const handleSubtypeChange = (value) => {
      if (value === 'directional' && (!areaForm.coordinates.points || areaForm.coordinates.points.length < 2)) {
        ElMessage.warning('请先绘制区域再选择方向检测模式');
        areaForm.coordinates.subtype = 'simple';
      } else if (value === 'directional') {
        updateDirectionArrow();
      } else if (value === 'simple') {
        areaForm.coordinates.direction = null;
        loadArea();
      }
    };

    // 更新方向箭头
    const updateDirectionArrow = () => {
      if (!areaForm.coordinates.points || areaForm.coordinates.points.length < 2) return;

      // 在线段上绘制箭头
      const canvas = drawingCanvas.value;
      if (!canvas) return;

      // 重绘所有点和线
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#00FF00';
      ctx.strokeStyle = '#00FF00';
      ctx.lineWidth = 1;

      // 先清除画布，然后重新绘制所有内容
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const points = areaForm.coordinates.points;

      // 绘制多边形
      ctx.beginPath();
      ctx.moveTo(points[0].x * drawingCanvas.value.width, points[0].y * drawingCanvas.value.height);
      points.forEach(point => {
        ctx.lineTo(point.x * drawingCanvas.value.width, point.y * drawingCanvas.value.height);
      });
      if (areaForm.coordinates.type === 'area' && points.length > 2) {
        ctx.closePath();
      }
      ctx.stroke();

      // 如果是方向检测，在第一个和第二个点之间绘制箭头
      if (areaForm.coordinates.subtype === 'directional' && points.length >= 2) {
        const p1 = points[0];
        const p2 = points[1];

        // 计算线段中点
        const midX = (p1.x + p2.x) / 2 * drawingCanvas.value.width;
        const midY = (p1.y + p2.y) / 2 * drawingCanvas.value.height;

        // 计算线段角度
        const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);

        // 根据方向绘制不同的箭头
        if (areaForm.coordinates.direction === 'in' || areaForm.coordinates.direction === 'both') {
          drawArrow(ctx, midX, midY, angle + Math.PI / 2, '#00FF00');
        }

        if (areaForm.coordinates.direction === 'out' || areaForm.coordinates.direction === 'both') {
          drawArrow(ctx, midX, midY, angle - Math.PI / 2, '#00FF00');
        }
      }
    };

    // 绘制箭头函数
    const drawArrow = (ctx, x, y, angle, color) => {
      const arrowSize = 10;

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);

      ctx.fillStyle = color;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(-arrowSize / 2, -arrowSize);
      ctx.lineTo(arrowSize / 2, -arrowSize);
      ctx.closePath();
      ctx.fill();

      ctx.stroke();

      ctx.restore();
    };

    return {
      getAreaTypeLabel,
      updateDirectionArrow,
      handleSubtypeChange,
      loadArea,
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
      coordinatesDisplay,
      targetClasses,
      areaModalVisible,
      areaForm,
      previewLoading,
      previewError,
      previewStream,
      currentFrame,
      showFallbackImage,
      onVideoLoaded,
      retryPreview,
      stopPreview,
      saveAreaConfig,
      setInterestArea,
      startDrawing,
      clearDrawing,
      handleMouseDown,
      handleMouseMove,
      handleRightClick,
      videoRef,
      drawingCanvas,
      updateTargetClasses,
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

.video-preview-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
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

.video-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 4px;
}

.preview-video,
.drawing-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.drawing-canvas {
  z-index: 1;
  cursor: crosshair;
}

.drawing-controls {
  position: absolute;
  bottom: 10px;
  left: 10px;
  z-index: 2;
}

.coordinate-hint {
  font-size: 12px;
  color: #909399;
  margin-top: -10px;
  margin-bottom: 10px;
}

.fallback-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #000;
  display: none;}
</style>