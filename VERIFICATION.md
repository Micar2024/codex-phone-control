# 加固版验证记录

验证日期：2026-10-21（Asia/Shanghai）。本轮只检查文件、静态语法和无设备模拟测试；**没有连接、安装或运行 STEP Neo**，也不把它写成新的真机通过。

## 真机安装与运行（2026-10-25）

设备：机型 `PZ261A`，Android 16（API 36），ARM64，ADB shell `uid=2000(shell)`。安装位置 `/data/local/tmp/stepneo-codex`。设备序列号与 USB 路径属于个人环境信息，已脱敏。

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 工具链 | Codex CLI 0.163.0、jq 1.8.2、UI helper JAR 全部上传，本地与手机端 SHA-256 一致 | 安装后逐文件 `sha256sum` 比对一致 |
| CLI | `codex --version` 正常；`codex mcp list --json` 显示 `stepneo-phone` | 命令实际输出 |
| UI helper | `geometry` 返回 920×2047 图像坐标、1200×2670 实际屏幕；`ui` 返回真实节点 | 手机端直接执行 app_process |
| 登录 | `codex login status` 显示已用 API Key 登录；`config/auth.json` 权限 600 | 状态输出与 `stat` |
| 模型 | 阶跃 Step Plan `step-5-preview` 最小调用成功，返回 `OK` | `codex exec --json` 输出 `agent_message: OK` |
| MCP 工具 | 模型直接调用 `stepneo-phone` 的 `phone_capabilities`、`phone_status`、`phone_ui` 成功，返回真实设备数据 | 会话事件中的 `mcp_tool_call` completed 项 |
| 观察档 | `observe` 只暴露 6 个只读工具，未发生点击、输入或截图 | `tools/list` 输出与本次提示词约束 |

**已修复的关键兼容问题**（详见 [STEPFUN-NOTES.md](STEPFUN-NOTES.md)）：Codex 的 `code_mode_only` 会把 MCP 工具折叠到模型无法触发的位置；必须同时设置 `code_mode = true`、`code_mode_tool_search = true`、`code_mode_only = false`，并提供 `model_catalog_json` 本地模型目录。此外 `env_vars` 必须包含 `PATH`，`mcp_optional_startup_grace_ms` 需从默认 1 秒提高到 5000 毫秒。

### 仍未验证

- `assist` 档的真实点击与输入（需要明确授权后才执行）。
- `full` 档、坐标点击、`phone_open_url`。
- 小跃桥接的配对与任务链路。
- 重启后恢复、其他 StepFun 模型、`step-router-v1`。
- `phone_ui` 在无前台应用时返回空 `nodes`，属预期行为，未在有界面前台下复核。

## 源包完整性

- 源包：`Codex手机控制-脱敏分享包-20261021.zip`（社群分享版本，未包含在本仓库中）
- ZIP 完整性：通过。
- 源包 SHA-256：`4d04fd6a1c8c20a2f85e4e3f4f1b48efc3cc36d783a110e25078cb5c40354e9f`。
- 源包 `SHA256SUMS.txt` 的 15 个内容文件全部与清单一致，没有漏项或改动。
- Codex 0.163.0 Linux ARM64 tarball 154,715,729 字节，SHA-512 与 README 固定值一致；jq 1.8.2 ARM64 1,797,688 字节，SHA-256 一致。
- 未发现明显的私钥、API Key、Bearer Token、邮箱或手机号；这是规则扫描，不是完整的恶意代码或法律合规审计。

## 加固版测试

执行：

```sh
python3 -m unittest discover -s tests -v
```

结果：**10/10 通过**。

- 客户端：一次性码配对、失败后保留令牌并复用原码、拒绝非 loopback BASE、读取 `--prompt-file`。
- 桥接 HTTP：拒绝 `Origin`、客户端资产必须带配对码、错误配对码被拒绝、成功配对消费配对码、默认禁止任务执行。
- MCP：OBSERVE 只暴露六个读取工具（状态、能力探测、查找、等待、UI、截图）；ASSIST 隐藏 `phone_tap`，隐藏 `ENTER`/`DPAD_CENTER`，要求输入/点击显式携带 package，拦截敏感点击和包名；`phone_open_url` 拒绝 `file:` 等非 HTTP(S) 地址；审计日志不保存查找文字、点击文字或 URL。
- Shell/Python 语法：`phone/codex`、`phone/network.sh`、`phone/provider-connect.sh`、`phone/phone-mcp.sh`、`optional/bridge.sh` 均通过 `sh -n`；`optional/client.py` 通过 `py_compile`。
- TOML：主配置、`exec`、`assist`、`bridge` 四个 profile 均通过 Python `tomllib` 解析。

## 未验证

- 未在 Android `/data/local/tmp` 中执行修改后的 bridge/MCP。
- 未验证 Codex CLI 0.163.0 对 `bridge.config.toml` 的 profile 合并行为。
- 未验证 Android 16 真机上的 `nc`、`od`、`grep`、`date` 行为和 UiAutomation 兼容性。
- 未验证 STEP Neo 固件、重启、后台、服务守护、屏幕锁定、第三方 App 的真实控件结构或支付场景。
- 未重新编译 `phone-ui-helper.jar`，因此它不是从本轮修改后的源码生成的二进制。

## 适用建议

加固版仍是受控实验。先做 `observe`，再在专用测试手机上做 `assist`；`full` 需要设备所有者单独决定。若要在真实手机上验收，应另开授权步骤，并记录设备型号、固件、App 版本、实际入口和退出结果。
