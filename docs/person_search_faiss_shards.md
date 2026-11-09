# 人员检索：提 limit + 按日 FAISS 分片

## 背景

原先检索从 DB 按 `last_seen` 只加载最近 **5000** 条轨迹再建临时索引，入库量大时「近 7/30 天」会被截断。现改为：

1. 回退候选上限 `PERSON_SEARCH_LIMIT` 默认 **50000**
2. 粗检 Top `PERSON_SEARCH_COARSE_TOP` 默认 **300**
3. **按自然日持久 FAISS 分片**（轨迹 `agg_embedding.deep`），检索跨日合并；落盘时增量 upsert

## 磁盘布局

目录：`PERSON_SEARCH_FAISS_DIR`（默认 `storage/person_search`，Docker 已挂载 `./storage`）

```
storage/person_search/shards_v{version}_d{dim}/
  YYYY-MM-DD.meta.npz
  YYYY-MM-DD.index      # 有 faiss 时写出
  manifest.json
```

## 上线步骤

1. 部署 detect 服务（含本改动）
2. 人员搜索页点击 **「重建检索索引」**（按当前搜索天数或默认 30 天扫 `person_track`）
3. 搜图结果里 `backend` 应为 `faiss_shards`，`scanned` 接近时间窗内活跃轨迹数

之后新轨迹在 `_persist_track` 时自动写入对应日分片，一般无需每次全量重建。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PERSON_SEARCH_LIMIT` | 50000 | 无分片时内存回退候选上限 |
| `PERSON_SEARCH_COARSE_TOP` | 300 | 粗检候选数（重排前） |
| `PERSON_SEARCH_FAISS_DIR` | storage/person_search | 索引根目录 |
| `PERSON_SEARCH_SHARD_CACHE_DAYS` | 8 | 进程内打开分片 LRU |
| `PERSON_SEARCH_SHARD_COMPACT_RATIO` | 0.20 | 无效槽位占比超此值则 compact |

## API

- `GET /api/v1/person-search/index/status`
- `POST /api/v1/person-search/index/rebuild` body `{ "days": 30 }`
- `GET /api/v1/person-search/index/rebuild/status`
- `POST /api/v1/person-search/index/drop-before?day=YYYY-MM-DD`

## 与「重建图库特征」的区别

| 操作 | 作用 |
|------|------|
| 重建图库特征 | 重新提 ReID / 补轨迹聚合 |
| 重建检索索引 | 用已有轨迹特征建/刷新 FAISS 日分片，不重新跑模型 |
