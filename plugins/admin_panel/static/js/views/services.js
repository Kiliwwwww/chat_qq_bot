import { api, toast, run, confirmAction } from "../api.js";

export default {
  name: "ServicesView",
  setup() {
    const { ref, reactive, computed, onMounted } = Vue;

    const data = ref({ services: [], active: null });
    const editingId = ref(null);
    const form = reactive({ name: "", api_key: "", base_url: "", model: "" });

    const activeService = computed(() => {
      const d = data.value || { services: [], active: null };
      return d.services.find((item) => item.id === d.active) || null;
    });

    const formTitle = computed(() =>
      editingId.value ? `编辑 AI 服务 #${editingId.value}` : "新增 AI 服务"
    );

    function resetForm() {
      editingId.value = null;
      form.name = "";
      form.api_key = "";
      form.base_url = "";
      form.model = "";
    }

    function fillForm(service) {
      editingId.value = service.id;
      form.name = service.name || "";
      form.base_url = service.base_url || "";
      form.model = service.model || "";
      form.api_key = "";
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    async function submit() {
      const payload = {
        name: form.name.trim(),
        api_key: form.api_key.trim(),
        base_url: form.base_url.trim(),
        model: form.model.trim(),
      };
      if (!payload.name || !payload.base_url || !payload.model) {
        toast("名称、接口地址和模型都不能为空", "error");
        return;
      }
      if (!editingId.value && !payload.api_key) {
        toast("新增服务时必须填写 API Key", "error");
        return;
      }
      if (editingId.value) {
        if (!payload.api_key) delete payload.api_key;
        data.value = await api(`/admin/api/ai-services/${editingId.value}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast("AI 服务已更新", "ok");
      } else {
        data.value = await api("/admin/api/ai-services", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast("AI 服务已添加", "ok");
      }
      resetForm();
    }

    async function activate(service) {
      const confirmed = await confirmAction("切换到这个 AI 服务？机器人会立即重新初始化。", {
        title: "切换 AI 服务",
        confirmText: "切换",
        danger: false,
      });
      if (!confirmed) return;
      data.value = await api(`/admin/api/ai-services/${service.id}/activate`, { method: "POST" });
      toast("已切换 AI 服务", "ok");
    }

    async function remove(service) {
      const confirmed = await confirmAction("删除后无法恢复，确定删除这个 AI 服务？", {
        title: "删除 AI 服务",
        confirmText: "删除",
      });
      if (!confirmed) return;
      data.value = await api(`/admin/api/ai-services/${service.id}`, { method: "DELETE" });
      toast("AI 服务已删除", "ok");
      if (editingId.value === service.id) resetForm();
    }

    onMounted(async () => {
      data.value = await api("/admin/api/ai-services");
    });

    return { data, form, editingId, formTitle, activeService, submit, resetForm, fillForm, activate, remove, run };
  },
  template: `
    <div>
      <div class="grid-2">
        <div class="panel">
          <div class="panel-head"><h2>{{ formTitle }}</h2></div>
          <el-form label-position="top" @submit.prevent>
            <div class="form-grid">
              <el-form-item label="名称">
                <el-input v-model="form.name" placeholder="例如：小米 AI" />
              </el-form-item>
              <el-form-item label="API Key">
                <el-input v-model="form.api_key" type="password" show-password autocomplete="off"
                  :placeholder="editingId ? '留空表示不修改原 Key' : '必填'" />
              </el-form-item>
              <el-form-item label="接口地址">
                <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" />
              </el-form-item>
              <el-form-item label="模型">
                <el-input v-model="form.model" placeholder="mimo-v2.5" />
              </el-form-item>
            </div>
            <div class="toolbar" style="margin-bottom:0">
              <el-button type="primary" @click="run(submit())">保存</el-button>
              <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
            </div>
          </el-form>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>当前使用</h2></div>
          <template v-if="activeService">
            <div style="font-size:16px;font-weight:600;margin-bottom:8px">{{ activeService.name }}</div>
            <div class="kv-row"><span class="kv-label">模型</span><span class="kv-value mono">{{ activeService.model }}</span></div>
            <div class="kv-row"><span class="kv-label">接口地址</span><span class="kv-value mono">{{ activeService.base_url }}</span></div>
            <div class="kv-row"><span class="kv-label">Key</span><span class="kv-value mono">{{ activeService.key_masked || '未配置' }}</span></div>
          </template>
          <p v-else class="empty-tip">数据库中没有激活的服务，当前使用 .env 配置</p>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head"><h2>服务列表</h2></div>
        <el-table :data="data.services || []" v-if="(data.services || []).length">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="名称" min-width="120" />
          <el-table-column label="模型" min-width="110"><template #default="{ row }"><span class="mono">{{ row.model }}</span></template></el-table-column>
          <el-table-column label="地址" min-width="180"><template #default="{ row }"><span class="mono">{{ row.base_url }}</span></template></el-table-column>
          <el-table-column label="Key" min-width="130"><template #default="{ row }"><span class="mono">{{ row.key_masked || '未配置' }}</span></template></el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="success" size="small">使用中</el-tag>
              <el-tag v-else type="info" size="small">备用</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="fillForm(row)">编辑</el-button>
              <el-button v-if="!row.is_active" size="small" @click="run(activate(row))">启用</el-button>
              <el-button v-if="!row.is_active" size="small" type="danger" @click="run(remove(row))">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">暂无 AI 服务配置</p>
      </div>
      <p class="hint">切换后机器人会立即重新初始化 AI 服务，不需要重启进程。</p>
    </div>
  `,
};
