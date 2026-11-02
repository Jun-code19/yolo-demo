# RF-DETR 最小接入说明

在现有检测链路中通过 `backend=yolo|rfdetr` 分流：YOLO 路径不变；RF-DETR 仅替换加载与推理，输出统一为 detections（bbox / confidence / class_id / class_name），任务、事件、ROI、VLM、人员搜索可复用。

## 环境要求

- 检测服务建议 **Python ≥ 3.10**（`rfdetr` 官方要求）
- 当前 CUDA11.7 / `torch==2.4.1` 部署请钉 **`rfdetr==1.5.1`**（`transformers` 4.x）  
  - 勿装 `rfdetr>=1.6`：其依赖 `transformers>=5.1`，而 transformers 5 需要 **torch≥2.6**，在 2.4.1 上会报 `BackboneConfigMixin` / “PyTorch was not found”
- 依赖见 `部署文件-cuda11.7.1-cudnn8/requirements.detect-server.txt`
- **建议 GPU**；CPU 可跑但明显更慢，多路任务时可能拖垮整体吞吐
- 首期仅 **目标检测**（`models_type=object_detection`），不做分割 / 姿态

## 权重获取

1. 使用官方预训练或自行 fine-tune 得到的 checkpoint（常见扩展名 `.pt` / `.pth`）
2. 可选在上传「模型参数」中指定规格：`{"rfdetr_size": "base"}`  
   取值：`nano` / `small` / `base` / `medium` / `large` / `xlarge`（用于无法 `from_checkpoint` 时的构造回退）
3. 自定义类别可写：`{"classes": {"0": "person", "1": "helmet"}}`；无元数据时默认 COCO80

## 上传步骤

1. 启动 `base_data_server` 与 `base_detect_server`（上传会调 detect 侧 `/api/v2/model/load`）
2. 前端「模型管理 → 本地模型 → 上传新模型」
3. **模型架构** 选 `RF-DETR`（类型锁定为目标检测）
4. 选择权重文件上传；入库字段：`detection_model.backend = rfdetr`，`parameters.backend` 同步写入
5. 编辑模型时建议打开 **GPU**

## 建任务与验收

1. 在检测配置中选择该模型（下拉会显示 RF-DETR 标签）
2. 启动任务：预览有框、事件可落库、detections 字段齐全
3. YOLO `.pt` 上传与运行行为应与接入前完全一致

## 与 YOLO A/B 建议

| 维度 | YOLO | RF-DETR |
|------|------|---------|
| 速度 | 通常更快（尤其小模型） | Transformer，同尺寸更重 |
| 小目标 / 复杂场景 | 视训练数据而定 | 往往边界更稳，可作对照 |
| 部署 | `.pt` / ONNX 成熟 | 首期仅 PyTorch + `rfdetr` 包 |
| 多路并发 | 更适合多路实时 | 建议少路 + GPU |

同一路视频、同一 ROI / 置信度下对比漏检与误检即可。

## 明确首期不做

- RF-DETR 分割 / 关键点
- 边缘盒子 / NCNN 导出
- 与 YOLO 训练管线打通
- 改人员搜索或 VLM 业务逻辑
