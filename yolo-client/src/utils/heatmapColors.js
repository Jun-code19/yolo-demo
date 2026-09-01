const HEATMAP_STOPS = [
  { t: 0, r: 49, g: 54, b: 149 },
  { t: 0.25, r: 69, g: 117, b: 180 },
  { t: 0.5, r: 255, g: 255, b: 191 },
  { t: 0.75, r: 252, g: 141, b: 89 },
  { t: 1, r: 215, g: 48, b: 39 },
]

export const HEATMAP_LEGEND_GRADIENT =
  'linear-gradient(to right, rgb(49, 54, 149) 0%, rgb(69, 117, 180) 25%, rgb(255, 255, 191) 50%, rgb(252, 141, 89) 75%, rgb(215, 48, 39) 100%)'

export function getAreaCount(area) {
  return Number(area?.stayingCount ?? area?.currentCount ?? 0) || 0
}

export function getHeatmapRatio(count, maxCount) {
  const max = Math.max(Number(maxCount) || 0, 1)
  return Math.min(Math.max(count / max, 0), 1)
}

function lerp(a, b, t) {
  return a + (b - a) * t
}

function interpolateHeatmapRgb(ratio) {
  const t = Math.min(Math.max(ratio, 0), 1)
  for (let i = 0; i < HEATMAP_STOPS.length - 1; i += 1) {
    const left = HEATMAP_STOPS[i]
    const right = HEATMAP_STOPS[i + 1]
    if (t <= right.t) {
      const local = (t - left.t) / (right.t - left.t)
      return {
        r: Math.round(lerp(left.r, right.r, local)),
        g: Math.round(lerp(left.g, right.g, local)),
        b: Math.round(lerp(left.b, right.b, local)),
      }
    }
  }
  const last = HEATMAP_STOPS[HEATMAP_STOPS.length - 1]
  return { r: last.r, g: last.g, b: last.b }
}

export function getHeatmapColor(count, maxCount, alpha = 0.55) {
  const { r, g, b } = interpolateHeatmapRgb(getHeatmapRatio(count, maxCount))
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function getHeatmapStrokeColor(count, maxCount) {
  const { r, g, b } = interpolateHeatmapRgb(getHeatmapRatio(count, maxCount))
  const darken = (v) => Math.max(0, Math.round(v * 0.72))
  return `rgb(${darken(r)}, ${darken(g)}, ${darken(b)})`
}

export function computeMaxAreaCount(areas, shapeType = 'polygon') {
  const list = (areas || []).filter((area) => (area.shapeType || 'polygon') === shapeType)
  if (!list.length) return 1
  return Math.max(...list.map(getAreaCount), 1)
}
