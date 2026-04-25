# WeChat Auto-Reply 开发入口

当前仓库里的微信自动回复实现位于 `wechat_auto_reply/`，与现有的 listing 后端 `app/` 保持隔离。

## 安装依赖

```powershell
python -m pip install -r requirements-wechat-auto-reply.txt
```

## 运行检查

```powershell
python -m wechat_auto_reply.main doctor
```

## 对比执行器探测

```powershell
python -m wechat_auto_reply.main compare-executors
```

这个命令会输出每个执行器当前机器上的探测结果，包括：
- 操作系统是否匹配
- `Astron` 运行时是否在 `PATH`
- `pywinauto` 是否已安装
- `pywinauto` 是否能在当前 Python 环境里真实导入 UIA backend
- 当前是否检测到微信进程和可见窗口

## 处理一条演示消息

```powershell
python -m wechat_auto_reply.main process-demo --contact "张三" --message "你好，发我一份资料"
```

默认使用 dry-run，不会真的操作桌面微信。

## 抓取微信窗口树

```powershell
python -m wechat_auto_reply.main inspect-window --platform windows-pywinauto --backend all --max-depth 2 --max-nodes 50
```

这个命令会尝试按当前检测到的微信窗口句柄接入 `pywinauto`，输出控件树快照，帮助后续定位：
- 会话列表
- 消息区
- 输入框
- 发送按钮

可选 backend：
- `uia`
- `win32`
- `all`

## 导出布局探针

```powershell
python -m wechat_auto_reply.main probe-layout --platform windows-pywinauto --no-dry-run
```

这个命令会：
- 聚焦当前微信主窗体
- 抓取窗口截图
- 生成启发式区域：
  - `conversation_list`
  - `message_pane`
  - `composer_input`
  - `send_button_candidate`
- 导出 overlay 图和每个区域的 crop 图，方便下一步 OCR/图像锚点定位

不加 `--no-dry-run` 时，命令只会生成失败 artifact，并提示需要真实截图。

## 运行 OCR 探针

```powershell
python -m wechat_auto_reply.main probe-ocr --layout-artifact data\wechat_auto_reply\runtime\artifacts\layout-probe-...\layout-probe.json
```

或者直接走实时截图 + OCR：

```powershell
python -m wechat_auto_reply.main probe-ocr --platform windows-pywinauto --no-dry-run
```

这个命令会：
- 复用已有 `layout-probe.json`，或者先抓一张新的窗口截图
- 对默认区域跑 OCR：
  - `chat_header`
  - `latest_message_band`
  - `composer_input`
- 导出预处理后的 OCR 输入图、原始 `tsv` 结果和 `ocr-probe.json`

当前 OCR 探针使用 `tesseract` 命令行作为轻量 spike：
- 如果 `tesseract` 不在 `PATH`，会生成失败 artifact，不会假装成功
- 可通过 `WECHAT_AUTO_REPLY_OCR_COMMAND` 指向自定义可执行文件
- 可通过 `WECHAT_AUTO_REPLY_OCR_LANGUAGES` 覆盖默认语言，默认值是 `chi_sim+eng`

## 提取结构化上下文

```powershell
python -m wechat_auto_reply.main probe-context --layout-artifact data\wechat_auto_reply\runtime\artifacts\layout-probe-...\layout-probe.json
```

这个命令会在 OCR 之后继续做一层共享核心解析，输出：
- `contact_name`
- `latest_message_text`
- `composer_text`
- `incoming_message`
- `decision_preview`

`decision_preview` 只做规则路由预览，不会真实发送消息。这样我们可以先验证：
- OCR 能否读到“最新一条客户消息”
- 规则引擎是否会把它分到 `low risk` 或 `must handoff`

如果表头 OCR 为空，可用：

```powershell
python -m wechat_auto_reply.main probe-context --layout-artifact ... --contact-fallback "未知联系人"
```
