import { api, toast, run, fmtDate } from "../api.js";

const CATEGORY_LABELS = {
  ai: "AI",
  search: "搜索",
  knowledge: "知识库",
  tts: "语音",
  redis: "Redis",
};

const STATUS = {
  ok: { label: "可用", type: "success" },
  fail: { label: "失败", type: "danger" },
  skipped: { label: "跳过", type: "info" },
  idle: { label: "未检测", type: "info" },
};

export default {
  name: "ChecksView",
  setup() {
    const { ref, computed, onMounted } = Vue;

    const targets = ref([]);
    const results = ref([]);
    const running = ref(false);
    const checkedAt = ref("");

    const rows = computed(() => {
      const map = new Map(results.value.map((item) => [item.id, item]));
      return targets.value.map((target) => {
        const result = map.get(target.id) || Object.assign({}, target, {
          status: "idle",
          latency_ms: 0,
          detail: "未检测",
          meta: {},
        });
        return { target, result };
      });
    });

    const summary = computed(() => {
      const counts = { ok: 0, fail: 0, skipped: 0, idle: 0 };
      targets.value.forEach((target) => {
        const result = results.value.find((item) => item.id === target.id);
        const status = result ? result.status : "idle";
        counts[status] = (counts[status] || 0) + 1;
      });
      const checked = checkedAt.value ? ` · 检测于 ${fmtDate(checkedAt.value)}` : "";
      return running.value
        ? "检测中..."
        : `可用 ${counts.ok || 0} · 失败 ${counts.fail || 0} · 跳过 ${counts.skipped || 0} · 未检测 ${counts.idle || 0}${checked}`;
    });

    function metaText(result) {
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
      return parts.join(" | ");
    }

    function categoryLabel(category) {
      return CATEGORY_LABELS[category] || category;
    }

    function statusOf(status) {
      return STATUS[status] || { label: status, type: "info" };
    }

    async function runChecks(ids) {
      running.value = true;
      try {
        const data = await api("/admin/api/checks/run", {
          method: "POST",
          body: JSON.stringify({ ids: ids || null }),
        });
        if (ids && ids.length) {
          const merged = new Map(results.value.map((item) => [item.id, item]));
          (data.results || []).forEach((item) => merged.set(item.id, item));
          results.value = Array.from(merged.values());
        } else {
          results.value = data.results || [];
        }
        checkedAt.value = data.checked_at || "";
        toast("检测完成", "ok");
      } finally {
        running.value = false;
      }
    }

    onMounted(async () => {
      const data = await api("/admin/api/checks");
      targets.value = data.targets || [];
    });

    return { targets, rows, summary, running, runChecks, metaText, categoryLabel, statusOf, run };
  },
  template: `
    <div>
      <div class="toolbar">
        <el-button type="primary" :loading="running" @click="run(runChecks())">开始检测</el-button>
        <span class="muted">{{ summary }}</span>
      </div>
      <div class="panel">
        <el-table :data="rows" v-if="rows.length">
          <el-table-column label="项目" min-width="200">
            <template #default="{ row }">
              <strong>{{ row.result.name || row.target.name }}</strong>
              <div class="muted" style="font-size:12px">
                {{ categoryLabel(row.target.category) }} · {{ row.target.source || '' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Key" width="150">
            <template #default="{ row }"><span class="mono">{{ row.result.key_masked || '无' }}</span></template>
          </el-table-column>
          <el-table-column label="地址 / 模型" min-width="200">
            <template #default="{ row }">
              <span class="mono">{{ row.target.base_url || '-' }}</span>
              <div class="muted" style="font-size:12px" v-if="row.target.model">{{ row.target.model }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="130">
            <template #default="{ row }">
              <el-tag :type="statusOf(row.result.status).type" size="small">{{ statusOf(row.result.status).label }}</el-tag>
              <el-tag v-if="row.result.in_use" type="success" size="small" style="margin-left:4px">使用中</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="延迟" width="90">
            <template #default="{ row }">{{ row.result.latency_ms ? row.result.latency_ms + ' ms' : '-' }}</template>
          </el-table-column>
          <el-table-column label="结果" min-width="220">
            <template #default="{ row }">
              {{ row.result.detail || '' }}
              <div class="muted" style="font-size:12px" v-if="metaText(row.result)">{{ metaText(row.result) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="" width="80">
            <template #default="{ row }">
              <el-button size="small" :disabled="running" @click="run(runChecks([row.target.id]))">检测</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">没有可检测的项目</p>
      </div>
      <p class="hint">检测 AI 服务时会优先请求模型列表接口；如果接口不支持，会退回到一次最小的对话请求（可能产生极少量 token 费用）。</p>
    </div>
  `,
};
