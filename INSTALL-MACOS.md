# macOS 安装到 STEPX Neo

本项目不是普通 APK，不能从文件管理器直接安装。它需要 **开发者选项 → USB 调试 → ADB shell**，把 CLI、脚本和配置放到手机的 `/data/local/tmp/stepneo-codex`。不需要 root、解锁 Bootloader 或 Magisk。

先在 Mac 终端确认工具：

```sh
command -v adb python3 tar unzip openssl
```

若没有 `adb`，安装 Android Platform Tools（例如 Android Studio 或 `brew install --cask android-platform-tools`），然后确认 `adb version`。

## 1. 打开开发者选项

1. 在 Neo 的“设置 → 关于手机”里找到“版本号/内部版本号”，连续点击约 7 次，直到系统提示开发者选项已打开。Step AOS 若使用不同名称，找“软件信息”或“版本信息”中的版本号。
2. 进入“开发者选项”，打开 **USB 调试**。不需要打开 OEM 解锁或 root 相关选项。
3. 用 USB 连接 Mac，解锁手机；在手机的“允许 USB 调试吗”弹窗中确认这台电脑。
4. 验证：

```sh
adb devices
adb -s <设备序列号> shell id
adb -s <设备序列号> shell getprop ro.product.cpu.abi
```

`id` 应显示类似 `uid=2000(shell)`，ABI 应为 `arm64-v8a`。如果设备状态是 `unauthorized`，在手机上重新确认授权；如果是 `offline`，重插 USB 或执行 `adb kill-server` 后重试。

## 2. 准备仓库文件和官方运行文件

把加固版 ZIP 解压到项目目录，然后准备固定版本的 Codex 和 jq：

```sh
mkdir -p ~/Projects/neo-codex-install
cd ~/Projects/neo-codex-install
unzip ~/Downloads/codex-phone-control-hardened-20261021.zip
cd codex-phone-control-hardened-20261021
mkdir -p downloads

curl -fL 'https://registry.npmjs.org/@openai/codex/-/codex-0.163.0-linux-arm64.tgz' -o downloads/codex.tgz
curl -fL 'https://github.com/jqlang/jq/releases/download/jq-1.8.2/jq-linux-arm64' -o downloads/jq
shasum -a 512 downloads/codex.tgz
shasum -a 256 downloads/jq
tar -xzf downloads/codex.tgz -C downloads
```

固定校验值：Codex tarball 的 SHA-512 为 `IH2/R+4OarjGvsAf1ll3fdyLwrPgYLl3uzp6u9CyD9sj2Lw+ViDSe3QBZVHdcHJs0eIiZFg6Wprcuy4CRZaUGw==`（用 `.NET`/Python 以 base64 比较时）；jq 的 SHA-256 为 `8b85c817833814ddca00a144c33705546355afccf0cf39b188f3cdb48b852309`。版本或地址不一致就停止。

## 3. 配置自己的模型接口

编辑两个文件：

- `templates/config.toml`：替换 `YOUR_MODEL_ID` 和 `https://api.example.com/v1`；需要 Responses API、工具调用，若要截图理解还需要图片输入。
- `phone/provider-connect.sh`：把两处 `api.example.com` 换成同一个模型域名，只写域名，不带协议、路径或端口。
- `templates/stepfun-models.json`：若使用非 OpenAI 模型（如阶跃 `step-5-preview`），必须一并上传到 `config/stepfun-models.json`，否则模型元数据会退回 fallback。详见 [STEPFUN-NOTES.md](STEPFUN-NOTES.md)。

使用阶跃 Step Plan 时，`config.toml` 关键项为：

```toml
model = "step-5-preview"
model_catalog_json = "/data/local/tmp/stepneo-codex/config/stepfun-models.json"
base_url = "https://api.stepfun.com/step_plan/v1"
wire_api = "responses"
```

同时 `[features]` 必须包含 `code_mode = true`、`code_mode_tool_search = true`、`code_mode_only = false`。这一组开关决定 MCP 工具能否直接进入模型请求，是非 OpenAI 模型接入的关键，模板已内置。

不要把 API Key 写入 TOML、脚本或聊天。Key 会在下一步通过隐藏输入送入手机 CLI。

## 4. 上传并设置权限

