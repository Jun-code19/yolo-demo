<template>
  <div class="detection-config-page">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>检测配置管理</span>
          <div class="header-right">
            <el-button type="primary" @click="showAddModal">
              <el-icon>
                <plus />
              </el-icon>创建配置
            </el-button>
          </div>
        </div>
      </template>

      <!-- 配置列表 -->
      <el-table :data="configList" v-loading="loading" style="width: 100%">
        <!-- 设备名称列 -->
        <el-table-column label="设备" prop="device_id" min-width="120">
          <template #default="scope">
            {{ getDeviceName(scope.row.device_id) }}
          </template>
        </el-table-column>

        <!-- 模型名称列 -->
        <el-table-column label="模型" prop="models_id" min-width="150">
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
        <el-table-column label="检测频率" prop="frequency" min-width="100">
          <template #default="scope">
            <el-tag :type="getFrequencyType(scope.row.frequency)">
              {{ getFrequencyLabel(scope.row.frequency) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 定时检测详细信息列 -->
        <el-table-column label="定时检测详细信息" prop="schedule_config" min-width="250">
          <template #default="scope">
            {{ getScheduleDetail(scope.row) }}
          </template>
        </el-table-column>

        <!-- 保存模式列 -->
        <el-table-column label="保存模式" prop="save_mode" min-width="150">
          <template #default="scope">
            <el-tag :type="getSaveModeType(scope.row.save_mode)">
              {{ getSaveModeLabel(scope.row.save_mode, scope.row.max_storage_days) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 区域设置列 -->
        <el-table-column label="智能方案" prop="area_coordinates" min-width="150">
          <template #default="scope">
            <el-tag>
              {{ getAreaTypeLabel(scope.row.area_coordinates) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 操作列 -->
        <el-table-column label="操作" min-width="230" fixed="right">
          <template #default="scope">
            <el-button-group>
              <el-button type="warning" size="small" @click="scope.row.enabled ? null : setInterestArea(scope.row)"
                :disabled="scope.row.enabled"> <!-- 禁用按钮 -->
                智能
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
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑配置的模态框 -->
    <el-dialog v-model="modalVisible" :title="isEdit ? '编辑检测配置' : '创建检测配置'" width="750px" top="5vh" destroy-on-close
      class="config-dialog">
      <div class="config-steps">
        <div class="step" :class="{ active: currentStep >= 1 }">
          <div class="step-number">1</div>
          <div class="step-label">基本设置</div>
        </div>
        <div class="step-divider"></div>
        <div class="step" :class="{ active: currentStep >= 2 }">
          <div class="step-number">2</div>
          <div class="step-label">定时设置</div>
        </div>
        <div class="step-divider"></div>
        <div class="step" :class="{ active: currentStep >= 3 }">
          <div class="step-number">3</div>
          <div class="step-label">保存设置</div>
        </div>
      </div>

      <el-form ref="formRef" :model="formState" :rules="rules" label-position="top" class="config-form">
        <!-- 基本设置部分 -->
        <div class="section-container" v-show="currentStep === 1">
          <el-divider content-position="left">
            <span class="divider-title">基本设置</span>
          </el-divider>

          <div class="form-section">
            <div class="form-grid">
              <!-- 设备选择 -->
              <el-form-item label="设备" prop="device_id" class="grid-item full-width">
                <el-select v-model="formState.device_id" placeholder="请选择设备" :disabled="isEdit" filterable>
                  <el-option v-for="device in deviceList" :key="device.device_id"
                    :label="`${device.device_name} (${device.device_id})`" :value="device.device_id">
                    <div class="device-option">
                      <el-icon>
                        <VideoCamera />
                      </el-icon>
                      <span>{{ device.device_name }}</span>
                      <span class="device-id">({{ device.device_id }})</span>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>

              <!-- 模型选择 -->
              <el-form-item label="检测模型" prop="models_id" class="grid-item full-width">
                <el-select v-model="formState.models_id" placeholder="请选择检测模型" @change="updateTargetClasses" filterable>
                  <el-option v-for="model in modelList" :key="model.models_id"
                    :label="`${model.models_name} (${getModelTypeName(model.models_type)})`" :value="model.models_id">
                    <div class="model-option">
                      <span>{{ model.models_name }}</span>
                      <el-tag size="small" effect="plain">{{ getModelTypeName(model.models_type) }}</el-tag>
                    </div>
                  </el-option>
                </el-select>
              </el-form-item>

              <!-- 状态和灵敏度 -->
              <div class="form-row">
                <!-- 是否启用 -->
                <el-form-item label="状态" prop="enabled" class="form-item-small">
                  <el-switch v-model="formState.enabled" active-text="启用" inactive-text="禁用" :active-value="true"
                    :inactive-value="false" />
                </el-form-item>

                <!-- 检测灵敏度 -->
                <el-form-item label="检测灵敏度" prop="sensitivity" class="form-item-large">
                  <div class="sensitivity-container">
                    <el-slider v-model="formState.sensitivity" :min="0.1" :max="0.9" :step="0.05"
                      :format-tooltip="value => `${Math.round(value * 100)}%`" :marks="{
                        0.1: '低',
                        0.5: '中',
                        0.9: '高'
                      }" />
                  </div>
                </el-form-item>
              </div>

              <!-- 目标类别 -->
              <el-form-item label="目标类别" prop="target_classes" class="grid-item full-width">
                <el-select v-model="formState.target_classes" multiple placeholder="请选择要检测的目标类别" collapse-tags
                  collapse-tags-tooltip :max-collapse-tags="4" filterable>
                  <el-option v-for="(classItem, index) in targetClasses" :key="classItem.value" :label="classItem.label"
                    :value="classItem.value">
                    <div class="class-option">
                      <span>{{ classItem.label }}</span>
                      <span class="class-id">{{ classItem.value }}</span>
                    </div>
                  </el-option>
                </el-select>
                <div class="select-hint">
                  <div class="hint-buttons">
                    <el-button link size="small" @click="selectAllClasses" v-if="targetClasses.length > 0">
                      <el-icon>
                        <CircleCheckFilled />
                      </el-icon> 全选
                    </el-button>
                    <el-button link size="small" @click="clearAllClasses" v-if="formState.target_classes.length > 0">
                      <el-icon>
                        <CircleCloseFilled />
                      </el-icon> 清空
                    </el-button>
                  </div>
                  <span class="selected-count" v-if="targetClasses.length > 0">
                    已选择 {{ formState.target_classes.length }}/{{ targetClasses.length }}
                  </span>
                </div>
              </el-form-item>
            </div>
          </div>
        </div>

        <!-- 定时设置部分 -->
        <div class="section-container" v-show="currentStep === 2">
          <el-divider content-position="left">
            <span class="divider-title">定时设置</span>
          </el-divider>

          <div class="form-section schedule-section">
            <!-- 检测频率设置 -->
            <div class="schedule-card">
              <div class="card-title">
                <el-icon>
                  <Calendar />
                </el-icon>
                <span>检测频率</span>
              </div>
              <div class="card-content">
                <div class="frequency-content">
                  <el-radio-group v-model="formState.frequency">
                    <div class="frequency-options">
                      <div class="radio-card" :class="{ active: formState.frequency === 'realtime' }">
                        <el-radio value="realtime">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">实时检测</div>
                              <div class="radio-desc">设备连接后立即开始检测</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                      <div class="radio-card" :class="{ active: formState.frequency === 'scheduled' }">
                        <el-radio value="scheduled">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">定时检测</div>
                              <div class="radio-desc">按照预定的时间计划执行检测</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                      <div class="radio-card" :class="{ active: formState.frequency === 'manual' }">
                        <el-radio value="manual">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">手动触发</div>
                              <div class="radio-desc">仅在手动启动时执行检测</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                    </div>
                  </el-radio-group>
                </div>
              </div>
            </div>

            <!-- 定时详细设置 -->
            <template v-if="formState.frequency === 'scheduled'">
              <!-- 模式选择 -->
              <div class="section-header" style="margin-top: 20px;">
                <div class="section-title">配置模式</div>
                <el-radio-group v-model="formState.scheduleMode" @change="handleScheduleModeChange" size="large"
                  class="mode-selector">
                  <el-radio-button value="simple">简单模式</el-radio-button>
                  <el-radio-button value="advanced">高级模式</el-radio-button>
                </el-radio-group>
              </div>

              <!-- 简单模式 -->
              <div v-if="formState.scheduleMode === 'simple'" class="schedule-simple-mode schedule-card">
                <div class="form-row time-settings">
                  <el-form-item label="执行时间" class="form-item">
                    <el-time-picker v-model="formState.scheduleTime" format="HH:mm" placeholder="选择时间"
                      class="time-picker"></el-time-picker>
                  </el-form-item>
                  <el-form-item label="执行时长" class="form-item">
                    <div class="input-with-unit">
                      <el-input-number v-model="formState.scheduleDuration" :min="1" :max="120" :step="1"
                        controls-position="right"></el-input-number>
                      <span class="unit-label">分钟</span>
                    </div>
                  </el-form-item>
                </div>
                <el-form-item label="执行日期">
                  <div class="weekday-selector">
                    <el-checkbox-group v-model="formState.scheduleDays" class="day-checkboxes">
                      <el-checkbox value="1" class="day-checkbox">周一</el-checkbox>
                      <el-checkbox value="2" class="day-checkbox">周二</el-checkbox>
                      <el-checkbox value="3" class="day-checkbox">周三</el-checkbox>
                      <el-checkbox value="4" class="day-checkbox">周四</el-checkbox>
                      <el-checkbox value="5" class="day-checkbox">周五</el-checkbox>
                      <el-checkbox value="6" class="day-checkbox">周六</el-checkbox>
                      <el-checkbox value="0" class="day-checkbox">周日</el-checkbox>
                    </el-checkbox-group>
                    <div class="quick-buttons">
                      <el-button link size="small" @click="selectAllWeekdays">全选</el-button>
                      <el-button link size="small" @click="selectWorkdays">工作日</el-button>
                      <el-button link size="small" @click="selectWeekends">周末</el-button>
                      <el-button link size="small" @click="clearWeekdays">清空</el-button>
                    </div>
                  </div>
                </el-form-item>
              </div>

              <!-- 高级模式 -->
              <div v-else class="schedule-advanced-mode">
                <div class="schedule-cards">
                  <!-- 时间设置卡片 -->
                  <div class="schedule-card">
                    <div class="card-title">
                      <el-icon>
                        <Clock />
                      </el-icon>
                      <span>时间设置</span>
                    </div>
                    <div class="card-content">
                      <el-radio-group v-model="formState.scheduleTimeType" class="time-type-selector">
                        <el-radio value="points">多时间点</el-radio>
                        <el-radio value="range">时间范围</el-radio>
                      </el-radio-group>

                      <!-- 多时间点模式 -->
                      <div v-if="formState.scheduleTimeType === 'points'" class="time-points-section">
                        <div class="time-points-header">
                          <el-button type="primary" plain @click="addTimePoint" size="small">
                            <el-icon>
                              <plus />
                            </el-icon>添加时间点
                          </el-button>
                        </div>
                        <transition-group name="time-point-list" tag="div" class="time-points-list">
                          <div v-for="(time, index) in formState.scheduleTimePoints" :key="index"
                            class="time-point-item">
                            <el-time-picker v-model="formState.scheduleTimePoints[index]" format="HH:mm"
                              class="time-point-picker"></el-time-picker>
                            <el-button type="danger" circle plain @click="removeTimePoint(index)"
                              class="remove-time-btn" size="small">
                              <el-icon>
                                <delete />
                              </el-icon>
                            </el-button>
                          </div>
                        </transition-group>
                        <div v-if="formState.scheduleTimePoints.length === 0" class="empty-time-points">
                          <el-empty description="暂无时间点" :image-size="60"></el-empty>
                        </div>
                      </div>

                      <!-- 时间范围模式 -->
                      <div v-else class="time-range-section">
                        <div class="time-range-row">
                          <el-form-item label="开始时间" class="form-item">
                            <el-time-picker v-model="formState.scheduleStartTime" format="HH:mm" placeholder="开始时间"
                              class="time-picker"></el-time-picker>
                          </el-form-item>
                          <div class="time-separator">至</div>
                          <el-form-item label="结束时间" class="form-item">
                            <el-time-picker v-model="formState.scheduleEndTime" format="HH:mm" placeholder="结束时间"
                              class="time-picker"></el-time-picker>
                          </el-form-item>
                        </div>
                        <el-form-item label="执行间隔">
                          <div class="input-with-unit">
                            <span class="unit-label-prefix">每隔</span>
                            <el-input-number v-model="formState.scheduleInterval" :min="1" :max="120" :step="5"
                              controls-position="right"></el-input-number>
                            <span class="unit-label">分钟执行一次</span>
                          </div>
                        </el-form-item>
                      </div>
                    </div>
                  </div>

                  <!-- 日期设置卡片 -->
                  <div class="schedule-card">
                    <div class="card-title">
                      <el-icon>
                        <Calendar />
                      </el-icon>
                      <span>日期设置</span>
                    </div>
                    <div class="card-content">
                      <el-radio-group v-model="formState.scheduleDateType" class="date-type-selector">
                        <el-radio value="weekday">星期几</el-radio>
                        <el-radio value="monthday">每月日期</el-radio>
                        <el-radio value="specific">特定日期</el-radio>
                      </el-radio-group>

                      <div class="date-content">
                        <!-- 星期几 -->
                        <div v-if="formState.scheduleDateType === 'weekday'" class="weekday-section">
                          <el-checkbox-group v-model="formState.scheduleAdvWeekdays" class="weekday-checkboxes">
                            <el-checkbox value="1" border class="day-checkbox">周一</el-checkbox>
                            <el-checkbox value="2" border class="day-checkbox">周二</el-checkbox>
                            <el-checkbox value="3" border class="day-checkbox">周三</el-checkbox>
                            <el-checkbox value="4" border class="day-checkbox">周四</el-checkbox>
                            <el-checkbox value="5" border class="day-checkbox">周五</el-checkbox>
                            <el-checkbox value="6" border class="day-checkbox">周六</el-checkbox>
                            <el-checkbox value="0" border class="day-checkbox">周日</el-checkbox>
                          </el-checkbox-group>
                          <div class="quick-buttons">
                            <el-button link size="small" @click="selectAllWeekdays">全选</el-button>
                            <el-button link size="small" @click="selectWorkdays">工作日</el-button>
                            <el-button link size="small" @click="selectWeekends">周末</el-button>
                            <el-button link size="small" @click="clearWeekdays">清空</el-button>
                          </div>
                        </div>

                        <!-- 每月日期 -->
                        <div v-else-if="formState.scheduleDateType === 'monthday'" class="monthday-section">
                          <el-select v-model="formState.scheduleMonthdays" multiple placeholder="选择每月几号执行"
                            style="width: 100%" collapse-tags>
                            <el-option v-for="i in 31" :key="i" :label="`${i}日`" :value="i"></el-option>
                          </el-select>
                          <div class="quick-buttons">
                            <el-button link size="small"
                              @click="selectMonthdays([1, 5, 10, 15, 20, 25])">常用日期</el-button>
                            <el-button link size="small" @click="clearMonthdays">清空</el-button>
                          </div>
                        </div>

                        <!-- 特定日期 -->
                        <div v-else class="specific-date-section">
                          <el-date-picker v-model="formState.scheduleSpecificDates" type="dates" placeholder="选择特定日期"
                            style="width: 100%">
                          </el-date-picker>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 执行控制卡片 -->
                  <div class="schedule-card">
                    <div class="card-title">
                      <el-icon>
                        <Setting />
                      </el-icon>
                      <span>执行控制</span>
                    </div>
                    <div class="card-content">
                      <div class="control-grid">
                        <el-form-item label="单次执行时长" class="control-item">
                          <div class="input-with-unit">
                            <el-input-number v-model="formState.scheduleDuration" :min="1" :max="120"
                              controls-position="right"></el-input-number>
                            <span class="unit-label">分钟</span>
                          </div>
                        </el-form-item>

                        <el-form-item label="最大执行次数" class="control-item">
                          <div class="input-with-unit">
                            <el-input-number v-model="formState.scheduleMaxExecutions" :min="-1" :max="100"
                              controls-position="right"></el-input-number>
                            <el-tooltip content="设置为-1表示不限制执行次数" placement="top">
                              <el-icon class="info-icon">
                                <InfoFilled />
                              </el-icon>
                            </el-tooltip>
                          </div>
                        </el-form-item>

                        <el-form-item label="无活动自动停止" class="control-item">
                          <div class="input-with-unit">
                            <el-input-number v-model="formState.scheduleIdleTimeout" :min="0" :max="60"
                              controls-position="right"></el-input-number>
                            <span class="unit-label">分钟</span>
                            <el-tooltip content="设置为0表示不自动停止" placement="top">
                              <el-icon class="info-icon">
                                <InfoFilled />
                              </el-icon>
                            </el-tooltip>
                          </div>
                        </el-form-item>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="empty-step-placeholder">
                <el-empty description="选择定时检测以启用此设置" :image-size="80"></el-empty>
              </div>
            </template>
          </div>
        </div>

        <!-- 保存设置部分 -->
        <div class="section-container" v-show="currentStep === 3">
          <el-divider content-position="left">
            <span class="divider-title">保存设置</span>
          </el-divider>

          <div class="form-section save-section">
            <!-- 保存模式 -->
            <!-- <el-form-item label="保存模式" prop="save_mode"> -->
            <div class="schedule-card">
              <div class="card-title">
                <el-icon>
                  <Edit />
                </el-icon>
                <span>保存模式</span>
              </div>
              <div class="card-content">
                <div class="save-mode-content">
                  <el-radio-group v-model="formState.save_mode">
                    <div class="save-mode-options">
                      <div class="radio-card" :class="{ active: formState.save_mode === 'none' }">
                        <el-radio value="none">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">不保存</div>
                              <div class="radio-desc">仅显示检测结果</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                      <div class="radio-card" :class="{ active: formState.save_mode === 'screenshot' }">
                        <el-radio value="screenshot">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">保存截图</div>
                              <div class="radio-desc">保存当前画面截图</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                      <div class="radio-card" :class="{ active: formState.save_mode === 'video' }">
                        <el-radio value="video">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">保存视频</div>
                              <div class="radio-desc">保存视频片段</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                      <div class="radio-card" :class="{ active: formState.save_mode === 'both' }">
                        <el-radio value="both">
                          <div class="radio-card-content">
                            <div>
                              <div class="radio-title">截图和视频</div>
                              <div class="radio-desc">同时保存两种格式</div>
                            </div>
                          </div>
                        </el-radio>
                      </div>
                    </div>
                  </el-radio-group>
                </div>
              </div>
            </div>
            <!-- </el-form-item> -->

            <!-- 高级配置 -->
            <div v-if="formState.save_mode !== 'none'" class="save-card">
              <div class="card-title">
                <!-- <el-icon><Setting /></el-icon> -->
                <span>存储配置</span>
              </div>
              <div class="card-content">
                <el-form-item label="视频片段时长" prop="save_duration" v-if="formState.save_mode !== 'screenshot'">
                  <div class="input-with-unit">
                    <el-input-number v-model="formState.save_duration" :min="5" :max="60" :step="5"
                      controls-position="right"></el-input-number>
                    <span class="unit-label">秒</span>
                  </div>
                </el-form-item>

                <el-form-item label="事件保留天数" prop="max_storage_days">
                  <div class="input-with-unit">
                    <el-input-number v-model="formState.max_storage_days" :min="1" :max="90" :step="1"
                      controls-position="right"></el-input-number>
                    <span class="unit-label">天</span>
                  </div>
                </el-form-item>
              </div>
            </div>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <div class="step-buttons">
            <el-button @click="prevStep" :disabled="currentStep === 1 || submitLoading">上一步</el-button>
            <el-button type="primary" v-if="currentStep < 3" @click="nextStep">下一步</el-button>
            <el-button type="primary" v-else @click="submitForm" :loading="submitLoading">
              {{ isEdit ? '保存修改' : '创建配置' }}
            </el-button>
          </div>
          <el-button @click="cancelModal" :disabled="submitLoading">取消</el-button>
        </div>
      </template>
    </el-dialog>


  </div>
</template>

<script>
import { defineComponent, ref, reactive, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { Plus, Delete, Edit, VideoPause, VideoPlay, InfoFilled, Calendar, Operation, CircleCloseFilled, Files, VideoCamera, CircleCheckFilled, Clock, Setting, CircleClose } from '@element-plus/icons-vue';
import deviceApi from '@/api/device'
import { detectionConfigApi } from '@/api/detection';
import { startDetection, stopDetection } from '@/api/detection_server';

export default defineComponent({
  name: 'DetectionConfig',
  components: {
    Plus,
    Delete,
    Edit,
    VideoPause,
    VideoPlay,
    InfoFilled,
    Calendar,
    Operation,
    CircleCloseFilled,
    Files,
    VideoCamera,
    CircleCheckFilled,
    Clock,
    Setting,
    CircleClose
  },
  setup() {
    const router = useRouter();

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

    // 高级定时设置当前标签
    const scheduleActiveTab = ref('time');

    // 设置感兴趣区域方法（跳转到新页面）
    const setInterestArea = (config) => {
      router.push({
        name: 'SmartConfigSetting',
        params: {
          configId: config.config_id
        },
        query: {
          deviceId: config.device_id
        }
      });
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
      max_storage_days: 30,
      scheduleTime: null,
      scheduleDays: [],
      scheduleMode: 'simple',
      scheduleTimeType: 'points',
      scheduleTimePoints: [],
      scheduleStartTime: null,
      scheduleEndTime: null,
      scheduleInterval: 5,
      scheduleDateType: 'weekday',
      scheduleAdvWeekdays: [],
      scheduleMonthdays: [],
      scheduleSpecificDates: [],
      scheduleDuration: 10,
      scheduleMaxExecutions: -1,
      scheduleIdleTimeout: 0
    });

    // 步骤控制
    const currentStep = ref(1);

    const nextStep = () => {
      if (currentStep.value < 3) {
        currentStep.value++;
      }
    };

    const prevStep = () => {
      if (currentStep.value > 1) {
        currentStep.value--;
      }
    };

    // 表单校验规则
    const rules = {
      device_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
      models_id: [{ required: true, message: '请选择检测模型', trigger: 'change' }],
      sensitivity: [{ required: true, message: '请设置检测灵敏度', trigger: 'change' }],
      frequency: [{ required: true, message: '请选择检测频率', trigger: 'change' }],
      save_mode: [{ required: true, message: '请选择保存模式', trigger: 'change' }],
      scheduleTime: [{
        required: true,
        message: '请选择定时检测时间',
        trigger: 'change',
        validator: (rule, value, callback) => {
          if (formState.frequency === 'scheduled' && formState.scheduleMode === 'simple' && !value) {
            callback(new Error('请选择定时检测时间'));
          } else {
            callback();
          }
        }
      }],
      scheduleDays: [{
        required: true,
        message: '请选择定时检测日期',
        trigger: 'change',
        validator: (rule, value, callback) => {
          if (formState.frequency === 'scheduled' && formState.scheduleMode === 'simple' && (!value || value.length === 0)) {
            callback(new Error('请选择定时检测日期'));
          } else {
            callback();
          }
        }
      }]
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

    const getAreaTypeLabel = (areaCoordinates) => {
      if (!areaCoordinates || Object.keys(areaCoordinates).length === 0) {
        return '未设置';
      }

      let result = '';

      // 根据分析类型确定主要描述
      if (areaCoordinates.analysisType === 'behavior') {
        result = '行为分析';
        if (areaCoordinates.behaviorType === 'area') {
          result += '-区域检测';
        } else if (areaCoordinates.behaviorType === 'line') {
          result += '-拌线检测';
        }

        if (areaCoordinates.behaviorSubtype === 'directional') {
          const directionText = areaCoordinates.behaviorDirection === 'in' ? '进入' : '离开';
          result += `(${directionText})`;
        }
      } else if (areaCoordinates.analysisType === 'counting') {
        result = '人数统计';
        if (areaCoordinates.countingType === 'occupancy') {
          result += '-区域统计';
        } else if (areaCoordinates.countingType === 'flow') {
          result += '-人流统计';
        }
      } else {
        result = '无智能方案';
      }

      return result;
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

    // 获取频率标签
    const getFrequencyLabel = (frequency) => {
      const map = {
        'realtime': '实时检测',
        'scheduled': '定时检测',
        'manual': '手动触发'
      };
      return map[frequency] || frequency;
    };

    // 获取频率类型（用于标签颜色）
    const getFrequencyType = (frequency) => {
      const map = {
        'realtime': 'success',
        'scheduled': 'warning',
        'manual': 'info'
      };
      return map[frequency] || '';
    };

    // 获取定时检测详细信息
    const getScheduleDetail = (row) => {
      if (row.frequency !== 'scheduled' || !row.schedule_config) {
        return '';
      }

      const config = row.schedule_config;

      // 简单模式
      if (!config.mode || config.mode === 'simple') {
        const time = config.time || '';
        const days = config.days || [];
        const duration = config.duration ? `${config.duration}分钟` : '';

        // 将数字转换为对应的星期名称
        const dayNames = {
          '0': '周日',
          '1': '周一',
          '2': '周二',
          '3': '周三',
          '4': '周四',
          '5': '周五',
          '6': '周六'
        };

        const daysString = days.map(d => dayNames[d]).join(', ');
        return `${time} - ${daysString} ${duration}`;
      }

      // 高级模式
      else {
        let result = [];

        // 时间设置
        if (config.timeType === 'points' && config.timePoints) {
          // 多时间点
          if (config.timePoints.length > 0) {
            result.push(`时间点: ${config.timePoints.join(', ')}`);
          }
        } else if (config.timeType === 'range') {
          // 时间范围
          if (config.startTime && config.endTime) {
            result.push(`时间段: ${config.startTime}-${config.endTime}, 间隔${config.interval || 5}分钟`);
          }
        }

        // 日期设置
        if (config.dateType === 'weekday' && config.weekdays) {
          // 星期几
          const dayNames = {
            '0': '周日', '1': '周一', '2': '周二', '3': '周三',
            '4': '周四', '5': '周五', '6': '周六'
          };
          const weekdays = config.weekdays.map(d => dayNames[d]).join(', ');
          if (weekdays) {
            result.push(`每周: ${weekdays}`);
          }
        } else if (config.dateType === 'monthday' && config.monthdays) {
          //
          const monthdays = config.monthdays.map(d => `${d}日`).join(', ');
          if (monthdays) {
            result.push(`每月: ${monthdays}`);
          }
        } else if (config.dateType === 'specific' && config.specificDates) {
          // 特定日期
          if (config.specificDates.length > 0) {
            result.push(`特定日期: ${config.specificDates.length}个日期`);
          }
        }

        // 执行控制
        const controls = [];
        if (config.duration) {
          controls.push(`执行${config.duration}分钟`);
        }
        if (config.maxExecutions && config.maxExecutions > 0) {
          controls.push(`最多${config.maxExecutions}次`);
        }
        if (config.idleTimeout && config.idleTimeout > 0) {
          controls.push(`空闲${config.idleTimeout}分钟自动停止`);
        }

        if (controls.length > 0) {
          result.push(controls.join(', '));
        }

        return result.join(' | ');
      }
    };

    // 获取保存模式标签
    const getSaveModeLabel = (saveMode, maxStorageDays) => {
      const map = {
        'none': '暂无',
        'screenshot': '截图(' + maxStorageDays + '天)',
        'video': '视频(无)',
        'both': '截图(' + maxStorageDays + '天)'+ '|' + '视频(无)'
      };
      return map[saveMode] || saveMode;
    };

    // 获取保存模式标签类型
    const getSaveModeType = (saveMode) => {
      const map = {
        'none': 'info',
        'screenshot': 'success',
        'video': 'warning',
        'both': 'danger'
      };
      return map[saveMode] || '';
    };

    // 加载配置列表
    const loadConfigList = async () => {
      loading.value = true;
      try {
        const response = await detectionConfigApi.getConfigs();
        configList.value = response.data.data;
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
        deviceList.value = response.data.data;
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
      currentStep.value = 1;
      resetForm();
      modalVisible.value = true;
    };

    // 重置表单
    const resetForm = () => {
      Object.assign(formState, {
        config_id: null,
        device_id: null,
        models_id: null,
        enabled: false,
        sensitivity: 0.5,
        target_classes: [],
        frequency: 'realtime',
        save_mode: 'none',
        save_duration: 10,
        max_storage_days: 30,
        scheduleTime: null,
        scheduleDays: [],
        scheduleMode: 'simple',
        scheduleTimeType: 'points',
        scheduleTimePoints: [],
        scheduleStartTime: null,
        scheduleEndTime: null,
        scheduleInterval: 5,
        scheduleDateType: 'weekday',
        scheduleAdvWeekdays: [],
        scheduleMonthdays: [],
        scheduleSpecificDates: [],
        scheduleDuration: 10,
        scheduleMaxExecutions: -1,
        scheduleIdleTimeout: 0
      });

      if (formRef.value) {
        formRef.value.clearValidate();
        // formRef.value.resetFields();
      }
    };

    // 编辑配置
    const editConfig = (record) => {
      isEdit.value = true;
      currentStep.value = 1;
      // 处理 schedule_config
      let scheduleTime = null;
      let scheduleDays = [];

      // 设置默认值
      const defaultSchedule = {
        scheduleMode: 'simple',
        scheduleTimeType: 'points',
        scheduleTimePoints: [],
        scheduleStartTime: null,
        scheduleEndTime: null,
        scheduleInterval: 5,
        scheduleDateType: 'weekday',
        scheduleAdvWeekdays: [],
        scheduleMonthdays: [],
        scheduleSpecificDates: [],
        scheduleDuration: 10,
        scheduleMaxExecutions: -1,
        scheduleIdleTimeout: 0
      };

      if (record.frequency === 'scheduled' && record.schedule_config) {
        const config = record.schedule_config;

        // 设置模式
        if (config.mode) {
          defaultSchedule.scheduleMode = config.mode;
        }

        // 设置时长
        if (config.duration) {
          defaultSchedule.scheduleDuration = config.duration;
        }

        if (config.mode === 'simple' || !config.mode) {
          // 简单模式
          // 解析时间字符串 "HH:MM" 为 Date 对象
          if (config.time) {
            const [hours, minutes] = config.time.split(':').map(Number);
            const date = new Date();
            date.setHours(hours, minutes, 0, 0);
            scheduleTime = date;
          }
          // 设置星期几
          scheduleDays = config.days || [];
        } else {
          // 高级模式
          defaultSchedule.scheduleTimeType = config.timeType || 'points';
          defaultSchedule.scheduleDateType = config.dateType || 'weekday';
          defaultSchedule.scheduleMaxExecutions = config.maxExecutions !== undefined ? config.maxExecutions : -1;
          defaultSchedule.scheduleIdleTimeout = config.idleTimeout || 0;

          // 时间设置
          if (config.timeType === 'points' && config.timePoints && config.timePoints.length > 0) {
            // 多时间点
            defaultSchedule.scheduleTimePoints = config.timePoints.map(timeStr => {
              const [hours, minutes] = timeStr.split(':').map(Number);
              const date = new Date();
              date.setHours(hours, minutes, 0, 0);
              return date;
            });
          } else if (config.timeType === 'range') {
            // 时间范围
            if (config.startTime) {
              const [startH, startM] = config.startTime.split(':').map(Number);
              const startDate = new Date();
              startDate.setHours(startH, startM, 0, 0);
              defaultSchedule.scheduleStartTime = startDate;
            }

            if (config.endTime) {
              const [endH, endM] = config.endTime.split(':').map(Number);
              const endDate = new Date();
              endDate.setHours(endH, endM, 0, 0);
              defaultSchedule.scheduleEndTime = endDate;
            }

            defaultSchedule.scheduleInterval = config.interval || 5;
          }

          // 日期设置
          if (config.dateType === 'weekday') {
            defaultSchedule.scheduleAdvWeekdays = config.weekdays || [];
          } else if (config.dateType === 'monthday') {
            defaultSchedule.scheduleMonthdays = config.monthdays || [];
          } else if (config.dateType === 'specific' && config.specificDates && config.specificDates.length > 0) {
            defaultSchedule.scheduleSpecificDates = config.specificDates.map(dateStr => new Date(dateStr));
          }
        }
      }

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
        max_storage_days: record.max_storage_days,
        scheduleTime: scheduleTime,
        scheduleDays: scheduleDays,
        ...defaultSchedule
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
              // 准备提交的数据
              const submitData = {
                models_id: formState.models_id,
                enabled: formState.enabled,
                sensitivity: formState.sensitivity,
                target_classes: formState.target_classes,
                frequency: formState.frequency,
                save_mode: formState.save_mode,
                save_duration: formState.save_duration,
                max_storage_days: formState.max_storage_days
              };

              // 如果是定时检测，添加定时配置
              if (formState.frequency === 'scheduled') {
                let scheduleConfig = {
                  mode: formState.scheduleMode,
                  duration: formState.scheduleDuration
                };

                if (formState.scheduleMode === 'simple') {
                  // 简单模式配置
                  const timeObj = formState.scheduleTime;
                  const hours = timeObj.getHours().toString().padStart(2, '0');
                  const minutes = timeObj.getMinutes().toString().padStart(2, '0');

                  scheduleConfig = {
                    ...scheduleConfig,
                    time: `${hours}:${minutes}`,
                    days: formState.scheduleDays
                  };
                } else {
                  // 高级模式配置
                  scheduleConfig = {
                    ...scheduleConfig,
                    timeType: formState.scheduleTimeType,
                    dateType: formState.scheduleDateType,
                    maxExecutions: formState.scheduleMaxExecutions,
                    idleTimeout: formState.scheduleIdleTimeout
                  };

                  // 根据时间类型配置
                  if (formState.scheduleTimeType === 'points') {
                    // 多时间点
                    scheduleConfig.timePoints = formState.scheduleTimePoints.map(time => {
                      const h = time.getHours().toString().padStart(2, '0');
                      const m = time.getMinutes().toString().padStart(2, '0');
                      return `${h}:${m}`;
                    });
                  } else {
                    // 时间范围
                    const startTimeObj = formState.scheduleStartTime;
                    const endTimeObj = formState.scheduleEndTime;

                    if (startTimeObj && endTimeObj) {
                      const startH = startTimeObj.getHours().toString().padStart(2, '0');
                      const startM = startTimeObj.getMinutes().toString().padStart(2, '0');
                      const endH = endTimeObj.getHours().toString().padStart(2, '0');
                      const endM = endTimeObj.getMinutes().toString().padStart(2, '0');

                      scheduleConfig.startTime = `${startH}:${startM}`;
                      scheduleConfig.endTime = `${endH}:${endM}`;
                      scheduleConfig.interval = formState.scheduleInterval;
                    }
                  }

                  // 根据日期类型配置
                  if (formState.scheduleDateType === 'weekday') {
                    scheduleConfig.weekdays = formState.scheduleAdvWeekdays;
                  } else if (formState.scheduleDateType === 'monthday') {
                    scheduleConfig.monthdays = formState.scheduleMonthdays;
                  } else if (formState.scheduleDateType === 'specific') {
                    scheduleConfig.specificDates = formState.scheduleSpecificDates.map(date => formatDate(date));
                  }
                }

                submitData.schedule_config = scheduleConfig;
              }

              if (isEdit.value) {
                // 更新配置
                await detectionConfigApi.updateConfig(formState.config_id, submitData);
                ElMessage.success('配置更新成功');
              } else {
                // 创建配置
                // 如果是新建，需要添加设备ID
                submitData.device_id = formState.device_id;
                await detectionConfigApi.createConfig(submitData);
                ElMessage.success('配置创建成功');
              }

              modalVisible.value = false;
              loadConfigList();
            } catch (error) {
              ElMessage.error('提交失败: ' + error.message);
            } finally {
              submitLoading.value = false;
            }
          } else {
            ElMessage.error('请完善表单信息');
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

    // 新增定时设置处理方法
    const handleScheduleModeChange = (mode) => {
      // 切换模式时，保留相关设置
      if (mode === 'advanced' && formState.scheduleAdvWeekdays.length === 0 && formState.scheduleDays.length > 0) {
        // 从简单模式切换到高级模式，将简单模式的星期几设置转移到高级模式
        formState.scheduleAdvWeekdays = [...formState.scheduleDays];
      } else if (mode === 'simple' && formState.scheduleDays.length === 0 && formState.scheduleAdvWeekdays.length > 0) {
        // 从高级模式切换到简单模式，将高级模式的星期几设置转移到简单模式
        formState.scheduleDays = [...formState.scheduleAdvWeekdays];
      }
    };

    // 添加时间点
    const addTimePoint = () => {
      const now = new Date();
      now.setHours(now.getHours(), 0, 0, 0); // 设置为当前小时整点
      formState.scheduleTimePoints.push(now);
    };

    // 移除时间点
    const removeTimePoint = (index) => {
      formState.scheduleTimePoints.splice(index, 1);
    };

    // 格式化日期为字符串
    const formatDate = (date) => {
      if (!date) return '';
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    };

    // 星期几选择辅助方法
    const selectAllWeekdays = () => {
      formState.scheduleAdvWeekdays = ['0', '1', '2', '3', '4', '5', '6'];
    };

    const selectWorkdays = () => {
      formState.scheduleAdvWeekdays = ['1', '2', '3', '4', '5'];
    };

    const selectWeekends = () => {
      formState.scheduleAdvWeekdays = ['0', '6'];
    };

    const clearWeekdays = () => {
      formState.scheduleAdvWeekdays = [];
    };

    // 每月日期选择辅助方法
    const selectMonthdays = (days) => {
      formState.scheduleMonthdays = days;
    };

    const clearMonthdays = () => {
      formState.scheduleMonthdays = [];
    };

    // 目标类别选择辅助方法
    const selectAllClasses = () => {
      formState.target_classes = targetClasses.value.map(item => item.value);
    };

    const clearAllClasses = () => {
      formState.target_classes = [];
    };

    return {
      getAreaTypeLabel,
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
      targetClasses,
      setInterestArea,
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
      deleteConfig,
      getScheduleDetail,
      handleScheduleModeChange,
      addTimePoint,
      removeTimePoint,
      formatDate,
      selectAllWeekdays,
      selectWorkdays,
      selectWeekends,
      clearWeekdays,
      selectMonthdays,
      clearMonthdays,
      selectAllClasses,
      clearAllClasses,
      scheduleActiveTab,
      currentStep,
      nextStep,
      prevStep
    };
  }
});
</script>

<style scoped>
.form-item-container {
  display: flex;
  justify-content: flex-start;
  gap: 20px;
}

.form-item-left {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
}

/* 基础样式 */
.divider-title {
  font-size: 16px;
  font-weight: 500;
  color: #409EFF;
}

.form-section {
  margin-bottom: 20px;
  padding: 5px 0;
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-row {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.form-item-small {
  flex: 1;
  min-width: 180px;
  margin-bottom: 0;
}

.form-item-large {
  flex: 2;
  min-width: 300px;
  margin-bottom: 0;
}

.form-item {
  flex: 1;
  min-width: 220px;
  margin-bottom: 0;
}

.full-width {
  width: 100%;
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

.unit-label-prefix {
  color: #606266;
  font-size: 14px;
  margin-right: 2px;
}

/* 灵敏度滑块 */
.sensitivity-container {
  width: 100%;
  padding: 5px 0;
}

:deep(.el-slider__marks-text) {
  color: #909399;
  font-size: 12px;
}

/* 目标类别选择 */
.select-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 12px;
}

.hint-buttons {
  display: flex;
  gap: 10px;
}

.selected-count {
  color: #909399;
}

/* 设备和模型选项 */
.device-option,
.model-option,
.class-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-id,
.class-id {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
}

.save-mode-content,
.frequency-content {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 选择卡片样式 */
.frequency-options,
.save-mode-options {
  display: flex;
  flex-direction: row;
  gap: 12px;
}

.radio-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.radio-card.active {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.radio-card:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.radio-card-content {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.radio-card-content .el-icon {
  font-size: 18px;
  margin-top: 2px;
  color: #409eff;
}

.radio-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.radio-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

/* 定时设置 */
.mode-selector {
  margin-bottom: 20px;
  text-align: center;
}

.schedule-tabs {
  margin-bottom: 0;
}

.tab-content {
  padding: 15px 0;
}

.time-picker {
  width: 100%;
}

.time-type-selector,
.date-type-selector {
  margin-bottom: 15px;
}

.date-content {
  margin-top: 15px;
}

.time-separator {
  font-weight: bold;
  color: #606266;
  padding: 0 10px;
  font-size: 16px;
  display: flex;
  align-items: center;
}

/* 时间点样式 */
.time-points-header {
  margin-bottom: 15px;
}

.time-points-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.time-point-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  transition: all 0.3s;
}

.time-point-item:hover {
  background-color: #ecf5ff;
}

.time-point-picker {
  width: 100%;
}

.empty-time-points {
  padding: 15px 0;
  text-align: center;
}

/* 时间范围样式 */
.time-range-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 15px;
}

/* 日期选择样式 */
.weekday-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 15px;
}

.quick-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}

/* 执行控制样式 */
.control-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 15px;
}

.control-item {
  margin-bottom: 0;
}

.info-icon {
  color: #909399;
  cursor: pointer;
}

/* 高级保存选项 */
.advanced-save-options {
  margin-top: 15px;
}

.slider-with-value {
  padding: 5px 0;
}

/* 动画效果 */
.time-point-list-enter-active,
.time-point-list-leave-active {
  transition: all 0.3s;
}

.time-point-list-enter-from,
.time-point-list-leave-to {
  opacity: 0;
  transform: translateY(-15px);
}

/* 对话框样式 */
:deep(.el-dialog__body) {
  padding: 0 20px 10px;
  max-height: 60vh;
  overflow-y: auto;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  padding-bottom: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 响应式设计 */
@media screen and (max-width: 768px) {

  .form-row,
  .time-range-row {
    flex-direction: column;
    gap: 15px;
  }

  .time-separator {
    align-self: center;
  }

  .control-grid {
    grid-template-columns: 1fr;
  }
}

/* 定时设置部分样式 */
.schedule-section {
  margin-top: 5px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 500;
  color: #606266;
}

.schedule-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 15px;
  margin-top: 5px;
}

.schedule-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s;
}

.schedule-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.card-title {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 500;
  color: #409EFF;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 10px;
}

.card-title .el-icon {
  margin-right: 8px;
  font-size: 18px;
}

.card-content {
  padding: 4px 0;
}

.time-settings {
  margin-bottom: 15px;
}

.day-checkbox {
  margin-right: 8px;
  margin-bottom: 8px;
}

.weekday-selector {
  display: flex;
  flex-direction: column;
}

.day-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

/* 响应式处理 */
@media screen and (max-width: 768px) {
  .schedule-cards {
    grid-template-columns: 1fr;
  }
}

/* 保存设置部分样式 */
.save-section {
  margin-top: 5px;
}

.save-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s;
  margin-top: 15px;
}

.save-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 滑块样式优化 */
.slider-with-value {
  padding: 5px 10px;
}

:deep(.el-slider__runway) {
  margin: 12px 0;
}

:deep(.el-slider__bar) {
  background-color: #409EFF;
}

:deep(.el-slider__button) {
  border-color: #409EFF;
  width: 16px;
  height: 16px;
}

:deep(.el-slider__marks-text) {
  margin-top: 8px;
  color: #606266;
}

/* 步骤指示器样式 */
.config-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 25px;
  padding: 0 20px;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  z-index: 1;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #f2f6fc;
  border: 2px solid #dcdfe6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  color: #909399;
  margin-bottom: 8px;
  transition: all 0.3s;
}

.step.active .step-number {
  background-color: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
}

.step-label {
  font-size: 14px;
  color: #606266;
  transition: all 0.3s;
}

.step.active .step-label {
  color: #409eff;
  font-weight: 500;
}

.step-divider {
  flex: 1;
  height: 2px;
  background-color: #dcdfe6;
  margin: 0 15px;
  position: relative;
  top: -13px;
  max-width: 80px;
  transition: all 0.3s;
}

.step-buttons {
  display: flex;
  gap: 10px;
}

.section-container {
  min-height: 400px;
}

.empty-step-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 250px;
}

/* 卡片头部样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-right {
  margin-left: auto;
}
</style>