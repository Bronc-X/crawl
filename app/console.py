from __future__ import annotations


def render_console() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>多平台自动上架工作台</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --black: #f5f5f5;
      --surface: #ffffff;
      --surface-raised: #f0f0f0;
      --border: #e8e8e8;
      --border-visible: #cccccc;
      --text-disabled: #999999;
      --text-secondary: #666666;
      --text-primary: #1a1a1a;
      --text-display: #000000;
      --accent: #d71921;
      --success: #4a9e5c;
      --warning: #9a6a18;
      --radius: 12px;
      --font-ui: "Space Grotesk", "Microsoft YaHei", sans-serif;
      --font-mono: "Space Mono", "Microsoft YaHei", monospace;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      color: var(--text-primary);
      background: var(--black);
      font-family: var(--font-ui);
      overflow: hidden;
    }
    button, input, textarea { font: inherit; }
    button {
      min-height: 42px;
      border: 1px solid transparent;
      border-radius: 999px;
      padding: 10px 18px;
      cursor: pointer;
      background: transparent;
      color: var(--text-primary);
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .06em;
      transition: border-color 150ms ease, color 150ms ease, background 150ms ease, opacity 150ms ease;
    }
    button:hover { border-color: var(--text-display); }
    button:disabled { cursor: wait; opacity: .45; }
    input, textarea {
      width: 100%;
      border: 1px solid var(--border-visible);
      border-radius: 8px;
      background: var(--surface);
      color: var(--text-primary);
      padding: 11px 12px;
      outline: none;
      font-family: var(--font-mono);
      font-size: 14px;
    }
    textarea { min-height: 108px; resize: vertical; }
    input:focus, textarea:focus { border-color: var(--text-display); }
    label {
      display: block;
      margin-bottom: 7px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    h1, h2, h3, p { margin: 0; }
    .app-shell {
      display: grid;
      grid-template-columns: 252px minmax(0, 1fr);
      height: 100vh;
      background: var(--black);
    }
    .sidebar {
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 24px;
      border-right: 1px solid var(--border-visible);
      padding: 22px 18px;
      overflow: hidden;
    }
    .brand {
      display: grid;
      gap: 8px;
    }
    .brand-code {
      color: var(--accent);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .12em;
    }
    .brand h1 {
      color: var(--text-display);
      font-size: 30px;
      line-height: 1.02;
      letter-spacing: 0;
    }
    .brand p {
      color: var(--text-secondary);
      font-size: 14px;
      line-height: 1.5;
    }
    .side-nav {
      display: grid;
      align-content: start;
      gap: 4px;
    }
    .nav-item {
      display: grid;
      grid-template-columns: 20px 1fr auto;
      align-items: center;
      gap: 8px;
      width: 100%;
      min-height: 46px;
      border: 0;
      border-radius: 0;
      padding: 0;
      color: var(--text-disabled);
      text-align: left;
      background: transparent;
    }
    .nav-item:hover,
    .nav-item.active {
      color: var(--text-display);
      border: 0;
    }
    .nav-item .dot {
      width: 8px;
      height: 8px;
      border: 1px solid currentColor;
      border-radius: 999px;
    }
    .nav-item.active .dot { background: var(--accent); border-color: var(--accent); }
    .nav-title {
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .06em;
    }
    .nav-meta {
      font-family: var(--font-mono);
      font-size: 10px;
      letter-spacing: .08em;
    }
    .sidebar-footer {
      display: grid;
      gap: 12px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      letter-spacing: .06em;
    }
    .channel-list {
      display: grid;
      gap: 8px;
    }
    .channel-list label,
    .checkline,
    .radio-line {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: var(--text-secondary);
      text-transform: none;
      letter-spacing: 0;
      font-family: var(--font-ui);
      font-size: 14px;
      font-weight: 500;
    }
    .workspace {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-width: 0;
      height: 100vh;
    }
    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      min-height: 118px;
      border-bottom: 1px solid var(--border-visible);
      padding: 22px 28px 18px;
      background: var(--black);
    }
    .eyebrow {
      margin-bottom: 6px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    .workspace-title {
      color: var(--text-display);
      font-size: clamp(28px, 4vw, 46px);
      line-height: 1;
      letter-spacing: 0;
    }
    .workspace-copy {
      max-width: 780px;
      margin-top: 9px;
      color: var(--text-secondary);
      font-size: 15px;
      line-height: 1.5;
    }
    .topbar-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .content {
      min-height: 0;
      overflow: auto;
      padding: 24px 28px;
    }
    .view {
      display: none;
      max-width: 1180px;
    }
    .view.active { display: block; }
    .layout-two {
      display: grid;
      grid-template-columns: minmax(420px, .9fr) minmax(360px, .7fr);
      gap: 18px;
      align-items: start;
    }
    .panel {
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface);
      padding: 18px;
    }
    .panel + .panel { margin-top: 18px; }
    .panel-header {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: start;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .panel h2 {
      color: var(--text-display);
      font-size: 22px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .hint {
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.5;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .full { grid-column: 1 / -1; }
    .media-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .radio-group {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      min-height: 42px;
      align-items: center;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    .step-rail {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 0 0 16px;
      padding: 0;
      list-style: none;
    }
    .step-item {
      display: grid;
      gap: 4px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      color: var(--text-secondary);
    }
    .step-item.active {
      border-color: var(--text-display);
      color: var(--text-display);
    }
    .step-item.done {
      border-color: var(--success);
      color: var(--success);
    }
    .step-index {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
    }
    .step-title {
      font-size: 14px;
      font-weight: 700;
    }
    .result-grid {
      display: grid;
      gap: 12px;
    }
    .result-row {
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 12px;
      padding: 11px 0;
      border-bottom: 1px solid var(--border);
    }
    .result-label {
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .result-value {
      min-width: 0;
      overflow-wrap: anywhere;
      color: var(--text-primary);
      font-size: 14px;
      line-height: 1.5;
    }
    .next-actions {
      display: grid;
      gap: 10px;
      margin-top: 16px;
    }
    .rewrite-card {
      border: 1px solid var(--border-visible);
      border-radius: var(--radius);
      padding: 14px;
      background: var(--surface-raised);
    }
    .empty-result {
      display: grid;
      gap: 10px;
      align-content: center;
      min-height: 260px;
      color: var(--text-secondary);
    }
    .primary { background: var(--text-display); color: var(--black); }
    .secondary { border-color: var(--border-visible); }
    .danger-btn { border-color: var(--accent); color: var(--accent); }
    .ghost { color: var(--text-secondary); }
    .muted-btn { background: var(--surface-raised); }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border: 1px solid var(--border-visible);
      border-radius: 999px;
      padding: 3px 9px;
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .05em;
      white-space: nowrap;
    }
    .ok { color: var(--success); border-color: var(--success); }
    .warn { color: var(--warning); border-color: var(--warning); }
    .danger { color: var(--accent); border-color: var(--accent); }
    .settings-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .setting-block {
      display: grid;
      gap: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
    }
    .setting-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      padding: 13px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--text-secondary);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .empty-row {
      padding: 28px 10px;
      color: var(--text-secondary);
      text-align: center;
    }
    .log {
      min-height: 420px;
      max-height: calc(100vh - 250px);
      overflow: auto;
      border: 1px solid var(--border-visible);
      border-radius: 10px;
      background: #050505;
      color: #f5f5f5;
      padding: 14px;
      font-family: var(--font-mono);
      font-size: 12px;
      line-height: 1.55;
      white-space: pre-wrap;
    }
    @media (max-width: 980px) {
      body { overflow: auto; }
      .app-shell { grid-template-columns: 1fr; height: auto; min-height: 100vh; }
      .sidebar { position: sticky; top: 0; z-index: 2; grid-template-rows: auto auto; border-right: 0; border-bottom: 1px solid var(--border-visible); background: var(--black); }
      .side-nav { display: flex; overflow-x: auto; }
      .nav-item { min-width: 130px; }
      .sidebar-footer { display: none; }
      .workspace { height: auto; }
      .topbar { grid-template-columns: 1fr; min-height: 0; }
      .content { overflow: visible; padding: 18px; }
      .layout-two, .settings-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      .form-grid, .media-grid { grid-template-columns: 1fr; }
      .step-rail { grid-template-columns: 1fr; }
      .topbar-actions, .actions { display: grid; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-code">AUTO LISTING / LOCAL</div>
        <h1>自动上架工作台</h1>
        <p>采集、建品、配置、任务分区处理，不再上下翻找。</p>
      </div>
      <nav class="side-nav" id="sideNav" aria-label="功能栏">
        <button class="nav-item active" type="button" data-section="import" data-title="小红书采集" data-copy="先采集商品来源，再决定只预览、建商品，或进入自动上架。">
          <span class="dot"></span><span class="nav-title">采集商品</span><span class="nav-meta">01</span>
        </button>
        <button class="nav-item" type="button" data-section="products" data-title="商品主数据" data-copy="录入标准商品，校验后进入多平台上架流程。">
          <span class="dot"></span><span class="nav-title">商品</span><span class="nav-meta">02</span>
        </button>
        <button class="nav-item" type="button" data-section="settings" data-title="平台配置" data-copy="维护平台默认字段，并查看真实发送桥是否已经可用。">
          <span class="dot"></span><span class="nav-title">配置</span><span class="nav-meta">03</span>
        </button>
        <button class="nav-item" type="button" data-section="tasks" data-title="任务与结果" data-copy="查看商品列表、上架任务、平台返回状态和失败原因。">
          <span class="dot"></span><span class="nav-title">任务</span><span class="nav-meta">04</span>
        </button>
        <button class="nav-item" type="button" data-section="log" data-title="运行日志" data-copy="查看每次采集、建品、上架请求的系统反馈。">
          <span class="dot"></span><span class="nav-title">日志</span><span class="nav-meta">05</span>
        </button>
      </nav>
      <div class="sidebar-footer">
        <div class="eyebrow">TARGET CHANNELS</div>
        <div class="channel-list" id="channelChecks"></div>
      </div>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <div class="eyebrow" id="workspaceEyebrow">SECTION 01</div>
          <h2 class="workspace-title" id="workspaceTitle">小红书采集</h2>
          <p class="workspace-copy" id="workspaceCopy">先采集商品来源，再决定只预览、建商品，或进入自动上架。</p>
        </div>
        <div class="topbar-actions">
          <button class="secondary" id="refreshAll" type="button">刷新数据</button>
        </div>
      </header>

      <div class="content">
        <section class="view active" id="view-import" data-view="import">
          <div class="layout-two">
            <section class="panel">
              <ol class="step-rail" id="importStepRail">
                <li class="step-item active" data-import-step="input">
                  <span class="step-index">STEP 01</span>
                  <span class="step-title">填链接</span>
                </li>
                <li class="step-item" data-import-step="preview">
                  <span class="step-index">STEP 02</span>
                  <span class="step-title">看预览</span>
                </li>
                <li class="step-item" data-import-step="rewrite">
                  <span class="step-index">STEP 03</span>
                  <span class="step-title">LLM 二创</span>
                </li>
                <li class="step-item" data-import-step="next">
                  <span class="step-index">STEP 04</span>
                  <span class="step-title">下一步</span>
                </li>
              </ol>
              <div class="panel-header">
                <div>
                  <div class="eyebrow">XIAOHONGSHU IMPORT</div>
                  <h2>1. 输入来源</h2>
                </div>
                <span class="badge warn">先预览再操作</span>
              </div>
              <form id="xiaohongshuImportForm">
                <div class="form-grid">
                  <div class="full">
                    <label for="xhsSourceUrl">小红书来源链接</label>
                    <input id="xhsSourceUrl" placeholder="https://www.xiaohongshu.com/explore/..." autocomplete="off">
                  </div>
                  <div class="full">
                    <label>账号类型</label>
                    <div class="radio-group">
                      <label class="radio-line"><input id="xhsAccountMerchant" type="radio" name="xhsAccountType" value="merchant" checked> 商家号商品</label>
                      <label class="radio-line"><input id="xhsAccountPersonal" type="radio" name="xhsAccountType" value="personal"> 个人号笔记</label>
                    </div>
                    <div class="hint">个人号笔记默认走人工确认安全模式，适合先测内容草稿和可见发布流程。</div>
                  </div>
                  <div>
                    <label for="xhsPrice">价格</label>
                    <input id="xhsPrice" type="number" min="0.01" step="0.01" value="129">
                  </div>
                  <div>
                    <label for="xhsCategory">商品分类</label>
                    <input id="xhsCategory" placeholder="可留空，优先使用平台默认分类">
                  </div>
                  <div>
                    <label for="xhsTopics">个人号话题</label>
                    <input id="xhsTopics" placeholder="新品, 测试商品">
                  </div>
                  <div>
                    <label>确认策略</label>
                    <label class="checkline"><input id="xhsConfirmRequired" type="checkbox" checked> 发布前人工确认</label>
                  </div>
                  <div class="full">
                    <label for="xhsHtmlSnapshot">HTML 快照</label>
                    <textarea id="xhsHtmlSnapshot" placeholder="可选。粘贴已授权来源快照可避免直接访问页面。"></textarea>
                  </div>
                  <div class="full">
                    <label class="checkline"><input id="xhsUseDefaults" type="checkbox" checked> 使用平台默认配置</label>
                  </div>
                </div>
                <div class="actions">
                  <button type="button" class="primary" id="scrapePreview">采集商品</button>
                </div>
              </form>
            </section>

            <section class="panel" id="previewResultPanel">
              <div class="panel-header">
                <div>
                  <div class="eyebrow">PREVIEW RESULT</div>
                  <h2>2. 预览结果</h2>
                </div>
              </div>
              <div class="empty-result" id="previewEmpty">
                <strong>还没有预览结果</strong>
                <span>先在左侧填小红书链接，然后点“采集商品”。抓到后这里会告诉你下一步做什么。</span>
              </div>
              <div class="result-grid" id="previewDetails" hidden>
                <div class="result-row">
                  <span class="result-label">标题</span>
                  <strong class="result-value" id="previewTitle">-</strong>
                </div>
                <div class="result-row">
                  <span class="result-label">描述</span>
                  <span class="result-value" id="previewDescription">-</span>
                </div>
                <div class="result-row">
                  <span class="result-label">素材</span>
                  <span class="result-value" id="previewMediaCount">0 张</span>
                </div>
                <div class="result-row">
                  <span class="result-label">来源 ID</span>
                  <span class="result-value" id="previewSourceId">-</span>
                </div>
                <div class="result-row">
                  <span class="result-label">账号</span>
                  <span class="result-value" id="previewAccountType">-</span>
                </div>
                <div class="rewrite-card" id="rewriteResultPanel" hidden>
                  <div class="result-grid">
                    <div class="result-row">
                      <span class="result-label">二创标题</span>
                      <strong class="result-value" id="rewriteTitle">-</strong>
                    </div>
                    <div class="result-row">
                      <span class="result-label">二创描述</span>
                      <span class="result-value" id="rewriteDescription">-</span>
                    </div>
                    <div class="result-row">
                      <span class="result-label">话题</span>
                      <span class="result-value" id="rewriteTopics">-</span>
                    </div>
                    <div class="result-row">
                      <span class="result-label">来源</span>
                      <span class="result-value" id="rewriteProvider">-</span>
                    </div>
                  </div>
                </div>
                <div class="next-actions">
                  <div class="eyebrow">下一步</div>
                  <button type="button" class="primary" id="rewritePreview" disabled>LLM 二创</button>
                  <button type="button" class="secondary" id="createFromPreview" disabled>用预览结果建商品</button>
                  <button type="button" class="primary" id="publishFromPreview" disabled>用二创结果自动上架</button>
                  <button type="button" class="ghost" id="editPreviewInput">返回修改链接或参数</button>
                </div>
              </div>
            </section>
          </div>
        </section>

        <section class="view" id="view-products" data-view="products">
          <div class="layout-two">
            <section class="panel">
              <div class="panel-header">
                <div>
                  <div class="eyebrow">PRODUCT MASTER</div>
                  <h2>新建商品</h2>
                </div>
              </div>
              <form id="productForm">
                <div class="form-grid">
                  <div>
                    <label for="title">商品标题</label>
                    <input id="title" required>
                  </div>
                  <div>
                    <label for="price">价格</label>
                    <input id="price" type="number" min="0.01" step="0.01" value="199" required>
                  </div>
                  <div>
                    <label for="category">商品分类</label>
                    <input id="category" placeholder="可留空，优先使用平台默认分类">
                  </div>
                  <div>
                    <label for="currency">币种</label>
                    <input id="currency" value="CNY">
                  </div>
                  <div class="full">
                    <label for="description">商品描述</label>
                    <textarea id="description"></textarea>
                  </div>
                  <div class="full">
                    <label>主图 / 素材链接</label>
                    <div class="media-grid">
                      <input id="media1" placeholder="图片 1 链接">
                      <input id="media2" placeholder="图片 2 链接">
                      <input id="media3" placeholder="图片 3 链接">
                      <input id="media4" placeholder="图片 4 链接，可选">
                    </div>
                  </div>
                </div>
                <div class="actions">
                  <button type="button" class="muted-btn" id="loadSample">加载样例</button>
                  <button type="button" class="secondary" id="createDraft">只存草稿</button>
                  <button type="button" class="primary" id="autoPublish">创建并自动上架</button>
                </div>
              </form>
            </section>
            <section class="panel">
              <div class="panel-header">
                <div>
                  <div class="eyebrow">PRODUCTS</div>
                  <h2>已创建商品</h2>
                </div>
              </div>
              <table>
                <thead>
                  <tr><th>ID</th><th>标题</th><th>价格</th><th>素材</th><th>操作</th></tr>
                </thead>
                <tbody id="productsBody"></tbody>
              </table>
            </section>
          </div>
        </section>

        <section class="view" id="view-settings" data-view="settings">
          <section class="panel">
            <div class="panel-header">
              <div>
                <div class="eyebrow">CHANNEL DEFAULTS</div>
                <h2>平台默认配置</h2>
              </div>
              <button type="button" class="primary" id="saveSettings">保存平台默认配置</button>
            </div>
            <div class="settings-grid">
              <div class="setting-block">
                <div class="setting-title"><strong>淘宝</strong><span class="badge" id="mode-taobao">加载中</span></div>
                <label for="taobao-default-category">默认分类</label><input id="taobao-default-category">
                <label for="taobao-default-currency">默认币种</label><input id="taobao-default-currency" value="CNY">
                <label for="taobao-brand">品牌</label><input id="taobao-brand">
                <label for="taobao-shipping-template-id">运费模板 ID</label><input id="taobao-shipping-template-id">
              </div>
              <div class="setting-block">
                <div class="setting-title"><strong>小红书</strong><span class="badge" id="mode-xiaohongshu">加载中</span></div>
                <label for="xiaohongshu-default-category">默认分类</label><input id="xiaohongshu-default-category">
                <label for="xiaohongshu-default-currency">默认币种</label><input id="xiaohongshu-default-currency" value="CNY">
                <label for="xiaohongshu-brand">品牌</label><input id="xiaohongshu-brand">
                <label for="xiaohongshu-merchant-category-id">商家类目 ID</label><input id="xiaohongshu-merchant-category-id">
              </div>
              <div class="setting-block">
                <div class="setting-title"><strong>抖音</strong><span class="badge" id="mode-douyin">加载中</span></div>
                <label for="douyin-default-category">默认分类</label><input id="douyin-default-category">
                <label for="douyin-default-currency">默认币种</label><input id="douyin-default-currency" value="CNY">
                <label for="douyin-brand">品牌</label><input id="douyin-brand">
                <label for="douyin-logistic-template-id">物流模板 ID</label><input id="douyin-logistic-template-id">
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <div>
                <div class="eyebrow">REAL SEND</div>
                <h2>真实发送状态</h2>
              </div>
            </div>
            <table>
              <thead>
                <tr><th>平台</th><th>模式</th><th>配置</th><th>缺失项</th></tr>
              </thead>
              <tbody id="adapterStatusBody"></tbody>
            </table>
          </section>
        </section>

        <section class="view" id="view-tasks" data-view="tasks">
          <section class="panel">
            <div class="panel-header">
              <div>
                <div class="eyebrow">TASKS</div>
                <h2>自动上架结果</h2>
              </div>
            </div>
            <table>
              <thead>
                <tr><th>ID</th><th>商品</th><th>平台</th><th>任务状态</th><th>上架状态</th></tr>
              </thead>
              <tbody id="tasksBody"></tbody>
            </table>
          </section>
        </section>

        <section class="view" id="view-log" data-view="log">
          <section class="panel">
            <div class="panel-header">
              <div>
                <div class="eyebrow">RUN LOG</div>
                <h2>运行日志</h2>
              </div>
            </div>
            <div class="log" id="log"></div>
          </section>
        </section>
      </div>
    </section>
  </main>

  <script>
    const logNode = document.getElementById("log");
    const productsBody = document.getElementById("productsBody");
    const tasksBody = document.getElementById("tasksBody");
    const channelChecks = document.getElementById("channelChecks");
    const adapterStatusBody = document.getElementById("adapterStatusBody");
    const workspaceEyebrow = document.getElementById("workspaceEyebrow");
    const workspaceTitle = document.getElementById("workspaceTitle");
    const workspaceCopy = document.getElementById("workspaceCopy");
    const previewEmpty = document.getElementById("previewEmpty");
    const previewDetails = document.getElementById("previewDetails");
    const previewTitle = document.getElementById("previewTitle");
    const previewDescription = document.getElementById("previewDescription");
    const previewMediaCount = document.getElementById("previewMediaCount");
    const previewSourceId = document.getElementById("previewSourceId");
    const previewAccountType = document.getElementById("previewAccountType");
    const rewritePreview = document.getElementById("rewritePreview");
    const rewriteResultPanel = document.getElementById("rewriteResultPanel");
    const rewriteTitle = document.getElementById("rewriteTitle");
    const rewriteDescription = document.getElementById("rewriteDescription");
    const rewriteTopics = document.getElementById("rewriteTopics");
    const rewriteProvider = document.getElementById("rewriteProvider");
    const createFromPreview = document.getElementById("createFromPreview");
    const publishFromPreview = document.getElementById("publishFromPreview");
    let lastPreviewResult = null;
    let lastRewriteResult = null;

    const channelLabelMap = { taobao: "淘宝", xiaohongshu: "小红书", douyin: "抖音" };
    const channelSpecificFieldMap = { taobao: "shipping_template_id", xiaohongshu: "merchant_category_id", douyin: "logistic_template_id" };
    const statusLabelMap = { queued: "已排队", completed: "已完成", blocked_validation: "校验拦截", failed: "失败" };
    const listingStateLabelMap = { draft: "草稿", queued: "待处理", submitted: "已提交", pending_review: "待审核", live: "已上架", rejected: "已驳回", off_shelf: "已下架" };
    const modeLabelMap = { mock: "模拟", manual: "人工", api: "API 预留", real_send: "真实发送" };

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function setActiveSection(section) {
      const navItems = [...document.querySelectorAll(".nav-item")];
      navItems.forEach((item) => item.classList.toggle("active", item.dataset.section === section));
      document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.dataset.view === section));
      const active = navItems.find((item) => item.dataset.section === section);
      if (active) {
        const index = navItems.indexOf(active) + 1;
        workspaceEyebrow.textContent = `SECTION ${String(index).padStart(2, "0")}`;
        workspaceTitle.textContent = active.dataset.title;
        workspaceCopy.textContent = active.dataset.copy;
      }
    }

    function badgeTone(status) {
      if (status === "completed" || status === "live" || status === true) return "ok";
      if (status === "queued" || status === "pending_review" || status === "mock" || status === "manual") return "warn";
      if (status === "failed" || status === "api" || status === "real_send" || status === false) return "danger";
      return "";
    }
    function badge(text, tone = "") { return `<span class="badge ${tone}">${escapeHtml(text)}</span>`; }
    function renderEmptyRow(message, colspan = 5) { return `<tr><td colspan="${colspan}" class="empty-row">${escapeHtml(message)}</td></tr>`; }

    function formatPayloadForLog(payload) {
      return JSON.stringify(payload, (key, value) => {
        if (typeof value === "string" && value.length > 520) {
          return `${value.slice(0, 520)}...（已截断 ${value.length - 520} 字符）`;
        }
        return value;
      }, 2);
    }

    async function withButtonBusy(buttonId, busyText, task) {
      const button = document.getElementById(buttonId);
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = busyText;
      try { return await task(); }
      finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    }

    function log(message, payload) {
      const time = new Date().toLocaleTimeString();
      const extra = payload ? "\\n" + formatPayloadForLog(payload) : "";
      const next = `[${time}] ${message}${extra}\\n\\n` + logNode.textContent;
      logNode.textContent = next;
    }

    function markImportStep(activeStep) {
      const steps = ["input", "preview", "rewrite", "next"];
      document.querySelectorAll("[data-import-step]").forEach((node) => {
        const index = steps.indexOf(node.dataset.importStep);
        const activeIndex = steps.indexOf(activeStep);
        node.classList.toggle("active", node.dataset.importStep === activeStep);
        node.classList.toggle("done", index >= 0 && activeIndex >= 0 && index < activeIndex);
      });
    }

    function resetRewriteResult() {
      lastRewriteResult = null;
      rewriteResultPanel.hidden = true;
      rewriteTitle.textContent = "-";
      rewriteDescription.textContent = "-";
      rewriteTopics.textContent = "-";
      rewriteProvider.textContent = "-";
      publishFromPreview.disabled = true;
      createFromPreview.textContent = "用预览结果建商品";
    }

    function renderPreviewResult(result) {
      lastPreviewResult = result;
      const draft = result?.draft || {};
      const attributes = draft.attributes || {};
      resetRewriteResult();
      previewEmpty.hidden = true;
      previewDetails.hidden = false;
      previewTitle.textContent = draft.title || "未识别标题";
      previewDescription.textContent = draft.description || "未识别描述";
      previewMediaCount.textContent = `${draft.media?.length || 0} 张`;
      previewSourceId.textContent = attributes.source_note_id || "-";
      previewAccountType.textContent = attributes.xiaohongshu_account_type === "personal" ? "个人号笔记" : "商家号商品";
      rewritePreview.disabled = false;
      createFromPreview.disabled = false;
      markImportStep("rewrite");
    }

    function renderRewriteResult(result) {
      lastRewriteResult = result;
      rewriteResultPanel.hidden = false;
      rewriteTitle.textContent = result.title || "-";
      rewriteDescription.textContent = result.description || "-";
      rewriteTopics.textContent = result.topics?.length ? result.topics.join("，") : "-";
      rewriteProvider.textContent = result.provider === "llm_bridge" ? "LLM 桥接" : "本地兜底";
      if (result.topics?.length) {
        document.getElementById("xhsTopics").value = result.topics.join(", ");
      }
      createFromPreview.textContent = "用二创结果建商品";
      publishFromPreview.disabled = false;
      markImportStep("next");
    }

    function selectedChannels() {
      return [...document.querySelectorAll('input[name="channels"]:checked')].map((node) => node.value);
    }
    function collectMedia() {
      return ["media1", "media2", "media3", "media4"]
        .map((id) => document.getElementById(id).value.trim())
        .filter(Boolean)
        .map((url) => ({ url, kind: "image" }));
    }
    function getSettingValue(channel, field) { return document.getElementById(`${channel}-${field}`).value.trim(); }
    async function fetchJson(url, options) {
      const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || JSON.stringify(data));
      return data;
    }

    function renderAdapterStatus(adapters) {
      adapterStatusBody.innerHTML = adapters.map((adapter) => {
        const missing = adapter.missing_env_vars?.length ? adapter.missing_env_vars.join(", ") : "无";
        return `
          <tr>
            <td>${escapeHtml(channelLabelMap[adapter.channel])}</td>
            <td>${badge(modeLabelMap[adapter.mode] || adapter.mode, badgeTone(adapter.mode))}</td>
            <td>${badge(adapter.configured ? "可用" : "未配置", badgeTone(adapter.configured))}</td>
            <td><span class="hint">${escapeHtml(missing)}</span></td>
          </tr>
        `;
      }).join("");
    }

    async function loadAdapters() {
      const adapters = await fetchJson("/adapters");
      channelChecks.innerHTML = adapters.map((adapter) => `
        <label><input type="checkbox" name="channels" value="${escapeHtml(adapter.channel)}" checked> ${escapeHtml(channelLabelMap[adapter.channel])}</label>
      `).join("");
      renderAdapterStatus(adapters);
      adapters.forEach((adapter) => {
        const node = document.getElementById(`mode-${adapter.channel}`);
        if (!node) return;
        node.className = `badge ${badgeTone(adapter.mode)}`;
        node.textContent = modeLabelMap[adapter.mode] || adapter.mode;
      });
    }

    function fillSettingCard(channel, setting) {
      document.getElementById(`${channel}-default-category`).value = setting.default_category || "";
      document.getElementById(`${channel}-default-currency`).value = setting.default_currency || "CNY";
      document.getElementById(`${channel}-brand`).value = setting.default_attributes?.brand || "";
      document.getElementById(`${channel}-${channelSpecificFieldMap[channel].replaceAll("_", "-")}`).value =
        setting.default_attributes?.[channelSpecificFieldMap[channel]] || "";
    }
    async function loadSettings() {
      const settings = await fetchJson("/channel-settings");
      settings.forEach((setting) => fillSettingCard(setting.channel, setting));
    }
    async function saveSettings() {
      const channels = ["taobao", "xiaohongshu", "douyin"];
      const requests = channels.map((channel) => {
        const payload = {
          default_category: getSettingValue(channel, "default-category") || null,
          default_currency: getSettingValue(channel, "default-currency") || null,
          default_attributes: {
            brand: getSettingValue(channel, "brand") || null,
            [channelSpecificFieldMap[channel]]: getSettingValue(channel, channelSpecificFieldMap[channel].replaceAll("_", "-")) || null
          }
        };
        Object.keys(payload.default_attributes).forEach((key) => {
          if (!payload.default_attributes[key]) delete payload.default_attributes[key];
        });
        return fetchJson(`/channel-settings/${channel}`, { method: "PUT", body: JSON.stringify(payload) });
      });
      const saved = await Promise.all(requests);
      log("平台默认配置已保存。", saved);
    }

    async function loadProducts() {
      const products = await fetchJson("/products");
      if (!products.length) {
        productsBody.innerHTML = renderEmptyRow("还没有商品。");
        return;
      }
      productsBody.innerHTML = products.map((product) => `
        <tr>
          <td>${product.id}</td>
          <td><strong>${escapeHtml(product.title)}</strong><div class="hint">${escapeHtml(product.category)}</div></td>
          <td>${product.price} ${escapeHtml(product.currency)}</td>
          <td>${product.media.length}</td>
          <td>
            <div class="actions">
              <button class="ghost" type="button" onclick="validateExisting(${product.id})">校验</button>
              <button class="primary" type="button" onclick="publishExisting(${product.id})">自动上架</button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    async function loadTasks() {
      const tasks = await fetchJson("/publish-tasks");
      if (!tasks.length) {
        tasksBody.innerHTML = renderEmptyRow("还没有上架任务。");
        return;
      }
      tasksBody.innerHTML = tasks.map((task) => `
        <tr>
          <td>${task.id}</td>
          <td>${task.product_id}</td>
          <td>${escapeHtml(channelLabelMap[task.channel])}</td>
          <td>${badge(statusLabelMap[task.status] || task.status, badgeTone(task.status))}</td>
          <td>${escapeHtml(listingStateLabelMap[task.listing_state] || task.listing_state)}</td>
        </tr>
      `).join("");
    }

    async function refreshAll() {
      await Promise.all([loadAdapters(), loadSettings(), loadProducts(), loadTasks()]);
      log("数据已刷新。");
    }

    function buildQuickPayload(autoPublish) {
      return {
        title: document.getElementById("title").value.trim(),
        description: document.getElementById("description").value.trim(),
        category: document.getElementById("category").value.trim() || null,
        price: Number(document.getElementById("price").value),
        currency: document.getElementById("currency").value.trim() || null,
        channels: selectedChannels(),
        media: collectMedia(),
        use_saved_defaults: true,
        auto_publish: autoPublish
      };
    }
    function buildScrapePayload(autoCreate, autoPublish) {
      const price = Number(document.getElementById("xhsPrice").value);
      const accountType = document.querySelector('input[name="xhsAccountType"]:checked')?.value || "merchant";
      const topics = document.getElementById("xhsTopics").value.split(/[，,]/).map((item) => item.trim()).filter(Boolean);
      const payload = {
        source_url: document.getElementById("xhsSourceUrl").value.trim(),
        account_type: accountType,
        html_snapshot: document.getElementById("xhsHtmlSnapshot").value.trim() || null,
        price: Number.isFinite(price) && price > 0 ? price : null,
        category: document.getElementById("xhsCategory").value.trim() || null,
        topics,
        confirm_required: document.getElementById("xhsConfirmRequired").checked,
        channels: selectedChannels(),
        auto_create_product: autoCreate,
        auto_publish: autoPublish,
        use_saved_defaults: document.getElementById("xhsUseDefaults").checked
      };
      if (lastRewriteResult) {
        payload.title_override = lastRewriteResult.title;
        payload.description_override = lastRewriteResult.description;
        if (lastRewriteResult.topics?.length) payload.topics = lastRewriteResult.topics;
      }
      return payload;
    }

    function buildRewritePayload() {
      if (!lastPreviewResult?.draft) {
        throw new Error("请先采集预览，再做二创。");
      }
      const accountType = document.querySelector('input[name="xhsAccountType"]:checked')?.value || "merchant";
      return {
        draft: lastPreviewResult.draft,
        account_type: accountType,
        style: "clean"
      };
    }

    async function quickCreate(autoPublish) {
      try {
        const payload = buildQuickPayload(autoPublish);
        const result = await fetchJson("/products/quick-create", { method: "POST", body: JSON.stringify(payload) });
        log(autoPublish ? "商品已创建并发起自动上架。" : "商品草稿已创建。", result);
        await loadProducts();
        await loadTasks();
        setActiveSection("tasks");
      } catch (error) {
        log(autoPublish ? "自动上架失败。" : "创建草稿失败。", { error: error.message });
      }
    }
    async function scrapeXiaohongshu(autoCreate, autoPublish) {
      try {
        const payload = buildScrapePayload(autoCreate, autoPublish);
        markImportStep("preview");
        log("开始采集小红书来源，请稍等。", {
          source_url: payload.source_url,
          account_type: payload.account_type,
          auto_create_product: payload.auto_create_product,
          auto_publish: payload.auto_publish
        });
        const result = await fetchJson("/xiaohongshu/scrape", { method: "POST", body: JSON.stringify(payload) });
        renderPreviewResult(result);
        if (autoCreate) {
          await loadProducts();
          await loadTasks();
        }
        log(autoPublish ? "小红书来源已采集并自动上架。" : autoCreate ? "小红书来源已采集并建商品。" : "小红书来源已采集。", result);
        if (autoCreate) setActiveSection(autoPublish ? "tasks" : "products");
      } catch (error) {
        log("小红书采集失败。", { error: error.message });
      }
    }
    async function rewriteXiaohongshu() {
      try {
        const payload = buildRewritePayload();
        log("开始 LLM 二创。", {
          title: payload.draft.title,
          account_type: payload.account_type
        });
        const result = await fetchJson("/xiaohongshu/rewrite", { method: "POST", body: JSON.stringify(payload) });
        renderRewriteResult(result);
        log("LLM 二创已完成。", result);
      } catch (error) {
        log("LLM 二创失败。", { error: error.message });
      }
    }
    async function validateExisting(productId) {
      try {
        const result = await fetchJson(`/products/${productId}/validate`, { method: "POST", body: JSON.stringify({ channels: selectedChannels() }) });
        log(`商品 ${productId} 校验完成。`, result);
        setActiveSection("log");
      } catch (error) {
        log("校验失败。", { error: error.message });
      }
    }
    async function publishExisting(productId) {
      try {
        const result = await fetchJson(`/products/${productId}/publish`, { method: "POST", body: JSON.stringify({ channels: selectedChannels(), action: "publish" }) });
        log(`商品 ${productId} 已发起自动上架。`, result);
        await loadTasks();
        setActiveSection("tasks");
      } catch (error) {
        log("自动上架失败。", { error: error.message });
      }
    }
    function loadSample() {
      document.getElementById("title").value = "多平台标准款商品";
      document.getElementById("price").value = "299";
      document.getElementById("category").value = "";
      document.getElementById("currency").value = "CNY";
      document.getElementById("description").value = "这是一条可直接替换的联调商品描述，正式上架前请改成真实卖点、规格和售后说明。";
      document.getElementById("media1").value = "https://example.com/1.png";
      document.getElementById("media2").value = "https://example.com/2.png";
      document.getElementById("media3").value = "https://example.com/3.png";
      document.getElementById("media4").value = "";
      log("样例商品已加载。");
    }

    document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => setActiveSection(item.dataset.section)));
    document.getElementById("refreshAll").addEventListener("click", () => refreshAll().catch((error) => log("刷新失败。", { error: error.message })));
    document.getElementById("saveSettings").addEventListener("click", () => saveSettings().catch((error) => log("保存平台默认配置失败。", { error: error.message })));
    document.getElementById("loadSample").addEventListener("click", loadSample);
    document.getElementById("createDraft").addEventListener("click", () => quickCreate(false));
    document.getElementById("autoPublish").addEventListener("click", () => quickCreate(true));
    document.getElementById("scrapePreview").addEventListener("click", () => withButtonBusy("scrapePreview", "采集中...", () => scrapeXiaohongshu(false, false)));
    document.getElementById("rewritePreview").addEventListener("click", () => withButtonBusy("rewritePreview", "二创中...", rewriteXiaohongshu));
    document.getElementById("createFromPreview").addEventListener("click", () => withButtonBusy("createFromPreview", "建商品中...", () => scrapeXiaohongshu(true, false)));
    document.getElementById("publishFromPreview").addEventListener("click", () => withButtonBusy("publishFromPreview", "上架中...", () => scrapeXiaohongshu(true, true)));
    document.getElementById("editPreviewInput").addEventListener("click", () => {
      resetRewriteResult();
      rewritePreview.disabled = true;
      createFromPreview.disabled = true;
      markImportStep("input");
    });

    refreshAll().catch((error) => log("页面加载失败。", { error: error.message }));
    window.validateExisting = validateExisting;
    window.publishExisting = publishExisting;
  </script>
</body>
</html>
"""
