from __future__ import annotations


def render_console() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>&#22810;&#24179;&#21488;&#33258;&#21160;&#19978;&#26550;&#24037;&#20316;&#21488;</title>
  <style>
    :root {
      --bg: #f4f2ed;
      --panel: #ffffff;
      --panel-soft: #f8f7f3;
      --ink: #181817;
      --muted: #6f6a61;
      --line: #d8d4ca;
      --line-strong: #aaa397;
      --accent: #1f6f5b;
      --accent-strong: #145341;
      --danger: #9b2f22;
      --shadow: 0 18px 48px rgba(24, 24, 23, 0.08);
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Bahnschrift", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    button, input, textarea { font: inherit; }
    button {
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      background: var(--panel);
      color: var(--ink);
      cursor: pointer;
    }
    button:hover { border-color: var(--ink); }
    button:disabled { cursor: not-allowed; opacity: 0.45; }
    input, textarea {
      width: 100%;
      min-height: 38px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      color: var(--ink);
      outline: none;
    }
    input[type="checkbox"], input[type="radio"] {
      width: 16px;
      min-height: 16px;
      height: 16px;
      margin: 0;
      accent-color: var(--accent);
      flex: 0 0 auto;
    }
    textarea { min-height: 86px; resize: vertical; }
    input:focus, textarea:focus, button:focus-visible {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(31, 111, 91, 0.14);
    }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    .app-shell {
      display: grid;
      grid-template-columns: 232px minmax(0, 1fr);
      height: 100vh;
      overflow: hidden;
    }
    .sidebar {
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 18px;
      height: 100vh;
      padding: 18px;
      border-right: 1px solid var(--line);
      background: #ece9e0;
    }
    .brand-mark {
      width: 42px;
      height: 42px;
      border: 2px solid var(--ink);
      display: grid;
      place-items: center;
      font-weight: 800;
      background: var(--accent);
      color: #fff;
    }
    .brand-kicker { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .brand-title { margin: 6px 0 0; font-size: 22px; line-height: 1.08; }
    .side-nav, .channel-list, .actions, .form-grid, .media-grid, .settings-grid, .next-actions {
      display: grid;
      gap: 10px;
    }
    .nav-item {
      display: grid;
      grid-template-columns: 28px 1fr;
      align-items: center;
      gap: 10px;
      padding: 10px;
      text-align: left;
      background: transparent;
      border-color: transparent;
    }
    .nav-item::before {
      content: attr(data-index);
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line-strong);
      border-radius: 50%;
      color: var(--muted);
      font-size: 12px;
    }
    .nav-item.active {
      background: var(--panel);
      border-color: var(--ink);
      box-shadow: var(--shadow);
      font-weight: 700;
    }
    .nav-item.active::before {
      background: var(--ink);
      color: #fff;
      border-color: var(--ink);
    }
    .channel-list {
      align-content: end;
      padding-top: 14px;
      border-top: 1px solid var(--line);
    }
    .channel-list label, .inline-check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 13px;
    }
    .workspace {
      height: 100vh;
      display: grid;
      grid-template-rows: 72px minmax(0, 1fr);
      overflow: hidden;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(244, 242, 237, 0.94);
    }
    #workspaceEyebrow { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    #workspaceTitle { margin: 4px 0 0; font-size: 24px; line-height: 1; }
    .content { min-height: 0; overflow: hidden; }
    .view { height: 100%; min-height: 0; overflow: auto; padding: 20px 24px 28px; }
    .view[hidden] { display: none !important; }
    .page-grid { display: grid; grid-template-columns: minmax(360px, 0.9fr) minmax(460px, 1.1fr); gap: 16px; align-items: start; }
    .panel, .setting-block, .rewrite-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 14px;
      box-shadow: 0 1px 0 rgba(24, 24, 23, 0.04);
    }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      font-weight: 700;
    }
    .primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    .primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    .secondary { background: var(--panel-soft); }
    .form-grid, .media-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .settings-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .full { grid-column: 1 / -1; }
    .step-rail {
      list-style: none;
      margin: 0 0 12px;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
    }
    .step-item {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 8px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
      background: var(--panel-soft);
    }
    .step-item.active { color: #fff; background: var(--ink); border-color: var(--ink); }
    .result-row {
      display: grid;
      grid-template-columns: 88px 1fr;
      gap: 12px;
      padding: 9px 0;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
    }
    .result-row > :first-child { color: var(--muted); }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      padding: 2px 9px;
      color: var(--muted);
      font-size: 12px;
    }
    .badge.pass, .check-status.pass { color: var(--accent); border-color: var(--accent); }
    .badge.fail, .check-status.fail { color: var(--danger); border-color: var(--danger); }
    .badge.skip, .check-status.skip { color: var(--muted); border-color: var(--line-strong); }
    .check-status {
      display: inline-flex;
      min-width: 54px;
      justify-content: center;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
    }
    .table-shell {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
    }
    .empty-row { text-align: center; color: var(--muted); }
    .log {
      min-height: calc(100vh - 136px);
      margin: 0;
      padding: 16px;
      border-radius: var(--radius);
      background: #151514;
      color: #f4f2ed;
      white-space: pre-wrap;
      font: 13px/1.5 "Cascadia Mono", Consolas, monospace;
    }
    .compact-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .compact-actions button { min-height: 30px; padding: 4px 8px; }
    @media (max-width: 960px) {
      .app-shell { grid-template-columns: 86px minmax(0, 1fr); }
      .brand-text, .nav-label, .channel-list { display: none; }
      .sidebar { padding: 12px; }
      .nav-item { grid-template-columns: 1fr; justify-items: center; }
      .page-grid, .settings-grid { grid-template-columns: 1fr; }
      .form-grid, .media-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="app-shell">
    <aside class="sidebar">
      <div>
        <div class="brand-mark">AL</div>
        <div class="brand-text">
          <div class="brand-kicker">AUTO LISTING / LOCAL</div>
          <h1 class="brand-title">&#33258;&#21160;&#19978;&#26550;&#24037;&#20316;&#21488;</h1>
        </div>
      </div>
      <nav class="side-nav" id="sideNav" aria-label="nav">
        <button class="nav-item active" type="button" data-index="01" data-section="import" data-title="&#23567;&#32418;&#20070;&#37319;&#38598;" data-copy="import"><span class="nav-label">&#37319;&#38598;</span></button>
        <button class="nav-item" type="button" data-index="02" data-section="products" data-title="&#21830;&#21697;&#20027;&#25968;&#25454;" data-copy="products"><span class="nav-label">&#21830;&#21697;</span></button>
        <button class="nav-item" type="button" data-index="03" data-section="settings" data-title="&#24179;&#21488;&#37197;&#32622;" data-copy="settings"><span class="nav-label">&#37197;&#32622;</span></button>
        <button class="nav-item" type="button" data-index="04" data-section="tasks" data-title="&#20219;&#21153;&#19982;&#32467;&#26524;" data-copy="tasks"><span class="nav-label">&#20219;&#21153;</span></button>
        <button class="nav-item" type="button" data-index="05" data-section="checks" data-title="&#21151;&#33021;&#24033;&#26816;" data-copy="checks"><span class="nav-label">&#24033;&#26816;</span></button>
        <button class="nav-item" type="button" data-index="06" data-section="log" data-title="&#36816;&#34892;&#26085;&#24535;" data-copy="log"><span class="nav-label">&#26085;&#24535;</span></button>
      </nav>
      <div class="channel-list" id="channelChecks"></div>
    </aside>
    <section class="workspace">
      <header class="topbar">
        <div>
          <div id="workspaceEyebrow">SECTION 01</div>
          <h2 id="workspaceTitle">&#23567;&#32418;&#20070;&#37319;&#38598;</h2>
        </div>
        <button class="secondary" id="refreshAll" type="button">&#21047;&#26032;</button>
      </header>
      <div class="content">
        <section class="view active" id="view-import" data-view="import">
          <div class="page-grid">
            <section class="panel">
              <div class="panel-title"><span>&#37319;&#38598;&#20837;&#21475;</span><span class="badge">XHS</span></div>
              <ol class="step-rail" id="importStepRail">
                <li class="step-item active" data-import-step="input">&#36755;&#20837;</li>
                <li class="step-item" data-import-step="preview">&#39044;&#35272;</li>
                <li class="step-item" data-import-step="rewrite">LLM &#20108;&#21019;</li>
                <li class="step-item" data-import-step="next">&#19979;&#19968;&#27493;</li>
              </ol>
              <form id="xiaohongshuImportForm">
                <div class="form-grid">
                  <label class="full" for="xhsSourceUrl">&#23567;&#32418;&#20070;&#38142;&#25509;<input id="xhsSourceUrl" autocomplete="off"></label>
                  <div class="full compact-actions">
                    <label class="inline-check"><input id="xhsAccountMerchant" type="radio" name="xhsAccountType" value="merchant" checked> &#21830;&#23478;&#21495;</label>
                    <label class="inline-check"><input id="xhsAccountPersonal" type="radio" name="xhsAccountType" value="personal"> &#20010;&#20154;&#21495;&#31508;&#35760;</label>
                    <label class="inline-check"><input id="xhsConfirmRequired" type="checkbox" checked> &#21457;&#24067;&#21069;&#30830;&#35748;</label>
                    <label class="inline-check"><input id="xhsUseDefaults" type="checkbox" checked> &#20351;&#29992;&#40664;&#35748;&#37197;&#32622;</label>
                  </div>
                  <label for="xhsPrice">&#20215;&#26684;<input id="xhsPrice" type="number" value="129"></label>
                  <label for="xhsCategory">&#20998;&#31867;<input id="xhsCategory"></label>
                  <label class="full" for="xhsTopics">&#35805;&#39064;<input id="xhsTopics"></label>
                  <label class="full" for="xhsHtmlSnapshot">HTML<textarea id="xhsHtmlSnapshot" spellcheck="false"></textarea></label>
                </div>
                <div class="actions" style="margin-top:12px;">
                  <button type="button" class="primary" id="scrapePreview">&#37319;&#38598;&#39044;&#35272;</button>
                  <button type="button" class="secondary" id="browserExtractPreview">&#27983;&#35272;&#22120;&#25552;&#21462;</button>
                  <button type="button" class="secondary" id="rewritePreview" disabled>&#20108;&#21019;</button>
                  <button type="button" id="editPreviewInput">&#37325;&#32622;</button>
                </div>
              </form>
            </section>
            <section class="panel" id="previewResultPanel">
              <div class="panel-title"><span>&#32467;&#26524;</span><span class="badge" id="previewState">empty</span></div>
              <div id="previewEmpty" class="empty-row">&#31561;&#24453;&#37319;&#38598;</div>
              <div id="previewDetails" hidden>
                <div class="result-row"><div>&#26631;&#39064;</div><div id="previewTitle">-</div></div>
                <div class="result-row"><div>&#25551;&#36848;</div><div id="previewDescription">-</div></div>
                <div class="result-row"><div>&#32032;&#26448;</div><div id="previewMediaCount">-</div></div>
                <div class="result-row"><div>&#26469;&#28304;</div><div id="previewSourceId">-</div></div>
                <div class="result-row"><div>&#36134;&#21495;</div><div id="previewAccountType">-</div></div>
              </div>
              <div class="rewrite-card" id="rewriteResultPanel" hidden style="margin-top:12px;">
                <div class="result-row"><div>&#26631;&#39064;</div><div id="rewriteTitle">-</div></div>
                <div class="result-row"><div>&#25551;&#36848;</div><div id="rewriteDescription">-</div></div>
                <div class="result-row"><div>&#35805;&#39064;</div><div id="rewriteTopics">-</div></div>
                <div class="result-row"><div>&#27169;&#22411;</div><div id="rewriteProvider">-</div></div>
              </div>
              <div class="next-actions" style="margin-top:12px;">
                <button type="button" class="secondary" id="createFromPreview" disabled>&#29992;&#39044;&#35272;&#32467;&#26524;&#24314;&#21830;&#21697;</button>
                <button type="button" class="primary" id="publishFromPreview" disabled>&#29992;&#20108;&#21019;&#32467;&#26524;&#33258;&#21160;&#19978;&#26550;</button>
              </div>
            </section>
          </div>
        </section>
        <section class="view" id="view-products" data-view="products" hidden>
          <div class="page-grid">
            <section class="panel">
              <div class="panel-title"><span>&#26032;&#24314;&#21830;&#21697;</span><span class="badge">MASTER</span></div>
              <form id="productForm">
                <div class="form-grid">
                  <label class="full" for="title">&#21830;&#21697;&#26631;&#39064;<input id="title"></label>
                  <label class="full" for="description">&#21830;&#21697;&#25551;&#36848;<textarea id="description"></textarea></label>
                  <label for="price">&#20215;&#26684;<input id="price" type="number" value="299"></label>
                  <label for="currency">&#24065;&#31181;<input id="currency" value="CNY"></label>
                  <label class="full" for="category">&#20998;&#31867;<input id="category"></label>
                  <label class="inline-check full"><input id="productUseDefaults" type="checkbox" checked> &#20351;&#29992;&#24179;&#21488;&#40664;&#35748;&#37197;&#32622;</label>
                </div>
                <div class="media-grid" style="margin-top:10px;">
                  <label for="media1">&#22270; 1<input id="media1"></label>
                  <label for="media2">&#22270; 2<input id="media2"></label>
                  <label for="media3">&#22270; 3<input id="media3"></label>
                  <label for="media4">&#22270; 4<input id="media4"></label>
                </div>
                <div class="actions" style="margin-top:12px;">
                  <button type="button" id="loadSample">&#26679;&#20363;</button>
                  <button type="button" id="createDraft">&#23384;&#33609;&#31295;</button>
                  <button type="button" id="autoPublish" class="primary">&#21019;&#24314;&#24182;&#33258;&#21160;&#19978;&#26550;</button>
                </div>
              </form>
            </section>
            <section class="panel">
              <div class="panel-title"><span>&#21830;&#21697;&#21015;&#34920;</span><span class="badge" id="productCount">0</span></div>
              <div class="table-shell">
                <table>
                  <thead><tr><th>ID</th><th>&#26631;&#39064;</th><th>&#20215;&#26684;</th><th>&#32032;&#26448;</th><th>&#25805;&#20316;</th></tr></thead>
                  <tbody id="productsBody"></tbody>
                </table>
              </div>
            </section>
          </div>
        </section>
        <section class="view" id="view-settings" data-view="settings" hidden>
          <section class="panel">
            <div class="panel-title"><span>&#24179;&#21488;&#40664;&#35748;&#37197;&#32622;</span><button id="saveSettings" type="button" class="primary">&#20445;&#23384;</button></div>
            <div class="settings-grid">
              <div class="setting-block">
                <div class="panel-title"><span>&#28120;&#23453;</span><span class="badge" id="mode-taobao">-</span></div>
                <label>&#20998;&#31867;<input id="taobao-default-category"></label>
                <label>&#24065;&#31181;<input id="taobao-default-currency"></label>
                <label>&#21697;&#29260;<input id="taobao-brand"></label>
                <label>&#36816;&#36153;&#27169;&#26495;<input id="taobao-shipping-template-id"></label>
              </div>
              <div class="setting-block">
                <div class="panel-title"><span>&#23567;&#32418;&#20070;</span><span class="badge" id="mode-xiaohongshu">-</span></div>
                <label>&#20998;&#31867;<input id="xiaohongshu-default-category"></label>
                <label>&#24065;&#31181;<input id="xiaohongshu-default-currency"></label>
                <label>&#21697;&#29260;<input id="xiaohongshu-brand"></label>
                <label>&#21830;&#23478;&#31867;&#30446;<input id="xiaohongshu-merchant-category-id"></label>
              </div>
              <div class="setting-block">
                <div class="panel-title"><span>&#25238;&#38899;</span><span class="badge" id="mode-douyin">-</span></div>
                <label>&#20998;&#31867;<input id="douyin-default-category"></label>
                <label>&#24065;&#31181;<input id="douyin-default-currency"></label>
                <label>&#21697;&#29260;<input id="douyin-brand"></label>
                <label>&#29289;&#27969;&#27169;&#26495;<input id="douyin-logistic-template-id"></label>
              </div>
            </div>
          </section>
          <section class="panel" style="margin-top:16px;">
            <div class="panel-title"><span>&#30495;&#23454;&#21457;&#36865;&#29366;&#24577;</span><span class="badge">ADAPTER</span></div>
            <div class="table-shell">
              <table>
                <thead><tr><th>&#24179;&#21488;</th><th>&#27169;&#24335;</th><th>&#21487;&#29992;</th><th>&#32570;&#22833;</th></tr></thead>
                <tbody id="adapterStatusBody"></tbody>
              </table>
            </div>
          </section>
        </section>
        <section class="view" id="view-tasks" data-view="tasks" hidden>
          <section class="panel">
            <div class="panel-title"><span>&#33258;&#21160;&#19978;&#26550;&#32467;&#26524;</span><span class="badge" id="taskCount">0</span></div>
            <div class="table-shell">
              <table>
                <thead><tr><th>ID</th><th>&#21830;&#21697;</th><th>&#24179;&#21488;</th><th>&#20219;&#21153;</th><th>&#19978;&#26550;</th></tr></thead>
                <tbody id="tasksBody"></tbody>
              </table>
            </div>
          </section>
        </section>
        <section class="view" id="view-checks" data-view="checks" hidden>
          <section class="panel">
            <div class="panel-title"><span>&#21151;&#33021;&#24033;&#26816;</span><span class="badge" id="checkSummary">ready</span></div>
            <div class="compact-actions" style="margin-bottom:12px;">
              <button type="button" class="primary" id="runFunctionCheck">&#24320;&#22987;&#24033;&#26816;</button>
              <button type="button" class="secondary" id="clearFunctionCheck">&#28165;&#31354;&#32467;&#26524;</button>
            </div>
            <div class="table-shell">
              <table>
                <thead><tr><th>&#21151;&#33021;</th><th>&#29366;&#24577;</th><th>&#32467;&#26524;</th></tr></thead>
                <tbody id="checkResultsBody"></tbody>
              </table>
            </div>
          </section>
        </section>
        <section class="view" id="view-log" data-view="log" hidden>
          <pre id="log" class="log"></pre>
        </section>
      </div>
    </section>
  </main>
  <script>
    const channelLabelMap = { taobao: "淘宝", xiaohongshu: "小红书", douyin: "抖音" };
    const channelSpecificFieldMap = { taobao: "shipping_template_id", xiaohongshu: "merchant_category_id", douyin: "logistic_template_id" };
    const statusLabelMap = { queued: "排队", completed: "完成", blocked_validation: "拦截", failed: "失败" };
    const listingStateLabelMap = { draft: "草稿", queued: "排队", submitted: "已提交", pending_review: "待审核", live: "已上架", rejected: "拒绝", off_shelf: "下架" };
    const modeLabelMap = { mock: "模拟", manual: "人工", api: "API", real_send: "真实" };
    let lastPreviewResult = null;
    let lastRewriteResult = null;
    function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
    function renderEmptyRow(message, colspan = 5) { return `<tr><td colspan="${colspan}" class="empty-row">${escapeHtml(message)}</td></tr>`; }
    function formatPayloadForLog(payload) { return JSON.stringify(payload, null, 2); }
    async function withButtonBusy(buttonId, busyText, task) { const button = document.getElementById(buttonId); const original = button.textContent; button.disabled = true; button.textContent = busyText; try { return await task(); } finally { button.disabled = false; button.textContent = original; } }
    function log(message, payload) { document.getElementById("log").textContent = `[${new Date().toLocaleTimeString()}] ${message}` + (payload ? "\\n" + formatPayloadForLog(payload) : ""); }
    function updateWorkspaceHeader(section) { const active = document.querySelector(`.nav-item[data-section="${section}"]`); if (!active) return; document.getElementById("workspaceEyebrow").textContent = `SECTION ${active.dataset.index || "01"}`; document.getElementById("workspaceTitle").textContent = active.dataset.title || active.textContent || ""; }
    function setActiveSection(section) {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.section === section));
      document.querySelectorAll(".view").forEach((view) => { const active = view.dataset.view === section; view.classList.toggle("active", active); view.hidden = !active; });
      updateWorkspaceHeader(section);
      if (section === "import") { markImportStep(lastRewriteResult ? "rewrite" : lastPreviewResult ? "preview" : "input"); }
    }
    function markImportStep(activeStep) { document.querySelectorAll("[data-import-step]").forEach((node) => node.classList.toggle("active", node.dataset.importStep === activeStep)); }
    function resetRewriteResult() { lastRewriteResult = null; document.getElementById("rewriteResultPanel").hidden = true; document.getElementById("publishFromPreview").disabled = true; document.getElementById("previewState").textContent = lastPreviewResult ? "preview" : "empty"; markImportStep(lastPreviewResult ? "preview" : "input"); }
    function renderPreviewResult(result) { lastPreviewResult = result; document.getElementById("previewState").textContent = "preview"; document.getElementById("previewEmpty").hidden = true; document.getElementById("previewDetails").hidden = false; document.getElementById("previewTitle").textContent = result?.draft?.title || "-"; document.getElementById("previewDescription").textContent = result?.draft?.description || "-"; document.getElementById("previewMediaCount").textContent = String(result?.draft?.media?.length || 0); document.getElementById("previewSourceId").textContent = result?.draft?.attributes?.source_note_id || "-"; document.getElementById("previewAccountType").textContent = result?.draft?.attributes?.xiaohongshu_account_type || "merchant"; document.getElementById("rewritePreview").disabled = false; document.getElementById("createFromPreview").disabled = false; markImportStep("preview"); }
    function renderRewriteResult(result) { lastRewriteResult = result; document.getElementById("previewState").textContent = "rewrite"; document.getElementById("rewriteResultPanel").hidden = false; document.getElementById("rewriteTitle").textContent = result.title || "-"; document.getElementById("rewriteDescription").textContent = result.description || "-"; document.getElementById("rewriteTopics").textContent = result.topics?.join(", ") || "-"; document.getElementById("rewriteProvider").textContent = result.provider || "-"; document.getElementById("publishFromPreview").disabled = false; markImportStep("rewrite"); }
    function selectedChannels() { return [...document.querySelectorAll("input[name=channels]:checked")].map((node) => node.value); }
    function collectMedia() { return ["media1", "media2", "media3", "media4"].map((id) => document.getElementById(id).value.trim()).filter(Boolean).map((url) => ({ url, kind: "image" })); }
    function getSettingValue(channel, field) { return document.getElementById(`${channel}-${field}`).value.trim(); }
    function buildSettingPayload(channel) { const specificField = channelSpecificFieldMap[channel]; const domField = specificField.replaceAll("_", "-"); return { default_category: getSettingValue(channel, "default-category") || null, default_currency: getSettingValue(channel, "default-currency") || null, default_attributes: { ...(getSettingValue(channel, "brand") ? { brand: getSettingValue(channel, "brand") } : {}), ...(getSettingValue(channel, domField) ? { [specificField]: getSettingValue(channel, domField) } : {}) } }; }
    async function fetchJson(url, options) { const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options }); const data = await response.json(); if (!response.ok) throw new Error(data.detail || JSON.stringify(data)); return data; }
    function fillSettingCard(channel, setting) { document.getElementById(`${channel}-default-category`).value = setting.default_category || ""; document.getElementById(`${channel}-default-currency`).value = setting.default_currency || "CNY"; document.getElementById(`${channel}-brand`).value = setting.default_attributes?.brand || ""; document.getElementById(`${channel}-${channelSpecificFieldMap[channel].replaceAll("_", "-")}`).value = setting.default_attributes?.[channelSpecificFieldMap[channel]] || ""; }
    async function loadAdapters() { const adapters = await fetchJson("/adapters"); document.getElementById("channelChecks").innerHTML = adapters.map((adapter) => `<label><input type="checkbox" name="channels" value="${adapter.channel}" checked> ${channelLabelMap[adapter.channel] || adapter.channel}</label>`).join(""); document.getElementById("adapterStatusBody").innerHTML = adapters.map((adapter) => `<tr><td>${channelLabelMap[adapter.channel] || adapter.channel}</td><td>${modeLabelMap[adapter.mode] || adapter.mode}</td><td>${adapter.configured ? "可用" : "缺配置"}</td><td>${(adapter.missing_env_vars || []).join(", ") || "无"}</td></tr>`).join(""); adapters.forEach((adapter) => { const node = document.getElementById(`mode-${adapter.channel}`); if (node) node.textContent = modeLabelMap[adapter.mode] || adapter.mode; }); }
    async function loadSettings() { (await fetchJson("/channel-settings")).forEach((setting) => fillSettingCard(setting.channel, setting)); }
    async function loadProducts() { const products = await fetchJson("/products"); document.getElementById("productCount").textContent = String(products.length); document.getElementById("productsBody").innerHTML = products.length ? products.map((product) => `<tr><td>${product.id}</td><td><strong>${escapeHtml(product.title)}</strong></td><td>${product.price} ${product.currency}</td><td>${product.media.length}</td><td><div class="compact-actions"><button onclick="validateExisting(${product.id})">校验</button><button onclick="publishExisting(${product.id})">上架</button></div></td></tr>`).join("") : renderEmptyRow("暂无商品"); }
    async function loadTasks() { const tasks = await fetchJson("/publish-tasks"); document.getElementById("taskCount").textContent = String(tasks.length); document.getElementById("tasksBody").innerHTML = tasks.length ? tasks.map((task) => `<tr><td>${task.id}</td><td>${task.product_id}</td><td>${channelLabelMap[task.channel] || task.channel}</td><td>${statusLabelMap[task.status] || task.status}</td><td>${listingStateLabelMap[task.listing_state] || task.listing_state}</td></tr>`).join("") : renderEmptyRow("暂无任务"); }
    async function saveSettings() { const channels = Object.keys(channelSpecificFieldMap); const results = await Promise.all(channels.map((channel) => fetchJson(`/channel-settings/${channel}`, { method: "PUT", body: JSON.stringify(buildSettingPayload(channel)) }))); log("配置已保存", { settings: results }); await loadSettings(); await loadAdapters(); }
    async function refreshAll() { await Promise.all([loadAdapters(), loadSettings(), loadProducts(), loadTasks()]); }
    function buildQuickPayload(autoPublish) { return { title: document.getElementById("title").value.trim(), description: document.getElementById("description").value.trim(), category: document.getElementById("category").value.trim() || null, price: Number(document.getElementById("price").value), currency: document.getElementById("currency").value.trim() || null, channels: selectedChannels(), media: collectMedia(), use_saved_defaults: document.getElementById("productUseDefaults").checked, auto_publish: autoPublish }; }
    function buildScrapePayload(autoCreate, autoPublish) { return { source_url: document.getElementById("xhsSourceUrl").value.trim(), account_type: document.querySelector("input[name=xhsAccountType]:checked")?.value || "merchant", html_snapshot: document.getElementById("xhsHtmlSnapshot").value.trim() || null, price: Number(document.getElementById("xhsPrice").value) || null, category: document.getElementById("xhsCategory").value.trim() || null, topics: document.getElementById("xhsTopics").value.split(/[,\\n]/).map((item) => item.trim()).filter(Boolean), confirm_required: document.getElementById("xhsConfirmRequired").checked, channels: selectedChannels(), auto_create_product: autoCreate, auto_publish: autoPublish, use_saved_defaults: document.getElementById("xhsUseDefaults").checked, title_override: lastRewriteResult?.title, description_override: lastRewriteResult?.description }; }
    function buildBrowserExtractPayload() { const sourceUrl = document.getElementById("xhsSourceUrl").value.trim(); return { source_url: sourceUrl, final_url: sourceUrl, html: document.getElementById("xhsHtmlSnapshot").value.trim(), account_type: document.querySelector("input[name=xhsAccountType]:checked")?.value || "merchant", price: Number(document.getElementById("xhsPrice").value) || null, category: document.getElementById("xhsCategory").value.trim() || null }; }
    function buildRewritePayload() { return { draft: lastPreviewResult.draft, account_type: document.querySelector("input[name=xhsAccountType]:checked")?.value || "merchant", style: "clean" }; }
    function buildCheckProductPayload() {
      return {
        title: `功能巡检商品 ${new Date().toLocaleTimeString()}`,
        description: "这是一条用于功能巡检的标准商品描述，覆盖建品、校验和模拟上架流程。",
        category: "software",
        price: 199,
        currency: "CNY",
        attributes: {
          brand: "SmokeTest",
          shipping_template_id: "st_smoke",
          merchant_category_id: "mc_smoke",
          logistic_template_id: "lt_smoke"
        },
        media: [
          { url: "https://example.com/check-1.png", kind: "image", width: 900, height: 900 },
          { url: "https://example.com/check-2.png", kind: "image", width: 900, height: 900 },
          { url: "https://example.com/check-3.png", kind: "image", width: 900, height: 900 }
        ]
      };
    }
    function renderCheckResults(results) {
      const body = document.getElementById("checkResultsBody");
      body.innerHTML = results.length ? results.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td><span class="check-status ${item.status}">${item.status === "pass" ? "通过" : item.status === "skip" ? "跳过" : "失败"}</span></td><td>${escapeHtml(item.detail || "")}</td></tr>`).join("") : renderEmptyRow("暂无巡检结果", 3);
      const passed = results.filter((item) => item.status === "pass").length;
      const failed = results.filter((item) => item.status === "fail").length;
      const skipped = results.filter((item) => item.status === "skip").length;
      const summary = document.getElementById("checkSummary");
      summary.textContent = results.length ? `${passed}/${results.length} 通过` : "ready";
      summary.className = `badge ${failed ? "fail" : skipped ? "skip" : results.length ? "pass" : ""}`.trim();
    }
    async function runCheckStep(results, name, action) {
      const item = { name, status: "skip", detail: "执行中" };
      results.push(item);
      renderCheckResults(results);
      try {
        const detail = await action();
        if (detail?.skip) {
          item.status = "skip";
          item.detail = detail.message || "已跳过";
        } else {
          item.status = "pass";
          item.detail = detail?.message || "正常";
        }
      } catch (error) {
        item.status = "fail";
        item.detail = error.message;
      }
      renderCheckResults(results);
      return item;
    }
    async function runFunctionCheck() {
      const results = [];
      let adapters = [];
      let scrapeResult = null;
      let rewriteResult = null;
      let product = null;
      let safeChannels = [];
      await runCheckStep(results, "服务连通", async () => {
        const health = await fetchJson("/health");
        if (health.status !== "ok") throw new Error("health 状态异常");
        return { message: "API 正常" };
      });
      await runCheckStep(results, "平台适配器", async () => {
        adapters = await fetchJson("/adapters");
        if (!adapters.length) throw new Error("未发现平台适配器");
        safeChannels = adapters.filter((adapter) => ["mock", "manual"].includes(adapter.mode)).map((adapter) => adapter.channel);
        return { message: `${adapters.length} 个适配器，${safeChannels.length} 个安全可发` };
      });
      await runCheckStep(results, "配置读取", async () => {
        const settings = await fetchJson("/channel-settings");
        if (settings.length !== 3) throw new Error("平台配置数量异常");
        return { message: "配置可读取" };
      });
      await runCheckStep(results, "列表读取", async () => {
        const products = await fetchJson("/products");
        const tasks = await fetchJson("/publish-tasks");
        return { message: `${products.length} 个商品，${tasks.length} 个任务` };
      });
      await runCheckStep(results, "小红书采集", async () => {
        scrapeResult = await fetchJson("/xiaohongshu/scrape", {
          method: "POST",
          body: JSON.stringify({
            source_url: "https://www.xiaohongshu.com/explore/function-check-note",
            html_snapshot: '<html><head><meta property="og:title" content="巡检采集商品"><meta name="description" content="用于功能巡检的采集内容，验证小红书抓取到建品前的数据链路。"><meta property="og:image" content="https://example.com/check-xhs.png"></head></html>',
            auto_create_product: false,
            auto_publish: false
          })
        });
        if (!scrapeResult?.draft?.title) throw new Error("采集结果缺少标题");
        return { message: scrapeResult.draft.title };
      });
      await runCheckStep(results, "LLM 二创", async () => {
        rewriteResult = await fetchJson("/xiaohongshu/rewrite", {
          method: "POST",
          body: JSON.stringify({ draft: scrapeResult.draft, account_type: "merchant", style: "clean" })
        });
        if (!rewriteResult?.title) throw new Error("二创结果缺少标题");
        return { message: rewriteResult.provider || "rewrite ok" };
      });
      await runCheckStep(results, "商品创建", async () => {
        product = await fetchJson("/products", { method: "POST", body: JSON.stringify(buildCheckProductPayload()) });
        if (!product?.id) throw new Error("创建商品未返回 ID");
        return { message: `商品 #${product.id}` };
      });
      await runCheckStep(results, "上架校验", async () => {
        if (!product?.id) throw new Error("缺少巡检商品");
        const validation = await fetchJson(`/products/${product.id}/validate`, { method: "POST", body: JSON.stringify({ channels: ["taobao", "xiaohongshu", "douyin"] }) });
        if (validation.blocked_channels.length) throw new Error(`被拦截: ${validation.blocked_channels.join(", ")}`);
        return { message: `${validation.publishable_channels.length} 个平台可上架` };
      });
      await runCheckStep(results, "安全上架", async () => {
        if (!product?.id) throw new Error("缺少巡检商品");
        if (!safeChannels.length) return { skip: true, message: "当前为真实/API 模式，已避免外部发送" };
        const tasks = await fetchJson(`/products/${product.id}/publish`, { method: "POST", body: JSON.stringify({ channels: safeChannels, action: "publish" }) });
        const blocked = tasks.filter((task) => ["failed", "blocked_validation"].includes(task.status));
        if (blocked.length) throw new Error(`${blocked.length} 个任务失败或被拦截`);
        return { message: `${tasks.length} 个上架任务已生成` };
      });
      await runCheckStep(results, "界面刷新", async () => {
        await refreshAll();
        return { message: "商品、任务、配置已刷新" };
      });
      log("功能巡检完成", { results });
    }
    async function quickCreate(autoPublish) { const result = await fetchJson("/products/quick-create", { method: "POST", body: JSON.stringify(buildQuickPayload(autoPublish)) }); log(autoPublish ? "商品已创建并发起自动上架" : "商品草稿已创建", result); await loadProducts(); await loadTasks(); if (autoPublish) setActiveSection("tasks"); }
    async function scrapeXiaohongshu(autoCreate, autoPublish) { const result = await fetchJson("/xiaohongshu/scrape", { method: "POST", body: JSON.stringify(buildScrapePayload(autoCreate, autoPublish)) }); renderPreviewResult(result); if (autoCreate && autoPublish) { markImportStep("next"); setActiveSection("tasks"); } await loadProducts(); await loadTasks(); log("采集完成", result); }
    async function browserExtractXiaohongshu() { const result = await fetchJson("/xiaohongshu/browser/extract", { method: "POST", body: JSON.stringify(buildBrowserExtractPayload()) }); renderPreviewResult(result); log("浏览器提取完成", result); }
    async function rewriteXiaohongshu() { const result = await fetchJson("/xiaohongshu/rewrite", { method: "POST", body: JSON.stringify(buildRewritePayload()) }); renderRewriteResult(result); log("二创完成", result); }
    async function validateExisting(productId) { const result = await fetchJson(`/products/${productId}/validate`, { method: "POST", body: JSON.stringify({ channels: selectedChannels() }) }); log("校验完成", result); setActiveSection("log"); }
    async function publishExisting(productId) { const result = await fetchJson(`/products/${productId}/publish`, { method: "POST", body: JSON.stringify({ channels: selectedChannels(), action: "publish" }) }); log("上架任务已发起", result); await loadTasks(); setActiveSection("tasks"); }
    function loadSample() { document.getElementById("title").value = "多平台标准款商品"; document.getElementById("description").value = "标准商品描述，正式上架前替换为真实卖点、规格和售后说明。"; document.getElementById("category").value = "software"; document.getElementById("price").value = "299"; document.getElementById("currency").value = "CNY"; document.getElementById("media1").value = "https://example.com/1.png"; document.getElementById("media2").value = "https://example.com/2.png"; document.getElementById("media3").value = "https://example.com/3.png"; }
    document.querySelectorAll(".nav-item").forEach((item) => item.addEventListener("click", () => setActiveSection(item.dataset.section)));
    document.getElementById("refreshAll").addEventListener("click", () => withButtonBusy("refreshAll", "刷新中", refreshAll).catch((error) => log("刷新失败", { error: error.message })));
    document.getElementById("saveSettings").addEventListener("click", () => withButtonBusy("saveSettings", "保存中", saveSettings).catch((error) => log("save", { error: error.message })));
    document.getElementById("loadSample").addEventListener("click", loadSample);
    document.getElementById("createDraft").addEventListener("click", () => withButtonBusy("createDraft", "\u521b\u5efa\u4e2d", () => quickCreate(false)).catch((error) => log("draft", { error: error.message })));
    document.getElementById("autoPublish").addEventListener("click", () => withButtonBusy("autoPublish", "\u4e0a\u67b6\u4e2d", () => quickCreate(true)).catch((error) => log("auto", { error: error.message })));
    document.getElementById("scrapePreview").addEventListener("click", () => withButtonBusy("scrapePreview", "采集中", () => scrapeXiaohongshu(false, false)).catch((error) => log("scrape", { error: error.message })));
    document.getElementById("browserExtractPreview").addEventListener("click", () => withButtonBusy("browserExtractPreview", "提取中", browserExtractXiaohongshu).catch((error) => log("browser_extract", { error: error.message })));
    document.getElementById("rewritePreview").addEventListener("click", () => withButtonBusy("rewritePreview", "二创中", rewriteXiaohongshu).catch((error) => log("rewrite", { error: error.message })));
    document.getElementById("createFromPreview").addEventListener("click", () => withButtonBusy("createFromPreview", "创建中", () => scrapeXiaohongshu(true, false)).catch((error) => log("create_from_preview", { error: error.message })));
    document.getElementById("publishFromPreview").addEventListener("click", () => withButtonBusy("publishFromPreview", "上架中", () => scrapeXiaohongshu(true, true)).catch((error) => log("publish_from_preview", { error: error.message })));
    document.getElementById("editPreviewInput").addEventListener("click", resetRewriteResult);
    document.getElementById("runFunctionCheck").addEventListener("click", () => withButtonBusy("runFunctionCheck", "巡检中", runFunctionCheck).catch((error) => log("check", { error: error.message })));
    document.getElementById("clearFunctionCheck").addEventListener("click", () => { document.getElementById("checkSummary").textContent = "ready"; document.getElementById("checkSummary").className = "badge"; renderCheckResults([]); });
    renderCheckResults([]);
    refreshAll().catch((error) => log("load", { error: error.message }));
    window.validateExisting = validateExisting;
    window.publishExisting = publishExisting;
    window.runFunctionCheck = runFunctionCheck;
    window.lastRewriteResult = lastRewriteResult;
    window.formatPayloadForLog = formatPayloadForLog;
  </script>
</body>
</html>
"""
