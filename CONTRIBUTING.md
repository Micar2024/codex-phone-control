# 贡献指南

感谢参与。这个项目把手机本地 Codex CLI 与一套受控的 Android UI MCP 工具接在一起，目标是让个人设备上的自动化**可审计、可限制、可随时停手**。

## 开发约定

- **先在真实设备验证目标 App 的入口**，再写实现。模拟器能跑通不代表目标 App 的分享、导出或系统入口可用。
- 任何新增工具都必须写清：读还是写、作用范围、是否需要用户确认、失败如何回滚。
- 写操作默认受安全档位约束：`observe` 只读、`assist` 受限、`full` 需显式选择。
- 不要把 API Key、设备序列号、无线调试地址、聊天记录或分享原文写进仓库、日志或 prompt 文件。
- 日志只记录工具名、参数长度和成败，不记录输入正文、点击目标文字或 URL 全文。

## 提交前检查

```sh
python3 -m unittest discover -s tests -v
sh -n phone/codex phone/network.sh phone/provider-connect.sh phone/phone-mcp.sh optional/bridge.sh
python3 -m py_compile optional/client.py
```

改动后请同步更新 `VERIFICATION.md`（区分已验证与待验证）和 `SHA256SUMS.txt`（运行 `python3 scripts/package.py` 重新生成）。

## 风险声明

本项目以 ADB shell 身份运行，可以读取界面树、截图、注入点击和输入。这在权限上高于普通第三方 App。请只在自己拥有或已获授权的设备上使用，不要用于绕过他人设备的安全机制。
