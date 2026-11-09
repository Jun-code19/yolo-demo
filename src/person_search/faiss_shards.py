"""按自然日持久化的轨迹级 FAISS 分片索引。

磁盘布局（PERSON_SEARCH_FAISS_DIR，默认 storage/person_search）::

    shards_v{version}_d{dim}/
      YYYY-MM-DD.meta.npz   # ids / device_ids / last_seen_ts / id_keys / id_vals / vectors
      YYYY-MM-DD.index      # 可选：faiss IndexFlatIP（有 faiss 时写出）
      manifest.json
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

from src.person_search.faiss_index import INDEX_DIR, _try_import_faiss, faiss_available

logger = logging.getLogger(__name__)

SHARD_CACHE_DAYS = int(os.getenv("PERSON_SEARCH_SHARD_CACHE_DAYS", "8"))
COMPACT_WASTE_RATIO = float(os.getenv("PERSON_SEARCH_SHARD_COMPACT_RATIO", "0.20"))
DEFAULT_DIM = 512

_lock = threading.RLock()
_lru = OrderedDict()  # type: OrderedDict[str, ShardState]
_manifest_cache = None  # type: Optional[Dict[str, Any]]


def _day_key(value: Union[datetime, date, str]) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _iter_days(since: datetime, until: datetime) -> List[str]:
    start = since.date()
    end = until.date()
    if end < start:
        start, end = end, start
    days: List[str] = []
    cur = start
    while cur <= end:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def _shard_root(embedding_version: int, dim: int) -> Path:
    path = INDEX_DIR / f"shards_v{embedding_version}_d{dim}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(embedding_version: int, dim: int) -> Path:
    return _shard_root(embedding_version, dim) / "manifest.json"


def _paths(embedding_version: int, dim: int, day: str) -> Tuple[Path, Path]:
    root = _shard_root(embedding_version, dim)
    return root / f"{day}.index", root / f"{day}.meta.npz"


def _normalize(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v)) + 1e-8
    return (v / n).astype(np.float32)


def _build_faiss(mat: np.ndarray, dim: int):
    faiss = _try_import_faiss()
    if not faiss:
        return None
    index = faiss.IndexFlatIP(dim)
    if mat is not None and mat.shape[0] > 0:
        index.add(np.asarray(mat, dtype=np.float32))
    return index


class ShardState:
    __slots__ = (
        "day",
        "dim",
        "version",
        "index",
        "ids",
        "device_ids",
        "last_seen_ts",
        "id_to_slot",
        "vectors",
        "dirty",
    )

    def __init__(
        self,
        *,
        day: str,
        dim: int,
        version: int,
        index: Any,
        ids: List[str],
        device_ids: List[str],
        last_seen_ts: np.ndarray,
        id_to_slot: Dict[str, int],
        vectors: np.ndarray,
        dirty: bool = False,
    ):
        self.day = day
        self.dim = dim
        self.version = version
        self.index = index
        self.ids = ids
        self.device_ids = device_ids
        self.last_seen_ts = np.asarray(last_seen_ts, dtype=np.float64)
        self.id_to_slot = id_to_slot
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.dirty = dirty

    @property
    def ntotal(self) -> int:
        return int(self.vectors.shape[0]) if self.vectors is not None else 0

    @property
    def active_count(self) -> int:
        return len(self.id_to_slot)

    @property
    def waste_ratio(self) -> float:
        n = self.ntotal
        if n <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.active_count / float(n)))


def _empty_shard(day: str, dim: int, version: int) -> ShardState:
    return ShardState(
        day=day,
        dim=dim,
        version=version,
        index=_build_faiss(np.zeros((0, dim), dtype=np.float32), dim),
        ids=[],
        device_ids=[],
        last_seen_ts=np.zeros(0, dtype=np.float64),
        id_to_slot={},
        vectors=np.zeros((0, dim), dtype=np.float32),
        dirty=False,
    )


def _touch_lru(day: str, shard: ShardState) -> None:
    if day in _lru:
        _lru.move_to_end(day)
    _lru[day] = shard
    while len(_lru) > max(1, SHARD_CACHE_DAYS):
        old_day, old = _lru.popitem(last=False)
        if old.dirty:
            try:
                _save_shard(old)
            except Exception as exc:
                logger.warning("淘汰分片时保存失败 day=%s: %s", old_day, exc)


def invalidate_shard_cache() -> None:
    """清空进程内 LRU；脏分片先落盘。不删磁盘文件。"""
    global _manifest_cache
    with _lock:
        for day, shard in list(_lru.items()):
            if shard.dirty:
                try:
                    _save_shard(shard)
                except Exception as exc:
                    logger.warning("invalidate 保存分片失败 day=%s: %s", day, exc)
        _lru.clear()
        _manifest_cache = None


def _load_manifest(embedding_version: int, dim: int) -> Dict[str, Any]:
    global _manifest_cache
    path = _manifest_path(embedding_version, dim)
    if _manifest_cache and _manifest_cache.get("path") == str(path):
        return _manifest_cache.get("data") or {}
    data: Dict[str, Any] = {
        "version": embedding_version,
        "dim": dim,
        "shards": [],
        "updated_at": None,
    }
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("读取 manifest 失败: %s", exc)
    _manifest_cache = {"path": str(path), "data": data}
    return data


def _write_manifest(embedding_version: int, dim: int, shards: Sequence[str]) -> None:
    global _manifest_cache
    path = _manifest_path(embedding_version, dim)
    data = {
        "version": embedding_version,
        "dim": dim,
        "shards": sorted(set(shards)),
        "updated_at": datetime.now().isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _manifest_cache = {"path": str(path), "data": data}


def _update_manifest_add(embedding_version: int, dim: int, day: str) -> None:
    data = _load_manifest(embedding_version, dim)
    shards = list(data.get("shards") or [])
    if day not in shards:
        shards.append(day)
        _write_manifest(embedding_version, dim, shards)
    else:
        # 刷新 updated_at
        _write_manifest(embedding_version, dim, shards)


def list_shard_days(embedding_version: int, dim: int = DEFAULT_DIM) -> List[str]:
    with _lock:
        data = _load_manifest(embedding_version, dim)
        shards = list(data.get("shards") or [])
        if shards:
            return sorted(shards)
        root = _shard_root(embedding_version, dim)
        return sorted({p.stem for p in root.glob("*.meta.npz")})


def shards_ready(embedding_version: int, dim: int = DEFAULT_DIM) -> bool:
    return bool(list_shard_days(embedding_version, dim))


def get_shard_status(embedding_version: int, dim: int = DEFAULT_DIM) -> Dict[str, Any]:
    days = list_shard_days(embedding_version, dim)
    total_active = 0
    total_slots = 0
    for day in days:
        _, meta_path = _paths(embedding_version, dim, day)
        if not meta_path.is_file():
            continue
        try:
            meta = np.load(str(meta_path), allow_pickle=True)
            ids = meta["ids"].tolist()
            if "id_keys" in meta.files and "id_vals" in meta.files:
                total_active += int(len(meta["id_keys"]))
            else:
                total_active += len(ids)
            total_slots += len(ids)
        except Exception:
            continue
    return {
        "faiss_available": faiss_available(),
        "embedding_version": embedding_version,
        "dim": dim,
        "shard_count": len(days),
        "days": days,
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "vector_slots": total_slots,
        "active_vectors": total_active,
        "index_dir": str(_shard_root(embedding_version, dim)),
    }


def _save_shard(shard: ShardState) -> None:
    index_path, meta_path = _paths(shard.version, shard.dim, shard.day)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    mat = np.asarray(shard.vectors, dtype=np.float32)
    id_keys = np.asarray(list(shard.id_to_slot.keys()), dtype=object)
    id_vals = np.asarray(list(shard.id_to_slot.values()), dtype=np.int32)
    np.savez_compressed(
        str(meta_path),
        ids=np.asarray(shard.ids, dtype=object),
        device_ids=np.asarray(shard.device_ids, dtype=object),
        last_seen_ts=np.asarray(shard.last_seen_ts, dtype=np.float64),
        id_keys=id_keys,
        id_vals=id_vals,
        vectors=mat,
    )
    faiss = _try_import_faiss()
    if faiss:
        index = shard.index if shard.index is not None else _build_faiss(mat, shard.dim)
        if index is not None:
            faiss.write_index(index, str(index_path))
            shard.index = index
    shard.dirty = False
    _update_manifest_add(shard.version, shard.dim, shard.day)


def _load_shard(day: str, embedding_version: int, dim: int) -> ShardState:
    with _lock:
        if day in _lru:
            _lru.move_to_end(day)
            return _lru[day]

    index_path, meta_path = _paths(embedding_version, dim, day)
    if not meta_path.is_file():
        shard = _empty_shard(day, dim, embedding_version)
        with _lock:
            _touch_lru(day, shard)
        return shard

    meta = np.load(str(meta_path), allow_pickle=True)
    ids = [str(x) for x in meta["ids"].tolist()]
    device_ids = [str(x) for x in meta["device_ids"].tolist()]
    last_seen_ts = np.asarray(meta["last_seen_ts"], dtype=np.float64)
    vectors = meta["vectors"].astype(np.float32) if "vectors" in meta.files else np.zeros((0, dim), dtype=np.float32)
    id_to_slot: Dict[str, int] = {}
    if "id_keys" in meta.files and "id_vals" in meta.files:
        for k, v in zip(meta["id_keys"].tolist(), meta["id_vals"].tolist()):
            id_to_slot[str(k)] = int(v)
    else:
        id_to_slot = {tid: i for i, tid in enumerate(ids)}

    index = None
    faiss = _try_import_faiss()
    if faiss and index_path.is_file():
        try:
            index = faiss.read_index(str(index_path))
            if int(getattr(index, "ntotal", 0) or 0) != int(vectors.shape[0]):
                index = _build_faiss(vectors, dim)
        except Exception as exc:
            logger.warning("读取 FAISS 分片失败 day=%s: %s", day, exc)
            index = _build_faiss(vectors, dim)
    elif faiss:
        index = _build_faiss(vectors, dim)

    shard = ShardState(
        day=day,
        dim=dim,
        version=embedding_version,
        index=index,
        ids=ids,
        device_ids=device_ids,
        last_seen_ts=last_seen_ts,
        id_to_slot=id_to_slot,
        vectors=vectors,
        dirty=False,
    )
    with _lock:
        _touch_lru(day, shard)
    return shard


def compact_shard(shard: ShardState) -> None:
    if not shard.id_to_slot:
        shard.ids = []
        shard.device_ids = []
        shard.last_seen_ts = np.zeros(0, dtype=np.float64)
        shard.vectors = np.zeros((0, shard.dim), dtype=np.float32)
        shard.index = _build_faiss(shard.vectors, shard.dim)
        shard.dirty = True
        return

    order = sorted(shard.id_to_slot.items(), key=lambda kv: kv[1])
    new_ids: List[str] = []
    new_devices: List[str] = []
    new_ts: List[float] = []
    rows: List[np.ndarray] = []
    for tid, slot in order:
        if slot < 0 or slot >= shard.ntotal:
            continue
        new_ids.append(tid)
        new_devices.append(shard.device_ids[slot] if slot < len(shard.device_ids) else "")
        new_ts.append(float(shard.last_seen_ts[slot]) if slot < len(shard.last_seen_ts) else 0.0)
        rows.append(shard.vectors[slot])
    mat = np.stack(rows, axis=0).astype(np.float32) if rows else np.zeros((0, shard.dim), dtype=np.float32)
    shard.ids = new_ids
    shard.device_ids = new_devices
    shard.last_seen_ts = np.asarray(new_ts, dtype=np.float64)
    shard.vectors = mat
    shard.id_to_slot = {tid: i for i, tid in enumerate(new_ids)}
    shard.index = _build_faiss(mat, shard.dim)
    shard.dirty = True
    logger.info("分片 compact day=%s active=%s", shard.day, len(new_ids))


def _maybe_compact(shard: ShardState) -> None:
    if shard.ntotal < 64:
        return
    if shard.waste_ratio < COMPACT_WASTE_RATIO:
        return
    compact_shard(shard)


def upsert_track(
    track_id: str,
    vector: Sequence[float],
    *,
    device_id: str,
    last_seen: datetime,
    embedding_version: int,
    dim: Optional[int] = None,
) -> bool:
    deep = _normalize(np.asarray(vector, dtype=np.float32))
    if deep.size == 0:
        return False
    use_dim = int(dim or deep.shape[0])
    if deep.shape[0] != use_dim:
        return False
    day = _day_key(last_seen)
    ts = last_seen.timestamp() if isinstance(last_seen, datetime) else time.time()

    with _lock:
        shard = _load_shard(day, embedding_version, use_dim)
        shard.vectors = np.vstack([shard.vectors, deep.reshape(1, -1)])
        shard.ids.append(str(track_id))
        shard.device_ids.append(str(device_id or ""))
        shard.last_seen_ts = np.append(shard.last_seen_ts, float(ts))
        shard.id_to_slot[str(track_id)] = len(shard.ids) - 1
        if shard.index is not None and hasattr(shard.index, "add"):
            shard.index.add(deep.reshape(1, -1))
        else:
            shard.index = _build_faiss(shard.vectors, use_dim)
        shard.dirty = True
        _maybe_compact(shard)
        try:
            _save_shard(shard)
        except Exception as exc:
            logger.warning("保存分片失败 day=%s: %s", day, exc)
            return False
        return True


def rebuild_shard_from_rows(
    day: str,
    rows: Iterable[Dict[str, Any]],
    *,
    embedding_version: int,
    dim: int = DEFAULT_DIM,
) -> Dict[str, Any]:
    ids: List[str] = []
    devices: List[str] = []
    ts_list: List[float] = []
    vecs: List[np.ndarray] = []
    for row in rows:
        tid = str(row.get("track_id") or "")
        deep = row.get("deep") or []
        if not tid or not deep:
            continue
        vec = _normalize(np.asarray(deep, dtype=np.float32))
        if vec.size != dim:
            continue
        ids.append(tid)
        devices.append(str(row.get("device_id") or ""))
        ls = row.get("last_seen")
        if isinstance(ls, datetime):
            ts_list.append(ls.timestamp())
        elif isinstance(ls, (int, float)):
            ts_list.append(float(ls))
        else:
            ts_list.append(time.time())
        vecs.append(vec)

    mat = np.stack(vecs, axis=0).astype(np.float32) if vecs else np.zeros((0, dim), dtype=np.float32)
    shard = ShardState(
        day=_day_key(day),
        dim=dim,
        version=embedding_version,
        index=_build_faiss(mat, dim),
        ids=ids,
        device_ids=devices,
        last_seen_ts=np.asarray(ts_list, dtype=np.float64),
        id_to_slot={tid: i for i, tid in enumerate(ids)},
        vectors=mat,
        dirty=True,
    )
    with _lock:
        _save_shard(shard)
        _touch_lru(shard.day, shard)
    return {"ok": True, "day": shard.day, "count": len(ids)}


def drop_shards_before(
    day: str,
    *,
    embedding_version: int,
    dim: int = DEFAULT_DIM,
) -> int:
    cutoff = _day_key(day)
    removed = 0
    with _lock:
        days = list_shard_days(embedding_version, dim)
        keep: List[str] = []
        for d in days:
            if d < cutoff:
                index_path, meta_path = _paths(embedding_version, dim, d)
                for p in (index_path, meta_path):
                    if p.is_file():
                        try:
                            p.unlink()
                        except OSError:
                            pass
                _lru.pop(d, None)
                removed += 1
            else:
                keep.append(d)
        _write_manifest(embedding_version, dim, keep)
    return removed


def search_shards(
    query: Sequence[float],
    *,
    since: datetime,
    until: Optional[datetime] = None,
    device_id: Optional[str] = None,
    top_k: int = 150,
    embedding_version: int,
    dim: Optional[int] = None,
) -> Tuple[List[str], np.ndarray, Dict[str, Any]]:
    q = _normalize(np.asarray(query, dtype=np.float32))
    use_dim = int(dim or q.shape[0] or DEFAULT_DIM)
    if q.size != use_dim:
        return [], np.zeros(0, dtype=np.float32), {"backend": "empty", "scanned": 0}

    until = until or datetime.now()
    want_days = _iter_days(since, until)
    available = set(list_shard_days(embedding_version, use_dim))
    days = [d for d in want_days if d in available]
    ts0 = float(since.timestamp())
    ts1 = float(until.timestamp())
    if not days:
        return [], np.zeros(0, dtype=np.float32), {
            "backend": "faiss_shards_empty",
            "scanned": 0,
            "days": 0,
            "day_list": [],
            "since": since.isoformat(),
            "until": until.isoformat(),
        }

    per_k = max(top_k, min(500, top_k * 2))
    if device_id:
        per_k = max(per_k, min(800, top_k * 4))

    merged: Dict[str, float] = {}
    scanned = 0
    used_days = 0

    for day in days:
        shard = _load_shard(day, embedding_version, use_dim)
        if shard.active_count <= 0 or shard.ntotal <= 0:
            continue
        used_days += 1
        # 按 meta 时间戳统计窗内活跃量，避免把全日槽位数当成扫描量
        in_window = 0
        for tid, slot in shard.id_to_slot.items():
            if slot < 0 or slot >= len(shard.last_seen_ts):
                continue
            ts = float(shard.last_seen_ts[slot])
            if ts0 <= ts <= ts1:
                in_window += 1
        scanned += in_window
        k = max(1, min(per_k, shard.ntotal))
        q2 = q.reshape(1, -1)

        if shard.index is not None and hasattr(shard.index, "search"):
            scores, idxs = shard.index.search(q2, k)
            pairs = [(int(i), float(s)) for i, s in zip(idxs.ravel(), scores.ravel()) if i >= 0]
        else:
            sims = (shard.vectors @ q).ravel()
            if k >= len(sims):
                order = np.argsort(-sims)
            else:
                part = np.argpartition(-sims, k)[:k]
                order = part[np.argsort(-sims[part])]
            pairs = [(int(i), float(sims[i])) for i in order]

        for slot, score in pairs:
            if slot >= len(shard.ids):
                continue
            tid = shard.ids[slot]
            if shard.id_to_slot.get(tid) != slot:
                continue
            if slot < len(shard.last_seen_ts):
                ts = float(shard.last_seen_ts[slot])
                if ts < ts0 or ts > ts1:
                    continue
            if device_id and (slot >= len(shard.device_ids) or shard.device_ids[slot] != device_id):
                continue
            prev = merged.get(tid)
            if prev is None or score > prev:
                merged[tid] = score

    if not merged:
        return [], np.zeros(0, dtype=np.float32), {
            "backend": "faiss_shards",
            "scanned": scanned,
            "days": used_days,
            "day_list": days,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "faiss_available": faiss_available(),
        }

    ordered = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[: max(1, top_k)]
    ids = [t for t, _ in ordered]
    scores = np.asarray([s for _, s in ordered], dtype=np.float32)
    return ids, scores, {
        "backend": "faiss_shards",
        "scanned": scanned,
        "days": used_days,
        "day_list": days,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "faiss_available": faiss_available(),
    }
