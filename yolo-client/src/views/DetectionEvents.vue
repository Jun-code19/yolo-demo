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
              :label="device.device_name"
              :value="device.device_id"
            />
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
              :key="type"
              :label="type"
              :value="type"
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
            <el-icon><search /></el-icon>搜索
          </el-button>
          <el-button @click="resetFilter">
            重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 事件列表 -->
      <el-table
        :columns="columns"
        :data="eventList"
        :loading="loading"
        :pagination="{
          pageSize: 10,
          current: page,
          total: total,
          onChange: handlePageChange
        }"
        row-key="event_id"
      >
        <!-- 设备名称列 -->
        <template #body-cell="{ column, record }">
          <template v-if="column.dataIndex === 'device_id'">
            {{ getDeviceName(record.device_id) }}
          </template>
          
          <!-- 事件类型列 -->
          <template v-if="column.dataIndex === 'event_type'">
            <el-tag :type="getEventTypeColor(record.event_type)">
              {{ record.event_type }}
            </el-tag>
          </template>
          
          <!-- 置信度列 -->
          <template v-if="column.dataIndex === 'confidence'">
            {{ (record.confidence * 100).toFixed(1) }}%
          </template>
          
          <!-- 时间列 -->
          <template v-if="column.dataIndex === 'timestamp'">
            {{ formatDateTime(record.timestamp) }}
          </template>
          
          <!-- 状态列 -->
          <template v-if="column.dataIndex === 'status'">
            <el-tag :type="getStatusColor(record.status)">
              {{ getStatusLabel(record.status) }}
            </el-tag>
          </template>
          
          <!-- 操作列 -->
          <template v-if="column.dataIndex === 'action'">
            <el-space>
              <el-button type="primary" size="small" @click="viewEvent(record)">
                查看
              </el-button>
              <el-dropdown>
                <template #overlay>
                  <el-menu>
                    <el-menu-item key="flag" @click="updateEventStatus(record, 'flagged')">
                      标记重要
                    </el-menu-item>
                    <el-menu-item key="archive" @click="updateEventStatus(record, 'archived')">
                      归档
                    </el-menu-item>
                    <el-menu-divider />
                    <el-menu-item key="delete" @click="deleteEvent(record)">
                      删除
                    </el-menu-item>
                  </el-menu>
                </template>
                <el-button size="small">
                  更多 <el-icon><down /></el-icon>
                </el-button>
              </el-dropdown>
            </el-space>
          </template>
        </template>
      </el-table>
    </el-card>
    
    <!-- 事件详情模态框 -->
    <el-dialog
      :visible="eventModalVisible"
      :title="`事件详情 - ${selectedEvent?.event_type || ''}`"
      @close="closeEventModal"
      :footer="null"
      width="800px"
    >
      <template v-if="selectedEvent">
        <div class="event-detail">
          <div class="event-image">
            <img
              :src="getImageUrl(selectedEvent.snippet_path, 'marked.jpg')"
              alt="事件图片"
              class="main-image"
              @click="showImagePreview(selectedEvent.snippet_path, 'marked.jpg')"
            />
          </div>
          
          <div class="event-info">
            <el-descriptions :column="1">
              <el-descriptions-item label="设备">
                {{ getDeviceName(selectedEvent.device_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="事件类型">
                <el-tag :type="getEventTypeColor(selectedEvent.event_type)">
                  {{ selectedEvent.event_type }}
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
                  v-model:value="selectedEvent.status"
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
                <el-textarea
                  v-model:value="eventNotes"
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
                  @click="showImagePreview(selectedEvent.snippet_path, 'original.jpg')"
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
    </el-dialog>
    
    <!-- 图片预览 -->
    <el-dialog
      :visible="imagePreviewVisible"
      :footer="null"
      @close="closeImagePreview"
      width="auto"
      center
      destroy-on-close
    >
      <img
        :src="previewImageUrl"
        alt="预览图片"
        style="max-width: 100%; max-height: 80vh;"
      />
    </el-dialog>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Delete, View, Star, Download, StarFilled } from '@element-plus/icons-vue';
import dayjs from 'dayjs';
import { detectionEventApi } from '@/api/detection';
import deviceApi from '@/api/device'

export default defineComponent({
  name: 'DetectionEvents',
  components: {
    Search,
    Delete,
    View,
    Star,
    Download,
    StarFilled
  },
  setup() {
    // 数据加载状态
    const loading = ref(false);
    
    // 表格数据
    const eventList = ref([]);
    const deviceList = ref([]);
    const eventTypes = ref([
      'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
      'dog', 'cat', 'bottle', 'chair', 'laptop', 'cell phone'
    ]);
    
    // 分页
    const page = ref(1);
    const total = ref(0);
    
    // 筛选表单
    const filterForm = reactive({
      device_id: undefined,
      event_type: undefined,
      status: undefined,
      dateRange: undefined,
      min_confidence: undefined
    });
    
    // 表格列定义
    const columns = [
      { title: '设备', dataIndex: 'device_id', key: 'device_id' },
      { title: '事件类型', dataIndex: 'event_type', key: 'event_type' },
      { title: '置信度', dataIndex: 'confidence', key: 'confidence', sorter: true },
      { title: '时间', dataIndex: 'timestamp', key: 'timestamp', sorter: true },
      { title: '状态', dataIndex: 'status', key: 'status', filters: [
        { text: '新事件', value: 'new' },
        { text: '已查看', value: 'viewed' },
        { text: '已标记', value: 'flagged' },
        { text: '已归档', value: 'archived' }
      ]},
      { title: '操作', dataIndex: 'action', key: 'action' }
    ];
    
    // 事件详情模态框
    const eventModalVisible = ref(false);
    const selectedEvent = ref(null);
    const eventNotes = ref('');
    
    // 图片预览
    const imagePreviewVisible = ref(false);
    const previewImageUrl = ref('');
    
    // 获取设备名称
    const getDeviceName = (deviceId) => {
      const device = deviceList.value.find(d => d.device_id === deviceId);
      return device ? device.device_name : deviceId;
    };
    
    // 获取事件类型颜色
    const getEventTypeColor = (eventType) => {
      const colorMap = {
        'person': 'blue',
        'car': 'green',
        'truck': 'cyan',
        'motorcycle': 'purple',
        'bicycle': 'magenta',
        'bus': 'orange'
      };
      return colorMap[eventType] || 'default';
    };
    
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
        'new': 'blue',
        'viewed': 'green',
        'flagged': 'red',
        'archived': 'gray'
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
        const response = await await deviceApi.getDevices();
        deviceList.value = response.data;
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
          skip: (page.value - 1) * 10,
          limit: 10
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
        eventList.value = response.data;
        
        // 暂时假设总数为当前数据长度的10倍
        // 实际应用中应该从API获取总数
        total.value = response.data.length * 10;
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
    
    // 查看事件详情
    const viewEvent = async (event) => {
      selectedEvent.value = { ...event };
      eventNotes.value = event.notes || '';
      eventModalVisible.value = true;
      
      // 如果状态是新事件，自动更新为已查看
      if (event.status === 'new') {
        await updateEventStatus(event, 'viewed', false);
      }
    };
    
    // 关闭事件详情模态框
    const closeEventModal = () => {
      eventModalVisible.value = false;
      selectedEvent.value = null;
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
      if (!event) return;
      
      try {
        await detectionEventApi.deleteEvent(event.event_id);
        
        // 从列表中移除
        eventList.value = eventList.value.filter(e => e.event_id !== event.event_id);
        
        // 如果正在查看该事件，关闭模态框
        if (selectedEvent.value && selectedEvent.value.event_id === event.event_id) {
          closeEventModal();
        }
        
        ElMessage.success('事件已删除');
      } catch (error) {
        ElMessage.error('删除事件失败: ' + error.message);
      }
    };
    
    // 获取事件图片URL
    const getImageUrl = (snippetPath, fileName) => {
      if (!snippetPath) return '';
      // 实际应用中应该从后端获取正确的URL
      return `/storage/${snippetPath}/${fileName}`;
    };
    
    // 显示图片预览
    const showImagePreview = (snippetPath, fileName) => {
      previewImageUrl.value = getImageUrl(snippetPath, fileName);
      imagePreviewVisible.value = true;
    };
    
    // 关闭图片预览
    const closeImagePreview = () => {
      imagePreviewVisible.value = false;
    };
    
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
      total,
      filterForm,
      columns,
      eventModalVisible,
      selectedEvent,
      eventNotes,
      imagePreviewVisible,
      previewImageUrl,
      getDeviceName,
      getEventTypeColor,
      getStatusLabel,
      getStatusColor,
      formatDateTime,
      loadEvents,
      handleSearch,
      resetFilter,
      handlePageChange,
      viewEvent,
      closeEventModal,
      updateEventStatus,
      saveEventNotes,
      deleteEvent,
      getImageUrl,
      showImagePreview,
      closeImagePreview,
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
</style> 