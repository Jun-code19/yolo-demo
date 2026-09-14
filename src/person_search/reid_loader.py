"""OSNet ReID 模型加载与权重管理。"""
import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
from torchvision import transforms

from src.person_search.osnet import osnet_x0_5, osnet_x1_0
from src.person_search.utils import REID_HEIGHT, REID_WIDTH, preprocess_reid_crop

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = os.getenv("PERSON_REID_MODEL", "osnet_x1_0").strip() or "osnet_x1_0"
DEFAULT_WEIGHTS_PATH = os.getenv("PERSON_REID_WEIGHTS", "models/reid/osnet_x1_0_msmt17.pth").strip()
REID_WEIGHT_FILENAME = (
    "osnet_x1_0_msmt17_combineall_256x128_amsgrad_ep150_stp60_lr0.0015_b64_fb10_softmax_labelsmooth_flip_jitter.pth"
)

_MODEL_BUILDERS = {
    "osnet_x1_0": osnet_x1_0,
    "osnet_x0_5": osnet_x0_5,
}


def _candidate_download_urls() -> list:
    custom = os.getenv("PERSON_REID_WEIGHTS_URL", "").strip()
    urls = []
    if custom:
        urls.append(custom)
    urls.extend(
        [
            f"https://huggingface.co/kaiyangzhou/osnet/resolve/main/{REID_WEIGHT_FILENAME}",
            f"https://hf-mirror.com/kaiyangzhou/osnet/resolve/main/{REID_WEIGHT_FILENAME}",
        ]
    )
    deduped = []
    seen = set()
    for url in urls:
        if url and url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def ensure_reid_weights(
    weights_path: str = DEFAULT_WEIGHTS_PATH,
    download_urls: Optional[list] = None,
) -> str:
    path = Path(weights_path)
    if path.is_file():
        return str(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    import requests

    errors = []
    for download_url in download_urls or _candidate_download_urls():
        try:
            logger.info("正在下载 ReID 权重: %s", download_url)
            with requests.get(download_url, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                tmp_path = path.with_suffix(path.suffix + ".download")
                with open(tmp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                tmp_path.replace(path)
            logger.info("ReID 权重已保存: %s", path)
            return str(path)
        except Exception as exc:
            logger.warning("ReID 权重下载失败 %s: %s", download_url, exc)
            errors.append(f"{download_url} -> {exc}")

    raise RuntimeError(
        "无法下载 OSNet ReID 权重。请手动下载后放到 "
        f"{path} ，或在 .env 中设置 PERSON_REID_WEIGHTS=/your/path.pth 。"
        f"下载地址: {_candidate_download_urls()[0]}。错误: {' | '.join(errors)}"
    )


def _load_state_dict(weights_path: str) -> dict:
    try:
        checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
    except Exception:
        checkpoint = torch.load(weights_path, map_location="cpu", weights_only=False)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        return checkpoint["state_dict"]
    if isinstance(checkpoint, dict):
        return checkpoint
    raise RuntimeError(f"无法解析 ReID 权重: {weights_path}")


def load_osnet_model(
    model_name: str = DEFAULT_MODEL_NAME,
    weights_path: Optional[str] = None,
) -> torch.nn.Module:
    builder = _MODEL_BUILDERS.get(model_name)
    if builder is None:
        raise RuntimeError(f"不支持的 ReID 模型: {model_name}")

    resolved_weights = ensure_reid_weights(weights_path or DEFAULT_WEIGHTS_PATH)
    model = builder(num_classes=1, loss="softmax")
    state_dict = _load_state_dict(resolved_weights)

    model_dict = model.state_dict()
    filtered = {}
    skipped = []
    for key, value in state_dict.items():
        normalized_key = key[7:] if key.startswith("module.") else key
        if normalized_key in model_dict and model_dict[normalized_key].shape == value.shape:
            filtered[normalized_key] = value
        else:
            skipped.append(normalized_key)

    model_dict.update(filtered)
    model.load_state_dict(model_dict)
    model.eval()

    logger.info(
        "OSNet ReID 已加载 model=%s weights=%s matched=%s skipped=%s",
        model_name,
        resolved_weights,
        len(filtered),
        len(skipped),
    )
    return model


class OsnetReidExtractor:
    """OSNet 专用行人 ReID 特征提取器。"""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        weights_path: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = load_osnet_model(model_name, weights_path)
        self.model.to(self.device)
        self.transform = transforms.Compose(
            [
                transforms.ToPILImage(),
                transforms.Resize((REID_HEIGHT, REID_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

    def _forward_bgr(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        if bgr is None or bgr.size == 0:
            return None
        reid = preprocess_reid_crop(bgr)
        rgb = cv2.cvtColor(reid, cv2.COLOR_BGR2RGB)
        tensor = self.transform(rgb).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feat = self.model(tensor)
        vec = feat.cpu().numpy().flatten().astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            return None
        return vec / norm

    def extract(self, bgr: np.ndarray, *, tta_flip: bool = True) -> Optional[np.ndarray]:
        v1 = self._forward_bgr(bgr)
        if v1 is None:
            return None
        if not tta_flip:
            return v1
        v2 = self._forward_bgr(cv2.flip(bgr, 1))
        if v2 is None:
            return v1
        merged = v1 + v2
        norm = float(np.linalg.norm(merged))
        if norm < 1e-8:
            return None
        return (merged / norm).astype(np.float32)
