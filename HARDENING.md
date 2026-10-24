# 加固说明

## 目标与边界

本项目针对原始分享版本的**配对、自动执行、敏感界面和日志泄露**做防御性加固。它没有改变 `phone-ui-helper.jar` 的 DEX，也没有重新实现厂商 UI Agent。工具仍然运行在 ADB shell UID 2000，仍然使用可访问性、截图和坐标注入；因此它不是“普通 App 权限版”控制，也不能替代 Android 系统级授权。

社群分享版本的原始内容未改动。加固后的文件即本仓库内容。

## 已做的改动

| 风险 | 加固措施 |
| --- | --- |
| 五分钟配对窗口内任意本机进程可抢配对 | `bridge.sh --pair-window` 生成一次性 256 位码，只在本机 ADB 终端显示；`/v1/pair` 必须带 `X-Pairing-Code`，成功即删除；自定义头使浏览器跨站请求无法直接伪造 |
| 浏览器/网页触达 loopback 服务 | 所有请求带 `Origin` 头时直接 403；Host 仍限制为 loopback 的两个名称 |
| 本机伪造客户端资产 | `/assets/client.py` 仅在配对窗口内且带正确一次性码时可取；客户端来源应优先使用本仓库 `optional/client.py` |
| 桥接启动后默认就能执行任务 | `--serve` 默认 `observe` 且 `tasks_enabled=false`；必须显式 `--profile assist` 或 `full` 加 `--enable-tasks`，且需要 `config/bridge.config.toml` |
| 模型默认拥有坐标点击和 Enter | OBSERVE 只暴露读取工具；ASSIST 隐藏 `phone_tap` 和 `ENTER`/`DPAD_CENTER`，点击必须使用精确可见文字；FULL 才开放全部工具 |
| 反复截图/UI 读取成本高、容易误点 | 增加 `phone_find` 精确查找和 `phone_wait` 状态等待；只读即可使用，返回结构化目标，不直接动作 |
| 设备兼容性只能靠猜 | 增加 `phone_capabilities`，探测 ABI、shell、显示、依赖和工具可用性 |
| 只能打开应用，不能受控进入网页 | 增加 `phone_open_url`，只接受经校验的 HTTP(S) 地址，不模拟点击、不隐藏来源 |
| 支付、删除、授权等敏感弹窗 | ASSIST 默认拦截 Settings、Alipay 包和相关中英文确认词；策略文件可追加规则，但不能当作不可绕过的系统权限 |
| 任务 prompt 暴露在进程命令行 | `client.py run --prompt-file` 为推荐路径；保留 `--prompt` 仅为兼容，文档不再使用 |
| 桥接令牌与模型 Key 混用 | 客户端令牌独立于模型 API Key，仍分别存放；桥接只负责提交任务 |
| 任务桥接允许文件写入 | 桥接 Codex 使用 `--sandbox read-only`，不再默认 `workspace-write` |
| 交互审批被静默关闭 | 人工主配置改为 `approval_policy = "on-request"` 和交互工具 `prompt`；只有显式 `exec/assist/bridge` profile 的无人值守档使用 `never/approve` |
| 日志保留敏感文字或 URL | MCP 审计日志不再保存 `target_text`、查找文字、输入正文和 URL，只保存长度/字符数；任务最终结果仍由桥接保存，需自行清理 |

## 使用档位

- `observe`：`phone_status`、`phone_capabilities`、`phone_find`、`phone_wait`、`phone_ui`、`phone_screenshot`。适合先看清楚屏幕，不产生 UI 操作。
- `assist`：增加启动、精确文字点击、输入、滑动和安全按键；禁止坐标点击、Enter/DPAD_CENTER 及策略命中的敏感动作。
- `full`：全部工具，包含坐标点击与 Enter/DPAD_CENTER。只能用于设备所有者明确许可、有人值守的测试，不应作为日常默认。

主 Codex 的手工配置默认是 `on-request`；桥接的无人值守配置单独放在 `config/bridge.config.toml`，不会在未显式选择 `--profile bridge` 时启用。

## 仍然存在的风险

1. **ADB shell 本身是高权限调试身份。** “无 root”不等于低权限；有 ADB 授权的主机可以访问 shell 可访问的文件并启动该服务。
2. **应用层策略不是安全内核。** ASSIST 的包名/文字过滤可被自定义 UI、资源 ID 点击、屏幕注入或恶意模型绕过；坐标点击在 FULL 中可达任意位置。
3. **模型与屏幕内容仍可能泄露或受提示注入影响。** 截图、可访问性文字、任务 prompt 和结果可能发送到你配置的模型服务并写入 Codex/桥接记录。
4. **没有系统级人工确认。** 当前加固不能替代一个独立的伴侣 App、系统授权弹窗或硬件确认按钮。
5. **没有完成重启自启、长期服务、另一台手机从零安装和厂商固件兼容验证。**
6. **JAR 未重新编译。** 为了方便离线复现，保留了原始 `phone-ui-helper.jar`；`src/PhoneUiHelper.java` 和 JAR 的一致性只做了可见字符串级核对，没有在本机重新构建。

## 推荐使用方式

先用 `observe` 在专用测试手机上读取 UI 和截图，再在有人值守、无支付/银行账号的环境中用 `assist`。桥接任务只在 600 秒窗口内运行，完成后停止服务并轮换配对。`full` 只用于明确的人工测试；不要把桥接令牌、模型 Key、任务文件或 `client.json` 放入聊天、日志或公开仓库。
