"""共享存储目录/文件权限辅助。

Docker 默认以 root 写入挂载卷时，宿主机 ubuntu 用户删除会 Permission denied。
Linux 下 Path.mkdir(mode=0o777) 仍会被 umask 收成 755，文件常为 644。
因此创建后必须显式 chmod，保证跨用户可删。

注意：本模块被 data-server（无 OpenCV）与 detect-server 共用。
cv2/numpy 仅在 write_bgr_image 内延迟导入，勿在模块顶层 import。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence, Union

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# 目录/文件默认权限（挂载卷跨 root/ubuntu 共用）
DIR_MODE = int(os.getenv("STORAGE_DIR_MODE", "0o777"), 0)
FILE_MODE = int(os.getenv("STORAGE_FILE_MODE", "0o666"), 0)


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as exc:
        logger.debug("chmod %s -> %o 失败: %s", path, mode, exc)


def ensure_dir(path: PathLike) -> Path:
    """创建目录并尽量把路径上的 storage/uploads 节点都设为可写。"""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    # 自下而上放宽权限，避免仅叶子目录 777、父级仍 755 root
    cur = target
    for _ in range(12):
        _chmod(cur, DIR_MODE)
        if cur.name in {"storage", "uploads", "models"} or cur.parent == cur:
            break
        cur = cur.parent
    return target


def soften_file(path: PathLike) -> None:
    p = Path(path)
    if p.is_file():
        _chmod(p, FILE_MODE)


def soften_tree(root: PathLike) -> int:
    """运维用：递归放宽已有 storage 树权限，返回处理节点数。"""
    root_path = Path(root)
    if not root_path.exists():
        return 0
    n = 0
    for dirpath, dirnames, filenames in os.walk(root_path):
        d = Path(dirpath)
        _chmod(d, DIR_MODE)
        n += 1
        for name in filenames:
            _chmod(d / name, FILE_MODE)
            n += 1
        _ = dirnames  # keep walk mutable
    return n


def write_bgr_image(
    path: PathLike,
    image: Any,
    params: Optional[Sequence[int]] = None,
) -> bool:
    """写 JPEG/图片：自动建目录、写文件、chmod 为可删。

    仅 detect 侧调用；需要环境已安装 opencv-python。
    """
    import cv2  # 延迟导入：data-server 只用 ensure_dir/safe_unlink

    out = Path(path)
    ensure_dir(out.parent)
    ok = bool(cv2.imwrite(str(out), image, list(params) if params is not None else []))
    if ok:
        soften_file(out)
    return ok


def safe_unlink(path: PathLike) -> bool:
    """删除文件；若权限不足先尝试 chmod 再删。"""
    p = Path(path)
    if not p.exists():
        return True
    try:
        p.unlink()
        return True
    except PermissionError:
        try:
            _chmod(p, FILE_MODE)
            if p.parent.exists():
                _chmod(p.parent, DIR_MODE)
            p.unlink()
            return True
        except OSError as exc:
            logger.warning("删除文件失败 %s: %s", p, exc)
            return False
    except OSError as exc:
        logger.warning("删除文件失败 %s: %s", p, exc)
        return False
