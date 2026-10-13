"""本域 OSNet 微调（离线）。

数据目录约定（Market1501 风格简化）:
  data/person_search_finetune/
    train/
      id_001/
        001.jpg
        002.jpg
      id_002/
        ...
    或 pairs.json: [{"id":"p1","images":["a.jpg","b.jpg"]}, ...]

用法:
  python scripts/finetune_osnet_reid.py --data data/person_search_finetune/train --epochs 30
  训练完成后设置:
    PERSON_REID_WEIGHTS=models/reid/osnet_x1_0_domain.pth
  并升高 embedder.EMBEDDING_VERSION 后执行「重建图库特征」。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.person_search.reid_loader import (  # noqa: E402
    DEFAULT_MODEL_NAME,
    DEFAULT_WEIGHTS_PATH,
    load_osnet_model,
)
from src.person_search.utils import REID_HEIGHT, REID_WIDTH, preprocess_reid_crop  # noqa: E402


class IdentityFolderDataset(Dataset):
    def __init__(self, root: Path):
        self.samples: List[Tuple[Path, int]] = []
        self.id_names: List[str] = []
        if (root / "pairs.json").is_file():
            data = json.loads((root / "pairs.json").read_text(encoding="utf-8"))
            for i, item in enumerate(data):
                name = str(item.get("id") or f"id_{i}")
                self.id_names.append(name)
                for rel in item.get("images") or []:
                    p = root / rel
                    if p.is_file():
                        self.samples.append((p, i))
        else:
            folders = sorted([p for p in root.iterdir() if p.is_dir()])
            for i, folder in enumerate(folders):
                self.id_names.append(folder.name)
                for img in folder.glob("*"):
                    if img.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                        self.samples.append((img, i))
        if not self.samples:
            raise RuntimeError(f"未找到训练样本: {root}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        bgr = cv2.imread(str(path))
        if bgr is None:
            bgr = np.zeros((REID_HEIGHT, REID_WIDTH, 3), dtype=np.uint8)
        rgb = cv2.cvtColor(preprocess_reid_crop(bgr), cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).float().permute(2, 0, 1) / 255.0
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        tensor = (tensor - mean) / std
        return tensor, label


class TripletSampler:
    """简单批内难样本：同 ID 为正，异 ID 为负。"""

    def __init__(self, labels: List[int]):
        self.labels = labels
        self.by_id: Dict[int, List[int]] = {}
        for i, y in enumerate(labels):
            self.by_id.setdefault(y, []).append(i)

    def sample(self, anchor_idx: int) -> Tuple[int, int]:
        y = self.labels[anchor_idx]
        pos_pool = [i for i in self.by_id[y] if i != anchor_idx]
        if not pos_pool:
            pos = anchor_idx
        else:
            pos = random.choice(pos_pool)
        neg_ids = [k for k in self.by_id if k != y]
        if not neg_ids:
            neg = anchor_idx
        else:
            neg = random.choice(self.by_id[random.choice(neg_ids)])
        return pos, neg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="训练数据根目录")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--margin", type=float, default=0.3)
    parser.add_argument(
        "--output",
        default=str(ROOT / "models" / "reid" / "osnet_x1_0_domain.pth"),
    )
    parser.add_argument("--base-weights", default=DEFAULT_WEIGHTS_PATH)
    args = parser.parse_args()

    data_root = Path(args.data)
    ds = IdentityFolderDataset(data_root)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, num_workers=0, drop_last=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = load_osnet_model(DEFAULT_MODEL_NAME, args.base_weights)
    # 暴露分类头：在特征后接 Linear
    feat_dim = 512
    classifier = nn.Linear(feat_dim, len(ds.id_names)).to(device)
    model = model.to(device)
    model.train()
    opt = torch.optim.Adam(
        list(model.parameters()) + list(classifier.parameters()), lr=args.lr, weight_decay=5e-4
    )
    labels_all = [y for _, y in ds.samples]
    sampler = TripletSampler(labels_all)

    print(f"samples={len(ds)} ids={len(ds.id_names)} device={device}")
    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        steps = 0
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            feats = model(images)
            if isinstance(feats, (tuple, list)):
                feats = feats[0]
            feats = F.normalize(feats, dim=1)
            logits = classifier(feats)
            ce = F.cross_entropy(logits, labels)

            # batch 内构造 triplet
            emb = feats
            trip = 0.0
            n = emb.size(0)
            for i in range(n):
                # 用同 batch 近似
                yi = int(labels[i].item())
                pos_idx = [j for j in range(n) if int(labels[j].item()) == yi and j != i]
                neg_idx = [j for j in range(n) if int(labels[j].item()) != yi]
                if not pos_idx or not neg_idx:
                    continue
                pos = emb[random.choice(pos_idx)]
                neg = emb[random.choice(neg_idx)]
                trip = trip + F.relu(
                    args.margin + torch.sum((emb[i] - pos) ** 2) - torch.sum((emb[i] - neg) ** 2)
                )
            trip = trip / max(1, n)
            loss = ce + trip
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += float(loss.item())
            steps += 1
        print(f"epoch {epoch}/{args.epochs} loss={total_loss / max(1, steps):.4f}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)
    meta = {
        "model": DEFAULT_MODEL_NAME,
        "ids": len(ds.id_names),
        "samples": len(ds),
        "epochs": args.epochs,
        "output": str(out),
        "note": "设置 PERSON_REID_WEIGHTS 后升高 EMBEDDING_VERSION 并重建图库",
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存权重: {out}")


if __name__ == "__main__":
    main()
