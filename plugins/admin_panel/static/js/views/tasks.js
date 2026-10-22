import { api, toast, run, confirmAction, fmtBytes, fmtDate } from "../api.js";

const STATUS = {
  idle: { label: "待执行", type: "info" },
  running: { label: "执行中", type: "warning" },
  success: { label: "成功", type: "success" },
  error: { label: "失败", type: "danger" },
};

export default {
  name: "TasksView",
  setup() {
    const { ref, onMounted, onBeforeUnmount } = Vue;

    const tasks = ref(null);
    const memes = ref(null);
    let timer = null;

    function statusOf(status) {
      return STATUS[status] || { label: status, type: "info" };
    }

    async function load() {
      const [data, memeData] = await Promise.all([
        api("/admin/api/actions"),
        api("/admin/api/memes").catch(() => null),
      ]);
      tasks.value = data;
      memes.value = memeData;
      clearTimeout(timer);
      const running = (data.actions || []).some((item) => item.status === "running");
      if (running) {
        timer = setTimeout(() => run(load()), 2000);
      }
    }

    async function execute(action) {
      const confirmed = await confirmAction("立即执行这个操作？", {
        title: "执行任务",
        confirmText: "执行",
        danger: false,
      });
      if (!confirmed) return;
      await api(`/admin/api/actions/${action.name}`, { method: "POST" });
      toast("任务已开始执行", "ok");
      await load();
    }

    onMounted(() => run(load()));
    onBeforeUnmount(() => clearTimeout(timer));

    return { tasks, memes, statusOf, execute, fmtBytes, fmtDate, run };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head"><h2>手动操作</h2></div>
        <div class="action-grid" v-if="tasks && (tasks.actions || []).length">
          <div class="action-card" v-for="item in tasks.actions" :key="item.name">
            <div class="title">{{ item.label || item.name }}</div>
            <div>
              <el-tag :type="statusOf(item.status).type" size="small">{{ statusOf(item.status).label }}</el-tag>
              <span class="muted" v-if="item.elapsed_seconds" style="margin-left:6px">{{ item.elapsed_seconds }}s</span>
            </div>
            <div class="desc">{{ item.description || '' }}</div>
            <div class="desc" v-if="item.result">{{ item.result }}</div>
            <div class="desc" v-if="item.error" style="color:var(--bad)">{{ item.error }}</div>
            <el-button type="primary" size="small" :disabled="item.status === 'running'"
              @click="run(execute(item))">执行</el-button>
          </div>
        </div>
        <p v-else class="empty-tip">暂无手动操作</p>
      </div>

      <div class="panel">
        <div class="panel-head"><h2>定时任务</h2></div>
        <el-table :data="(tasks && tasks.scheduler) || []" v-if="tasks && (tasks.scheduler || []).length">
          <el-table-column label="ID" min-width="160"><template #default="{ row }"><span class="mono">{{ row.id }}</span></template></el-table-column>
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column label="触发规则" min-width="140"><template #default="{ row }"><span class="mono">{{ row.trigger || '' }}</span></template></el-table-column>
          <el-table-column label="下次运行" min-width="170">
            <template #default="{ row }">{{ row.next_run_time ? fmtDate(row.next_run_time) : '-' }}</template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">暂无定时任务</p>
      </div>

      <div class="panel">
        <div class="panel-head"><h2>表情包库</h2></div>
        <div class="stat-grid" v-if="memes">
          <div class="stat-card">
            <div class="label">奶龙表情库</div>
            <div class="value">{{ (memes.naihub || {}).count || 0 }} 张</div>
            <div class="sub">{{ fmtBytes((memes.naihub || {}).bytes || 0) }}<template v-if="(memes.naihub || {}).last_modified"> · 最近 {{ fmtDate(memes.naihub.last_modified) }}</template></div>
          </div>
          <div class="stat-card">
            <div class="label">猪猪表情库</div>
            <div class="value">{{ (memes.pighub || {}).count || 0 }} 张</div>
            <div class="sub">{{ fmtBytes((memes.pighub || {}).bytes || 0) }}<template v-if="(memes.pighub || {}).last_modified"> · 最近 {{ fmtDate(memes.pighub.last_modified) }}</template></div>
          </div>
        </div>
        <p v-else class="empty-tip">暂无数据</p>
      </div>
    </div>
  `,
};
