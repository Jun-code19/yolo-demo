"""人体特征提取：OSNet ReID + 颜色分布混合特征。"""
import logging
import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from src.person_search.par_attrs import compare_person_attributes, extract_person_attributes
from src.person_search.reid_loader import DEFAULT_MODEL_NAME, OsnetReidExtractor
from src.person_search.utils import (
    compare_body_signature,
    compare_clothing_signature,
    compare_color_similarity,
    compare_garment_appearance,
    compare_garment_signature,
    compare_hue_signature,
    compare_hue_similarity,
    extract_body_signature,
    extract_clothing_signature,
    extract_color_signature,
    extract_garment_signature,
    extract_hue_signature,
    strip_segmentation_border,
)

logger = logging.getLogger(__name__)

EMBEDDING_VERSION = 4
DEEP_HIGH_CONFIDENCE = 0.80
COLOR_STRONG_MATCH = 0.62
COLOR_WEAK_MATCH = 0.48
# 深度 ReID 超过该值时，不因换装/色相差异做 hard veto（仍保留展示用的颜色/体态分）
DEEP_APPEARANCE_TRUST = float(os.getenv("PERSON_SEARCH_DEEP_TRUST", "0.56"))
# 仅当深度低于该值时，体态=0（高置信性别/轮廓冲突）才参与否决
BODY_VETO_DEEP_MAX = float(os.getenv("PERSON_SEARCH_BODY_VETO_DEEP", "0.52"))
HUE_HARD_VETO_MAX = 0.28

_embedder = None


class PersonEmbedder:
    def __init__(self):
        self.reid = OsnetReidExtractor(model_name=DEFAULT_MODEL_NAME)
        self.model_name = DEFAULT_MODEL_NAME
        logger.info(
            "PersonEmbedder 已加载 (model=%s, device=%s, hybrid=v%s)",
            self.model_name,
            self.reid.device,
            EMBEDDING_VERSION,
        )

    def _deep_embed(self, bgr: np.ndarray) -> Optional[List[float]]:
        vec = self.reid.extract(bgr, tta_flip=True)
        if vec is None:
            return None
        return vec.astype(np.float32).tolist()

    def embed_bgr(self, bgr: np.ndarray) -> Optional[Dict[str, Any]]:
        if bgr is None or bgr.size == 0:
            return None
        h, w = bgr.shape[:2]
        if h < 8 or w < 8:
            return None

        deep = self._deep_embed(bgr)
        clean = strip_segmentation_border(bgr)
        color = extract_color_signature(clean)
        color_hue = extract_hue_signature(clean)
        garment = extract_garment_signature(clean)
        clothing = extract_clothing_signature(clean)
        body = extract_body_signature(clean)
        attrs = extract_person_attributes(clean)
        if not deep and not color:
            return None
        return {
            "v": EMBEDDING_VERSION,
            "model": self.model_name,
            "deep": deep or [],
            "color": color or [],
            "color_hue": color_hue or [],
            "garment": garment or [],
            "clothing": clothing or [],
            "body": body or [],
            "attrs": attrs or {},
        }


def get_person_embedder() -> PersonEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = PersonEmbedder()
    return _embedder


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b))


