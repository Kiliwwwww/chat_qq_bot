import { api, toast, run, confirmAction, fmtDate } from "../api.js";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

function parseJson(text, fallback) {
  const value = (text || "").trim();
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch (error) {
    throw new Error(`JSON 格式错误：${error.message}`);
  }
}

export default {
  name: "SkillsView",
  setup() {
    const { ref, reactive, onMounted } = Vue;

    const items = ref([]);
    const loading = ref(false);
    const editingId = ref(null);
    const dialogVisible = ref(false);
    const reservedNames = ref([]);

    const form = reactive({
      name: "",
      title: "",
      description: "",
      type: "prompt",
      content: "",
      scope: "global",
      group_id: null,
      enabled: true,
      method: "GET",
      url: "",
      headers: "{}",
      body: "",
      timeout: 15,
      max_length: 2000,
      params: [],
    });

    async function load() {
      loading.value = true;
      try {
        const data = await api("/admin/api/skills");
        items.value = data.skills || [];
        reservedNames.value = data.reserved_names || [];
      } finally {
        loading.value = false;
      }
    }

    function resetForm() {
      editingId.value = null;
      form.name = "";
      form.title = "";
      form.description = "";
      form.type = "prompt";
      form.content = "";
      form.scope = "global";
      form.group_id = null;
      form.enabled = true;
      form.method = "GET";
      form.url = "";
      form.headers = "{}";
      form.body = "";
      form.timeout = 15;
      form.max_length = 2000;
      form.params = [];
    }

    function applyToolConfig(config) {
      form.method = (config.method || "GET").toUpperCase();
      form.url = config.url || "";
      form.headers = JSON.stringify(config.headers || {}, null, 2);
      form.body = config.body != null ? JSON.stringify(config.body, null, 2) : "";
      form.timeout = Number(config.timeout) || 15;
      form.max_length = Number(config.max_length) || 2000;
      const parameters = config.parameters || {};
      const properties = parameters.properties || {};
      const required = new Set(parameters.required || []);
      form.params = Object.entries(properties).map(([name, def]) => ({
        name,
        type: (def && def.type) || "string",
        description: (def && def.description) || "",
        required: required.has(name),
      }));
    }

    function openCreate() {
      resetForm();
      dialogVisible.value = true;
    }

    function openEdit(row) {
      resetForm();
      editingId.value = row.id;
      form.name = row.name || "";
      form.title = row.title || "";
      form.description = row.description || "";
      form.type = row.type || "prompt";
      form.content = row.content || "";
      form.scope = row.scope || "global";
      form.group_id = row.group_id || null;
      form.enabled = !!row.enabled;
      if (form.type === "tool") {
        let config = row.config;
        if (!config) {
          try {
            config = JSON.parse(row.content || "{}");
          } catch (error) {
            config = {};
          }
        }
        applyToolConfig(config);
      }
      dialogVisible.value = true;
    }

    function addParam() {
      form.params.push({ name: "", type: "string", description: "", required: false });
    }

    function buildToolContent() {
      const headers = parseJson(form.headers, {});
      if (!headers || typeof headers !== "object" || Array.isArray(headers)) {
        throw new Error("请求头必须是 JSON 对象");
      }
      const parameters = { type: "object", properties: {}, required: [] };
      for (const param of form.params) {
        const name = (param.name || "").trim();
        if (!name) continue;
        if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) {
          throw new Error(`参数名 ${name} 不合法，只能用英文、数字、下划线`);
        }
        parameters.properties[name] = {
          type: param.type || "string",
          description: (param.description || "").trim(),
        };
        if (param.required) parameters.required.push(name);
      }
      const config = {
        method: form.method,
        url: (form.url || "").trim(),
        headers,
        parameters,
        timeout: Number(form.timeout) || 15,
        max_length: Number(form.max_length) || 2000,
      };
      const bodyText = (form.body || "").trim();
      if (bodyText) config.body = parseJson(bodyText, null);
      return JSON.stringify(config, null, 2);
    }

    async function save() {
      const name = (form.name || "").trim();
      const title = (form.title || "").trim();
      if (!name || !title) {
        toast("标识和名称不能为空", "error");
        return;
      }
      if (!/^[A-Za-z0-9_-]+$/.test(name)) {
        toast("标识只能用英文、数字、下划线或短横线", "error");
        return;
      }
      if (form.scope === "group" && !Number(form.group_id)) {
        toast("作用域为指定群时必须填写群号", "error");
        return;
      }
      let content = "";
      if (form.type === "prompt") {
        content = (form.content || "").trim();
        if (!content) {
          toast("提示词内容不能为空", "error");
          return;
        }
      } else {
        content = buildToolContent();
      }
      const payload = {
        name,
        title,
        description: (form.description || "").trim(),
        type: form.type,
        content,
        scope: form.scope,
        group_id: form.scope === "group" ? Number(form.group_id) : null,
        enabled: !!form.enabled,
      };
      if (editingId.value) {
        await api(`/admin/api/skills/${editingId.value}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast("技能已更新", "ok");
      } else {
        await api("/admin/api/skills", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast("技能已创建", "ok");
      }
      dialogVisible.value = false;
      await load();
    }

    async function toggle(row) {
      try {
        await api(`/admin/api/skills/${row.id}/enabled`, {
          method: "PATCH",
          body: JSON.stringify({ enabled: !!row.enabled }),
        });
        toast(row.enabled ? "技能已启用" : "技能已停用", "ok");
      } catch (error) {
        row.enabled = !row.enabled;
        throw error;
      }
    }

    async function remove(row) {
      const confirmed = await confirmAction(
        `删除技能「${row.title}」后无法恢复，确定删除？`,
        { title: "删除技能", confirmText: "删除" }
      );
      if (!confirmed) return;
      await api(`/admin/api/skills/${row.id}`, { method: "DELETE" });
      toast("技能已删除", "ok");
      await load();
    }

    onMounted(() => {
      run(load());
    });

    return {
      items,
      loading,
      dialogVisible,
      editingId,
      reservedNames,
      form,
      methods: METHODS,
      load,
      openCreate,
      openEdit,
      addParam,
      save,
      toggle,
      remove,
      fmtDate,
      run,
    };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head">
          <h2>技能列表</h2>
          <el-button type="primary" @click="openCreate">
            <el-icon style="margin-right:4px"><Plus /></el-icon>新增技能
          </el-button>
        </div>
        <p class="hint" style="margin-top:0">
          提示词型技能会拼接到系统提示词末尾；HTTP 工具型技能会让 AI 在需要时主动调用外部接口。
          修改后下一条消息立即生效，无需重启。
        </p>
        <el-table :data="items" v-loading="loading" v-if="items.length">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column label="名称" min-width="150">
            <template #default="{ row }">
              <div>{{ row.title }}</div>
              <div class="mono" style="font-size:12px;opacity:.7">{{ row.name }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.type === 'tool'" type="warning" size="small">HTTP 工具</el-tag>
              <el-tag v-else type="primary" size="small">提示词</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="作用域" width="130">
            <template #default="{ row }">
              <span v-if="row.scope === 'global'">全局</span>
              <span v-else class="mono">群 {{ row.group_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="简介" min-width="220">
            <template #default="{ row }">
              <div class="prompt-summary">{{ row.description || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="run(toggle(row))" />
            </template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ fmtDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="run(remove(row))">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">还没有技能，点击右上角新增</p>
      </div>

      <el-dialog v-model="dialogVisible" :title="editingId ? ('编辑技能 #' + editingId) : '新增技能'"
        width="860px" top="6vh" destroy-on-close>
        <el-form label-position="top">
          <div class="form-grid">
            <el-form-item label="名称">
              <el-input v-model="form.title" maxlength="100" placeholder="例如：查天气" />
            </el-form-item>
            <el-form-item label="标识">
              <el-input v-model="form.name" :disabled="!!editingId" maxlength="64"
                placeholder="英文/数字/下划线，如 weather" />
            </el-form-item>
          </div>
          <el-form-item label="简介（告诉 AI 什么时候使用）">
            <el-input v-model="form.description" type="textarea" :rows="2" maxlength="1000"
              placeholder="例如：用户询问天气、气温、是否下雨时使用" />
          </el-form-item>
          <div class="form-grid">
            <el-form-item label="类型">
              <el-radio-group v-model="form.type">
                <el-radio-button label="prompt">提示词型</el-radio-button>
                <el-radio-button label="tool">HTTP 工具型</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="作用域">
              <el-radio-group v-model="form.scope">
                <el-radio-button label="global">全局</el-radio-button>
                <el-radio-button label="group">指定群</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </div>
          <el-form-item v-if="form.scope === 'group'" label="群号">
            <el-input v-model.number="form.group_id" type="number" placeholder="QQ 群号，可在业务数据页查看" />
          </el-form-item>

          <template v-if="form.type === 'prompt'">
            <el-form-item label="技能内容（Markdown）">
              <el-input v-model="form.content" type="textarea" :rows="12" resize="vertical"
                placeholder="写清楚触发场景、处理步骤和输出要求..." />
            </el-form-item>
          </template>

          <template v-else>
            <div class="form-grid">
              <el-form-item label="请求方法">
                <el-select v-model="form.method">
                  <el-option v-for="method in methods" :key="method" :label="method" :value="method" />
                </el-select>
              </el-form-item>
              <el-form-item label="请求地址">
                <el-input v-model="form.url" placeholder="https://api.example.com/weather?city={city}" />
              </el-form-item>
            </div>
            <el-form-item label="请求头（JSON 对象，可选）">
              <el-input v-model="form.headers" type="textarea" :rows="3"
                placeholder='{"Authorization": "Bearer xxx"}' />
            </el-form-item>
            <el-form-item label="请求体（JSON，可选，GET 请求会忽略）">
              <el-input v-model="form.body" type="textarea" :rows="4"
                placeholder='{"city": "{city}"}' />
            </el-form-item>
            <div class="form-grid">
              <el-form-item label="超时（秒）">
                <el-input-number v-model="form.timeout" :min="1" :max="120" />
              </el-form-item>
              <el-form-item label="结果最大长度（字符）">
                <el-input-number v-model="form.max_length" :min="200" :max="8000" :step="100" />
              </el-form-item>
            </div>
            <el-form-item label="参数定义（供 AI 填写，地址/请求头/请求体里用 {参数名} 占位）">
              <div v-for="(param, index) in form.params" :key="index"
                style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
                <el-input v-model="param.name" placeholder="参数名" style="width:150px" />
                <el-select v-model="param.type" style="width:120px">
                  <el-option label="string" value="string" />
                  <el-option label="number" value="number" />
                  <el-option label="integer" value="integer" />
                  <el-option label="boolean" value="boolean" />
                </el-select>
                <el-input v-model="param.description" placeholder="参数说明" style="flex:1" />
                <el-checkbox v-model="param.required">必填</el-checkbox>
                <el-button size="small" type="danger" text @click="form.params.splice(index, 1)">删除</el-button>
              </div>
              <el-button size="small" @click="addParam">添加参数</el-button>
            </el-form-item>
            <p class="hint" style="margin-top:0">
              内置工具名不可占用：{{ reservedNames.join('、') }}
            </p>
          </template>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="run(save())">保存</el-button>
        </template>
      </el-dialog>
    </div>
  `,
};
