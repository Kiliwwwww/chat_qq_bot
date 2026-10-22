import { api, run, downloadBackup } from "../api.js";

export default {
  name: "ConfigView",
  setup() {
    const { ref, onMounted } = Vue;
    const sections = ref([]);

    onMounted(async () => {
      const data = await api("/admin/api/config");
      sections.value = data.sections || [];
    });

    return { sections, downloadBackup, run };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head">
          <h2>配置速览</h2>
          <span class="muted">只读，修改 .env 后需重启</span>
        </div>
        <div v-if="sections.length">
          <div v-for="section in sections" :key="section.title" style="margin-bottom:18px">
            <h3 style="margin:0 0 8px;font-size:14px">{{ section.title }}</h3>
            <div class="kv-row" v-for="item in section.items" :key="item.label">
              <span class="kv-label">{{ item.label }}</span>
              <span class="kv-value" :class="{ mono: item.secret }">{{ item.value }}</span>
            </div>
          </div>
        </div>
        <p v-else class="empty-tip">暂无配置</p>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>数据备份</h2></div>
        <p class="muted">备份 SQLite 数据库和少量业务 JSON，不包含 .env、日志和表情包图片。</p>
        <el-button type="primary" @click="run(downloadBackup())">下载备份 ZIP</el-button>
      </div>
    </div>
  `,
};
