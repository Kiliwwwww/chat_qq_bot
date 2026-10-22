import { api, toast, run, confirmAction, fmtDate } from "../api.js";

export default {
  name: "PromptsView",
  setup() {
    const { ref, reactive, onMounted, onBeforeUnmount } = Vue;

    const items = ref([]);
    const whitelisted = ref([]);
    const defaultPreview = reactive({ mode: "default", prompt: "" });
    const loading = ref(false);

    const dialog = reactive({
      visible: false,
      isEdit: false,
      group_id: null,
      name: "",
      prompt: "",
    });

    async function load() {
      loading.value = true;
      try {
        const [list, preview] = await Promise.all([
          api("/admin/api/group-prompts"),
          api("/admin/api/group-prompts/default-preview").catch(() => null),
        ]);
        items.value = list.items || [];
        whitelisted.value = list.whitelisted_groups || [];
        if (preview) {
          defaultPreview.mode = preview.mode;
          defaultPreview.prompt = preview.prompt || "";
        }
      } finally {
        loading.value = false;
      }
    }

    function openCreate() {
      dialog.visible = true;
      dialog.isEdit = false;
      dialog.group_id = null;
      dialog.name = "";
      dialog.prompt = "";
    }

    function openEdit(row) {
      dialog.visible = true;
      dialog.isEdit = true;
      dialog.group_id = row.group_id;
      dialog.name = row.name || "";
      dialog.prompt = row.prompt || "";
    }

    function copyDefault() {
      dialog.prompt = defaultPreview.prompt || "";
      toast("已填入默认提示词内容", "ok");
    }

    async function save() {
      const prompt = dialog.prompt || "";
      if (!dialog.group_id) {
        toast("请填写群号", "error");
        return;
      }
      if (!prompt.trim()) {
        toast("提示词内容不能为空", "error");
        return;
      }
      const payload = {
        group_id: Number(dialog.group_id),
        name: (dialog.name || "").trim(),
        prompt,
      };
      if (dialog.isEdit) {
        await api(`/admin/api/group-prompts/${payload.group_id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast("群提示词已更新", "ok");
      } else {
        await api("/admin/api/group-prompts", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast("群提示词已创建", "ok");
      }
      dialog.visible = false;
      await load();
    }

    async function remove(row) {
      const confirmed = await confirmAction(
        `删除群 ${row.group_id} 的专属提示词后，该群将回退到默认人格提示词。确定删除？`,
        { title: "删除群提示词", confirmText: "删除" }
      );
      if (!confirmed) return;
      await api(`/admin/api/group-prompts/${row.group_id}`, { method: "DELETE" });
      toast("已删除，该群恢复使用默认提示词", "ok");
      await load();
    }

    function onKeydown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && dialog.visible) {
        event.preventDefault();
        run(save());
      }
    }

    onMounted(() => {
      run(load());
      document.addEventListener("keydown", onKeydown);
    });
    onBeforeUnmount(() => {
      document.removeEventListener("keydown", onKeydown);
    });

    return {
      items,
      whitelisted,
      defaultPreview,
      loading,
      dialog,
      load,
      openCreate,
      openEdit,
      copyDefault,
      save,
      remove,
      fmtDate,
      run,
    };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head">
          <h2>默认提示词</h2>
          <el-tag size="small" :type="defaultPreview.mode === 'kind' ? 'success' : 'primary'">
            {{ defaultPreview.mode === 'kind' ? '邻家大姐姐人格' : '雌小鬼人格' }}
          </el-tag>
        </div>
        <p class="hint" style="margin-top:0">
          未配置专属提示词的群使用此默认人格；配置了专属提示词的群会完全替换默认人格（时间感知、全局提示词片段等动态内容仍会自动拼接）。
          支持占位符 {admin_qq}、{admin_name}。
        </p>
        <el-collapse>
          <el-collapse-item title="查看默认提示词内容（只读）" name="default">
            <pre class="log-preview" style="height:320px">{{ defaultPreview.prompt || '(空)' }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h2>群专属提示词</h2>
          <el-button type="primary" @click="openCreate">
            <el-icon style="margin-right:4px"><Plus /></el-icon>新增群提示词
          </el-button>
        </div>
        <el-table :data="items" v-loading="loading" v-if="items.length">
          <el-table-column label="群号" width="130">
            <template #default="{ row }"><span class="mono">{{ row.group_id }}</span></template>
          </el-table-column>
          <el-table-column label="备注名" width="150">
            <template #default="{ row }">{{ row.name || '—' }}</template>
          </el-table-column>
          <el-table-column label="内容摘要" min-width="280">
            <template #default="{ row }">
              <div class="prompt-summary">{{ row.summary || '(空)' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="长度" width="90">
            <template #default="{ row }">{{ row.length }} 字</template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ fmtDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="run(remove(row))">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">还没有群专属提示词，所有群均使用默认人格提示词</p>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h2>群白名单参考</h2>
          <span class="muted">以下群已接入机器人，可为它们配置专属提示词</span>
        </div>
        <div class="chips" v-if="whitelisted.length">
          <span class="chip" v-for="gid in whitelisted" :key="gid">
            {{ gid }}
            <el-tag v-if="items.some(i => i.group_id === gid)" size="small" type="success" effect="plain">专属</el-tag>
            <el-tag v-else size="small" type="info" effect="plain">默认</el-tag>
          </span>
        </div>
        <p v-else class="empty-tip">群白名单为空</p>
      </div>

      <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? ('编辑群提示词 · ' + dialog.group_id) : '新增群提示词'"
        width="880px" top="6vh" destroy-on-close>
        <el-form label-position="top">
          <div class="form-grid">
            <el-form-item label="群号">
              <el-input v-model.number="dialog.group_id" type="number" :disabled="dialog.isEdit" placeholder="QQ 群号" />
            </el-form-item>
            <el-form-item label="备注名（可选）">
              <el-input v-model="dialog.name" maxlength="100" placeholder="例如：摸鱼群、测试群" />
            </el-form-item>
          </div>
        </el-form>
        <div class="toolbar" style="margin-bottom:10px">
          <span class="muted">纯文本编辑 · Ctrl+S 保存，内容会原样作为系统提示词</span>
          <span class="spacer"></span>
          <el-button size="small" @click="copyDefault">填入默认提示词</el-button>
        </div>
        <el-input v-model="dialog.prompt" type="textarea" :rows="18" resize="vertical"
          class="prompt-textarea" placeholder="在这里输入这个群专属的系统提示词..." />
        <template #footer>
          <el-button @click="dialog.visible = false">取消</el-button>
          <el-button type="primary" @click="run(save())">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `,
};
