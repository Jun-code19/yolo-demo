"""手动下载 OSNet ReID 预训练权重。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.person_search.reid_loader import DEFAULT_WEIGHTS_PATH, ensure_reid_weights

if __name__ == "__main__":
    path = ensure_reid_weights(DEFAULT_WEIGHTS_PATH)
    print(f"ReID 权重已就绪: {path}")
