# StepFun（Step Plan）接入 Codex CLI 的实测要点

2026-10-25 在 STEPX Neo（`PZ261A`，Android 16，ARM64，ADB shell UID 2000）上实测。目标是让手机本地 Codex 通过 StepFun 调用 `stepneo-phone` MCP 工具。

## 1. Step Plan 通道与模型

- Step Plan 的 base URL 是 `https://api.stepfun.com/step_plan/v1`，域名固定 `api.stepfun.com`，HTTPS 443。
- Step Plan 官方文档只描述 Chat Completions 与 Anthropic Messages 两个协议，但 `POST /step_plan/v1/responses` 实测可用，Codex 的 `wire_api = "responses"` 正常工作，流式、工具调用、usage 统计均正常。
- 可用模型 ID：`step-5-preview`、`step-3.7-flash`、`step-3.5-flash`、`step-3.5-flash-2603`、`step-router-v1`（智能路由，在 `deepseek-v4-pro` 与 `step-3.7-flash` 间调度）。本次使用 `step-5-preview`。
- `step-router-v1` 仅在 Step Plan 通道可用。

## 2. 三个必须解决的 Codex 兼容问题

### 2.1 Code Mode 开关（最关键）

Codex 自带模型元数据里 `gpt-6.1-sol` 的 `tool_mode = "code_mode_only"`。启用该模式后，MCP 工具不会直接进入模型请求，而是被折叠到 `tool_search` 之后。StepFun 模型不触发 code-mode 工具搜索，因此**模型看到的工具表里完全没有 `phone_capabilities`**，只会去调用 `list_mcp_resources`，而我们的 MCP 不实现 resources 能力，于是返回空列表并放弃。

实测有效的配置：

```toml
[features]
code_mode = true          # 打开 code mode 的工具搜索通道
code_mode_tool_search = true
code_mode_only = false    # 关键：不要让工具只对 code-mode-only 模型可见
```

配合本地模型目录（见 2.2），模型会直接在请求中看到 MCP 工具定义并发起 `mcp_tool_call`。只关 `code_mode`（不打开 `code_mode_tool_search`）会让工具重新消失；只开 `code_mode` 而保留 `code_mode_only = true` 同样不生效。

Codex 会在会话开始时提示 “model does not advertise Code Mode support”，属于警告，不影响工具调用。

### 2.2 本地模型目录

Codex 的内置模型目录没有 `step-5-preview`，会退回 fallback 元数据并给出 “Model metadata not found” 提示。用 `codex debug models` 导出内置目录，复制一条**非 code-mode** 模型条目（如 `gpt-5.5`）作为模板，改 slug 与名称后保存为 `config/stepfun-models.json`，再在 `config.toml` 中设置：

```toml
model_catalog_json = "/data/local/tmp/stepneo-codex/config/stepfun-models.json"
```

注意事项：

- 该 JSON 的 schema 有必填字段（例如 `support_verbosity`），缺失会被拒绝。
- 值为 `null` 的键也会被拒绝（`invalid type: null`），需在写入前剔除。
- 参考条目不要用 `gpt-6.1-sol`，否则会继承 `tool_mode = "code_mode_only"`，重现 2.1 的问题。

### 2.3 MCP 子进程环境

`phone-mcp.sh` 需要 `PATH`、`mktemp`、`grep`、`base64`、`screencap` 等命令。Codex 的 `env_vars` 必须显式包含 `PATH`，否则子进程启动即失败。同时建议设置：

```toml
mcp_optional_startup_grace_ms = 5000   # 默认 1 秒不足以完成 app_process 冷启动
startup_timeout_sec = 20
required = true                          # 初始化失败时直接报错，而不是静默降级
```

## 3. 网络代理

`phone/network.sh` 在手机本地监听 `127.0.0.1:19092`，把 `CONNECT <domain>:443` 转发到真实域名，TLS 校验由 Codex 端用 Android 系统 CA 完成。`provider-connect.sh` 中只写域名，且必须与 `config.toml` 的 `base_url` 域名一致，否则返回 403。

## 4. 实测通过项

- `codex login --with-api-key` 成功，`config/auth.json` 权限 600。
- 最小模型调用成功（返回 `OK`），Step Plan Responses 通道可用。
- 模型直接调用 `phone_capabilities`、`phone_status`、`phone_ui` 成功，返回真实设备数据。
- `phone_ui` 在锁屏或无前台应用时返回空 `nodes`，属于预期，不是故障。

## 5. 尚未验证

- `assist` 档的点击与输入尚未在真机上执行（需要你明确授权对界面做动作）。
- `full` 档、坐标点击、桥接任务链路与重启后恢复未验证。
- 其他 StepFun 模型（`step-3.7-flash`、`step-router-v1`）未验证。
- 手机本地 Codex 的 bwrap 沙箱在 Android 上不可用（无法读 `/proc/sys/kernel/overflowuid`），因此模型无法用 shell 绕过 MCP；这是好事，但意味着所有操作必须经 MCP 工具。
