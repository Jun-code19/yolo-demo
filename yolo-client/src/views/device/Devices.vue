<template>
  <div class="devices-container">
    <div class="page-header">
      <h2>视频设备管理</h2>
      <el-space>
        <el-dropdown @command="handleExport">
          <el-button type="primary">
            <el-icon>
              <Download />
            </el-icon>导出
            <el-icon>
              <ArrowDown />
            </el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="template">导出模板</el-dropdown-item>
              <el-dropdown-item command="data">导出数据</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" @click="handleImport">
          <el-icon>
            <Upload />
          </el-icon>导入
        </el-button>
        <el-button type="primary" @click="handleAdd">
          <el-icon>
            <Plus />
          </el-icon>添加设备
        </el-button>
      </el-space>
    </div>
    <!-- 筛选区域 -->
    <el-card class="filter-section">
        <el-form :model="filterForm" inline>
          <el-form-item label="设备类型">
            <el-select v-model="filterForm.device_type" placeholder="请选择设备类型" clearable style="width: 150px;">
              <el-option label="摄像头" value="camera" />
              <el-option label="硬盘录像机" value="nvr" />
              <el-option label="边缘服务器" value="edge_server" />
              <el-option label="存储节点" value="storage_node" />
            </el-select>
          </el-form-item>

          <el-form-item label="设备状态">
            <el-select v-model="filterForm.status" placeholder="请选择状态" clearable style="width: 120px;">
              <el-option label="在线" :value="true" />
              <el-option label="离线" :value="false" />
            </el-select>
          </el-form-item>

          <el-form-item label="设备名称">
            <el-input v-model="filterForm.device_name" placeholder="请输入设备名称" clearable style="width: 150px;" />
          </el-form-item>

          <!-- <el-form-item label="IP地址">
            <el-input v-model="filterForm.ip_address" placeholder="请输入IP地址" clearable style="width: 150px;" />
          </el-form-item> -->

          <el-form-item label="位置">
            <el-input v-model="filterForm.location" placeholder="请输入位置" clearable style="width: 120px;" />
          </el-form-item>

          <!-- <el-form-item label="区域">
            <el-input v-model="filterForm.area" placeholder="请输入区域" clearable style="width: 120px;" />
          </el-form-item> -->

          <el-form-item>
            <el-space>
              <el-button type="primary" @click="handleFilter" :loading="loading">
                <el-icon>
                  <Search />
                </el-icon>搜索
              </el-button>
              <el-button @click="handleResetFilter">
                <el-icon>
                  <Refresh />
                </el-icon>重置
              </el-button>
            </el-space>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 设备列表 -->
    <el-card class="device-list">
      <!-- 设备表格 -->
      <el-table :data="devices" style="width: 100%" v-loading="loading">
        <el-table-column prop="device_id" label="设备ID" sortable min-width="120" />
        <el-table-column prop="device_name" label="设备名称" sortable min-width="150" />
        <el-table-column prop="device_type" label="设备类型" sortable min-width="120">
          <template #default="{ row }">
            <el-tag :type="getDeviceTypeTag(row.device_type)">
              {{ getDeviceTypeName(row.device_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP地址" sortable min-width="120" />
        <el-table-column prop="port" label="端口" width="120" />
        <!-- <el-table-column prop="username" label="用户名" min-width="100" /> -->
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'">
              {{ row.status ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_heartbeat" label="最后心跳" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" sortable min-width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button type="warning" link @click="setInterestArea(row)">
                区域
              </el-button>
              <el-button type="primary" link @click="handlePreview(row)">
                预览
              </el-button>
              <el-button type="primary" link @click="handleEdit(row)">
                编辑
              </el-button>             
              <el-button type="danger" link @click="handleDelete(row)">
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50, 100, 200]" layout="prev, pager, next, jumper, ->, total, sizes"
          @size-change="handleSizeChange" @current-change="handleCurrentChange" />
      </div>
    </el-card>

    <!-- 添加/编辑设备对话框 -->
    <el-dialog 
      v-model="dialogVisible" 
      :title="dialogType === 'add' ? '添加设备' : '编辑设备'" 
      width="30%" top="5vh"
      destroy-on-close
      :z-index="999999"
      append-to-body
      class="high-priority-dialog"
    >
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceRules" label-width="100px">
        <el-form-item label="设备ID" prop="device_id">
          <el-input v-model="deviceForm.device_id" placeholder="请输入设备ID" :disabled="dialogType === 'edit'" />
        </el-form-item>
        <el-form-item label="设备名称" prop="device_name">
          <el-input v-model="deviceForm.device_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="deviceForm.device_type" placeholder="请选择设备类型" style="width: 100%">
            <el-option label="摄像头" value="camera" />
            <el-option label="硬盘录像机" value="nvr" />
            <el-option label="边缘服务器" value="edge_server" />
            <el-option label="存储节点" value="storage_node" />
          </el-select>
        </el-form-item>
        <el-form-item label="通道号" prop="channel" v-if="deviceForm.device_type === 'nvr'">
          <el-input-number v-model="deviceForm.channel" :min="1" :max="64" placeholder="请输入通道号" style="width: 100%" />
        </el-form-item>
        <el-form-item label="码流选择" prop="stream_type">
          <el-select v-model="deviceForm.stream_type" placeholder="请选择码流" style="width: 100%">
            <el-option label="主码流" value="main" />
            <el-option label="辅码流" value="sub" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="deviceForm.location" placeholder="请输入设备位置" />
        </el-form-item>
        <el-form-item label="区域" prop="area">
          <el-input v-model="deviceForm.area" placeholder="请输入设备区域" />
        </el-form-item>
        <el-form-item label="IP地址" prop="ip_address">
          <el-input v-model="deviceForm.ip_address" placeholder="请输入IP地址" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="deviceForm.port" :min="1" :max="65535" placeholder="请输入端口号" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="deviceForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="deviceForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog 
      v-model="previewVisible" 
      title="设备预览" 
      width="50%" top="5vh"
      destroy-on-close 
      @close="stopPreview"
      :z-index="100000"
      append-to-body
      class="preview-dialog high-priority-dialog"
    >
      <div class="preview-container">
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
          <!-- 视频元素 -->
          <video ref="videoRef" class="video-player" autoplay muted @loadedmetadata="onVideoLoaded"></video>

          <!-- 备用图像显示 -->
          <img v-if="currentFrame" :src="currentFrame" class="fallback-image"
            :style="{ display: showFallbackImage ? 'block' : 'none' }" />

          <div class="stream-info">
            <span>{{ currentDevice?.device_name || '未知设备' }}</span>
            <span v-if="streamResolution">{{ streamResolution }}</span>
          </div>
        </div>
      </div>
      <div class="preview-controls">
        <el-space>
          <el-button @click="takeSnapshot" :disabled="!previewStream">
            <el-icon>
              <Camera />
            </el-icon>截图
          </el-button>
          <el-button @click="toggleFallbackMode" v-if="previewStream">
            切换显示模式
          </el-button>
          <el-button @click="toggleFullscreen">
            <el-icon>
              <FullScreen />
            </el-icon>{{ isFullscreen ? '退出全屏' : '全屏' }}
          </el-button>
        </el-space>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="previewVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog 
      v-model="importDialogVisible" 
      title="导入设备" 
      width="30%" top="5vh"
      destroy-on-close
      :z-index="100001"
      append-to-body
      class="import-dialog high-priority-dialog"
    >
      <el-upload class="upload-demo" drag action="#" :auto-upload="false" :on-change="handleFileChange" :limit="1"
        accept=".xlsx,.xls,.csv">
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            请上传Excel(.xlsx/.xls)或CSV(.csv)格式文件，文件大小不超过10MB
          </div>
        </template>
      </el-upload>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitImport" :loading="importing">
            确认导入
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Plus, VideoCamera, CircleClose, Camera, Download, ArrowDown, Upload, UploadFilled, Search, Refresh, FullScreen } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import deviceApi from '@/api/device'
import router from '@/router'

// 列表数据
const loading = ref(false)
const devices = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 对话框控制
const dialogVisible = ref(false)
const dialogType = ref('add')
const previewVisible = ref(false)
const submitting = ref(false)

// 表单相关
const deviceFormRef = ref(null)
const deviceForm = reactive({
  device_id: '',
  device_name: '',
  device_type: 'camera',
  ip_address: '',
  port: 554,
  username: '',
  password: '',
  channel: 1,
  stream_type: 'main',
  location: '',
  area: ''
})

const deviceRules = {
  device_id: [{ required: true, message: '请输入设备ID', trigger: 'blur' }],
  device_name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  ip_address: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    {
      pattern: /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
      message: '请输入正确的IP地址',
      trigger: 'blur'
    }
  ],
  port: [{ required: true, message: '请输入端口号', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 预览相关
const previewLoading = ref(false)
const previewError = ref(null)
const previewStream = ref(null)
const currentDevice = ref(null)
const videoRef = ref(null)
const streamResolution = ref('')
let ws = null
const currentFrame = ref(null)
const showFallbackImage = ref(false)
const isFullscreen = ref(false)

// 导入相关
const importDialogVisible = ref(false)
const importFile = ref(null)
const importing = ref(false)

// 筛选相关
const filterForm = reactive({
  device_type: '',
  status: '',
  device_name: '',
  ip_address: '',
  location: '',
  area: ''
})

// 跟踪当前是否在筛选状态
const isFiltering = ref(false)

// 加载设备数据
const loadData = async (useFilter = false) => {
  loading.value = true
  try {
    const skip = (currentPage.value - 1) * pageSize.value
    const paginationParams = { skip, limit: pageSize.value }

    let response
    if (useFilter) {
      // 使用筛选参数
      response = await deviceApi.getFilteredDevices(filterForm, paginationParams)
    } else {
      // 不使用筛选，获取所有数据
      response = await deviceApi.getDevices(paginationParams)
    }

    devices.value = response.data.data
    total.value = response.data.total
  } catch (error) {
    ElMessage.error('加载设备数据失败，请检查网络连接或服务器状态')
  } finally {
    loading.value = false
  }
}

// 刷新状态
const refreshStatus = async () => {
  try {
    // 获取设备在线状态
    const response = await deviceApi.getDevicesStatus()
    if (response.status === 200) {
      loadData()  // 刷新数据
    } else {
      ElMessage.error('获取设备在线状态失败')
    }
  } catch (error) {
    ElMessage.error('获取设备在线状态失败')
  }
}

// 处理全屏状态变化
const handleFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement || !!document.mozFullScreenElement || !!document.webkitFullscreenElement || !!document.msFullscreenElement;
};

// 初始化
onMounted(() => {
  loadData()
  // refreshStatus()
  // refreshInterval = setInterval(refreshStatus, 60000)
  
  // 监听全屏状态变化
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.addEventListener('mozfullscreenchange', handleFullscreenChange)
  document.addEventListener('MSFullscreenChange', handleFullscreenChange)
  
  // 监听键盘事件
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  stopPreview()
  // if (refreshInterval) {
  //   clearInterval(refreshInterval)
  // }
  
  // 确保清理全屏资源
  stopFullscreenFrameUpdate()
  if (isFullscreen.value) {
    exitFullscreen()
  }
  
  // 移除全屏状态监听
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('webkitfullscreenchange', handleFullscreenChange)
  document.removeEventListener('mozfullscreenchange', handleFullscreenChange)
  document.removeEventListener('MSFullscreenChange', handleFullscreenChange)
  
  // 移除键盘事件监听
  document.removeEventListener('keydown', handleKeyDown)
})

// 设置感兴趣区域方法（跳转到新页面）
const setInterestArea = (device) => {
      router.push({
        name: 'AreaConfigSetting',
        params: {
          deviceId: device.device_id
        },
        query: {
          deviceId: device.device_id
        }
      });
    };

// 处理键盘事件
const handleKeyDown = (event) => {
  if (event.key === 'Escape' && isFullscreen.value) {
    exitFullscreen()
  }
}

// 分页处理
const handleSizeChange = (val) => {
  pageSize.value = val
  loadData(isFiltering.value)
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadData(isFiltering.value)
}

// 添加设备
const handleAdd = () => {
  dialogType.value = 'add'
  dialogVisible.value = true
  Object.assign(deviceForm, {
    device_id: '',
    device_name: '',
    device_type: 'camera',
    ip_address: '',
    port: 554,
    username: '',
    password: '',
    channel: 1,
    stream_type: 'main',
    location: '',
    area: ''
  })
}

// 编辑设备
const handleEdit = (row) => {
  dialogType.value = 'edit'
  dialogVisible.value = true
  Object.assign(deviceForm, {
    device_id: row.device_id,
    device_name: row.device_name,
    device_type: row.device_type,
    ip_address: row.ip_address,
    port: row.port,
    username: row.username,
    password: row.password,
    channel: row.channel || 1,
    stream_type: row.stream_type || 'main',
    location: row.location || '',
    area: row.area || ''
  })
}

// 提交表单
const handleSubmit = async () => {
  if (!deviceFormRef.value) return

  await deviceFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (dialogType.value === 'add') {
        // 创建设备
        await deviceApi.createDevice(deviceForm)
        ElMessage.success('设备添加成功')
      } else {
        // 更新设备信息
        await deviceApi.updateDevice(deviceForm.device_id, deviceForm)
        ElMessage.success('设备更新成功')
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      // console.error('操作失败:', error)
      ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`)
    } finally {
      submitting.value = false
    }
  })
}

// 删除设备
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确认删除设备 "${row.device_name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deviceApi.deleteDevice(row.device_id)
      ElMessage.success('删除成功')
      loadData()
    } catch (error) {
      // console.error('删除失败:', error)
      ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`)
    }
  }).catch(() => { })
}

// 预览设备
const handlePreview = (row) => {
  currentDevice.value = row
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = null
  previewStream.value = null
  currentFrame.value = null
  showFallbackImage.value = true
  streamResolution.value = ''
  isFullscreen.value = false // 重置全屏状态

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
}

// 开始预览
const startPreview = async () => {
  try {
    if (!currentDevice.value) {
      throw new Error('设备信息不完整')
    }

    if(currentDevice.value.status == false){
      previewLoading.value = false
      previewError.value = '设备离线，无法预览'
      return
    }

    // 构建流地址
    const { device_type, ip_address, port, username, password } = currentDevice.value

    if (device_type === 'camera' || device_type === 'nvr') {
      // 构建RTSP URL（根据摄像头类型可能需要调整URL格式）
      // const rtspUrl = `rtsp://${username}:${password}@${ip_address}:${port}/cam/realmonitor?channel=1&subtype=0`

      // 使用WebSocket连接服务器请求代理流
      await connectToWebSocket()
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
const connectToWebSocket = async () => {
  return new Promise((resolve, reject) => {
    try {
      // 关闭已有的连接
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }

      // 创建新的WebSocket连接
      ws = new WebSocket(`ws://${window.location.host}/ws/rtsp/preview`)

      // 连接超时
      const connectionTimeout = setTimeout(() => {
        reject(new Error('连接超时'))
      }, 10000)

      ws.onopen = () => {
        clearTimeout(connectionTimeout)
        // console.log('WebSocket已连接，正在发送连接请求...')

        // 发送连接请求
        ws.send(JSON.stringify({
          type: 'connect',
          client_type: 'preview_client'
        }))
      }

      ws.onmessage = handleWsMessage

      ws.onerror = (error) => {
        clearTimeout(connectionTimeout)
        // console.error('WebSocket错误:', error)
        reject(new Error('WebSocket连接错误'))
      }

      ws.onclose = () => {
        // console.log('WebSocket已关闭')
        if (previewVisible.value && !previewError.value) {
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
        if (ws && ws.readyState === WebSocket.OPEN && currentDevice.value) {
          // console.log('发送预览请求')
          ws.send(
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
    if (videoRef.value) {
      // console.log('videoRef已存在，可以初始化视频元素');
    } else {
      // console.log('videoRef尚未就绪，将在收到第一帧时初始化');
    }
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

      // 如果当前在全屏模式，立即更新全屏图像
      if (isFullscreen.value && showFallbackImage.value) {
        updateFullscreenImage();
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

// 视频加载完成
const onVideoLoaded = () => {
  if (!videoRef.value) return

  const { videoWidth, videoHeight } = videoRef.value
  streamResolution.value = `${videoWidth}x${videoHeight}`
}

// 截图功能
const takeSnapshot = () => {
  if (!previewStream.value) return

  try {
    let canvas, ctx, width, height

    if (showFallbackImage.value && currentFrame.value) {
      // 备用图像模式：从当前帧截图
      const img = new Image()
      img.onload = () => {
        width = img.naturalWidth || 640
        height = img.naturalHeight || 480
        
        canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        ctx = canvas.getContext('2d')
        
        // 绘制图像
        ctx.drawImage(img, 0, 0, width, height)
        
        // 下载截图
        downloadSnapshot(canvas)
      }
      img.onerror = () => {
        ElMessage.error('图像加载失败，无法截图')
      }
      img.src = currentFrame.value
    } else if (videoRef.value && videoRef.value.videoWidth > 0) {
      // 视频模式：从视频元素截图
      width = videoRef.value.videoWidth
      height = videoRef.value.videoHeight
      
      canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      ctx = canvas.getContext('2d')
      
      // 绘制当前视频帧
      ctx.drawImage(videoRef.value, 0, 0, width, height)
      
      // 下载截图
      downloadSnapshot(canvas)
    } else {
      ElMessage.warning('当前没有可用的视频流或图像，无法截图')
    }
  } catch (error) {
    console.error('截图失败:', error)
    ElMessage.error('截图失败')
  }
}

// 下载截图
const downloadSnapshot = (canvas) => {
  try {
    const image = canvas.toDataURL('image/png')
    const link = document.createElement('a')
    link.href = image
    link.download = `${currentDevice.value?.device_name || 'device'}_snapshot_${new Date().toISOString().replace(/:/g, '-')}.png`
    link.click()
    
    ElMessage.success('截图已保存')
  } catch (error) {
    console.error('保存截图失败:', error)
    ElMessage.error('保存截图失败')
  }
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
  if (ws) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop' }))
    }
    ws.close()
    ws = null
  }

  // 停止视频流
  if (videoRef.value && videoRef.value.srcObject) {
    const tracks = videoRef.value.srcObject.getTracks()
    tracks.forEach(track => track.stop())
    videoRef.value.srcObject = null
  }

  // 停止全屏帧更新
  stopFullscreenFrameUpdate()

  // 重置状态
  previewStream.value = null
  streamResolution.value = ''
  isFullscreen.value = false // 退出全屏
}

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN')
}

// 获取设备类型名称
const getDeviceTypeName = (type) => {
  const typeMap = {
    'camera': '摄像头',
    'nvr': '硬盘录像机',
    'edge_server': '边缘服务器',
    'storage_node': '存储节点',
  }
  return typeMap[type] || type
}

// 获取设备类型标签样式
const getDeviceTypeTag = (type) => {
  const typeTagMap = {
    'camera': 'info',
    'nvr': 'success',
    'edge_server': 'warning',
    'storage_node': 'danger'
  }
  return typeTagMap[type] || 'info'
}

// 切换备用图像显示模式
const toggleFallbackMode = () => {
  showFallbackImage.value = !showFallbackImage.value
}

// 切换全屏
const toggleFullscreen = () => {
  if (!isFullscreen.value) {
    // 进入全屏
    if (showFallbackImage.value && currentFrame.value) {
      // 备用图像模式：全屏显示图像，并实时更新
      createFullscreenDisplay()
    } else if (videoRef.value) {
      // 视频模式：使用浏览器原生全屏
      if (videoRef.value.requestFullscreen) {
        videoRef.value.requestFullscreen().catch(err => {
          console.error(`错误进入全屏模式: ${err.message} (${err.name})`)
        })
      } else if (videoRef.value.mozRequestFullScreen) { // Firefox
        videoRef.value.mozRequestFullScreen()
      } else if (videoRef.value.webkitRequestFullscreen) { // Chrome, Safari and Opera
        videoRef.value.webkitRequestFullscreen()
      } else if (videoRef.value.msRequestFullscreen) { // IE/Edge
        videoRef.value.msRequestFullscreen()
      }
      isFullscreen.value = true
    }
  } else {
    // 退出全屏
    exitFullscreen()
  }
}

// 创建全屏显示（备用模式）
const createFullscreenDisplay = () => {
  // 创建全屏容器
  const fullscreenDiv = document.createElement('div')
  fullscreenDiv.id = 'fullscreen-container'
  fullscreenDiv.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: #000;
    z-index: 999999;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: pointer;
  `
  
  // 创建图像元素
  const fullscreenImg = document.createElement('img')
  fullscreenImg.id = 'fullscreen-image'
  fullscreenImg.style.cssText = `
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  `
  
  // 创建设备信息显示
  const infoDiv = document.createElement('div')
  infoDiv.style.cssText = `
    position: absolute;
    bottom: 20px;
    left: 20px;
    right: 20px;
    padding: 10px 15px;
    background-color: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 4px;
  `
  
  // 添加设备名称和分辨率信息
  const deviceName = document.createElement('span')
  deviceName.textContent = currentDevice.value?.device_name || '未知设备'
  
  const resolution = document.createElement('span')
  resolution.textContent = streamResolution.value || ''
  
  infoDiv.appendChild(deviceName)
  infoDiv.appendChild(resolution)
  
  // 添加退出全屏提示
  const exitHint = document.createElement('div')
  exitHint.style.cssText = `
    position: absolute;
    top: 20px;
    right: 20px;
    padding: 8px 12px;
    background-color: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 12px;
    border-radius: 4px;
  `
  exitHint.textContent = '点击任意位置或按ESC键退出全屏'
  
  fullscreenDiv.appendChild(fullscreenImg)
  fullscreenDiv.appendChild(infoDiv)
  fullscreenDiv.appendChild(exitHint)
  
  // 点击退出全屏
  fullscreenDiv.onclick = () => exitFullscreen()
  
  // 添加到页面
  document.body.appendChild(fullscreenDiv)
  
  // 设置初始图像
  updateFullscreenImage()
  
  // 启动帧更新定时器
  startFullscreenFrameUpdate()
  
  isFullscreen.value = true
}

// 更新全屏图像
const updateFullscreenImage = () => {
  if (!isFullscreen.value || !currentFrame.value) return
  
  const fullscreenImg = document.getElementById('fullscreen-image')
  if (fullscreenImg) {
    fullscreenImg.src = currentFrame.value
  }
}

// 启动全屏帧更新
const startFullscreenFrameUpdate = () => {
  // 清除之前的定时器
  if (window.fullscreenUpdateTimer) {
    clearInterval(window.fullscreenUpdateTimer)
  }
  
  // 创建新的定时器，每100ms更新一次（10fps）
  window.fullscreenUpdateTimer = setInterval(() => {
    if (isFullscreen.value && showFallbackImage.value && currentFrame.value) {
      updateFullscreenImage()
    } else {
      // 如果不再全屏或切换到视频模式，停止更新
      stopFullscreenFrameUpdate()
    }
  }, 100)
}

// 停止全屏帧更新
const stopFullscreenFrameUpdate = () => {
  if (window.fullscreenUpdateTimer) {
    clearInterval(window.fullscreenUpdateTimer)
    window.fullscreenUpdateTimer = null
  }
}

// 退出全屏
const exitFullscreen = () => {
  // 停止帧更新
  stopFullscreenFrameUpdate()
  
  // 移除自定义全屏显示
  const customFullscreen = document.getElementById('fullscreen-container')
  if (customFullscreen) {
    document.body.removeChild(customFullscreen)
  }
  
  // 退出浏览器原生全屏
  if (document.exitFullscreen) {
    document.exitFullscreen()
  } else if (document.mozCancelFullScreen) { // Firefox
    document.mozCancelFullScreen()
  } else if (document.webkitExitFullscreen) { // Chrome, Safari and Opera
    document.webkitExitFullscreen()
  } else if (document.msExitFullscreen) { // IE/Edge
    document.msExitFullscreen()
  }
  
  isFullscreen.value = false
}

// 构建RTSP URL
const buildRtspUrl = () => {
  if (!currentDevice.value) return '';

  if (currentDevice.value.device_type === 'nvr') {
    // NVR设备，包含通道号
    return `rtsp://${currentDevice.value.username}:${currentDevice.value.password}@${currentDevice.value.ip_address}:${currentDevice.value.port}/cam/realmonitor?channel=${currentDevice.value.channel || 1}&subtype=${currentDevice.value.stream_type === 'sub' ? 1 : 0}`
  } else {
    // 普通摄像头
    return `rtsp://${currentDevice.value.username}:${currentDevice.value.password}@${currentDevice.value.ip_address}:${currentDevice.value.port}/cam/realmonitor?channel=1&subtype=${currentDevice.value.stream_type === 'sub' ? 1 : 0}`
  }
}

// 导入功能
const handleImport = () => {
  importDialogVisible.value = true
  importFile.value = null
}

const handleFileChange = (file) => {
  if (!file) return

  // 检查文件类型
  const validTypes = [
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv'
  ]

  if (!validTypes.includes(file.raw.type)) {
    ElMessage.error('请上传Excel或CSV格式的文件')
    return false
  }

  // 检查文件大小，不超过10MB
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('文件大小不能超过10MB')
    return false
  }

  importFile.value = file.raw
}

const submitImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请先选择要导入的文件')
    return
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)

    const response = await deviceApi.importDevices(formData)

    if (response.status === 200) {
      ElMessage.success('导入成功')
      importDialogVisible.value = false
      loadData() // 刷新列表
    } else {
      ElMessage.error(`导入失败: ${response.data.detail || '未知错误'}`)
    }
  } catch (error) {
    // console.error('导入设备失败:', error)
    ElMessage.error(`导入失败: ${error.response?.data?.detail || error.message}`)
  } finally {
    importing.value = false
  }
}

// 导出功能
const handleExport = async (command) => {
  try {
    let response
    let filename

    if (command === 'template') {
      // 导出模板
      response = await deviceApi.exportDeviceTemplate()
      filename = '设备导入模板.xlsx'
    } else if (command === 'data') {
      // 导出数据
      response = await deviceApi.exportDevices()
      filename = `设备数据_${new Date().toISOString().split('T')[0]}.xlsx`
    }

    // 处理文件下载
    if (response && response.data) {
      const blob = new Blob([response.data], {
        type: response.headers['content-type'] 
      })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      ElMessage.success('导出成功')
    }
  } catch (error) {
    // console.error('导出失败:', error)
    ElMessage.error(`导出失败: ${error.response?.data?.detail || error.message}`)
  }
}

// 筛选功能
const handleFilter = () => {
  currentPage.value = 1 // 重置到第一页
  isFiltering.value = true
  loadData(true)
}

const handleResetFilter = () => {
  Object.assign(filterForm, {
    device_type: '',
    status: '',
    device_name: '',
    ip_address: '',
    location: '',
    area: ''
  })
  currentPage.value = 1 // 重置到第一页
  isFiltering.value = false
  loadData(false)
}
</script>

<style scoped>
.devices-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.device-list {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.preview-container {
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

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #000;
}

.stream-info {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px 12px;
  background-color: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
}

.preview-controls {
  margin-top: 15px;
  padding: 0 10px;
  display: flex;
  justify-content: flex-end;
}

.fallback-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #000;
  display: none;
}

.upload-demo {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.el-upload__tip {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
}

.el-icon--upload {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 10px;
}

.filter-section {
  margin-bottom: 20px;
  /* padding: 20px; */
  /* background-color: #f8f9fa; */
  border-radius: 8px;
  /* border: 1px solid #e9ecef; */
}

.filter-section .el-form {
  margin-bottom: 0;
}

.filter-section .el-form-item {
  margin-bottom: 0;
}

/* 高优先级对话框样式 - 确保不被菜单和头部遮挡 */
.high-priority-dialog {
  z-index: 999999 !important;
}

.preview-dialog {
  z-index: 100000 !important;
}

.import-dialog {
  z-index: 100001 !important;
}

/* 全屏样式 */
.video-player:fullscreen {
  object-fit: contain;
}

.video-player:-webkit-full-screen {
  object-fit: contain;
}

.video-player:-moz-full-screen {
  object-fit: contain;
}

.video-player:-ms-fullscreen {
  object-fit: contain;
}

/* 全屏按钮样式 */
.preview-controls .el-button {
  min-width: 80px;
}

/* 全屏时的图像显示 */
.fullscreen-image {
  max-width: 100vw;
  max-height: 100vh;
  object-fit: contain;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}
</style> 
