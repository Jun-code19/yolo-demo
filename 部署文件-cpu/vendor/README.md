# NetSDK 本地 Wheel

检测服务的事件订阅（SmartSchemer）依赖大华 NetSDK，该包**不在 PyPI**，只能通过本地 wheel 安装。

## 构建前准备

构建上下文内需有 wheel（任选其一）：

- `vendor/NetSDK-2.0.0.1-py3-none-linux_x86_64.whl`
- `docs/NetSDK-2.0.0.1-py3-none-linux_x86_64.whl`

```bash
cp ../../docs/NetSDK-2.0.0.1-py3-none-linux_x86_64.whl ./vendor/
```

## 要求

- 仅支持 **Linux x86_64** 容器
- Python 3.10
- 构建 **detect-server** 时 Dockerfile 会自动 `pip install`

若构建上下文无 wheel，镜像仍可构建，但 SDK 事件订阅不可用。
