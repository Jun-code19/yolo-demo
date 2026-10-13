# 人员搜索本域微调

## 目标

用现场相机抠图微调 OSNet，提升跨光照 / 跨机位召回。在线服务不训练，只加载新权重。

## 数据准备

推荐目录：

```text
data/person_search_finetune/train/
  person_a/
    001.jpg
    002.jpg
  person_b/
    ...
```

或 `pairs.json`：

```json
[
  {"id": "person_a", "images": ["a1.jpg", "a2.jpg"]},
  {"id": "person_b", "images": ["b1.jpg"]}
]
```

建议至少几十个 ID，每 ID 多视角更好。同 `track_id` 多帧可直接导出为正样本包。

## 训练

```bash
python scripts/finetune_osnet_reid.py --data data/person_search_finetune/train --epochs 30
```

输出默认：`models/reid/osnet_x1_0_domain.pth`

## 切换权重

在 `.env` 或环境变量中设置：

```bash
PERSON_REID_WEIGHTS=models/reid/osnet_x1_0_domain.pth
```

然后：

1. 将 `src/person_search/embedder.py` 中 `EMBEDDING_VERSION` +1（或确认已升级）
2. 重启 `base_detect_server.py`
3. 人员搜索页点击「重建图库特征」（会同步刷新轨迹聚合与 FAISS）

## 评测集应该什么样、要多少

评测要贴近真实搜法：用一张查询图，在一批图库里找「是不是同一个人」。**先固定一份评测集**，再对比改阈值 / 重建 / 微调前后的指标；没有固定及格线，重点是前后可比。

### 目录结构

```text
data/person_search_eval/
  queries/          # 查询图（模拟用户上传）
  gallery/          # 图库候选（模拟已入库抠图）
  pairs.json        # 标注：谁是正样本、谁是负样本
```

### pairs.json 示例

```json
{
  "description": "人员搜索评测对",
  "gallery": [],
  "pairs": [
    {
      "query": "queries/p01_front.jpg",
      "positives": ["gallery/p01_side.jpg", "gallery/p01_far.jpg"],
      "negatives": ["gallery/p02_front.jpg", "gallery/p03_side.jpg"],
      "note": "same_cam"
    }
  ]
}
```

- `positives`：与 query 同一人的其它角度/远近图  
- `negatives`：他人；尽量选「容易混」的（同色衣服、同场景路人）  
- `note` 建议标注：`same_cam`（同摄）或 `cross_cam`（跨摄）

### 图片要求

- 尽量用**人体抠图**（全身/大半身），不要整帧大场景  
- 同一人至少覆盖：**正面 / 侧身 / 远近 / 略不同光照**  
- 负样本不要全用差很远的人，要有 hard negative  

### 规模建议（软落地）

| 阶段 | Query 数 | 身份数 | Gallery 规模 | 用途 |
|------|----------|--------|-------------|------|
| 最小可用 | 20～30 | 10～15 | 80～150 张 | 能跑出指标，看改动有没有倒退 |
| 建议基线 | 50～80 | 25～40 | 300～600 张 | 同摄为主，少量跨摄；日常回归 |
| 跨摄认真做 | 80～150 | 40～80 | 800～2000 张 | 才比较敢说跨机位效果 |

经验配比：

- **同摄对约 70%，跨摄对约 30%**（先同摄做稳）  
- 每个 query：**2～5 张 positives**  
- 每个 query 至少 **10～30 张 hard negatives**（或把整个 gallery 列表放进顶层 `gallery` 字段共用）

图库还不大时：**先做 20 query × 10～15 人**就够验证；场景稳定后再扩到 50+。

### 怎么采最快

1. 从人员图库/轨迹里挑 **20～40 个 track**，每轨导出 3～8 张高质量关键帧  
2. 每轨留 1 张当 query，其余进 gallery 当 positives  
3. 其它轨的图当 negatives  
4. 有两台摄像头时，再补一批「A 机 query → B 机 gallery」跨摄对  

### 跑评测

```bash
# 准备好图片与 pairs.json 后
python scripts/eval_person_search.py
```

结果写入 `storage/person_search/last_eval.json`。优先看：

- **Rank-5**：同摄建议先盯这个（进前 5 就算可用）  
- **mAP**：整体排序质量  
- **Rank-1**：更严，跨摄往往明显更低  

微调前后用**同一份评测集**对比上述三项即可。

## 在线能力说明

- 检索对象：轨迹聚合特征（`person_track`）
- 后处理：k-reciprocal re-rank
- 索引：FAISS（未安装则内存矩阵）
- 颜色/属性：仅弱融合，不做硬否决
