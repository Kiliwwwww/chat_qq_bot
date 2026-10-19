(() => {
  "use strict";

  const state = {
    session: null,
    currentTab: "overview",
    overview: null,
    checkTargets: [],
    checkResults: [],
    checkRunning: false,
    checkCheckedAt: "",
    services: null,
    editingService: null,
    business: null,
    logSource: "logs",
    logFiles: [],
    selectedLog: "",
    tasks: null,
    taskTimer: null,
    toastTimer: null,
  };

  const $ = (selector, root = document) => root.querySelector(selector);

  const CATEGORY_LABELS = {
    ai: "AI",
    search: "搜索",
    knowledge: "知识库",
    tts: "语音",
    redis: "Redis",
  };

  const TAB_META = {
    overview: {
      title: "运行概览",
      subtitle: "机器人、系统与外部服务状态",
      load: loadOverview,
    },
    checks: {
      title: "API Key 体检",
      subtitle: "检测当前配置的密钥与服务连通性",
      load: loadChecks,
    },
    services: {
      title: "AI 服务",
      subtitle: "管理数据库中的多个 AI 服务配置",
      load: loadServices,
    },
    business: {
      title: "业务数据",
      subtitle: "白名单、欢迎语、广告词、知识库群与提示词",
      load: loadBusiness,
    },
    logs: {
      title: "日志与记录",
      subtitle: "查看运行日志和群聊记录",
      load: loadLogsTab,
    },
    tasks: {
      title: "任务与表情包",
      subtitle: "定时任务、手动操作与表情包库统计",
      load: loadTasks,
    },
    config: {
      title: "配置与备份",
      subtitle: "只读配置速览与数据库备份",
      load: loadConfig,
    },
  };

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (ch) => {
      switch (ch) {
        case "&": return "&amp;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        case '"': return "&quot;";
        case "'": return "&#39;";
        default: return ch;
      }
    });
  }

  function fmtBytes(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let size = value / 1024;
    let index = 0;
    while (size >= 1024 && index < units.length - 1) {
      size /= 1024;
      index += 1;
    }
    return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[index]}`;
  }

  function fmtDuration(seconds) {
    let value = Math.max(0, Math.floor(Number(seconds) || 0));
    const days = Math.floor(value / 86400);
    value %= 86400;
    const hours = Math.floor(value / 3600);
    value %= 3600;
    const minutes = Math.floor(value / 60);
    const secs = value % 60;
    const parts = [];
    if (days) parts.push(`${days} 天`);
    if (hours) parts.push(`${hours} 小时`);
    if (minutes) parts.push(`${minutes} 分`);
    if (!days && !hours) parts.push(`${secs} 秒`);
    return parts.join(" ");
  }

  function fmtDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("zh-CN", { hour12: false });
  }

  function statusBadge(status) {
    const labels = {
      ok: "可用",
      fail: "失败",
      skipped: "跳过",
      idle: "未检测",
      running: "执行中",
      success: "成功",
      error: "失败",
    };
    return `<span class="badge ${esc(status)}">${esc(labels[status] || status)}</span>`;
  }

  function taskStatusBadge(status) {
    if (status === "idle") return '<span class="badge idle">待执行</span>';
    return statusBadge(status);
  }

  function card(label, value, sub = "") {
    const text = String(value == null ? "-" : value);
    return `
      <div class="card">
        <div class="card-label">${esc(label)}</div>
        <div class="card-value ${text.length > 12 ? "small" : ""}">${esc(text)}</div>
        ${sub ? `<div class="card-sub">${esc(sub)}</div>` : ""}
      </div>`;
  }

  function renderKV(container, rows) {
    if (!rows.length) {
      container.innerHTML = '<p class="empty">暂无数据</p>';
      return;
    }
    container.innerHTML = rows
      .map(
        (row) => `
        <div class="kv-row">
          <span class="kv-label">${esc(row[0])}</span>
          <span class="kv-value ${row[2] ? "mono" : ""}">${esc(row[1])}</span>
        </div>`
      )
      .join("");
  }

  async function api(path, options = {}) {
    const headers = Object.assign({ "X-Admin-Request": "1" }, options.headers || {});
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(path, Object.assign({ credentials: "same-origin" }, options, { headers }));
    const contentType = response.headers.get("content-type") || "";
    let payload = null;
    if (contentType.includes("application/json")) {
      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }
    }
    if (response.status === 401) {
      showLogin();
      throw new Error("请先登录");
    }
    if (!response.ok) {
      throw new Error((payload && payload.detail) || `请求失败 (${response.status})`);
    }
    return payload;
  }

  function toast(message, type = "info") {
    const element = $("#toast");
    element.textContent = message;
    element.className = `toast ${type}`;
    element.classList.remove("hidden");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => element.classList.add("hidden"), 3200);
  }

  function run(promise) {
    Promise.resolve(promise).catch((error) => {
      if (error && error.message !== "请先登录") {
        toast(error.message || String(error), "error");
      }
    });
  }

  function setConn(ok, text) {
    const element = $("#connState");
    element.classList.toggle("ok", ok);
    element.classList.toggle("bad", !ok);
    const label = element.querySelector("span:last-child");
    if (label) label.textContent = text;
  }

  async function fetchSession() {
    const response = await fetch("/admin/api/session", { credentials: "same-origin" });
    if (!response.ok) throw new Error(`读取登录状态失败 (${response.status})`);
    return response.json();
  }

  function showLogin() {
    clearTimeout(state.taskTimer);
    $("#appView").classList.add("hidden");
    $("#loginView").classList.remove("hidden");
    const session = state.session || {};
    const hint = $("#loginHint");
    const button = $("#loginBtn");
    const password = $("#loginPassword");
    $("#loginError").textContent = "";
    button.disabled = false;
    password.disabled = false;
    if (!session.enabled) {
      hint.textContent = "管理面板未启用（admin_panel_enabled=false）";
      button.disabled = true;
      password.disabled = true;
    } else if (!session.password_configured) {
      hint.textContent = "尚未配置 admin_panel_password，请在 .env 中设置后重启";
      button.disabled = true;
      password.disabled = true;
    } else {
      hint.textContent = "请输入管理密码";
    }
    setConn(false, "未登录");
  }

  function showApp() {
    $("#loginView").classList.add("hidden");
    $("#appView").classList.remove("hidden");
    setConn(true, "已登录");
    switchTab("overview");
  }

  function switchTab(tab) {
    const meta = TAB_META[tab];
    if (!meta) return;
    state.currentTab = tab;
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.tab === tab);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${tab}`);
    });
    $("#pageTitle").textContent = meta.title;
    $("#pageSubtitle").textContent = meta.subtitle;
    run(meta.load());
  }

  async function loadTab(tab) {
    const meta = TAB_META[tab];
    if (!meta) return;
    try {
      await meta.load();
    } catch (error) {
      if (error.message !== "请先登录") toast(error.message, "error");
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    const button = $("#loginBtn");
    const password = $("#loginPassword").value;
    $("#loginError").textContent = "";
    button.disabled = true;
    try {
      const response = await fetch("/admin/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Admin-Request": "1" },
        body: JSON.stringify({ password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `登录失败 (${response.status})`);
      }
      state.session = Object.assign({}, state.session, { authenticated: true });
      $("#loginPassword").value = "";
      showApp();
    } catch (error) {
      $("#loginError").textContent = error.message || String(error);
    } finally {
      button.disabled = false;
    }
  }

  async function handleLogout() {
    try {
      await api("/admin/api/logout", { method: "POST" });
    } catch (error) {
      // ignore
    }
    state.session = Object.assign({}, state.session, { authenticated: false });
    state.overview = null;
    state.checkResults = [];
    state.services = null;
    state.business = null;
    state.tasks = null;
    clearTimeout(state.taskTimer);
    showLogin();
  }

  async function loadOverview() {
    const [overview, logFiles] = await Promise.all([
      api("/admin/api/overview"),
      api("/admin/api/logs/files").catch(() => ({ files: [] })),
    ]);
    state.overview = overview;
    renderOverview(overview);
    if (logFiles.files && logFiles.files.length) {
      try {
        const latest = logFiles.files[0].name;
        const data = await api(`/admin/api/logs/file/${encodeURIComponent(latest)}?lines=40`);
        $("#overviewLog").textContent = data.content || "(空)";
      } catch (error) {
        $("#overviewLog").textContent = `读取日志失败: ${error.message}`;
      }
    } else {
      $("#overviewLog").textContent = "暂无日志文件";
    }
  }

  function renderOverview(overview) {
    const system = overview.system || {};
    const memory = system.memory || {};
    const disk = system.disk || {};
    const process = system.process || {};
    const stats = overview.stats || {};
    const counts = overview.counts || {};
    const bots = overview.bots || [];
    const redis = overview.redis || { status: "fail", detail: "未检测" };
    const active = overview.services && overview.services.active;

    $("#overviewCards").innerHTML = [
      card("在线 Bot", bots.length, bots.map((bot) => bot.self_id).join(", ") || "未连接"),
      card("运行时长", fmtDuration(overview.uptime_seconds)),
      card("CPU", `${system.cpu_percent == null ? "-" : system.cpu_percent}%`, `${system.cpu_count || "-"} 核`),
      card("内存", `${memory.percent == null ? "-" : memory.percent}%`, `${fmtBytes(memory.used)} / ${fmtBytes(memory.total)}`),
      card("磁盘", `${disk.percent == null ? "-" : disk.percent}%`, `${fmtBytes(disk.used)} / ${fmtBytes(disk.total)}`),
      card("Redis", redis.status === "ok" ? "正常" : redis.status === "skipped" ? "跳过" : "异常", redis.detail || ""),
    ].join("");

    renderKV($("#resourceList"), [
      ["CPU 核心", `${system.cpu_count || "-"}`, false],
      ["进程内存", fmtBytes(process.rss), false],
      ["线程数", process.threads == null ? "-" : String(process.threads), false],
      ["进程启动", fmtDate(process.create_time), false],
      ["Swap", `${(system.swap || {}).percent == null ? "-" : system.swap.percent}%`, false],
      ["数据目录", "data / log", true],
    ]);

    renderKV($("#overviewMeta"), [
      ["当前 AI 服务", active ? active.name : "使用 .env 配置", false],
      ["AI 模型", active ? active.model : "-", true],
      ["AI 服务数", String((overview.services || {}).total || 0), false],
      ["私聊白名单", String(counts.users || 0), false],
      ["群白名单", String(counts.groups || 0), false],
      ["AI 请求", String(stats.ai_request_count || 0), false],
      ["联网搜索", String(stats.web_search_count || 0), false],
      ["知识库检索", String(stats.kb_retrieve_count || 0), false],
      ["知识库上传/解析", `${stats.kb_upload_count || 0} / ${stats.kb_parse_count || 0}`, false],
      ["定时任务", String((overview.scheduler || {}).job_count || 0), false],
    ]);

    setConn(redis.status === "ok", redis.status === "ok" ? "Redis 正常" : "Redis 异常");
  }

  async function loadChecks() {
    const data = await api("/admin/api/checks");
    state.checkTargets = data.targets || [];
    renderChecks();
  }

  async function runChecks(ids) {
    state.checkRunning = true;
    renderChecks();
    const summary = $("#checksSummary");
    summary.textContent = "检测中...";
    try {
      const data = await api("/admin/api/checks/run", {
        method: "POST",
        body: JSON.stringify({ ids: ids || null }),
      });
      if (ids && ids.length) {
        const merged = new Map(state.checkResults.map((item) => [item.id, item]));
        (data.results || []).forEach((item) => merged.set(item.id, item));
        state.checkResults = Array.from(merged.values());
      } else {
        state.checkResults = data.results || [];
      }
      state.checkCheckedAt = data.checked_at || "";
      toast("检测完成", "ok");
    } finally {
      state.checkRunning = false;
      renderChecks();
    }
  }

  function checkMeta(result) {
    const meta = result.meta || {};
    const parts = [];
    if (Array.isArray(meta.models) && meta.models.length) {
      parts.push(`模型: ${meta.models.join(", ")}`);
    }
    if (Array.isArray(meta.datasets) && meta.datasets.length) {
      parts.push(`知识库: ${meta.datasets.join(", ")}`);
    }
    if (meta.loaded != null) {
      parts.push(`模型加载: ${meta.loaded ? "是" : "否"}`);
    }
    return parts.length ? `<div class="meta-line">${esc(parts.join(" | "))}</div>` : "";
  }

  function renderChecks() {
    const resultMap = new Map(state.checkResults.map((item) => [item.id, item]));
    if (!state.checkTargets.length) {
      $("#checkTable").innerHTML = '<p class="empty">没有可检测的项目</p>';
      $("#checksSummary").textContent = "";
      return;
    }
    const rows = state.checkTargets.map((target) => {
      const result = resultMap.get(target.id) || Object.assign({}, target, {
        status: "idle",
        latency_ms: 0,
        detail: "未检测",
        meta: {},
      });
      return `
        <tr>
          <td>
            <strong>${esc(result.name || target.name)}</strong>
            <div class="meta-line">${esc(CATEGORY_LABELS[target.category] || target.category)} · ${esc(target.source || "")}</div>
          </td>
          <td class="mono">${esc(result.key_masked || "无")}</td>
          <td class="mono">${esc(target.base_url || "-")}${target.model ? `<div class="meta-line">${esc(target.model)}</div>` : ""}</td>
          <td>
            ${statusBadge(result.status)}
            ${result.in_use ? '<span class="badge active">使用中</span>' : ""}
          </td>
          <td>${result.latency_ms ? `${result.latency_ms} ms` : "-"}</td>
          <td>
            ${esc(result.detail || "")}
            ${checkMeta(result)}
          </td>
          <td><button class="btn ghost small" data-check-id="${esc(target.id)}" type="button" ${state.checkRunning ? "disabled" : ""}>检测</button></td>
        </tr>`;
    });

    $("#checkTable").innerHTML = `
      <table>
        <thead>
          <tr><th>项目</th><th>Key</th><th>地址 / 模型</th><th>状态</th><th>延迟</th><th>结果</th><th></th></tr>
        </thead>
        <tbody>${rows.join("")}</tbody>
      </table>`;

    const counts = { ok: 0, fail: 0, skipped: 0, idle: 0 };
    state.checkTargets.forEach((target) => {
      const result = resultMap.get(target.id);
      const status = result ? result.status : "idle";
      counts[status] = (counts[status] || 0) + 1;
    });
    const checked = state.checkCheckedAt ? ` · 检测于 ${fmtDate(state.checkCheckedAt)}` : "";
    $("#checksSummary").textContent = state.checkRunning
      ? "检测中..."
      : `可用 ${counts.ok || 0} · 失败 ${counts.fail || 0} · 跳过 ${counts.skipped || 0} · 未检测 ${counts.idle || 0}${checked}`;
    $("#runAllChecks").disabled = state.checkRunning;
    $("#runAllChecks").textContent = state.checkRunning ? "检测中..." : "开始检测";
  }

  async function loadServices() {
    state.services = await api("/admin/api/ai-services");
    renderServices();
  }

  function renderServices() {
    const data = state.services || { services: [], active: null };
    const active = data.services.find((item) => item.id === data.active);
    if (active) {
      $("#activeService").innerHTML = `
        <div class="service-name">${esc(active.name)}</div>
        <div class="service-line">${esc(active.model)} · ${esc(active.base_url)}</div>
        <div class="service-line">Key: ${esc(active.key_masked || "未配置")}</div>`;
    } else {
      $("#activeService").innerHTML = '<span class="muted">数据库中没有激活的服务，当前使用 .env 配置</span>';
    }

    if (!data.services.length) {
      $("#serviceList").innerHTML = '<p class="empty">暂无 AI 服务配置</p>';
      return;
    }
    const rows = data.services.map((item) => `
      <tr>
        <td>${item.id}</td>
        <td>${esc(item.name)}</td>
        <td class="mono">${esc(item.model)}</td>
        <td class="mono">${esc(item.base_url)}</td>
        <td class="mono">${esc(item.key_masked || "未配置")}</td>
        <td>${item.is_active ? '<span class="badge active">使用中</span>' : '<span class="badge">备用</span>'}</td>
        <td>
          <div class="row-actions">
            <button class="btn ghost small" data-service-edit="${item.id}" type="button">编辑</button>
            ${item.is_active ? "" : `<button class="btn ghost small" data-service-activate="${item.id}" type="button">启用</button>`}
            ${item.is_active ? "" : `<button class="btn danger small" data-service-delete="${item.id}" type="button">删除</button>`}
          </div>
        </td>
      </tr>`).join("");
    $("#serviceList").innerHTML = `
      <table>
        <thead><tr><th>ID</th><th>名称</th><th>模型</th><th>地址</th><th>Key</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  function fillServiceForm(service) {
    state.editingService = service.id;
    $("#serviceFormTitle").textContent = `编辑 AI 服务 #${service.id}`;
    $("#svcName").value = service.name || "";
    $("#svcBase").value = service.base_url || "";
    $("#svcModel").value = service.model || "";
    $("#svcKey").value = "";
    $("#svcKey").required = false;
    $("#svcKey").placeholder = "留空表示不修改原 Key";
    $("#svcCancel").classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetServiceForm() {
    state.editingService = null;
    $("#serviceFormTitle").textContent = "新增 AI 服务";
    $("#serviceForm").reset();
    $("#svcKey").required = true;
    $("#svcKey").placeholder = "编辑时留空保持不变";
    $("#svcCancel").classList.add("hidden");
  }

  async function handleServiceSubmit(event) {
    event.preventDefault();
    const payload = {
      name: $("#svcName").value.trim(),
      api_key: $("#svcKey").value.trim(),
      base_url: $("#svcBase").value.trim(),
      model: $("#svcModel").value.trim(),
    };
    if (!payload.name || !payload.base_url || !payload.model) {
      throw new Error("名称、接口地址和模型都不能为空");
    }
    if (!state.editingService && !payload.api_key) {
      throw new Error("新增服务时必须填写 API Key");
    }
    if (state.editingService) {
      if (!payload.api_key) delete payload.api_key;
      state.services = await api(`/admin/api/ai-services/${state.editingService}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      toast("AI 服务已更新", "ok");
    } else {
      state.services = await api("/admin/api/ai-services", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast("AI 服务已添加", "ok");
    }
    resetServiceForm();
    renderServices();
  }

  async function handleServiceAction(event) {
    const edit = event.target.closest("[data-service-edit]");
    if (edit) {
      const service = (state.services.services || []).find((item) => item.id === Number(edit.dataset.serviceEdit));
      if (service) fillServiceForm(service);
      return;
    }
    const activate = event.target.closest("[data-service-activate]");
    if (activate) {
      if (!window.confirm("切换到这个 AI 服务？机器人会立即重新初始化。")) return;
      state.services = await api(`/admin/api/ai-services/${activate.dataset.serviceActivate}/activate`, {
        method: "POST",
      });
      toast("已切换 AI 服务", "ok");
      renderServices();
      return;
    }
    const remove = event.target.closest("[data-service-delete]");
    if (remove) {
      if (!window.confirm("确定删除这个 AI 服务？")) return;
      state.services = await api(`/admin/api/ai-services/${remove.dataset.serviceDelete}`, {
        method: "DELETE",
      });
      toast("AI 服务已删除", "ok");
      renderServices();
    }
  }

  async function loadBusiness() {
    state.business = await api("/admin/api/business");
    renderBusiness();
  }

  function chipMarkup(items, kind) {
    if (!items.length) return '<span class="muted">暂无</span>';
    return items
      .map((item) => {
        const id = typeof item === "object" ? item.id : item;
        const label = typeof item === "object" ? item.label : item;
        return `<button type="button" class="chip" data-remove="${esc(kind)}" data-id="${esc(id)}" title="点击移除">${esc(label)}<span class="chip-x">×</span></button>`;
      })
      .join("");
  }

  function tableMarkup(headers, rows, emptyText = "暂无数据") {
    return `
      <div class="table-wrap">
        <table>
          <thead><tr>${headers.map((item) => `<th>${esc(item)}</th>`).join("")}</tr></thead>
          <tbody>${rows.length ? rows.join("") : `<tr><td colspan="${headers.length}" class="empty">${esc(emptyText)}</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  function renderBusiness() {
    const data = state.business;
    if (!data) {
      $("#businessRoot").innerHTML = '<p class="empty">暂无数据</p>';
      return;
    }

    const welcomeRows = data.welcome.map((item) => `
      <tr>
        <td class="mono">${esc(item.group_id)}</td>
        <td>${esc(item.message)}</td>
        <td>
          <div class="row-actions">
            <button class="btn ghost small" data-edit-welcome="${esc(item.group_id)}" type="button">编辑</button>
            <button class="btn danger small" data-remove="welcome" data-id="${esc(item.group_id)}" type="button">删除</button>
          </div>
        </td>
      </tr>`);

    const kbRows = data.kb_groups.map((item) => `
      <tr>
        <td class="mono">${esc(item.group_id)}</td>
        <td class="mono">${esc(item.kb_id)}</td>
        <td><button class="btn danger small" data-remove="kb" data-id="${esc(item.group_id)}" type="button">移除</button></td>
      </tr>`);

    const keywordRows = data.keywords.map((item) => `
      <tr>
        <td>${item.id}</td>
        <td>${esc(item.content)}</td>
        <td><button class="btn danger small" data-remove="keyword" data-id="${item.id}" type="button">删除</button></td>
      </tr>`);

    const html = [
      `<div class="panel">
        <div class="panel-head"><h2>私聊白名单</h2><span class="muted">只有这些 QQ 可以私聊机器人</span></div>
        <form class="inline-form" data-form="user">
          <input name="user_id" type="number" min="1" placeholder="QQ 号" required>
          <button class="btn primary small" type="submit">添加用户</button>
        </form>
        <div class="chips">${chipMarkup(data.users.map((id) => ({ id, label: id })), "user")}</div>
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>群白名单</h2><span class="muted">机器人只在这些群里工作</span></div>
        <form class="inline-form" data-form="group">
          <input name="group_id" type="number" min="1" placeholder="群号" required>
          <button class="btn primary small" type="submit">添加群</button>
        </form>
        <div class="chips">${chipMarkup(data.groups.map((id) => ({ id, label: id })), "group")}</div>
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>群欢迎语</h2><span class="muted">新成员入群时自动发送</span></div>
        <form class="inline-form" data-form="welcome">
          <input name="group_id" type="number" min="1" placeholder="群号" required>
          <input name="message" placeholder="欢迎语内容" required>
          <button class="btn primary small" type="submit">保存欢迎语</button>
        </form>
        ${tableMarkup(["群号", "欢迎语", "操作"], welcomeRows)}
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>广告关键词</h2><span class="muted">命中后会触发广告撤回判断</span></div>
        <form class="inline-form" data-form="ad-keyword">
          <input name="keyword" placeholder="新增广告关键词" required>
          <button class="btn primary small" type="submit">添加关键词</button>
        </form>
        <div class="chips">${chipMarkup(data.ad_keywords.map((item) => ({ id: item.id, label: item.keyword })), "ad-keyword")}</div>
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>广告撤回群</h2><span class="muted">这些群会开启广告检测与自动撤回</span></div>
        <form class="inline-form" data-form="ad-recall">
          <input name="group_id" type="number" min="1" placeholder="群号" required>
          <button class="btn primary small" type="submit">开启撤回</button>
        </form>
        <div class="chips">${chipMarkup(data.ad_recall_groups.map((id) => ({ id, label: id })), "ad-recall")}</div>
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>知识库群绑定</h2><span class="muted">群聊记录会入库到对应 RAGFlow 知识库</span></div>
        <form class="inline-form" data-form="kb">
          <input name="group_id" type="number" min="1" placeholder="群号" required>
          <input name="kb_id" placeholder="RAGFlow 知识库 ID" required>
          <button class="btn primary small" type="submit">保存绑定</button>
        </form>
        ${tableMarkup(["群号", "知识库 ID", "操作"], kbRows)}
      </div>`,
      `<div class="panel">
        <div class="panel-head"><h2>提示词</h2><span class="muted">对话时追加到系统提示词的关键词提示</span></div>
        <form class="inline-form" data-form="keyword">
          <input name="content" placeholder="新增提示词内容" required>
          <button class="btn primary small" type="submit">添加提示词</button>
        </form>
        ${tableMarkup(["ID", "内容", "操作"], keywordRows)}
      </div>`,
    ];
    $("#businessRoot").innerHTML = html.join("");
  }

  async function handleBusinessSubmit(event) {
    const form = event.target.closest("form[data-form]");
    if (!form) return;
    event.preventDefault();
    const kind = form.dataset.form;
    const data = new FormData(form);
    let path = "";
    let method = "POST";
    let body = {};

    if (kind === "user") {
      path = "/admin/api/whitelist/users";
      body = { user_id: Number(data.get("user_id")) };
    } else if (kind === "group") {
      path = "/admin/api/whitelist/groups";
      body = { group_id: Number(data.get("group_id")) };
    } else if (kind === "welcome") {
      path = "/admin/api/welcome";
      method = "PUT";
      body = { group_id: Number(data.get("group_id")), message: String(data.get("message") || "") };
    } else if (kind === "ad-keyword") {
      path = "/admin/api/ad-keywords";
      body = { keyword: String(data.get("keyword") || "") };
    } else if (kind === "ad-recall") {
      path = "/admin/api/ad-recall-groups";
      body = { group_id: Number(data.get("group_id")) };
    } else if (kind === "kb") {
      path = "/admin/api/kb-groups";
      method = "PUT";
      body = { group_id: Number(data.get("group_id")), kb_id: String(data.get("kb_id") || "") };
    } else if (kind === "keyword") {
      path = "/admin/api/keywords";
      body = { content: String(data.get("content") || "") };
    } else {
      return;
    }

    state.business = await api(path, { method, body: JSON.stringify(body) });
    renderBusiness();
    toast("已保存", "ok");
  }

  async function handleBusinessClick(event) {
    const edit = event.target.closest("[data-edit-welcome]");
    if (edit) {
      const groupId = Number(edit.dataset.editWelcome);
      const current = (state.business.welcome || []).find((item) => item.group_id === groupId);
      const message = window.prompt("修改欢迎语", current ? current.message : "");
      if (message == null) return;
      if (!message.trim()) {
        toast("欢迎语不能为空", "error");
        return;
      }
      state.business = await api("/admin/api/welcome", {
        method: "PUT",
        body: JSON.stringify({ group_id: groupId, message: message.trim() }),
      });
      renderBusiness();
      toast("欢迎语已更新", "ok");
      return;
    }

    const remove = event.target.closest("[data-remove]");
    if (!remove) return;
    const kind = remove.dataset.remove;
    const id = remove.dataset.id;
    const paths = {
      user: `/admin/api/whitelist/users/${id}`,
      group: `/admin/api/whitelist/groups/${id}`,
      welcome: `/admin/api/welcome/${id}`,
      "ad-keyword": `/admin/api/ad-keywords/${id}`,
      "ad-recall": `/admin/api/ad-recall-groups/${id}`,
      kb: `/admin/api/kb-groups/${id}`,
      keyword: `/admin/api/keywords/${id}`,
    };
    if (!paths[kind]) return;
    if (!window.confirm("确定移除这一项？")) return;
    state.business = await api(paths[kind], { method: "DELETE" });
    renderBusiness();
    toast("已移除", "ok");
  }

  async function loadLogsTab() {
    if (!state.logFiles.length) {
      await loadLogFiles();
    } else {
      renderLogFileOptions();
    }
  }

  async function loadLogFiles() {
    const source = state.logSource;
    const data = await api(`/admin/api/${source}/files`);
    state.logFiles = data.files || [];
    state.selectedLog = "";
    renderLogFileOptions();
    $("#logContent").textContent = "选择文件后点击加载";
    $("#logMeta").textContent = "";
    if (state.selectedLog) {
      await loadLog();
    }
  }

  function renderLogFileOptions() {
    const query = $("#logSearch").value.trim().toLowerCase();
    const files = state.logFiles.filter((file) => !query || file.name.toLowerCase().includes(query));
    if (!files.some((file) => file.name === state.selectedLog)) {
      state.selectedLog = files.length ? files[0].name : "";
    }
    const options = files.map(
      (file) => `<option value="${esc(file.name)}">${esc(file.name)} (${fmtBytes(file.size)})</option>`
    );
    $("#logFile").innerHTML = options.join("") || '<option value="">无文件</option>';
    $("#logFile").value = state.selectedLog;
    $("#logMeta").textContent = state.logFiles.length
      ? `共 ${state.logFiles.length} 个文件，当前显示 ${files.length} 个`
      : "暂无文件";
  }

  async function loadLog() {
    const name = $("#logFile").value || state.selectedLog;
    if (!name) {
      $("#logContent").textContent = "没有可加载的文件";
      return;
    }
    state.selectedLog = name;
    const lines = Math.max(1, Math.min(2000, Number($("#logLines").value) || 200));
    const keyword = $("#logKeyword").value.trim();
    const level = state.logSource === "logs" ? $("#logLevel").value : "";
    const source = state.logSource;
    const query = new URLSearchParams({
      lines: String(lines),
      keyword,
      level,
    });
    const data = await api(`/admin/api/${source}/file/${encodeURIComponent(name)}?${query.toString()}`);
    $("#logMeta").textContent = `${name} · 显示 ${data.returned_lines} 行 · 匹配 ${data.matched_lines} 行${data.truncated ? " · 已截取末尾 512KB" : ""}`;
    $("#logContent").textContent = data.content || "(空)";
  }

  async function loadTasks() {
    const [data, memes] = await Promise.all([
      api("/admin/api/actions"),
      api("/admin/api/memes").catch(() => null),
    ]);
    state.tasks = data;
    renderTasks();
    if (memes) renderMemeStats(memes);
    clearTimeout(state.taskTimer);
    const running = (data.actions || []).some((item) => item.status === "running");
    if (running) {
      state.taskTimer = setTimeout(() => {
        loadTasks().catch((error) => {
          if (error.message !== "请先登录") toast(error.message, "error");
        });
      }, 2000);
    }
  }

  function renderTasks() {
    const data = state.tasks || { actions: [], scheduler: [] };
    const actions = data.actions || [];
    $("#actionCards").innerHTML = actions.length
      ? actions.map((item) => `
        <div class="card action-card">
          <div class="card-label">${esc(item.label || item.name)}</div>
          <div>${taskStatusBadge(item.status)} ${item.elapsed_seconds ? `<span class="muted">${item.elapsed_seconds}s</span>` : ""}</div>
          <p>${esc(item.description || "")}</p>
          ${item.result ? `<p>${esc(item.result)}</p>` : ""}
          ${item.error ? `<p class="error-text">${esc(item.error)}</p>` : ""}
          <button class="btn primary small" data-action="${esc(item.name)}" type="button" ${item.status === "running" ? "disabled" : ""}>执行</button>
        </div>`).join("")
      : '<p class="empty">暂无手动操作</p>';

    const jobs = data.scheduler || [];
    const rows = jobs.map((job) => `
      <tr>
        <td class="mono">${esc(job.id)}</td>
        <td>${esc(job.name || "")}</td>
        <td class="mono">${esc(job.trigger || "")}</td>
        <td>${esc(job.next_run_time ? fmtDate(job.next_run_time) : "-")}</td>
      </tr>`);
    $("#schedulerList").innerHTML = tableMarkup(["ID", "名称", "触发规则", "下次运行"], rows, "暂无定时任务");
  }

  function renderMemeStats(stats) {
    const build = (title, item) => `
      <div class="card">
        <div class="card-label">${esc(title)}</div>
        <div class="card-value">${esc(item.count || 0)} 张</div>
        <div class="card-sub">${esc(fmtBytes(item.bytes || 0))}${item.last_modified ? ` · 最近 ${esc(fmtDate(item.last_modified))}` : ""}</div>
      </div>`;
    $("#memeStats").innerHTML = build("奶龙表情库", stats.naihub || {}) + build("猪猪表情库", stats.pighub || {});
  }

  async function loadConfig() {
    const data = await api("/admin/api/config");
    state.config = data;
    const html = (data.sections || []).map((section) => `
      <div class="config-section">
        <h3>${esc(section.title)}</h3>
        <div class="kv-list">
          ${(section.items || []).map((item) => `
            <div class="kv-row">
              <span class="kv-label">${esc(item.label)}</span>
              <span class="kv-value ${item.secret ? "mono" : ""}">${esc(item.value)}</span>
            </div>`).join("")}
        </div>
      </div>`).join("");
    $("#configRoot").innerHTML = html || '<p class="empty">暂无配置</p>';
  }

  async function downloadBackup() {
    const response = await fetch("/admin/api/backup", {
      credentials: "same-origin",
      headers: { "X-Admin-Request": "1" },
    });
    if (response.status === 401) {
      showLogin();
      throw new Error("请先登录");
    }
    if (!response.ok) {
      let detail = `备份失败 (${response.status})`;
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch (error) {
        // ignore
      }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const filename = match ? match[1] : `qqbot-backup-${Date.now()}.zip`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    toast("备份已开始下载", "ok");
  }

  function bindEvents() {
    $("#loginForm").addEventListener("submit", (event) => run(handleLogin(event)));
    $("#logoutBtn").addEventListener("click", () => run(handleLogout()));
    $("#nav").addEventListener("click", (event) => {
      const button = event.target.closest(".nav-item");
      if (button) switchTab(button.dataset.tab);
    });
    $("#refreshBtn").addEventListener("click", () => run(loadTab(state.currentTab)));
    document.addEventListener("click", (event) => {
      const jump = event.target.closest("[data-jump]");
      if (jump) switchTab(jump.dataset.jump);
    });

    $("#runAllChecks").addEventListener("click", () => run(runChecks()));
    $("#checkTable").addEventListener("click", (event) => {
      const button = event.target.closest("[data-check-id]");
      if (button) run(runChecks([button.dataset.checkId]));
    });

    $("#serviceForm").addEventListener("submit", (event) => run(handleServiceSubmit(event)));
    $("#svcCancel").addEventListener("click", resetServiceForm);
    $("#serviceList").addEventListener("click", (event) => run(handleServiceAction(event)));

    $("#businessRoot").addEventListener("submit", (event) => run(handleBusinessSubmit(event)));
    $("#businessRoot").addEventListener("click", (event) => run(handleBusinessClick(event)));

    $("#logSourceSwitch").addEventListener("click", (event) => {
      const button = event.target.closest("[data-source]");
      if (!button) return;
      state.logSource = button.dataset.source;
      $("#logSourceSwitch").querySelectorAll("button").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      $("#logLevelWrap").classList.toggle("hidden", state.logSource !== "logs");
      state.logFiles = [];
      state.selectedLog = "";
      $("#logSearch").value = "";
      run(loadLogFiles());
    });
    $("#logSearch").addEventListener("input", renderLogFileOptions);
    $("#logFile").addEventListener("change", () => {
      state.selectedLog = $("#logFile").value;
      run(loadLog());
    });
    $("#loadLogBtn").addEventListener("click", () => run(loadLog()));

    $("#actionCards").addEventListener("click", (event) => {
      const button = event.target.closest("[data-action]");
      if (!button) return;
      const name = button.dataset.action;
      if (!window.confirm("立即执行这个操作？")) return;
      button.disabled = true;
      run((async () => {
        await api(`/admin/api/actions/${name}`, { method: "POST" });
        toast("任务已开始执行", "ok");
        await loadTasks();
      })());
    });

    $("#backupBtn").addEventListener("click", () => run(downloadBackup()));
  }

  async function init() {
    bindEvents();
    try {
      state.session = await fetchSession();
    } catch (error) {
      state.session = { enabled: true, password_configured: true, authenticated: false };
      toast(error.message, "error");
    }
    if (state.session.authenticated) {
      showApp();
    } else {
      showLogin();
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
