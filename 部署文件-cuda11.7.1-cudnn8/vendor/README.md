# NetSDK 本地 Wheel

构建 **detect-server** 时，Dockerfile 会自动从 `vendor/` 或 `docs/` 安装 `NetSDK*.whl`。

将 wheel 放入构建上下文即可，例如：

```bash
cp ../../docs/NetSDK-2.0.0.1-py3-none-linux_x86_64.whl ./vendor/
```
