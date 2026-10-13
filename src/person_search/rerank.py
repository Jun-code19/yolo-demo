"""k-reciprocal re-ranking（纯 numpy，适用于粗检 Top-N）。"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def pairwise_cosine(matrix: np.ndarray) -> np.ndarray:
    """matrix: (N, D) L2-normalized → (N, N) cosine similarity."""
    if matrix.size == 0:
        return np.zeros((0, 0), dtype=np.float32)
    m = matrix.astype(np.float32, copy=False)
    norms = np.linalg.norm(m, axis=1, keepdims=True) + 1e-8
    m = m / norms
    return m @ m.T


def k_reciprocal_neighbors(sim: np.ndarray, k1: int = 20) -> List[np.ndarray]:
    n = sim.shape[0]
    k1 = max(1, min(k1, max(1, n - 1)))
    neighbors: List[np.ndarray] = []
    for i in range(n):
        order = np.argsort(-sim[i])
        # 排除自身
        order = order[order != i][:k1]
        neighbors.append(order)
    return neighbors


def k_reciprocal_encode(
    query_vec: np.ndarray,
    gallery_matrix: np.ndarray,
    *,
    k1: int = 20,
    k2: int = 6,
    lambda_value: float = 0.3,
) -> np.ndarray:
    """
    对 query + gallery 做 k-reciprocal re-rank，返回 gallery 重排相似度（越高越好）。
    query_vec: (D,), gallery_matrix: (N, D)
    """
    if gallery_matrix.size == 0:
        return np.zeros(0, dtype=np.float32)

    q = np.asarray(query_vec, dtype=np.float32).reshape(1, -1)
    g = np.asarray(gallery_matrix, dtype=np.float32)
    if g.ndim != 2 or q.shape[1] != g.shape[1]:
        # 维度不匹配时退回余弦
        qn = q / (np.linalg.norm(q) + 1e-8)
        gn = g / (np.linalg.norm(g, axis=1, keepdims=True) + 1e-8)
        return (gn @ qn.T).ravel().astype(np.float32)

    all_feats = np.vstack([q, g])
    sim = pairwise_cosine(all_feats)
    n_all = all_feats.shape[0]
    # original query-gallery cosine
    original = sim[0, 1:].copy()

    k1 = max(1, min(k1, n_all - 1))
    k2 = max(1, min(k2, k1))
    initial_rank = np.argsort(-sim, axis=1)

    V = np.zeros((n_all, n_all), dtype=np.float32)
    for i in range(n_all):
        forward_k = initial_rank[i, : k1 + 1]
        # k-reciprocal: j in forward of i, and i in forward of j
        k_reciprocal = [i]
        for j in forward_k:
            if j == i:
                continue
            backward_k = initial_rank[j, : k1 + 1]
            if i in backward_k:
                k_reciprocal.append(int(j))
        k_reciprocal = np.array(list(dict.fromkeys(k_reciprocal)), dtype=np.int32)
        weight = np.exp(sim[i, k_reciprocal])
        weight = weight / (weight.sum() + 1e-8)
        V[i, k_reciprocal] = weight

    # query expansion with top-k2 of query
    if k2 > 1:
        q_expand = initial_rank[0, :k2]
        V[0, :] = V[q_expand, :].mean(axis=0)

    # Jaccard distance between query encoding and gallery
    inv_idx: List[List[int]] = [[] for _ in range(n_all)]
    for i in range(n_all):
        for j in np.where(V[:, i] > 0)[0]:
            inv_idx[i].append(int(j))

    jaccard = np.zeros(g.shape[0], dtype=np.float32)
    q_nonzero = np.where(V[0, :] > 0)[0]
    for gi in range(g.shape[0]):
        i = gi + 1
        ind = np.unique(np.concatenate([q_nonzero, np.where(V[i, :] > 0)[0]]))
        min_v = np.minimum(V[0, ind], V[i, ind]).sum()
        max_v = np.maximum(V[0, ind], V[i, ind]).sum() + 1e-8
        jaccard[gi] = 1.0 - float(min_v / max_v)

    # 转为相似度：越高越好
    jaccard_sim = 1.0 - jaccard
    final = (1.0 - lambda_value) * jaccard_sim + lambda_value * original
    return final.astype(np.float32)


def rerank_scores(
    query_deep: List[float],
    gallery_deeps: List[List[float]],
    *,
    k1: int = 20,
    k2: int = 6,
    lambda_value: float = 0.3,
) -> np.ndarray:
    if not gallery_deeps:
        return np.zeros(0, dtype=np.float32)
    q = np.asarray(query_deep, dtype=np.float32)
    mats = []
    valid = []
    for i, d in enumerate(gallery_deeps):
        arr = np.asarray(d or [], dtype=np.float32)
        if arr.size == q.size and arr.size > 0:
            mats.append(arr)
            valid.append(i)
        else:
            mats.append(np.zeros_like(q))
            valid.append(i)
    g = np.stack(mats, axis=0)
    return k_reciprocal_encode(q, g, k1=k1, k2=k2, lambda_value=lambda_value)
