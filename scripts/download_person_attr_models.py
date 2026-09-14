"""下载人员搜索辅助模型（可选 LIP Human Parsing ONNX）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.person_search.model_assets import ensure_parsing_onnx, get_parsing_onnx_path

if __name__ == "__main__":
    path = ensure_parsing_onnx()
    if path:
        print(f"Human Parsing ONNX 已就绪: {path}")
    else:
        ready = get_parsing_onnx_path()
        if ready:
            print(f"Human Parsing ONNX 已存在: {ready}")
        else:
            print(
                "未下载 Parsing ONNX，将使用内置 fast_zone 快速分割（无需模型文件）。\n"
                "如需 LIP 精细分割，可设置 PERSON_PARSING_ONNX_URL 后重试，"
                "或手动放置到 models/person_search/parsing_lip.onnx"
            )
