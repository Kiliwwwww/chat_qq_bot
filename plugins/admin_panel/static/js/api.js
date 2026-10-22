const { reactive } = Vue;
const { ElMessage } = ElementPlus;

export const session = reactive({
  loaded: false,
  enabled: true,
  password_configured: true,
  authenticated: false,
});

let unauthorizedHandler = () => {};

export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn || (() => {});
}

export async function fetchSession() {
  const response = await fetch("/admin/api/session", { credentials: "same-origin" });
  if (!response.ok) throw new Error(`读取登录状态失败 (${response.status})`);
  return response.json();
}

export async function api(path, options = {}) {
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
    unauthorizedHandler();
    throw new Error("请先登录");
  }
  if (!response.ok) {
    throw new Error((payload && payload.detail) || `请求失败 (${response.status})`);
  }
  return payload;
}

export function toast(message, type = "info") {
  const map = { info: "info", ok: "success", error: "error", warn: "warning" };
  ElMessage({ message: String(message), type: map[type] || "info", duration: 3200 });
}

export function run(promise) {
  Promise.resolve(promise).catch((error) => {
    if (error && error.message !== "请先登录") {
      toast(error.message || String(error), "error");
    }
  });
}

export function fmtBytes(bytes) {
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

export function fmtDuration(seconds) {
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

export function fmtDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function fmtNumber(value) {
  const number = Number(value) || 0;
  return number.toLocaleString("zh-CN", { maximumFractionDigits: 1 });
}

export function shortDate(value) {
  return value ? String(value).slice(5) : "";
}

export function escapeHtml(value) {
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

export function highlightHtml(text, keyword) {
  const source = String(text == null ? "" : text);
  const key = String(keyword || "");
  if (!key) return escapeHtml(source);
  const lowerText = source.toLowerCase();
  const lowerKey = key.toLowerCase();
  let start = 0;
  let index = lowerText.indexOf(lowerKey);
  let html = "";
  while (index !== -1) {
    html += escapeHtml(source.slice(start, index));
    html += `<mark>${escapeHtml(source.slice(index, index + key.length))}</mark>`;
    start = index + key.length;
    index = lowerText.indexOf(lowerKey, start);
  }
  html += escapeHtml(source.slice(start));
  return html;
}

export async function confirmAction(message, options = {}) {
  try {
    await ElementPlus.ElMessageBox.confirm(message, options.title || "确认操作", {
      confirmButtonText: options.confirmText || "确定",
      cancelButtonText: options.cancelText || "取消",
      type: options.danger === false ? "info" : "warning",
    });
    return true;
  } catch (error) {
    return false;
  }
}

export async function downloadBackup() {
  const response = await fetch("/admin/api/backup", {
    credentials: "same-origin",
    headers: { "X-Admin-Request": "1" },
  });
  if (response.status === 401) {
    unauthorizedHandler();
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
