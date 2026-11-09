<template>
  <div class="person-search-page">
    <div class="page-header">
      <div>
        <h2>人员搜索</h2>
        <p>轨迹聚合 + OSNet ReID + k-reciprocal 重排 · 辅助以图搜人</p>
      </div>
      <el-space wrap>
        <el-button type="primary" :loading="rebuilding" @click="handleRebuildEmbeddings">
          重建图库特征
        </el-button>
        <el-button type="success" plain :loading="indexRebuilding" @click="handleRebuildSearchIndex">
          重建检索索引
        </el-button>
        <el-button :loading="indexing" @click="handleBatchIndex">
          回填最近事件
        </el-button>
        <el-button :loading="cleaningOrphans" @click="handleCleanupOrphans">
          清理空轨迹
        </el-button>
        <el-button @click="loadStats">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </el-space>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never"><div class="stat-num">{{ stats.track_count || 0 }}</div><div class="stat-label">轨迹数</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat-num">{{ stats.total || 0 }}</div><div class="stat-label">帧图库</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat-num">{{ stats.today || 0 }}</div><div class="stat-label">今日入库</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="stat-num">{{ stats.device_count || 0 }}</div><div class="stat-label">覆盖设备</div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="query-card">
          <template #header>以图搜人</template>
          <div class="query-upload-wrap">
            <el-upload
              class="query-upload"
              drag
              multiple
              :auto-upload="false"
              :show-file-list="false"
              accept="image/*"
              :disabled="queryImages.length >= QUERY_IMAGE_MAX"
              @change="handleQueryFileChange"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div>上传查询照片（全身/半身，最多 {{ QUERY_IMAGE_MAX }} 张）</div>
              <div class="upload-sub">同一人多角度/多清晰度，分取最高匹配</div>
            </el-upload>
            <div v-if="queryImages.length" class="query-thumbs">
              <div v-for="(item, idx) in queryImages" :key="item.id" class="query-thumb">
                <img :src="item.url" :alt="`查询图${idx + 1}`" />
                <button type="button" class="query-thumb-remove" title="移除" @click="removeQueryImage(idx)">
                  ×
                </button>
              </div>
            </div>
          </div>

          <el-form label-width="88px" class="query-form">
            <el-form-item label="匹配分≥">
              <el-slider v-model="searchForm.minSimilarity" :min="0.35" :max="0.95" :step="0.01" show-input />
              <div class="field-tip">
                按 ReID 深度分筛选；搜索后拖动即可即时过滤当前结果，无需重新搜索。
                建议 0.50–0.60，误报多再上调。
              </div>
            </el-form-item>
            <el-form-item label="返回条数">
              <el-input-number v-model="searchForm.topK" :min="5" :max="100" />
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="searchForm.dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始日期时间"
                end-placeholder="结束日期时间"
                value-format="YYYY-MM-DD HH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                time-format="HH:mm:ss"
                :shortcuts="dateTimeShortcuts"
                :default-time="dateTimeDefaultTime"
                :disabled-date="disableFutureDate"
                style="width: 100%"
                @change="onDateTimeRangeChange"
              />
            </el-form-item>
            <el-form-item label="设备">
              <el-select v-model="searchForm.deviceId" clearable filterable placeholder="全部设备" style="width: 100%">
                <el-option
                  v-for="d in devices"
                  :key="d.device_id"
                  :label="`${d.device_name} (${d.device_id})`"
                  :value="d.device_id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="searching" :disabled="!queryImages.length" @click="handleSearch">
                开始搜索
              </el-button>
              <el-button @click="clearQuery">清空</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="16">
        <el-card shadow="never">
          <template #header>
            <div class="result-header">
              <span>{{ activeTab === 'search' ? '搜索结果' : '最近入库' }}</span>
              <el-radio-group v-model="activeTab" size="small">
                <el-radio-button value="search">搜索结果</el-radio-button>
                <el-radio-button value="gallery">图库浏览</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <div v-if="activeTab === 'search'" v-loading="searching">
            <el-empty
              v-if="!searchResultsRaw.length"
              description="上传照片并搜索，或先回填历史检测事件"
            />
            <template v-else>
              <div class="result-toolbar">
                <div class="result-toolbar-left">
                  <el-checkbox
                    :model-value="isAllFilteredSelected"
                    :indeterminate="isFilteredSelectIndeterminate"
                    :disabled="!filteredSearchResults.length"
                    @change="toggleSelectAllFiltered"
                  >
                    全选
                  </el-checkbox>
                  <span class="result-toolbar-hint">已选 {{ selectedInFilteredCount }}</span>
                  <div class="sort-icon-btns">
                    <el-tooltip content="按相似度排序" placement="top">
                      <span class="toolbar-icon-wrap">
                        <el-button
                          size="small"
                          :type="activeSortMode === 'similarity' ? 'primary' : 'default'"
                          :disabled="!selectedResultKeys.size"
                          @click="sortSelectedResults('similarity')"
                        >
                          <el-icon><TrendCharts /></el-icon>
                        </el-button>
                      </span>
                    </el-tooltip>
                    <el-tooltip content="按时间排序" placement="top">
                      <span class="toolbar-icon-wrap">
                        <el-button
                          size="small"
                          :type="activeSortMode === 'time' ? 'primary' : 'default'"
                          :disabled="!selectedResultKeys.size"
                          @click="sortSelectedResults('time')"
                        >
                          <el-icon><Clock /></el-icon>
                        </el-button>
                      </span>
                    </el-tooltip>
                  </div>
                </div>
                <div v-if="searchMeta" class="result-toolbar-meta">
                  <span class="meta-pill" title="当前匹配分下显示 / 本次返回候选">
                    显示 {{ filteredSearchResults.length }}/{{ searchResultsRaw.length }}
                  </span>
                  <span
                    v-if="searchMeta.query_count > 1"
                    class="meta-pill"
                    title="查询图数量（分数已按 max 融合）"
                  >
                    查询 {{ searchMeta.query_count }} 张
                  </span>
                  <span class="meta-pill" title="检索扫描量">扫描 {{ searchMeta.scanned }}</span>
                  <span class="meta-pill" title="重排候选数">重排 {{ searchMeta.reranked }}</span>
                  <span v-if="searchMeta.backend" class="meta-pill meta-pill--backend" :title="searchMeta.backend">
                    {{ searchMeta.backend }}
                  </span>
                  <span class="meta-pill meta-pill--time" title="检索耗时">{{ searchMeta.search_ms }} ms</span>
                </div>
              </div>
              <el-empty
                v-if="!filteredSearchResults.length"
                description="当前匹配分下无结果，可调低「匹配分≥」查看更多"
              />
              <el-row v-else :gutter="12">
                <el-col
                  v-for="item in filteredSearchResults"
                  :key="resultKey(item)"
                  :xs="12"
                  :sm="8"
                  :md="6"
                >
                  <div
                    class="result-card"
                    :class="{ 'is-selected': selectedResultKeys.has(resultKey(item)) }"
                    @click="toggleResultSelected(item)"
                  >
                    <div class="result-img-wrap">
                      <el-checkbox
                        class="result-check"
                        :model-value="selectedResultKeys.has(resultKey(item))"
                        @click.stop
                        @change="(val) => setResultSelected(item, val)"
                      />
                      <el-image
                        :src="cropUrl(item.crop_path)"
                        :preview-src-list="[cropUrl(item.crop_path)]"
                        :preview-z-index="IMAGE_PREVIEW_Z_INDEX"
                        fit="contain"
                        class="result-img"
                        preview-teleported
                        hide-on-click-modal
                        @click.stop
                      />
                    </div>
                    <div class="result-meta">
                      <div class="result-tags">
                        <el-tag type="success" size="small">
                          {{ formatPercentFromRatio(primarySimilarity(item), 1) }}
                        </el-tag>
                        <el-tag v-if="item.result_type === 'track'" size="small" effect="plain">
                          轨迹 {{ item.frame_count || 1 }} 帧
                        </el-tag>
                        <el-tag v-if="item.match_confidence === 'high'" type="success" size="small" effect="plain">高置信</el-tag>
                        <el-tag v-else-if="item.match_confidence === 'medium'" type="warning" size="small" effect="plain">中置信</el-tag>
                        <el-tag v-else-if="item.match_confidence === 'low'" type="info" size="small" effect="plain">低置信</el-tag>
                      </div>
                      <span class="device-name">{{ item.device_name || item.device_id }}</span>
                      <span class="time-text">{{ formatTime(item.last_seen || item.created_at) }}</span>
                      <el-button
                        link
                        type="primary"
                        size="small"
                        class="detail-btn"
                        @click.stop="openSearchResult(item)"
                      >
                        {{ item.track_id ? '轨迹详情' : '查看详情' }}
                      </el-button>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </template>
          </div>

          <div v-else v-loading="galleryLoading">
            <el-row :gutter="12">
              <el-col v-for="item in galleryItems" :key="item.gallery_id" :xs="12" :sm="8" :md="6">
                <div class="result-card">
                  <div class="result-img-wrap">
                    <el-image
                      :src="cropUrl(item.crop_path)"
                      :preview-src-list="[cropUrl(item.crop_path)]"
                      :preview-z-index="IMAGE_PREVIEW_Z_INDEX"
                      fit="contain"
                      class="result-img"
                      preview-teleported
                      hide-on-click-modal
                    />
                  </div>
                  <div class="result-meta">
                    <el-tag size="small">{{ formatPercentFromRatio(item.confidence, 0) }}</el-tag>
                    <span class="device-name">{{ item.device_name || item.device_id }}</span>
                    <span class="time-text">{{ formatTime(item.created_at) }}</span>
                    <span v-if="item.bbox_index != null" class="time-text">目标 #{{ item.bbox_index + 1 }}</span>
                    <el-button link type="primary" size="small" class="detail-btn" @click.stop="openDetail(item)">
                      查看详情
                    </el-button>
                  </div>
                </div>
              </el-col>
            </el-row>
            <div class="pager">
              <el-pagination
                v-model:current-page="galleryPage"
                v-model:page-size="galleryPageSize"
                :total="galleryTotal"
                layout="prev, pager, next, total"
                @current-change="loadGallery"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="rebuildJob.running"
      class="rebuild-warning"
      type="info"
      :closable="false"
      show-icon
      title="正在重建图库特征"
      :description="rebuildProgressText"
    />

    <el-alert
      v-else-if="indexRebuildJob.running"
      class="rebuild-warning"
      type="info"
      :closable="false"
      show-icon
      title="正在重建检索索引（FAISS 日分片）"
      :description="indexRebuildProgressText"
    />

    <el-alert
      v-else-if="stats.needs_rebuild"
      class="rebuild-warning"
      type="warning"
      :closable="false"
      show-icon
      title="图库特征需要更新"
    >
      <template #default>
        {{ rebuildWarningText }}
        <el-button link type="primary" style="margin-left: 8px" :loading="rebuilding" @click="handleRebuildEmbeddings">
          立即重建
        </el-button>
      </template>
    </el-alert>

    <el-alert
      class="poc-tip"
      type="info"
      :closable="false"
      title="POC 说明"
      :description="modelTipText"
    />

    <el-dialog
      v-model="detailVisible"
      :title="detailDialogTitle"
      width="960px"
      destroy-on-close
      append-to-body
      class="gallery-detail-dialog"
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detailData">
          <el-row :gutter="16">
            <el-col :xs="24" :sm="9">
              <div class="detail-img-wrap">
                <el-image
                  :src="cropUrl(detailData.crop_path)"
                  :preview-src-list="[cropUrl(detailData.crop_path)]"
                  :preview-z-index="IMAGE_PREVIEW_Z_INDEX"
                  fit="contain"
                  preview-teleported
                  hide-on-click-modal
                />
              </div>
              <div v-if="detailData.event?.thumbnail_path" class="detail-event-block">
                <div class="detail-block-title">关联事件截图</div>
                <div class="detail-img-wrap detail-img-wrap--event">
                  <el-image
                    :src="cropUrl(detailData.event.thumbnail_path)"
                    :preview-src-list="[cropUrl(detailData.event.thumbnail_path)]"
                    :preview-z-index="IMAGE_PREVIEW_Z_INDEX"
                    fit="contain"
                    preview-teleported
                    hide-on-click-modal
                  />
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="15">
              <el-descriptions :column="1" border size="small" class="detail-desc">
                <el-descriptions-item v-if="detailData.deep_similarity != null" label="深度相似度（ReID）">
                  <el-tag type="success">{{ formatPercentFromRatio(detailData.deep_similarity, 1) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.similarity != null" label="综合相似度">
                  {{ formatPercentFromRatio(detailData.similarity, 1) }}
                  <span v-if="isCombinedSimilarityCapped(detailData)" class="field-tip inline-tip">
                    外观 veto 时综合分会被压低，不代表 ReID 匹配度
                  </span>
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.color_similarity != null" label="颜色相似度">
                  {{ formatPercentFromRatio(detailData.color_similarity, 1) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.hue_similarity != null" label="色相相似度">
                  {{ formatPercentFromRatio(detailData.hue_similarity, 1) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.garment_similarity != null" label="上衣外观">
                  {{ formatPercentFromRatio(detailData.garment_similarity, 1) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.body_similarity != null" label="体态相似度（参考）">
                  {{ formatPercentFromRatio(detailData.body_similarity, 1) }}
                  <span v-if="Number(detailData.body_similarity) === 0" class="field-tip inline-tip">
                    启发式判定轮廓/性别冲突；深度≥约 56% 时不会因此否决或压分
                  </span>
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.attr_similarity != null" label="属性相似度">
                  {{ formatPercentFromRatio(detailData.attr_similarity, 1) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.gender_hint" label="查询图性别倾向">
                  {{ genderHintLabel(detailData.gender_hint) }}
                </el-descriptions-item>
                <el-descriptions-item v-if="detailData.match_confidence" label="匹配置信">
                  {{ matchConfidenceLabel(detailData.match_confidence) }}
                </el-descriptions-item>
                <el-descriptions-item label="图库 ID">{{ detailData.gallery_id || '-' }}</el-descriptions-item>
                <el-descriptions-item label="关联事件">
                  <span>{{ detailData.event_id || '-' }}</span>
                  <el-button
                    v-if="detailData.event_id"
                    link
                    type="primary"
                    size="small"
                    @click="goDetectionEvents"
                  >
                    打开检测事件
                  </el-button>
                </el-descriptions-item>
                <el-descriptions-item label="设备">{{ detailData.device_name || detailData.device_id }}</el-descriptions-item>
                <el-descriptions-item label="设备 ID">{{ detailData.device_id }}</el-descriptions-item>
                <el-descriptions-item label="检测置信度">
                  {{ detailData.confidence != null ? formatPercentFromRatio(detailData.confidence, 1) : '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="目标序号">
                  {{ formatBboxIndex(detailData.bbox_index) }}
                </el-descriptions-item>
                <el-descriptions-item label="边界框">{{ formatBbox(detailData.bbox) }}</el-descriptions-item>
                <el-descriptions-item label="特征维度">{{ detailData.embedding_dim || '-' }}</el-descriptions-item>
                <el-descriptions-item label="入库时间">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
                <el-descriptions-item label="事件类型">{{ detailData.event?.event_type || '-' }}</el-descriptions-item>
                <el-descriptions-item label="事件时间">{{ formatTime(detailData.event?.timestamp) }}</el-descriptions-item>
                <el-descriptions-item label="检测配置">{{ detailData.event?.config_id || '-' }}</el-descriptions-item>
                <el-descriptions-item label="抠图路径">
                  <span class="path-text">{{ detailData.crop_path || '-' }}</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Clock, Refresh, TrendCharts, UploadFilled } from '@element-plus/icons-vue'
import deviceApi from '@/api/device'
import {
  batchIndexPersonEvents,
  cleanupPersonOrphans,
  rebuildPersonGalleryEmbeddings,
  getPersonRebuildEmbeddingsStatus,
  getPersonGallery,
  getPersonGalleryDetail,
  getPersonTrackDetail,
  getPersonReidModelInfo,
  getPersonSearchStats,
  getPersonSearchIndexStatus,
  rebuildPersonSearchIndex,
  getPersonSearchIndexRebuildStatus,
  searchPersonByImage
} from '@/api/personSearch'

const router = useRouter()

const stats = ref({ total: 0, today: 0, device_count: 0 })
const modelInfo = ref(null)
const devices = ref([])
const QUERY_IMAGE_MAX = 5
const queryImages = ref([]) // { id, file, url }
let queryImageSeq = 0
const searching = ref(false)
const indexing = ref(false)
const cleaningOrphans = ref(false)
const rebuilding = ref(false)
const rebuildJob = ref({ running: false })
let rebuildPollTimer = null
const indexRebuilding = ref(false)
const indexRebuildJob = ref({ running: false })
const indexStatus = ref(null)
let indexRebuildPollTimer = null
const searchResultsRaw = ref([])
const searchMeta = ref(null)
const activeTab = ref('search')
/** 搜索结果勾选：key = track_id || gallery_id */
const selectedResultKeys = ref(new Set())
/** 当前生效的排序方式：similarity | time | '' */
const activeSortMode = ref('')

/** 按当前匹配分（ReID 深度分）即时筛选，不重新请求 */
const filteredSearchResults = computed(() => {
  const thr = Number(searchForm.minSimilarity)
  const floor = Number.isFinite(thr) ? thr : 0.55
  return (searchResultsRaw.value || []).filter((item) => primarySimilarity(item) >= floor)
})

const resultKey = (item) => String(item?.track_id || item?.gallery_id || '')

const resultTimeMs = (item) => {
  const raw = item?.last_seen || item?.created_at
  if (!raw) return 0
  const t = new Date(raw).getTime()
  return Number.isFinite(t) ? t : 0
}

const selectedInFilteredCount = computed(() =>
  filteredSearchResults.value.filter((item) => selectedResultKeys.value.has(resultKey(item))).length
)

const isAllFilteredSelected = computed(() => {
  const list = filteredSearchResults.value
  return list.length > 0 && list.every((item) => selectedResultKeys.value.has(resultKey(item)))
})

const isFilteredSelectIndeterminate = computed(() => {
  const n = selectedInFilteredCount.value
  return n > 0 && n < filteredSearchResults.value.length
})

const clearResultSelection = () => {
  selectedResultKeys.value = new Set()
  activeSortMode.value = ''
}

const setResultSelected = (item, selected) => {
  const key = resultKey(item)
  if (!key) return
  const next = new Set(selectedResultKeys.value)
  if (selected) next.add(key)
  else next.delete(key)
  selectedResultKeys.value = next
}

const toggleResultSelected = (item) => {
  const key = resultKey(item)
  if (!key) return
  setResultSelected(item, !selectedResultKeys.value.has(key))
}

const toggleSelectAllFiltered = (checked) => {
  const next = new Set(selectedResultKeys.value)
  for (const item of filteredSearchResults.value) {
    const key = resultKey(item)
    if (!key) continue
    if (checked) next.add(key)
    else next.delete(key)
  }
  selectedResultKeys.value = next
}

/** 已勾选结果排到前面；未勾选保持相对顺序。mode: similarity | time */
const sortSelectedResults = (mode) => {
  const selected = selectedResultKeys.value
  const label = mode === 'similarity' ? '相似度' : '时间'
  if (!selected.size) {
    ElMessage.warning(`请先勾选要按${label}排序的结果`)
    return
  }
  const list = searchResultsRaw.value || []
  const picked = []
  const rest = []
  for (const item of list) {
    if (selected.has(resultKey(item))) picked.push(item)
    else rest.push(item)
  }
  if (!picked.length) {
    ElMessage.warning('当前勾选项不在结果中，请重新勾选')
    return
  }
  if (mode === 'similarity') {
    picked.sort((a, b) => primarySimilarity(b) - primarySimilarity(a))
  } else {
    picked.sort((a, b) => resultTimeMs(b) - resultTimeMs(a))
  }
  searchResultsRaw.value = [...picked, ...rest]
  activeSortMode.value = mode
  ElMessage.success(`已将 ${picked.length} 条勾选结果按${label}排序`)
}

const pad2 = (n) => String(n).padStart(2, '0')

const formatYmdHms = (d) =>
  `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`

const startOfDay = (base) => {
  const d = new Date(base)
  d.setHours(0, 0, 0, 0)
  return d
}

const endOfDay = (base) => {
  const d = new Date(base)
  d.setHours(23, 59, 59, 0)
  return d
}

const addDays = (base, delta) => {
  const d = new Date(base)
  d.setDate(d.getDate() + delta)
  return d
}

/** 返回 Date[]，供快捷项使用 */
const rangeDatesFromPreset = (preset) => {
  const today0 = startOfDay(new Date())
  if (preset === 'yesterday') {
    const y = addDays(today0, -1)
    return [y, endOfDay(y)]
  }
  if (preset === '2d') return [addDays(today0, -1), endOfDay(today0)]
  if (preset === '3d') return [addDays(today0, -2), endOfDay(today0)]
  if (preset === '7d') return [addDays(today0, -6), endOfDay(today0)]
  return [today0, endOfDay(today0)]
}

const rangeStringsFromPreset = (preset) => {
  const [a, b] = rangeDatesFromPreset(preset)
  return [formatYmdHms(a), formatYmdHms(b)]
}

const dateTimeDefaultTime = [
  new Date(2000, 0, 1, 0, 0, 0),
  new Date(2000, 0, 1, 23, 59, 59)
]

const dateTimeShortcuts = [
  { text: '今天', value: () => rangeDatesFromPreset('today') },
  { text: '昨天', value: () => rangeDatesFromPreset('yesterday') },
  { text: '最近2天', value: () => rangeDatesFromPreset('2d') },
  { text: '最近3天', value: () => rangeDatesFromPreset('3d') },
  { text: '最近7天', value: () => rangeDatesFromPreset('7d') }
]

const searchForm = reactive({
  minSimilarity: 0.55,
  topK: 30,
  dateRange: rangeStringsFromPreset('today'),
  deviceId: ''
})

const disableFutureDate = (date) => date.getTime() > Date.now()

const onDateTimeRangeChange = (val) => {
  if (val?.length === 2 && activeTab.value === 'gallery') {
    loadGallery()
  }
}

const timeRangeParams = () => {
  const range = searchForm.dateRange?.length === 2
    ? searchForm.dateRange
    : rangeStringsFromPreset('today')
  return {
    date_from: range[0],
    date_to: range[1]
  }
}

/** 重建索引时按所选跨度估算天数 */
const selectedRangeDays = () => {
  const { date_from, date_to } = timeRangeParams()
  const a = new Date(String(date_from).replace(/-/g, '/'))
  const b = new Date(String(date_to).replace(/-/g, '/'))
  const span = Math.floor((b - a) / 86400000) + 1
  return Math.min(90, Math.max(1, span || 1))
}

const galleryItems = ref([])
const galleryLoading = ref(false)
const galleryPage = ref(1)
const galleryPageSize = ref(24)
const galleryTotal = ref(0)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref(null)
const IMAGE_PREVIEW_Z_INDEX = 1000000

const detailDialogTitle = computed(() =>
  detailData.value?.track_id ? '轨迹详情' : '图库详情'
)

const rebuildWarningText = computed(() => {
  const legacy = stats.value.legacy_embeddings || 0
  const stale = stats.value.stale_embeddings || 0
  if (legacy > 0 || stale > 0) {
    return `旧版特征 ${legacy} 条；待补全字段 ${stale} 条（需重建以启用轨迹聚合/FAISS）。`
  }
  return ''
})

const rebuildProgressText = computed(() => {
  const j = rebuildJob.value || {}
  if (j.phase === 'starting') {
    return '正在加载 ReID / 解析模型，请稍候…'
  }
  const pending = j.pending || 0
  const updated = j.updated || 0
  const failed = j.failed || 0
  const skipped = j.skipped || 0
  if (pending > 0) {
    return `进度：已升级 ${updated}/${pending}（跳过 ${skipped}，失败 ${failed}）`
  }
  return `扫描 ${j.total || 0} 条记录，已升级 ${updated}，跳过 ${skipped}，失败 ${failed}`
})

const indexRebuildProgressText = computed(() => {
  const j = indexRebuildJob.value || {}
  if (j.phase === 'starting') return '正在准备按日重建 FAISS 分片…'
  return `已重建 ${j.shards_rebuilt || 0} 天分片，向量 ${j.vectors || 0}（近 ${j.days || 30} 天）`
})

const modelTipText = computed(() => {
  const info = modelInfo.value
  const legacy = stats.value.legacy_embeddings || 0
  const stale = stats.value.stale_embeddings || 0
  const current = stats.value.current_embeddings || 0
  const tracks = stats.value.track_count || 0
  const idx = indexStatus.value || {}
  let base =
    '检索对象为轨迹聚合特征；按日 FAISS 分片粗检 + k-reciprocal 重排。颜色仅弱融合，需人审确认。'
  if (legacy > 0 || stale > 0) {
    base += ` 图库：完整 ${current}，旧版 ${legacy}，待补全 ${stale}；轨迹 ${tracks}。`
  } else {
    base += ` 轨迹 ${tracks}，帧 ${stats.value.total || 0}。`
  }
  if (idx.shard_count) {
    base += ` 检索索引：${idx.shard_count} 天分片，活跃向量 ${idx.active_vectors || 0}（${idx.first_day || '-'} ~ ${idx.last_day || '-'}）。`
  } else {
    base += ' 检索索引未重建时将回退内存候选（PERSON_SEARCH_LIMIT）。'
  }
  if (!info) return `${base} 首次搜索/入库会自动加载 ReID 权重。`
  const backend = info.faiss_available ? (info.faiss_ready ? 'FAISS 就绪' : 'FAISS 可用') : '内存矩阵'
  if (info.weights_ready) {
    return `${base} 模型 ${info.model} v${info.embedding_version}；${backend}；权重 ${info.weights_path}。`
  }
  return `${base} ReID 权重尚未下载，首次使用将自动下载。`
})

const cropUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const normalized = String(path).replace(/^\/+/, '').replace(/\\/g, '/')
  if (normalized.startsWith('storage/')) return `/${normalized}`
  if (normalized.startsWith('person_crops/') || normalized.startsWith('events/')) {
    return `/storage/${normalized}`
  }
  return `/${normalized}`
}

const formatTime = (value) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatBboxIndex = (index) => {
  if (index === null || index === undefined || index === '') return '-'
  const n = Number(index)
  if (Number.isNaN(n)) return '-'
  return `#${n + 1}`
}

const formatBbox = (bbox) => {
  if (!bbox) return '-'
  if (Array.isArray(bbox) && bbox.length >= 4) {
    const [x1, y1, x2, y2] = bbox
    return `[${Math.round(x1)}, ${Math.round(y1)}, ${Math.round(x2)}, ${Math.round(y2)}]`
  }
  return JSON.stringify(bbox)
}

const matchConfidenceLabel = (tier) => {
  const map = { high: '高置信', medium: '中置信', low: '低置信', weak: '弱匹配' }
  return map[tier] || tier
}

const genderHintLabel = (hint) => {
  const map = { male: '偏男性', female: '偏女性', unknown: '不确定' }
  return map[hint] || hint
}

const colorLabel = (name) => {
  const map = {
    black: '黑', white: '白', gray: '灰', red: '红', orange: '橙', yellow: '黄',
    green: '绿', blue: '蓝', purple: '紫', brown: '棕', unknown: '未知'
  }
  return map[name] || name
}

/** 卡片主分：深度相似度（ReID）；详情里另有综合分 */
const primarySimilarity = (item) => {
  if (item == null) return 0
  const deep = Number(item.deep_similarity)
  if (Number.isFinite(deep)) return deep
  const rerank = Number(item.rerank_similarity)
  if (Number.isFinite(rerank)) return rerank
  const finalScore = Number(item.similarity)
  if (Number.isFinite(finalScore)) return finalScore
  return 0
}

const formatPercentFromRatio = (ratio, digits = 1) => {
  const n = Number(ratio)
  if (!Number.isFinite(n)) return '-'
  if (n > 1 && n <= 100) return `${n.toFixed(digits)}%`
  return `${(n * 100).toFixed(digits)}%`
}

const isCombinedSimilarityCapped = (item) => {
  const deep = primarySimilarity(item)
  const combined = Number(item?.similarity)
  if (!Number.isFinite(combined) || deep <= 0) return false
  return combined + 0.02 < deep
}

const suggestSearchThreshold = (results) => {
  if (!Array.isArray(results) || results.length < 2) return null
  const top = primarySimilarity(results[0])
  const second = primarySimilarity(results[1])
  // 仅当首条近原图、且与第二名落差极大时提示上调，避免压掉跨视角同一人
  if (top >= 0.90 && top - second >= 0.25) {
    const suggested = Math.min(0.78, Math.max(0.55, second + 0.08))
    return Math.round(suggested * 100) / 100
  }
  return null
}

const openDetail = async (item, extra = {}) => {
  if (!item?.gallery_id) return
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await getPersonGalleryDetail(item.gallery_id)
    // 列表项兜底（如 bbox_index），接口字段优先
    detailData.value = { ...item, ...(res.data?.data || {}), ...extra }
  } catch {
    detailData.value = { ...item, ...extra }
    ElMessage.warning('加载完整详情失败，已展示列表数据')
  } finally {
    detailLoading.value = false
  }
}

const openSearchResult = async (item) => {
  const extra = {
    similarity: item.similarity,
    deep_similarity: item.deep_similarity,
    rerank_similarity: item.rerank_similarity,
    color_similarity: item.color_similarity,
    hue_similarity: item.hue_similarity,
    match_confidence: item.match_confidence,
  }
  if (item.track_id && item.result_type === 'track') {
    detailVisible.value = true
    detailLoading.value = true
    detailData.value = null
    try {
      const res = await getPersonTrackDetail(item.track_id)
      const data = res.data?.data || {}
      const frames = data.frames || item.frames || []
      const reprPath = data.repr_crop_path || item.crop_path
      const firstFrame =
        frames.find((f) => f.crop_path && reprPath && f.crop_path === reprPath) || frames[0]
      const merged = {
        ...extra,
        track_id: data.track_id,
        crop_path: reprPath,
        device_id: data.device_id,
        device_name: data.device_name,
        created_at: data.last_seen,
        confidence: firstFrame?.confidence ?? data.quality_score,
        frame_count: data.frame_count,
        frames,
        gallery_id: firstFrame?.gallery_id,
        event_id: firstFrame?.event_id,
        bbox_index: firstFrame?.bbox_index ?? item.bbox_index,
        bbox: firstFrame?.bbox ?? item.bbox,
      }
      // 轨迹详情补充关联事件截图与完整图库字段
      if (firstFrame?.gallery_id) {
        try {
          const gRes = await getPersonGalleryDetail(firstFrame.gallery_id)
          const g = gRes.data?.data || {}
          Object.assign(merged, {
            event: g.event,
            event_id: g.event_id || merged.event_id,
            bbox: g.bbox ?? merged.bbox,
            bbox_index: g.bbox_index ?? merged.bbox_index,
            confidence: g.confidence ?? merged.confidence,
            embedding_dim: g.embedding_dim,
            gallery_id: g.gallery_id || merged.gallery_id,
          })
        } catch {
          /* 事件截图加载失败不影响轨迹主信息 */
        }
      }
      detailData.value = merged
    } catch {
      detailData.value = { ...item, ...extra }
      ElMessage.warning('加载轨迹详情失败，已展示列表数据')
    } finally {
      detailLoading.value = false
    }
    return
  }
  await openDetail(item, extra)
}

const goDetectionEvents = () => {
  if (!detailData.value?.event_id) return
  detailVisible.value = false
  router.push({ path: '/detection/events', query: { event_id: detailData.value.event_id } })
}

const loadModelInfo = async () => {
  try {
    const res = await getPersonReidModelInfo()
    modelInfo.value = res.data?.data || null
  } catch {
    modelInfo.value = null
  }
}

const loadStats = async () => {
  try {
    const res = await getPersonSearchStats()
    stats.value = res.data?.data || {}
  } catch {
    ElMessage.error('加载统计失败')
  }
}

const loadDevices = async () => {
  try {
    const res = await deviceApi.getDevices({ skip: 0, limit: 500 })
    devices.value = res.data?.data || res.data || []
  } catch {
    devices.value = []
  }
}

const loadGallery = async () => {
  galleryLoading.value = true
  try {
    const res = await getPersonGallery({
      page: galleryPage.value,
      page_size: galleryPageSize.value,
      device_id: searchForm.deviceId || undefined,
      ...timeRangeParams()
    })
    const data = res.data?.data || {}
    galleryItems.value = data.items || []
    galleryTotal.value = data.total || 0
  } catch {
    ElMessage.error('加载图库失败')
  } finally {
    galleryLoading.value = false
  }
}

const revokeQueryUrls = (list) => {
  for (const item of list || []) {
    if (item?.url) URL.revokeObjectURL(item.url)
  }
}

const handleQueryFileChange = (uploadFile) => {
  const raw = uploadFile?.raw
  if (!raw) return
  if (queryImages.value.length >= QUERY_IMAGE_MAX) {
    ElMessage.warning(`最多上传 ${QUERY_IMAGE_MAX} 张查询图`)
    return
  }
  queryImages.value = [
    ...queryImages.value,
    {
      id: `q-${Date.now()}-${queryImageSeq++}`,
      file: raw,
      url: URL.createObjectURL(raw)
    }
  ]
}

const removeQueryImage = (idx) => {
  const list = [...queryImages.value]
  const [removed] = list.splice(idx, 1)
  if (removed?.url) URL.revokeObjectURL(removed.url)
  queryImages.value = list
}

const clearQuery = () => {
  revokeQueryUrls(queryImages.value)
  queryImages.value = []
  searchResultsRaw.value = []
  searchMeta.value = null
  clearResultSelection()
}

const handleSearch = async () => {
  if (!queryImages.value.length) {
    ElMessage.warning('请先上传查询图片')
    return
  }
  searching.value = true
  activeTab.value = 'search'
  try {
    const formData = new FormData()
    for (const item of queryImages.value) {
      formData.append('files', item.file)
    }
    // 用较低门槛拉全量候选，返回后由匹配分滑块即时筛选
    const res = await searchPersonByImage(formData, {
      top_k: searchForm.topK,
      min_similarity: 0.35,
      device_id: searchForm.deviceId || undefined,
      ...timeRangeParams()
    })
    searchResultsRaw.value = res.data?.data?.results || []
    clearResultSelection()
    searchMeta.value = {
      search_ms: res.data?.data?.search_ms ?? 0,
      scanned: res.data?.data?.scanned ?? 0,
      reranked: res.data?.data?.reranked ?? 0,
      backend: res.data?.data?.backend,
      query_count: res.data?.data?.query_count ?? queryImages.value.length,
    }
    const needsRebuild = res.data?.data?.needs_rebuild
    const legacySkipped = res.data?.data?.legacy_skipped || 0
    const suggested = suggestSearchThreshold(searchResultsRaw.value)
    if (needsRebuild) {
      ElMessage.warning(`图库中有 ${legacySkipped} 条旧版特征无法匹配，请先点击「重建图库特征」`)
    } else if (!searchResultsRaw.value.length) {
      ElMessage.info('未找到足够相似的结果，可调低相似度或扩大时间范围')
    } else if (!filteredSearchResults.value.length) {
      ElMessage.info('已有候选但低于当前匹配分，可拖低「匹配分≥」查看')
    } else if (suggested && searchForm.minSimilarity < suggested) {
      ElMessage.info(`首条结果明显领先，可上调匹配分至约 ${(suggested * 100).toFixed(0)} 减少误报`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '搜索失败')
  } finally {
    searching.value = false
  }
}

const stopRebuildPolling = () => {
  if (rebuildPollTimer) {
    clearInterval(rebuildPollTimer)
    rebuildPollTimer = null
  }
}

const pollRebuildStatus = async () => {
  try {
    const res = await getPersonRebuildEmbeddingsStatus()
    const job = res.data?.data || {}
    rebuildJob.value = job
    if (!job.running) {
      stopRebuildPolling()
      rebuilding.value = false
      if (job.error) {
        ElMessage.error(`重建失败：${job.error}`)
      } else {
        ElMessage.success(
          `重建完成：升级 ${job.updated || 0} 条，跳过 ${job.skipped || 0} 条，失败 ${job.failed || 0} 条，轨迹 ${job.tracks_updated || 0} 条`
        )
      }
      await loadStats()
      await loadModelInfo()
      await loadGallery()
    }
  } catch (error) {
    stopRebuildPolling()
    rebuilding.value = false
    ElMessage.error(error.response?.data?.detail || '获取重建进度失败')
  }
}

const handleRebuildEmbeddings = async () => {
  if (rebuilding.value || rebuildJob.value?.running) {
    ElMessage.info('重建任务进行中，请查看上方进度提示')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将按当前模型重新提取图库抠图特征，并补齐缺失轨迹（否则搜图会按单帧检索、结果容易乱）。图库较大时可能需数分钟。',
      '重建图库特征',
      { type: 'info', confirmButtonText: '开始重建', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  rebuilding.value = true
  try {
    const res = await rebuildPersonGalleryEmbeddings(10000, true)
    const data = res.data?.data || {}
    if (data.started === false) {
      rebuildJob.value = data.job || { running: true }
      ElMessage.warning(data.message || '已有任务进行中')
    } else {
      rebuildJob.value = data.job || { running: true, phase: 'starting' }
      ElMessage.success(data.message || '重建已开始')
    }
    stopRebuildPolling()
    rebuildPollTimer = setInterval(pollRebuildStatus, 2000)
    await pollRebuildStatus()
  } catch (error) {
    rebuilding.value = false
    const detail = error.response?.data?.detail
    const msg = error.message || ''
    if (!error.response) {
      ElMessage.error('无法连接 detect 服务，请确认 base_detect_server 已启动且 /api/v1/person-search 可访问')
    } else {
      ElMessage.error(detail || msg || '启动重建失败')
    }
  }
}

const stopIndexRebuildPolling = () => {
  if (indexRebuildPollTimer) {
    clearInterval(indexRebuildPollTimer)
    indexRebuildPollTimer = null
  }
}

const loadIndexStatus = async () => {
  try {
    const res = await getPersonSearchIndexStatus()
    indexStatus.value = res.data?.data || null
  } catch {
    indexStatus.value = null
  }
}

const pollIndexRebuildStatus = async () => {
  try {
    const res = await getPersonSearchIndexRebuildStatus()
    const job = res.data?.data || {}
    indexRebuildJob.value = job
    if (!job.running) {
      stopIndexRebuildPolling()
      indexRebuilding.value = false
      if (job.error) {
        ElMessage.error(`检索索引重建失败：${job.error}`)
      } else if (job.phase === 'done') {
        ElMessage.success(
          `检索索引重建完成：${job.shards_rebuilt || 0} 天分片，向量 ${job.vectors || 0}`
        )
      }
      await loadIndexStatus()
    }
  } catch (error) {
    stopIndexRebuildPolling()
    indexRebuilding.value = false
    ElMessage.error(error.response?.data?.detail || '获取索引重建进度失败')
  }
}

const handleRebuildSearchIndex = async () => {
  if (indexRebuilding.value || indexRebuildJob.value?.running) {
    ElMessage.info('检索索引重建进行中')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将按轨迹 last_seen 重建近 30 天的按日 FAISS 分片（不重新提特征）。部署后或大批量回填后建议执行一次，之后入库会增量写入。',
      '重建检索索引',
      { type: 'info', confirmButtonText: '开始重建', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  indexRebuilding.value = true
  try {
    const res = await rebuildPersonSearchIndex(Math.max(selectedRangeDays(), 7))
    const data = res.data?.data || {}
    if (data.started === false) {
      indexRebuildJob.value = data.job || { running: true }
      ElMessage.warning(data.message || '已有任务进行中')
    } else {
      indexRebuildJob.value = data.job || { running: true, phase: 'starting' }
      ElMessage.success(data.message || '检索索引重建已开始')
    }
    stopIndexRebuildPolling()
    indexRebuildPollTimer = setInterval(pollIndexRebuildStatus, 2000)
    await pollIndexRebuildStatus()
  } catch (error) {
    indexRebuilding.value = false
    ElMessage.error(error.response?.data?.detail || error.message || '启动索引重建失败')
  }
}

const handleBatchIndex = async () => {
  indexing.value = true
  try {
    const res = await batchIndexPersonEvents(80)
    const data = res.data?.data || {}
    ElMessage.success(`已处理 ${data.processed_events || 0} 个事件，入库 ${data.indexed_persons || 0} 张人体图`)
    await loadStats()
    await loadGallery()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '回填失败')
  } finally {
    indexing.value = false
  }
}

const handleCleanupOrphans = async () => {
  try {
    await ElMessageBox.confirm(
      '将删除：无检测事件关联的图库帧、已无任何帧的空轨迹、磁盘遗留抠图。不影响仍有有效帧的轨迹。',
      '清理空轨迹 / 孤儿数据',
      { type: 'warning', confirmButtonText: '开始清理', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  cleaningOrphans.value = true
  try {
    const res = await cleanupPersonOrphans()
    const data = res.data?.data || {}
    ElMessage.success(
      `清理完成：空轨迹 ${data.tracks_deleted || 0}，孤儿图库 ${data.gallery_deleted || 0}，遗留文件 ${data.files_deleted || 0}`
    )
    await loadStats()
    await loadGallery()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '清理失败')
  } finally {
    cleaningOrphans.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'gallery') {
    // 不再重复打 /stats；列表接口已优化
    loadGallery()
  }
})

onMounted(() => {
  // 首屏只等 stats + 设备；model-info / 重建状态延后，避免卡住页面
  loadStats()
  loadDevices()
  Promise.resolve().then(() => {
    loadModelInfo()
    loadIndexStatus()
    getPersonRebuildEmbeddingsStatus()
      .then((res) => {
        const job = res.data?.data || {}
        rebuildJob.value = job
        if (job.running) {
          rebuilding.value = true
          stopRebuildPolling()
          rebuildPollTimer = setInterval(pollRebuildStatus, 2000)
        }
      })
      .catch(() => {})
    getPersonSearchIndexRebuildStatus()
      .then((res) => {
        const job = res.data?.data || {}
        indexRebuildJob.value = job
        if (job.running) {
          indexRebuilding.value = true
          stopIndexRebuildPolling()
          indexRebuildPollTimer = setInterval(pollIndexRebuildStatus, 2000)
        }
      })
      .catch(() => {})
  })
})

onBeforeUnmount(() => {
  stopRebuildPolling()
  stopIndexRebuildPolling()
  revokeQueryUrls(queryImages.value)
})
</script>

<style scoped>
.person-search-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0 0 6px;
}

.page-header p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-label {
  margin-top: 4px;
  color: #909399;
  font-size: 13px;
}

.query-card :deep(.el-card__body) {
  padding-top: 8px;
}

.query-upload-wrap {
  width: 100%;
  margin-bottom: 16px;
}

.query-upload {
  width: 100%;
}

.query-upload :deep(.el-upload),
.query-upload :deep(.el-upload-dragger) {
  width: 100%;
}

.query-upload :deep(.el-upload-dragger) {
  min-height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.upload-icon {
  font-size: 36px;
  color: #409eff;
  margin-bottom: 6px;
}

.upload-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.query-thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.query-thumb {
  position: relative;
  width: 72px;
  height: 96px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.query-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.query-thumb-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}

.query-form {
  margin-top: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 16px;
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #f7f8fa;
  border-radius: 8px;
  flex-wrap: wrap;
}

.result-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.sort-icon-btns {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.toolbar-icon-wrap {
  display: inline-flex;
  vertical-align: middle;
}

.result-toolbar-hint {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.result-toolbar-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: auto;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e4e7ed;
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  white-space: nowrap;
}

.meta-pill--backend {
  color: #409eff;
  border-color: #d9ecff;
  background: #ecf5ff;
}

.meta-pill--time {
  color: #67c23a;
  border-color: #e1f3d8;
  background: #f0f9eb;
}

.result-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.result-card.is-selected {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35);
}

.result-img-wrap {
  position: relative;
  width: 100%;
  height: 220px;
  background: #f2f3f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-check {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 2;
  height: auto;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 4px;
  padding: 2px 4px;
}

.result-img-wrap :deep(.el-image) {
  width: 100%;
  height: 100%;
}

.result-img-wrap :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.result-img {
  width: 100%;
  height: 100%;
}

.result-meta {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.device-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-text {
  font-size: 12px;
  color: #909399;
}

.field-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.inline-tip {
  display: block;
  margin-top: 4px;
}

.score-text {
  font-size: 12px;
  color: #67c23a;
}

.pager {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}

.poc-tip {
  margin-top: 16px;
}

.rebuild-warning {
  margin-bottom: 16px;
}

.detail-btn {
  align-self: flex-start;
  padding-left: 0;
}

.detail-body {
  min-height: 120px;
}

.detail-img-wrap {
  width: 100%;
  height: 260px;
  background: #f2f3f5;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.detail-img-wrap :deep(.el-image) {
  width: 100%;
  height: 100%;
}

.detail-img-wrap :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.detail-img-wrap--event {
  height: 180px;
}

.detail-event-block {
  margin-top: 12px;
}

.detail-block-title {
  margin-bottom: 8px;
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.detail-desc {
  margin-top: 0;
  width: 100%;
}

.detail-desc :deep(.el-descriptions__label) {
  width: 148px;
  min-width: 148px;
  max-width: 148px;
  white-space: nowrap;
  vertical-align: top;
}

.detail-desc :deep(.el-descriptions__content) {
  word-break: break-word;
}

.path-text {
  word-break: break-all;
  font-size: 12px;
  color: #606266;
}

.gallery-detail-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}
</style>