```sh
export PHONE='<adb devices 中显示的序列号>'
ROOT=/data/local/tmp/stepneo-codex
VENDOR="downloads/package/vendor/aarch64-unknown-linux-musl"

adb -s "$PHONE" shell "mkdir -p $ROOT/bin $ROOT/codex-path $ROOT/codex-resources $ROOT/home $ROOT/config $ROOT/tmp $ROOT/workspace"
adb -s "$PHONE" push "$VENDOR/bin/codex" "$ROOT/bin/codex"
adb -s "$PHONE" push "$VENDOR/bin/codex-code-mode-host" "$ROOT/bin/codex-code-mode-host"
adb -s "$PHONE" push "$VENDOR/codex-path/rg" "$ROOT/codex-path/rg"
adb -s "$PHONE" push "$VENDOR/codex-resources/bwrap" "$ROOT/codex-resources/bwrap"
adb -s "$PHONE" push "$VENDOR/codex-package.json" "$ROOT/codex-package.json"
adb -s "$PHONE" push downloads/jq "$ROOT/bin/jq"
adb -s "$PHONE" push phone/codex "$ROOT/codex"
adb -s "$PHONE" push phone/network.sh "$ROOT/network.sh"
adb -s "$PHONE" push phone/provider-connect.sh "$ROOT/provider-connect.sh"
adb -s "$PHONE" push phone/phone-mcp.sh "$ROOT/phone-mcp.sh"
adb -s "$PHONE" push phone/phone-ui-helper.jar "$ROOT/phone-ui-helper.jar"
adb -s "$PHONE" push templates/config.toml "$ROOT/config/config.toml"
adb -s "$PHONE" push templates/exec.config.toml "$ROOT/config/exec.config.toml"
adb -s "$PHONE" push templates/assist.config.toml "$ROOT/config/assist.config.toml"
adb -s "$PHONE" push templates/bridge.config.toml "$ROOT/config/bridge.config.toml"
adb -s "$PHONE" push templates/phone-policy.txt "$ROOT/config/phone-policy.txt"
adb -s "$PHONE" push templates/stepfun-models.json "$ROOT/config/stepfun-models.json"
adb -s "$PHONE" shell "chmod 700 $ROOT $ROOT/home $ROOT/config $ROOT/tmp $ROOT/workspace $ROOT/codex $ROOT/network.sh $ROOT/provider-connect.sh $ROOT/phone-mcp.sh $ROOT/bin/codex $ROOT/bin/codex-code-mode-host $ROOT/bin/jq"
adb -s "$PHONE" shell "chmod 600 $ROOT/config/config.toml $ROOT/config/exec.config.toml $ROOT/config/assist.config.toml $ROOT/config/bridge.config.toml $ROOT/config/phone-policy.txt $ROOT/config/stepfun-models.json $ROOT/phone-ui-helper.jar"
```

## 5. 不调用模型先检查

```sh
adb -s "$PHONE" shell "$ROOT/codex --version"
adb -s "$PHONE" shell "$ROOT/codex mcp list --json"
adb -s "$PHONE" shell "CLASSPATH=$ROOT/phone-ui-helper.jar app_process / PhoneUiHelper geometry"
adb -s "$PHONE" shell "CLASSPATH=$ROOT/phone-ui-helper.jar app_process / PhoneUiHelper ui"
```

看到 CLI 版本、MCP 配置、屏幕尺寸和 UI JSON 才算基础环境可用。`mcp list` 只证明配置存在，不证明工具执行成功。

## 6. 输入自己的 API Key

```sh
python3 - "$PHONE" <<'PY'
import getpass, subprocess, sys
phone = sys.argv[1]
key = getpass.getpass('API Key（不回显）：')
if not key.strip():
    raise SystemExit('Key 为空')
result = subprocess.run([
    'adb', '-s', phone, 'shell', '-T',
    '/data/local/tmp/stepneo-codex/codex', 'login', '--with-api-key'
], input=(key + '\n').encode(), check=False)
del key
raise SystemExit(result.returncode)
PY
adb -s "$PHONE" shell "$ROOT/codex login status"
adb -s "$PHONE" shell "chmod 600 $ROOT/config/auth.json"
```

## 7. 第一次只读调用

先用只读 profile，避免首次调试就触发 UI 动作：

```sh
cat > /tmp/neo-check.txt <<'EOF'
只使用 stepneo-phone MCP 的读取工具，概述当前页面，不点击、不输入，不读取凭据。
EOF
adb -s "$PHONE" push /tmp/neo-check.txt "$ROOT/workspace/neo-check.txt"
adb -s "$PHONE" shell "STEPNEO_PHONE_PROFILE=observe $ROOT/codex exec --json --profile exec --skip-git-repo-check --sandbox read-only --color never - < $ROOT/workspace/neo-check.txt"
```

`observe` 会提供状态、能力探测、查找、等待、UI 和截图；不会点击或输入。确认读取正常后，再显式使用 `assist`。

## 8. 再启动小跃桥接（可选）

只有需要 Amoo/小跃发起任务时才部署 `optional/bridge.sh`、`client.py` 和两个 `.jq` 文件，并使用文档中的一次性配对码流程。桥接默认不执行任务，启动命令必须显式包含：

```sh
--serve --profile assist --enable-tasks
```

配对和提交步骤见 [docs/小跃委托.md](docs/小跃委托.md)。不要开启 `full`，不要把桥接端口改成 `0.0.0.0`，也不要长期保持 ADB 调试或桥接服务。

## 安装完成后的边界

- 关闭 USB 调试不会删除 `/data/local/tmp` 中的文件，但当前方案没有完成重启自启和守护；重启后需要重新核对并启动。
- 这套方案使用 ADB shell，不等于普通 App 权限；在支付、银行、账号和隐私数据上应先停手。
- 本轮尚未在你的 Neo 上完成真实安装验收；命令中的失败项应记录具体输出，不要用模拟器结果替代。
