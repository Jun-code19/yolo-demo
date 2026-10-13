"""轨迹级 FAISS 索引；未安装 faiss 时自动回退内存矩阵。"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

INDEX_DIR = Path(os.getenv("PERSON_SEARCH_FAISS_DIR", "storage/person_search"))
_faiss = None
_lock = threading.Lock()
_state: Dict[str, Any] = {
    "index": None,
    "ids": [],
    "dim": 0,
    "built_at": 0.0,
    "path": None,
}


def _try_import_faiss():
    global _faiss
    if _faiss is not None:
        return _faiss
    try:
        import faiss  # type: ignore

        _faiss = faiss
        return faiss
    except Exception as exc:
        logger.info("faiss 不可用，人员搜索将使用内存矩阵: %s", exc)
        _faiss = False
        return None


def faiss_available() -> bool:
    mod = _try_import_faiss()
    return mod is not False and mod is not None


def _index_path(version: int, dim: int) -> Path:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return INDEX_DIR / f"faiss_v{version}_d{dim}.index"


def _ids_path(version: int, dim: int) -> Path:
    return INDEX_DIR / f"faiss_v{version}_d{dim}.ids.npy"


def invalidate_faiss_index() -> None:
    with _lock:
        _state["index"] = None
        _state["ids"] = []
        _state["dim"] = 0
        _state["path"] = None


def build_faiss_index(
    track_ids: List[str],
    vectors: np.ndarray,
    *,
    embedding_version: int,
) -> Dict[str, Any]:
    """全量重建索引。vectors: (N, D) float32，建议已 L2 归一。"""
    if vectors is None or len(track_ids) == 0:
        invalidate_faiss_index()
        return {"ok": False, "count": 0, "backend": "empty"}

    mat = np.asarray(vectors, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] != len(track_ids):
        raise ValueError("vectors 与 track_ids 数量不一致")

    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8
    mat = mat / norms
    dim = int(mat.shape[1])
    faiss = _try_import_faiss()

    with _lock:
        if faiss:
            index = faiss.IndexFlatIP(dim)
            index.add(mat)
            path = _index_path(embedding_version, dim)
            faiss.write_index(index, str(path))
            np.save(str(_ids_path(embedding_version, dim)), np.asarray(track_ids))
            _state.update(
                {
                    "index": index,
                    "ids": list(track_ids),
                    "dim": dim,
                    "path": str(path),
                }
            )
            return {"ok": True, "count": len(track_ids), "backend": "faiss", "path": str(path)}

        # 内存回退：仅缓存矩阵
        _state.update(
            {
                "index": mat,
                "ids": list(track_ids),
                "dim": dim,
                "path": None,
            }
        )
        return {"ok": True, "count": len(track_ids), "backend": "memory"}


def search_faiss(
    query: np.ndarray,
    *,
    top_k: int = 100,
) -> Tuple[List[str], np.ndarray]:
    """返回 (track_ids, scores)。"""
    q = np.asarray(query, dtype=np.float32).reshape(1, -1)
    q = q / (np.linalg.norm(q) + 1e-8)

    with _lock:
        index = _state.get("index")
        ids = _state.get("ids") or []
        dim = int(_state.get("dim") or 0)
        if index is None or not ids or q.shape[1] != dim:
            return [], np.zeros(0, dtype=np.float32)

        k = max(1, min(top_k, len(ids)))
        faiss = _try_import_faiss()
        if faiss and not isinstance(index, np.ndarray):
            scores, idxs = index.search(q, k)
            scores = scores.ravel()
            idxs = idxs.ravel()
            out_ids = []
            out_scores = []
            for i, s in zip(idxs, scores):
                if i < 0 or i >= len(ids):
                    continue
                out_ids.append(ids[int(i)])
                out_scores.append(float(s))
            return out_ids, np.asarray(out_scores, dtype=np.float32)

        # memory matrix
        mat = index if isinstance(index, np.ndarray) else None
        if mat is None:
            return [], np.zeros(0, dtype=np.float32)
        sims = (mat @ q.T).ravel()
        if k >= len(sims):
            order = np.argsort(-sims)
        else:
            part = np.argpartition(-sims, k)[:k]
            order = part[np.argsort(-sims[part])]
        return [ids[int(i)] for i in order], sims[order].astype(np.float32)


def has_index() -> bool:
    with _lock:
        return _state.get("index") is not None and bool(_state.get("ids"))
