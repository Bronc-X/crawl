# 小红书浏览器采集 worker

目标：低频、人工登录、遇到验证码或风控即停止，不做绕过。

## 安装可选依赖

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
```

## 保存登录态

```powershell
.\.venv\Scripts\python.exe scripts\xhs_browser_worker.py capture-login --storage-state .auth\xhs-storage.json
```

浏览器打开后手动扫码登录，登录完成后回到终端按回车。

## 真实浏览器 CDP 模式（推荐）

这个模式复用你自己电脑上已经登录的小红书浏览器窗口，路线更接近 MediaCrawler 的真实浏览器思路。

1. 关闭正在运行的 Edge/Chrome。
2. 用远程调试端口启动一个独立浏览器用户目录：

```powershell
Start-Process msedge -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\Administrator\AppData\Local\Temp\xhs-cdp-profile','https://www.xiaohongshu.com/'
```

3. 在打开的浏览器里人工登录小红书。
4. 低频采集：

```powershell
.\.venv\Scripts\python.exe scripts\xhs_browser_worker.py scrape-search --keyword "提臀塑形" --limit 3 --cdp-url http://127.0.0.1:9222 --output data\xhs-browser\latest.json
```

## storage_state 备用模式

```powershell
.\.venv\Scripts\python.exe scripts\xhs_browser_worker.py scrape-search --keyword "提臀塑形" --limit 3 --storage-state .auth\xhs-storage.json --output data\xhs-browser\latest.json
```

输出 JSON 的每条 `html` 可直接放进控制台 `采集 -> HTML`，再点 `浏览器提取`。

## 提取策略

- 优先读取页面里已经渲染出来的 `window.__INITIAL_STATE__` 等结构化状态。
- 读不到结构化状态时，回退到详情页 DOM、meta、图片标签。
- 不做接口签名逆向，不做验证码绕过，不做风控规避。

## 停止条件

- 出现验证码
- 出现安全验证
- 提示访问频繁
- 登录态失效
- 返回 `XHS_BLOCKED`

这些情况都需要人工处理，工具不会绕过平台验证。
