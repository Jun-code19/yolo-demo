"""人员搜索辅助模型（Human Parsing / PAR）下载与路径。"""
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

MODELS_ROOT = Path(os.getenv("PERSON_SEARCH_MODELS_DIR", "models/person_search"))
PARSING_ONNX_PATH = Path(os.getenv("PERSON_PARSING_ONNX", str(MODELS_ROOT / "parsing_lip.onnx")))
PAR_ONNX_PATH = Path(os.getenv("PERSON_PAR_ONNX", str(MODELS_ROOT / "pa100k_par.onnx")))


def _download_file(urls: List[str], dest: Path, timeout: int = 300) -> Optional[str]:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1024:
        return str(dest)

    errors = []
    for url in urls:
        try:
            logger.info("正在下载模型: %s -> %s", url, dest)
            with requests.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".download")
                with open(tmp, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                tmp.replace(dest)
            logger.info("模型已保存: %s (%.1f MB)", dest, dest.stat().st_size / (1024 * 1024))
            return str(dest)
        except Exception as exc:
            logger.warning("模型下载失败 %s: %s", url, exc)
            errors.append(f"{url} -> {exc}")
    logger.warning("模型下载全部失败: %s", " | ".join(errors))
    return None


def ensure_parsing_onnx() -> Optional[str]:
    """可选 LIP 人体解析 ONNX（未下载时使用快速区域分割）。"""
    custom = os.getenv("PERSON_PARSING_ONNX", "").strip()
    if custom and Path(custom).is_file():
        return custom
    if PARSING_ONNX_PATH.is_file():
        return str(PARSING_ONNX_PATH)

    mirror = os.getenv("HF_MIRROR", "https://hf-mirror.com").strip().rstrip("/")
    urls = [
        os.getenv("PERSON_PARSING_ONNX_URL", "").strip(),
        f"{mirror}/spaces/pngwn/IDM-VTON/resolve/main/ckpt/humanparsing/parsing_lip.onnx",
        "https://huggingface.co/spaces/pngwn/IDM-VTON/resolve/main/ckpt/humanparsing/parsing_lip.onnx",
    ]
    urls = [u for u in urls if u]
    if not urls:
        return None
    return _download_file(urls, PARSING_ONNX_PATH)


def get_parsing_onnx_path() -> Optional[str]:
    path = os.getenv("PERSON_PARSING_ONNX", "").strip()
    if path and Path(path).is_file():
        return path
    if PARSING_ONNX_PATH.is_file():
        return str(PARSING_ONNX_PATH)
    return None


def get_par_onnx_path() -> Optional[str]:
    path = os.getenv("PERSON_PAR_ONNX", "").strip()
    if path and Path(path).is_file():
        return path
    if PAR_ONNX_PATH.is_file():
        return str(PAR_ONNX_PATH)
    return None