def _as_embedding_dict(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {"v": 1, "model": "legacy", "deep": raw, "color": [], "color_hue": []}
    return {"v": 1, "model": "legacy", "deep": [], "color": [], "color_hue": []}


def _read_crop_bgr(crop_path: Optional[str]) -> Optional[np.ndarray]:
    if not crop_path or not os.path.exists(crop_path):
        return None
    try:
        return cv2.imread(crop_path)
    except Exception:
        return None


def resolve_color_signature(raw: Any, crop_path: Optional[str] = None) -> List[float]:
    data = _as_embedding_dict(raw)
    color = data.get("color") or []
    if color:
        return color
    bgr = _read_crop_bgr(crop_path)
    return extract_color_signature(bgr) or []


def resolve_hue_signature(raw: Any, crop_path: Optional[str] = None) -> List[float]:
    data = _as_embedding_dict(raw)
    color_hue = data.get("color_hue") or []
    if color_hue:
        return color_hue
    bgr = _read_crop_bgr(crop_path)
    return extract_hue_signature(bgr) or []


def embedding_version(raw: Any) -> int:
    data = _as_embedding_dict(raw)
    try:
        return int(data.get("v") or 1)
    except (TypeError, ValueError):
        return 1


def embedding_needs_rebuild(raw: Any) -> bool:
    """判断图库特征是否需要重建（版本过旧或缺少新字段）。"""
    data = _as_embedding_dict(raw)
    if embedding_version(raw) < EMBEDDING_VERSION:
        return True
    garment = data.get("garment") or []
    if len(garment) < 39:
        return True
    clothing = data.get("clothing") or []
    if len(clothing) < 9:
        return True
    body = data.get("body") or []
    if len(body) < 7:
        return True
    return False


def deep_feature_dim(raw: Any) -> int:
    data = _as_embedding_dict(raw)
    return len(data.get("deep") or [])


def embeddings_compatible(query_raw: Any, gallery_raw: Any) -> bool:
    q_dim = deep_feature_dim(query_raw)
    g_dim = deep_feature_dim(gallery_raw)
    if q_dim <= 0 or g_dim <= 0:
        return False
    return q_dim == g_dim


def _core_appearance_scores(color_sim: float, hue_sim: float, garment_sim: float) -> List[float]:
    """仅用工装/色相/上衣 LAB，不用易虚高的全图颜色直方图。"""
    scores: List[float] = []
    if hue_sim > 0:
        scores.append(hue_sim)
    if garment_sim >= 0:
        scores.append(garment_sim)
    return scores


def is_hard_veto(
    hue_sim: float,
    garment_sim: float = -1.0,
    body_sim: float = -1.0,
    attrs_veto: bool = False,
    deep_sim: float = 0.0,
) -> bool:
    """外观 hard veto：仅在 ReID 深度不够可靠时启用，避免换装/角度误伤同一人。"""
    del attrs_veto, garment_sim
    if deep_sim >= DEEP_APPEARANCE_TRUST:
        return False
    if body_sim == 0.0 and deep_sim < BODY_VETO_DEEP_MAX:
        return True
    if hue_sim > 0 and hue_sim <= HUE_HARD_VETO_MAX:
        return True
    return False


def passes_match_gate(
    deep_sim: float,
    color_sim: float,
    hue_sim: float,
    garment_sim: float = -1.0,
    body_sim: float = -1.0,
    attrs_veto: bool = False,
    attr_sim: float = -1.0,
) -> bool:
    """准入：深度达标且未被极端否决（不依赖不可靠的属性分）。"""
    del color_sim, attrs_veto, attr_sim
    if is_hard_veto(hue_sim, garment_sim, body_sim, deep_sim=deep_sim):
        return False
    return deep_sim >= 0.45


def _blend_similarity(
    deep_sim: float,
    color_sim: float,
    hue_sim: float,
    garment_sim: float = -1.0,
    body_sim: float = -1.0,
    attr_sim: float = -1.0,
    attrs_veto: bool = False,
) -> float:
    """排序分以 OSNet 深度为主；深度可靠时综合分=深度分（支持换装）。"""
    del color_sim, attr_sim, attrs_veto
    if is_hard_veto(hue_sim, garment_sim, body_sim, deep_sim=deep_sim):
        return min(deep_sim, max(0.05, hue_sim + 0.05))
    return float(deep_sim)


def batch_deep_similarity(query_raw: Any, gallery_raws: List[Any]) -> np.ndarray:
    """批量计算深度特征余弦相似度。"""
    query = _as_embedding_dict(query_raw)
    q_deep = np.asarray(query.get("deep") or [], dtype=np.float32)
    if q_deep.size == 0:
        return np.zeros(len(gallery_raws), dtype=np.float32)

    q_dim = q_deep.size
    scores = np.full(len(gallery_raws), -1.0, dtype=np.float32)
    valid_idx: List[int] = []
    valid_vecs: List[np.ndarray] = []
    for i, raw in enumerate(gallery_raws):
        gallery = _as_embedding_dict(raw)
        g_deep = np.asarray(gallery.get("deep") or [], dtype=np.float32)
        if g_deep.size != q_dim:
            continue
        valid_idx.append(i)
        valid_vecs.append(g_deep)
    if not valid_vecs:
        return scores

    matrix = np.stack(valid_vecs, axis=0)
    sims = matrix @ q_deep
    for pos, idx in enumerate(valid_idx):
        scores[idx] = float(sims[pos])
    return scores


def _resolve_clothing_signature(raw: Any, crop_path: Optional[str] = None) -> List[float]:
    data = _as_embedding_dict(raw)
    clothing = data.get("clothing") or []
    if clothing:
        return clothing
    bgr = _read_crop_bgr(crop_path)
    return extract_clothing_signature(bgr) or []


def _resolve_garment_signature(raw: Any, crop_path: Optional[str] = None) -> List[float]:
    data = _as_embedding_dict(raw)
    garment = data.get("garment") or []
    if garment:
        return garment
    bgr = _read_crop_bgr(crop_path)
    return extract_garment_signature(bgr) or []


def _resolve_body_signature(raw: Any, crop_path: Optional[str] = None) -> List[float]:
    data = _as_embedding_dict(raw)
    body = data.get("body") or []
    if body:
        return body
    bgr = _read_crop_bgr(crop_path)
    return extract_body_signature(bgr) or []


def _resolve_attrs(
    raw: Any,
    crop_path: Optional[str] = None,
    bgr: Optional[np.ndarray] = None,
    allow_image_io: bool = False,
) -> Dict[str, Any]:
    data = _as_embedding_dict(raw)
    attrs = data.get("attrs") or {}
    if attrs.get("upper_color") and attrs.get("upper_color") != "unknown":
        return attrs
    if allow_image_io:
        img = bgr if bgr is not None else _read_crop_bgr(crop_path)
        if img is not None:
            return extract_person_attributes(img)
    return attrs if isinstance(attrs, dict) else {}


def _resolve_hue_score(
    query_raw: Any,
    gallery_raw: Any,
    *,
    query_crop_path: Optional[str] = None,
    gallery_crop_path: Optional[str] = None,
    allow_image_io: bool = False,
) -> float:
    q_clothing = _resolve_clothing_signature(query_raw, query_crop_path if allow_image_io else None)
    g_clothing = _resolve_clothing_signature(gallery_raw, gallery_crop_path if allow_image_io else None)
    if q_clothing and g_clothing:
        clothing_sim = compare_clothing_signature(q_clothing, g_clothing)
        if clothing_sim >= 0:
            return clothing_sim

    q_hue = resolve_hue_signature(query_raw, query_crop_path if allow_image_io else None)
    g_hue = resolve_hue_signature(gallery_raw, gallery_crop_path if allow_image_io else None)
    if q_hue and g_hue:
        return compare_hue_signature(q_hue, g_hue)
    return 0.0


def embedding_similarity(
    query_raw: Any,
    gallery_raw: Any,
    *,
    gallery_crop_path: Optional[str] = None,
    query_crop_path: Optional[str] = None,
    query_bgr: Optional[np.ndarray] = None,
    gallery_bgr: Optional[np.ndarray] = None,
    precomputed_deep_sim: Optional[float] = None,
    allow_image_io: bool = False,
    deep_weight: float = 1.0,
    color_weight: float = 0.0,
) -> Dict[str, float]:
    del deep_weight, color_weight
    query = _as_embedding_dict(query_raw)
    gallery = _as_embedding_dict(gallery_raw)

    if not embeddings_compatible(query_raw, gallery_raw):
        return {
            "similarity": 0.0,
            "deep_similarity": 0.0,
            "color_similarity": 0.0,
            "hue_similarity": 0.0,
            "compatible": False,
        }

    q_deep = query.get("deep") or []
    g_deep = gallery.get("deep") or []
    deep_sim = float(precomputed_deep_sim) if precomputed_deep_sim is not None else cosine_similarity(q_deep, g_deep)

    q_color = query.get("color") or []
    g_color = resolve_color_signature(gallery_raw, gallery_crop_path if allow_image_io else None)
    color_sim = compare_color_similarity(q_color, g_color)

    hue_sim = _resolve_hue_score(
        query_raw,
        gallery_raw,
        query_crop_path=query_crop_path,
        gallery_crop_path=gallery_crop_path,
        allow_image_io=allow_image_io,
    )

    q_garment = _resolve_garment_signature(query_raw, query_crop_path if allow_image_io else None)
    g_garment = _resolve_garment_signature(gallery_raw, gallery_crop_path if allow_image_io else None)
    garment_sim = -1.0
    if q_garment and g_garment:
        garment_sim = compare_garment_signature(q_garment, g_garment)

    q_body = _resolve_body_signature(query_raw, query_crop_path if allow_image_io else None)
    g_body = _resolve_body_signature(gallery_raw, gallery_crop_path if allow_image_io else None)
    body_sim = -1.0
    if q_body and g_body:
        body_sim = compare_body_signature(q_body, g_body)

    q_attrs = _resolve_attrs(query_raw, query_crop_path if allow_image_io else None, query_bgr, allow_image_io)
    g_attrs = _resolve_attrs(gallery_raw, gallery_crop_path if allow_image_io else None, gallery_bgr, allow_image_io)
    attr_cmp = compare_person_attributes(q_attrs, g_attrs)
    attr_sim = float(attr_cmp.get("similarity", -1))
    attrs_veto = bool(attr_cmp.get("veto"))

    if allow_image_io:
        q_img = query_bgr if query_bgr is not None else _read_crop_bgr(query_crop_path)
        g_img = gallery_bgr if gallery_bgr is not None else _read_crop_bgr(gallery_crop_path)
        if q_img is not None and g_img is not None:
            live_hue = compare_hue_similarity(q_img, g_img)
            if live_hue > 0 and deep_sim < DEEP_APPEARANCE_TRUST:
                hue_sim = min(hue_sim, live_hue) if hue_sim > 0 else live_hue
            if garment_sim < 0:
                garment_sim = compare_garment_appearance(q_img, g_img)
            live_body = compare_body_signature(
                extract_body_signature(q_img) or [],
                extract_body_signature(g_img) or [],
            )
            if live_body >= 0:
                body_sim = live_body if body_sim < 0 else min(body_sim, live_body)
            if not q_attrs.get("upper_color") or q_attrs.get("upper_color") == "unknown":
                q_attrs = extract_person_attributes(q_img)
            if not g_attrs.get("upper_color") or g_attrs.get("upper_color") == "unknown":
                g_attrs = extract_person_attributes(g_img)
            attr_cmp = compare_person_attributes(q_attrs, g_attrs)
            attr_sim = float(attr_cmp.get("similarity", -1))
            attrs_veto = bool(attr_cmp.get("veto"))

    combined = _blend_similarity(
        deep_sim, color_sim, hue_sim, garment_sim, body_sim, attr_sim, attrs_veto=attrs_veto
    )

    gender_hint = None
    if q_attrs.get("gender") and q_attrs.get("gender") != "unknown":
        gender_hint = q_attrs.get("gender")
    elif q_body and len(q_body) >= 7:
        code = int(round(q_body[5]))
        gender_hint = "male" if code > 0 else "female" if code < 0 else "unknown"

    return {
        "similarity": round(float(combined), 4),
        "deep_similarity": round(float(deep_sim), 4),
        "color_similarity": round(float(color_sim), 4),
        "hue_similarity": round(float(hue_sim), 4),
        "garment_similarity": round(float(garment_sim), 4) if garment_sim >= 0 else None,
        "body_similarity": round(float(body_sim), 4) if body_sim >= 0 else None,
        "attr_similarity": round(float(attr_sim), 4) if attr_sim >= 0 else None,
        "attrs_veto": attrs_veto,
        "gender_hint": gender_hint,
        "compatible": True,
        "confidence": _confidence_tier(
            deep_sim, color_sim, hue_sim, combined, garment_sim, body_sim, attr_sim, attrs_veto
        ),
    }


def _confidence_tier(
    deep_sim: float,
    color_sim: float,
    hue_sim: float,
    combined: float,
    garment_sim: float = -1.0,
    body_sim: float = -1.0,
    attr_sim: float = -1.0,
    attrs_veto: bool = False,
) -> str:
    del color_sim, combined, attrs_veto
    if is_hard_veto(hue_sim, garment_sim, body_sim, deep_sim=deep_sim):
        return "weak"
    if deep_sim >= 0.78 and (attr_sim >= 0.55 or body_sim >= 0.50):
        return "high"
    if deep_sim >= 0.68:
        return "medium"
    if deep_sim >= 0.55:
        return "low"
    return "weak"
