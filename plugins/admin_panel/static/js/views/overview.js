import { api, fmtBytes, fmtDuration, fmtDate, run } from "../api.js";

export default {
  name: "OverviewView",
  setup() {
    const { ref, onMounted } = Vue;
    const overview = ref(null);
    const recentLog = ref("加载中...");

    const systemRows = Vue.computed(() => {
      const data = overview.value;
      if (!data) return [];
      const system = data.system || {};
      const process = system.process || {};
      return [
        ["CPU 核心", String(system.cpu_count || "-")],
        ["进程内存", fmtBytes(process.rss)],
        ["线程数", process.threads == null ? "-" : String(process.threads)],
        ["进程启动", fmtDate(process.create_time)],
        ["Swap", `${(system.swap || {}).percent == null ? "-" : system.swap.percent}%`],
        ["数据目录", "data / log", true],
      ];
    });

    const metaRows = Vue.computed(() => {
      const data = overview.value;
      if (!data) return [];
      const stats = data.stats || {};
      const counts = data.counts || {};
      const active = data.services && data.services.active;
      return [
        ["当前 AI 服务", active ? active.name : "使用 .env 配置"],
        ["AI 模型", active ? active.model : "-", true],
        ["AI 服务数", String((data.services || {}).total || 0)],
        ["私聊白名单", String(counts.users || 0)],
        ["群白名单", String(counts.groups || 0)],
        ["AI 请求", String(stats.ai_request_count || 0)],
        ["联网搜索", String(stats.web_search_count || 0)],
        ["知识库检索", String(stats.kb_retrieve_count || 0)],
        ["知识库上传/解析", `${stats.kb_upload_count || 0} / ${stats.kb_parse_count || 0}`],
        ["定时任务", String((data.scheduler || {}).job_count || 0)],
      ];
    });

    const statCards = Vue.computed(() => {
      const data = overview.value;
      if (!data) return [];
      const system = data.system || {};
      const memory = system.memory || {};
      const disk = system.disk || {};
      const redis = data.redis || { status: "fail", detail: "未检测" };
      const bots = data.bots || [];
      return [
        { label: "在线 Bot", value: String(bots.length), sub: bots.map((b) => b.self_id).join(", ") || "未连接" },
        { label: "运行时长", value: fmtDuration(data.uptime_seconds) },
        { label: "CPU", value: system.cpu_percent == null ? "-" : `${system.cpu_percent}%`, sub: `${system.cpu_count || "-"} 核` },
        { label: "内存", value: memory.percent == null ? "-" : `${memory.percent}%`, sub: `${fmtBytes(memory.used)} / ${fmtBytes(memory.total)}` },
        { label: "磁盘", value: disk.percent == null ? "-" : `${disk.percent}%`, sub: `${fmtBytes(disk.used)} / ${fmtBytes(disk.total)}` },
        {
          label: "Redis",
          value: redis.status === "ok" ? "正常" : redis.status === "skipped" ? "跳过" : "异常",
          sub: redis.detail || "",
        },
      ];
    });

    async function load() {
      const [data, logFiles] = await Promise.all([
        api("/admin/api/overview"),
        api("/admin/api/logs/files").catch(() => ({ files: [] })),
      ]);
      overview.value = data;
      if (logFiles.files && logFiles.files.length) {
        try {
          const latest = logFiles.files[0].name;
          const log = await api(`/admin/api/logs/file/${encodeURIComponent(latest)}?lines=40`);
          recentLog.value = log.content || "(空)";
        } catch (error) {
          recentLog.value = `读取日志失败: ${error.message}`;
        }
      } else {
        recentLog.value = "暂无日志文件";
      }
    }

    onMounted(() => run(load()));
    return { overview, recentLog, statCards, systemRows, metaRows, load };
  },
  template: `
    <div>
      <div class="stat-grid">
        <div class="stat-card" v-for="item in statCards" :key="item.label">
          <div class="label">{{ item.label }}</div>
          <div class="value" :class="{ small: String(item.value).length > 12 }">{{ item.value }}</div>
          <div class="sub" v-if="item.sub">{{ item.sub }}</div>
        </div>
      </div>
      <div class="grid-2">
        <div class="panel">
          <div class="panel-head"><h2>系统资源</h2></div>
          <div class="kv-row" v-for="row in systemRows" :key="row[0]">
            <span class="kv-label">{{ row[0] }}</span>
            <span class="kv-value" :class="{ mono: row[2] }">{{ row[1] }}</span>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>连接与统计</h2></div>
          <div class="kv-row" v-for="row in metaRows" :key="row[0]">
            <span class="kv-label">{{ row[0] }}</span>
            <span class="kv-value" :class="{ mono: row[2] }">{{ row[1] }}</span>
          </div>
        </div>
      </div>
      <div class="panel" style="margin-top:16px">
        <div class="panel-head">
          <h2>最近日志</h2>
          <el-button size="small" text type="primary" @click="$emit('jump', 'logs')">查看全部</el-button>
        </div>
        <pre class="log-preview">{{ recentLog }}</pre>
      </div>
    </div>
  `,
};
