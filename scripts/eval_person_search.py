"""人员搜索离线评测：Rank-1 / Rank-5 / mAP / 耗时。

用法:
  python scripts/eval_person_search.py
  python scripts/eval_person_search.py --pairs data/person_search_eval/pairs.json

pairs.json 格式见 data/person_search_eval/pairs.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.person_search.embedder import get_person_embedder  # noqa: E402
from src.person_search.query_preprocess import prepare_query_image  # noqa: E402
from src.person_search.rerank import rerank_scores  # noqa: E402


def _load_bgr(path: Path):
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(path)
    return img


def _embed(path: Path, embedder) -> np.ndarray:
    bgr = prepare_query_image(_load_bgr(path))
    vec = embedder.embed_bgr(bgr, tta_flip=True)
    deep = np.asarray((vec or {}).get("deep") or [], dtype=np.float32)
    if deep.size == 0:
        raise RuntimeError(f"无法提取特征: {path}")
    deep = deep / (np.linalg.norm(deep) + 1e-8)
    return deep


def average_precision(ranked_relevant: List[bool]) -> float:
    hits = 0
    sum_prec = 0.0
    for i, rel in enumerate(ranked_relevant, start=1):
        if not rel:
            continue
        hits += 1
        sum_prec += hits / i
    return float(sum_prec / hits) if hits else 0.0


def main():
    parser = argparse.ArgumentParser(description="Person search offline eval")
    parser.add_argument(
        "--pairs",
        default=str(ROOT / "data" / "person_search_eval" / "pairs.json"),
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--use-rerank", action="store_true", default=True)
    args = parser.parse_args()

    pairs_path = Path(args.pairs)
    if not pairs_path.is_file():
        print(f"找不到 pairs 文件: {pairs_path}")
        sys.exit(1)

    data = json.loads(pairs_path.read_text(encoding="utf-8"))
    base = pairs_path.parent
    pair_list = [p for p in data.get("pairs") or [] if p.get("query") and p.get("positives")]
    if not pair_list:
        print("pairs.json 中没有有效评测对，请先放入图片并填写 positives。")
        sys.exit(0)

    embedder = get_person_embedder()
    rank1 = rank5 = 0
    aps: List[float] = []
    latencies: List[float] = []

    for pair in pair_list:
        q_path = base / pair["query"]
        positives = {str((base / p).resolve()) for p in pair["positives"]}
        # gallery = positives + negatives（若未列全 gallery，则只用这对里的）
        gallery_rel = list(pair.get("positives") or []) + list(pair.get("negatives") or [])
        if data.get("gallery"):
            gallery_rel = list(dict.fromkeys(list(data["gallery"]) + gallery_rel))

        t0 = time.perf_counter()
        q = _embed(q_path, embedder)
        g_vecs = []
        g_paths = []
        for rel in gallery_rel:
            gp = base / rel
            if not gp.is_file():
                continue
            g_vecs.append(_embed(gp, embedder))
            g_paths.append(str(gp.resolve()))
        if not g_vecs:
            print(f"跳过（无 gallery）: {pair['query']}")
            continue
        mat = np.stack(g_vecs, axis=0)
        if args.use_rerank and len(g_vecs) >= 2:
            scores = rerank_scores(list(q), [list(v) for v in g_vecs])
        else:
            scores = mat @ q
        order = np.argsort(-scores)
        ranked_paths = [g_paths[int(i)] for i in order]
        ranked_rel = [p in positives for p in ranked_paths]
        latencies.append((time.perf_counter() - t0) * 1000)

        if ranked_rel and ranked_rel[0]:
            rank1 += 1
        if any(ranked_rel[:5]):
            rank5 += 1
        aps.append(average_precision(ranked_rel))

    n = len(aps)
    if n == 0:
        print("没有成功评测的 query。")
        sys.exit(0)

    summary: Dict[str, Any] = {
        "queries": n,
        "rank1": round(rank1 / n, 4),
        "rank5": round(rank5 / n, 4),
        "mAP": round(float(np.mean(aps)), 4),
        "avg_ms": round(float(np.mean(latencies)), 1),
        "use_rerank": bool(args.use_rerank),
    }
    out = ROOT / "storage" / "person_search" / "last_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
