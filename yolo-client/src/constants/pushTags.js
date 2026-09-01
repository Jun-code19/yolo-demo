/** 数据推送预定义标签（与各业务模块推送 tags 对齐） */
export const PUSH_TAG_GROUPS = [
  {
    label: '设备监控',
    tags: [
      { value: 'device_online_status', label: 'device_online_status（设备在线状态）' },
    ],
  },
  {
    label: 'VLM 巡检',
    tags: [
      { value: 'vlm_inspection', label: 'vlm_inspection（VLM 巡检）' },
      { value: 'vlm_alert', label: 'vlm_alert（VLM 告警）' },
    ],
  },
  {
    label: '人群分析',
    tags: [
      { value: 'crowd_analysis', label: 'crowd_analysis（人群分析）' },
      { value: 'crowd_warning', label: 'crowd_warning（人群密度预警）' },
    ],
  },
  {
    label: '订阅事件 / 监听事件',
    tags: [
      { value: 'subscribe_event', label: 'subscribe_event（订阅事件）' },
      { value: 'external_event', label: 'external_event（监听事件）' },
    ],
  },
  {
    label: '检测与告警',
    tags: [
      { value: 'detection', label: 'detection（普通检测）' },
      { value: 'smart_scheme', label: 'smart_scheme（智能方案）' },
      { value: 'alarm', label: 'alarm（告警事件）' },
    ],
  },
  {
    label: '通用',
    tags: [
      { value: 'system', label: 'system（系统事件）' },
      { value: 'statistics', label: 'statistics（统计数据）' },
    ],
  },
]

export const COMMON_PUSH_TAGS = PUSH_TAG_GROUPS.flatMap((group) =>
  group.tags.map((tag) => tag.value)
)

/** 事件订阅默认推送标签 */
export const DEFAULT_SUBSCRIBE_PUSH_TAG = 'subscribe_event'

/** 智能检测配置默认推送标签 */
export const DEFAULT_SMART_SCHEME_PUSH_TAG = 'smart_scheme'
