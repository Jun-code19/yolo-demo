<template>
  <div class="detection-events-page">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>检测事件记录</span>
        </div>
      </template>
      
      <!-- 筛选条件 -->
      <el-form :model="filterForm" inline class="filter-form">
        <el-form-item label="设备">
          <el-select
            v-model="filterForm.device_id"
            placeholder="选择设备"
            style="width: 200px"
            clearable
          >
            <el-option
              v-for="device in deviceList"
              :key="device.device_id"
              :label="`${device.device_name} (${device.device_id})`"
              :value="device.device_id"
            >
              <div class="device-option">
                <span>{{ device.device_name }}</span>
                <span class="device-id">({{ device.device_id }})</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        
        <el-form-item label="事件类型">
          <el-select
            v-model="filterForm.event_type"
            placeholder="选择类型"
            style="width: 150px"
            clearable
          >
            <el-option
              v-for="type in eventTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            placeholder="选择状态"
            style="width: 120px"
            clearable
          >
            <el-option value="new" label="新事件" />
            <el-option value="viewed" label="已查看" />
            <el-option value="flagged" label="已标记" />
            <el-option value="archived" label="已归档" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="最小置信度">
          <el-slider
            v-model="filterForm.min_confidence"
            :min="0"
            :max="1"
            :step="0.05"
            :show-tooltip="true"
            style="width: 150px"
          />
        </el-form-item>
        
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 300px"
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetFilter">
            重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 事件列表 -->
      <el-table
        :data="eventList"
        :loading="loading"
        row-key="event_id"
        style="width: 100%"
      >
        <el-table-column
          prop="device_id"
          label="设备"
          min-width="120"
        >
          <template #default="{ row }">           
              <span>{{ getDeviceName(row.device_id) }}</span>
              <span>({{ row.device_id }})</span>
          </template>
        </el-table-column>

        <el-table-column
          prop="event_type"
          label="事件类型"
          min-width="120"
        >
          <template #default="{ row }">
            <el-tag :type="getEventTypeColor(row.event_type)">
              {{ getEventTypeName(row.event_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
          prop="confidence"
          label="置信度"
          min-width="100"
        >
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(1) }}%
          </template>
        </el-table-column>

        <el-table-column
          prop="timestamp"
          label="时间"
          min-width="160"
        >
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>

        <el-table-column
          prop="status"
          label="状态"
          min-width="100"
        >
          <template #default="{ row }">
            <el-tag :type="getStatusColor(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
          label="操作"
          width="180"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button-group>
              <el-button type="primary" size="small" @click="viewEvent(row)">
                查看
              </el-button>
              <el-dropdown>
                <el-button size="small">
                  更多 <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="updateEventStatus(row, 'flagged')">
                      标记重要
                    </el-dropdown-item>
                    <el-dropdown-item @click="updateEventStatus(row, 'archived')">
                      归档
                    </el-dropdown-item>
                    <el-divider border-style="dashed" />
                    <el-dropdown-item @click="deleteEvent(row)">
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="prev, pager, next, jumper, ->, total, sizes"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
    
    <!-- 事件详情模态框 -->
    <el-dialog
      v-model="eventModalVisible"
      :title="`事件详情 - ${selectedEvent?.event_type || ''}`"
      width="800px"
      destroy-on-close
    >
      <template v-if="selectedEvent">
        <div class="event-detail">
          <div class="event-image">
            <img
              :src="selectedEventThumbnail"
              alt="事件图片"
              class="main-image"
              @click="showImagePreview(selectedEvent.thumbnail_path)"
            />
          </div>
          
          <div class="event-info">
            <el-descriptions :column="1">
              <el-descriptions-item label="设备">
                <span>{{ getDeviceName(selectedEvent.device_id) }}</span>
                <span>({{ selectedEvent.device_id }})</span>
              </el-descriptions-item>
              <el-descriptions-item label="事件类型">
                <el-tag :type="getEventTypeColor(selectedEvent.event_type)">
                  {{ getEventTypeName(selectedEvent.event_type) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="置信度">
                {{ (selectedEvent.confidence * 100).toFixed(1) }}%
              </el-descriptions-item>
              <el-descriptions-item label="时间">
                {{ formatDateTime(selectedEvent.timestamp) }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-select
                  v-model="selectedEvent.status"
                  style="width: 100%"
                  @change="(val) => updateEventStatus(selectedEvent, val)"
                >
                  <el-option value="new" label="新事件" />
                  <el-option value="viewed" label="已查看" />
                  <el-option value="flagged" label="已标记" />
                  <el-option value="archived" label="已归档" />
                </el-select>
              </el-descriptions-item>
              <el-descriptions-item label="备注">
                <el-input
                  v-model="eventNotes"
                  type="textarea"
                  :rows="3"
                  placeholder="添加事件备注..."
                />
                <el-button
                  type="primary"
                  style="margin-top: 8px"
                  @click="saveEventNotes"
                >
                  保存备注
                </el-button>
              </el-descriptions-item>
            </el-descriptions>
            
            <div class="event-actions">
              <el-space>
                <el-button
                  type="primary"
                  @click="showImagePreview(selectedEvent.event_id)"
                >
                  查看原图
                </el-button>
                <el-button
                  type="primary"
                  v-if="hasVideo(selectedEvent)"
                  @click="playVideo(selectedEvent)"
                >
                  播放视频
                </el-button>
                <el-button
                  type="default"
                  @click="downloadEvent(selectedEvent)"
                >
                  下载证据
                </el-button>
              </el-space>
            </div>
          </div>
        </div>
      </template>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="eventModalVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 图片预览 -->
    <el-dialog
      v-model="imagePreviewVisible"
      fullscreen
      destroy-on-close
      :modal="true"
    >
    <div style="display: flex; justify-content: center; align-items: center; max-height: 90vh; overflow: hidden;" 
      @wheel="handleWheel"
      @mousedown="startDrag"
      @mouseup="stopDrag"
      @mousemove="drag"
    >
      <img
        :src="previewImageUrl"
        alt="预览图片"
        :style="imageStyle"
      />
    </div>
    </el-dialog>
  </div>
</template>

<script>
  import { defineComponent, ref, reactive, onMounted } from 'vue';
  import { ElMessage, ElMessageBox } from 'element-plus';
  import { Search, Delete, View, Star, Download, StarFilled, ArrowDown } from '@element-plus/icons-vue';
  import dayjs from 'dayjs';
  import { detectionEventApi } from '@/api/detection';
  import deviceApi from '@/api/device';

export default defineComponent({
  name: 'DetectionEvents',
  components: {
    Search,
    Delete,
    View,
    Star,
    Download,
    StarFilled,
    ArrowDown
  },
  setup() {
    // 数据加载状态
    const loading = ref(false);
    
    // 表格数据
    const eventList = ref([]);
    const deviceList = ref([]);
    const eventTypes = ref([
    { label: '目标检测', value: 'object_detection' },
    { label: '图像分割', value: 'segmentation' },
    { label: '关键点检测', value: 'keypoint' },
    { label: '姿态估计', value: 'pose' },
    { label: '人脸识别', value: 'face' },
    { label: '其他类型', value: 'other' }
  ]);
    
    // 分页
    const page = ref(1);
    const pageSize = ref(10);
    const total = ref(0);
    
    // 筛选表单
    const filterForm = reactive({
      device_id: undefined,
      event_type: undefined,
      status: undefined,
      dateRange: undefined,
      min_confidence: undefined
    });
    
    // 事件详情模态框
    const eventModalVisible = ref(false);
    const selectedEvent = ref(null);
    const eventNotes = ref('');
    
    // 图片预览
    const selectedEventThumbnail = ref('');
    const imagePreviewVisible = ref(false);
    const previewImageUrl = ref('');
    
    const scale = ref(0.75);  // 用于缩放
    const imageStyle = ref({ transform: `scale(${scale.value}) translate(0px, 0px)` });  // 动态样式
    const isDragging = ref(false);  // 拖动状态
    const startX = ref(0);  // 鼠标起始位置
    const startY = ref(0);
    const translateX = ref(0);  // 图片位移
    const translateY = ref(0);

    // 鼠标滚轮事件处理
    const handleWheel = (event) => {
      event.preventDefault();  // 阻止默认滚动行为
      const delta = event.deltaY < 0 ? 0.1 : -0.1;  // 根据滚轮方向调整缩放
      scale.value = Math.min(Math.max(scale.value + delta, 0.5), 3);  // 限制缩放范围
      imageStyle.value.transform = `scale(${scale.value}) translate(${translateX.value}px, ${translateY.value}px)`;  // 更新样式
    };

    // 鼠标按下事件
    const startDrag = (event) => {
      isDragging.value = true;
      startX.value = event.clientX - translateX.value;  // 记录起始位置
      startY.value = event.clientY - translateY.value;

      // 添加鼠标抬起事件监听
      window.addEventListener('mouseup', stopDrag);
      window.addEventListener('mousemove', drag);
    };

    // 鼠标抬起事件
    const stopDrag = () => {
      isDragging.value = false;

      // 移除鼠标抬起和移动事件监听
      window.removeEventListener('mouseup', stopDrag);
      window.removeEventListener('mousemove', drag);
    };

    // 鼠标移动事件
    const drag = (event) => {
      if (isDragging.value) {
        translateX.value = event.clientX - startX.value;  // 更新位移
        translateY.value = event.clientY - startY.value;
        imageStyle.value.transform = `scale(${scale.value}) translate(${translateX.value}px, ${translateY.value}px)`;  // 更新样式
      }
    };

    // 获取设备名称
    const getDeviceName = (deviceId) => {
      const device = deviceList.value.find(d => d.device_id === deviceId);
      return device ? device.device_name : deviceId;
    };
    
    // 获取事件类型颜色
    const getEventTypeColor = (eventType) => {
      const colorMap = {
        'object_detection': 'primary',
        'segmentation': 'success',
        'keypoint': 'warning',
        'pose': 'danger',
        'face': 'info',
        'other': 'success'
      };
      return colorMap[eventType] || 'default';
    };

    // 获取模型类型名称
    const getEventTypeName = (eventType) => {
      const typeMap = {
        'object_detection': '目标检测',
        'segmentation': '图像分割',
        'keypoint': '关键点检测',
        'pose': '姿态估计',
        'face': '人脸识别',
        'other': '其他类型'
      }
      return typeMap[eventType] || 'default'
    }
    
    // 获取状态标签
    const getStatusLabel = (status) => {
      const map = {
        'new': '新事件',
        'viewed': '已查看',
        'flagged': '已标记',
        'archived': '已归档'
      };
      return map[status] || status;
    };
    
    // 获取状态颜色
    const getStatusColor = (status) => {
      const map = {
        'new': 'primary',
        'viewed': 'success',
        'flagged': 'warning',
        'archived': 'info'
      };
      return map[status] || 'default';
    };
    
    // 格式化日期时间
    const formatDateTime = (dateStr) => {
      if (!dateStr) return '';
      return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss');
    };
    
    // 加载设备列表
    const loadDeviceList = async () => {
      try {
        const response = await deviceApi.getDevices();        
        deviceList.value = response.data.data;
      } catch (error) {
        ElMessage.error('获取设备列表失败: ' + error.message);
      }
    };
    
    // 加载事件列表
    const loadEvents = async () => {
      loading.value = true;
      
      try {
        // 构建查询参数
        const params = {
          skip: (page.value - 1) * pageSize.value,
          limit: pageSize.value
        };
        
        if (filterForm.device_id) {
          params.device_id = filterForm.device_id;
        }
        
        if (filterForm.event_type) {
          params.event_type = filterForm.event_type;
        }
        
        if (filterForm.status) {
          params.status = filterForm.status;
        }
        
        if (filterForm.dateRange && filterForm.dateRange.length === 2) {
          params.start_date = filterForm.dateRange[0].toISOString();
          params.end_date = filterForm.dateRange[1].toISOString();
        }
        
        if (filterForm.min_confidence) {
          params.min_confidence = filterForm.min_confidence;
        }
        
        const response = await detectionEventApi.getEvents(params);
        // 从修改后的API响应结构中获取数据和总数
        eventList.value = response.data.data;
        total.value = response.data.total;
      } catch (error) {
        ElMessage.error('获取事件列表失败: ' + error.message);
      } finally {
        loading.value = false;
      }
    };

    const handleSearch = () => {
      page.value = 1;
      loadEvents();
    };
    
    // 重置筛选条件
    const resetFilter = () => {
      Object.assign(filterForm, {
        device_id: undefined,
        event_type: undefined,
        status: undefined,
        dateRange: undefined,
        min_confidence: undefined
      });
      
      page.value = 1;
      loadEvents();
    };
    
    // 切换页码
    const handlePageChange = (newPage) => {
      page.value = newPage;
      loadEvents();
    };
    
    // 切换每页显示数量
    const handleSizeChange = (newSize) => {
      pageSize.value = newSize;
      loadEvents();
    };
    
    // 查看事件详情
    const viewEvent = async (event) => {
      selectedEvent.value = { ...event };
      eventNotes.value = event.notes || '';
      eventModalVisible.value = true;
      
      // 加载缩略图
      // selectedEventThumbnail.value = await loadThumbnail(event.event_id);
      selectedEventThumbnail.value = getImageUrl(event.thumbnail_path);

      // 如果状态是新事件，自动更新为已查看
      if (event.status === 'new') {
        await updateEventStatus(event, 'viewed', false);
      }
    };
    
    // 更新事件状态
    const updateEventStatus = async (event, newStatus, showMessage = true) => {
      try {
        await detectionEventApi.updateEventStatus(event.event_id, newStatus);
        
        // 更新本地状态
        if (selectedEvent.value && selectedEvent.value.event_id === event.event_id) {
          selectedEvent.value.status = newStatus;
        }
        
        // 更新列表中的状态
        const index = eventList.value.findIndex(e => e.event_id === event.event_id);
        if (index !== -1) {
          eventList.value[index].status = newStatus;
        }
        
        if (showMessage) {
          ElMessage.success('状态更新成功');
        }
      } catch (error) {
        ElMessage.error('更新状态失败: ' + error.message);
      }
    };
    
    // 保存事件备注
    const saveEventNotes = async () => {
      if (!selectedEvent.value) return;
      
      try {
        await detectionEventApi.updateEventNotes(selectedEvent.value.event_id, eventNotes.value);
        
        // 更新本地和列表状态
        selectedEvent.value.notes = eventNotes.value;
        
        const index = eventList.value.findIndex(e => e.event_id === selectedEvent.value.event_id);
        if (index !== -1) {
          eventList.value[index].notes = eventNotes.value;
        }
        
        ElMessage.success('备注保存成功');
      } catch (error) {
        ElMessage.error('保存备注失败: ' + error.message);
      }
    };
    
    // 删除事件
    const deleteEvent = async (event) => {
      ElMessageBox.confirm(
        `确认删除该事件吗？`,
        '删除确认',
        {
          confirmButtonText: '确认',
          cancelButtonText: '取消',
          type: 'warning'
        }
      ).then(async () => {
        try {
          await detectionEventApi.deleteEvent(event.event_id);
          
          // 从列表中移除
          eventList.value = eventList.value.filter(e => e.event_id !== event.event_id);
          
          // 如果正在查看该事件，关闭模态框
          if (selectedEvent.value && selectedEvent.value.event_id === event.event_id) {
            eventModalVisible.value = false;
          }
          
          ElMessage.success('事件已删除');
        } catch (error) {
          ElMessage.error('删除事件失败: ' + error.message);
        }
      }).catch(() => {});
    };
    
    const loadThumbnail = async (eventId) => {
      try {
          const thumbnailUrl = await detectionEventApi.fetchThumbnail(eventId);            
          return thumbnailUrl; // 返回图像 URL         
      } catch (error) {
          console.error('加载缩略图失败:', error);
      }
    };

    // 获取事件图片URL
    const getImageUrl = (thumbnailPath) => {
      if (!thumbnailPath) return '';
      
      // 使用相对路径，通过Nginx代理访问后端服务
      const baseUrl = '/api/v1/files';
  
      // 返回完整的图片URL
      return `${baseUrl}/${thumbnailPath.replace(/\\/g, '/')}`; // 替换反斜杠为正斜杠
    };
    
    // 显示图片预览
    const showImagePreview = (thumbnailPath) => {
      // const result = getImageUrl(thumbnailPath);
      // if(result)
      //   previewImageUrl.value = result;
      // else
      previewImageUrl.value = selectedEventThumbnail.value
      
      imagePreviewVisible.value = true;
    };
    
    // // 显示图片预览
    // const showImagePreview = (eventId) => {
    //   previewImageUrl.value = selectedEventThumbnail.value
    //   imagePreviewVisible.value = true;
    // };
    
    // 检查是否有视频
    const hasVideo = (event) => {
      // 根据实际情况判断是否有关联视频
      return event.save_mode === 'video' || event.save_mode === 'both';
    };
    
    // 播放视频
    const playVideo = (event) => {
      // 实现视频播放逻辑
      ElMessage.info('视频播放功能正在开发中');
    };
    
    // 下载事件证据
    const downloadEvent = (event) => {
      // 实现下载逻辑
      ElMessage.info('下载功能正在开发中');
    };
    
    // 初始化
    onMounted(() => {
      loadDeviceList();
      loadEvents();
    });
    
    return {
      loading,
      eventList,
      deviceList,
      eventTypes,
      page,
      pageSize,
      total,
      filterForm,
      eventModalVisible,
      selectedEvent,
      eventNotes,
      imagePreviewVisible,
      previewImageUrl,
      imageStyle,
      selectedEventThumbnail,
      handleWheel,
      startDrag,
      stopDrag,
      drag,
      getDeviceName,
      getEventTypeColor,
      getEventTypeName,
      getStatusLabel,
      getStatusColor,
      formatDateTime,
      loadEvents,
      handleSearch,
      resetFilter,
      handlePageChange,
      handleSizeChange,
      viewEvent,
      updateEventStatus,
      saveEventNotes,
      deleteEvent,
      loadThumbnail,
      showImagePreview,
      hasVideo,
      playVideo,
      downloadEvent
    };
  }
});
</script>

<style scoped>
.detection-events-page {
  padding: 24px;
}

.main-card {
  margin-bottom: 24px;
}

.filter-form {
  margin-bottom: 24px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.event-detail {
  display: flex;
  gap: 24px;
}

.event-image {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.main-image {
  max-width: 100%;
  cursor: pointer;
  border: 1px solid #eee;
  border-radius: 4px;
}

.event-info {
  flex: 1;
}

.event-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.device-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-id {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}
</style> 