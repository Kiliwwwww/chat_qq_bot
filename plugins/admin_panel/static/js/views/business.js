import { api, toast, run, confirmAction } from "../api.js";

export default {
  name: "BusinessView",
  setup() {
    const { ref, reactive, onMounted } = Vue;

    const business = ref(null);
    const groups = ref([]);
    const botOnline = ref(true);
    const sendForm = reactive({ group_id: null, message: "" });

    const welcomeDialog = reactive({ visible: false, group_id: null, message: "" });

    async function load() {
      const [data, groupData] = await Promise.all([
        api("/admin/api/business"),
        api("/admin/api/groups").catch(() => ({ groups: [], bot_online: false })),
      ]);
      business.value = data;
      groups.value = groupData.groups || [];
      botOnline.value = !!groupData.bot_online;
    }

    async function mutate(path, method, body) {
      business.value = await api(path, {
        method,
        body: body ? JSON.stringify(body) : undefined,
      });
      toast("已保存", "ok");
    }

    function removePath(path) {
      return mutate(path, "DELETE");
    }

    async function removeItem(message, path) {
      const confirmed = await confirmAction(message, {
        title: "移除确认",
        confirmText: "移除",
      });
      if (!confirmed) return;
      await removePath(path);
    }

    function groupLabel(item) {
      if (item.group_name) {
        return `${item.group_name} (${item.group_id})`;
      }
      return `未命名群 (${item.group_id})`;
    }

    async function sendMessage() {
      let groupId = Number(sendForm.group_id);
      if (!groupId && /^\d+$/.test(String(sendForm.group_id || "").trim())) {
        groupId = Number(String(sendForm.group_id).trim());
      }
      const message = (sendForm.message || "").trim();
      if (!groupId) {
        toast("请选择要发送的群", "error");
        return;
      }
      if (!message) {
        toast("请输入要发送的内容", "error");
        return;
      }
      await api("/admin/api/send-group", {
        method: "POST",
        body: JSON.stringify({ group_id: groupId, message }),
      });
      toast("已发送", "ok");
      sendForm.message = "";
    }

    async function reloadGroups() {
      const groupData = await api("/admin/api/groups");
      groups.value = groupData.groups || [];
      botOnline.value = !!groupData.bot_online;
      toast("群列表已刷新", "ok");
    }

    function openWelcomeEdit(item) {
      welcomeDialog.group_id = item.group_id;
      welcomeDialog.message = item.message;
      welcomeDialog.visible = true;
    }

    async function saveWelcome() {
      const message = (welcomeDialog.message || "").trim();
      if (!message) {
        toast("欢迎语不能为空", "error");
        return;
      }
      await mutate("/admin/api/welcome", "PUT", {
        group_id: welcomeDialog.group_id,
        message,
      });
      welcomeDialog.visible = false;
    }

    const forms = {
      user: (fd) => ({ path: "/admin/api/whitelist/users", method: "POST", body: { user_id: Number(fd.user_id) } }),
      group: (fd) => ({ path: "/admin/api/whitelist/groups", method: "POST", body: { group_id: Number(fd.group_id) } }),
      welcome: (fd) => ({
        path: "/admin/api/welcome",
        method: "PUT",
        body: { group_id: Number(fd.group_id), message: String(fd.message || "") },
      }),
      "ad-keyword": (fd) => ({ path: "/admin/api/ad-keywords", method: "POST", body: { keyword: String(fd.keyword || "").trim() } }),
      "ad-recall": (fd) => ({ path: "/admin/api/ad-recall-groups", method: "POST", body: { group_id: Number(fd.group_id) } }),
      kb: (fd) => ({
        path: "/admin/api/kb-groups",
        method: "PUT",
        body: { group_id: Number(fd.group_id), kb_id: String(fd.kb_id || "").trim() },
      }),
      keyword: (fd) => ({ path: "/admin/api/keywords", method: "POST", body: { content: String(fd.content || "").trim() } }),
    };

    const inlineForms = reactive({
      user: { user_id: null },
      group: { group_id: null },
      welcome: { group_id: null, message: "" },
      "ad-keyword": { keyword: "" },
      "ad-recall": { group_id: null },
      kb: { group_id: null, kb_id: "" },
      keyword: { content: "" },
    });

    async function submitInline(kind) {
      const build = forms[kind];
      if (!build) return;
      const { path, method, body } = build(inlineForms[kind]);
      await mutate(path, method, body);
      Object.assign(inlineForms[kind], {
        user_id: null,
        group_id: null,
        message: "",
        keyword: "",
        kb_id: "",
        content: "",
      });
    }

    onMounted(() => run(load()));

    return {
      business,
      groups,
      botOnline,
      sendForm,
      welcomeDialog,
      inlineForms,
      load,
      groupLabel,
      sendMessage,
      reloadGroups,
      openWelcomeEdit,
      saveWelcome,
      submitInline,
      removeItem,
      run,
    };
  },
  template: `
    <div v-if="business">
      <div class="panel">
        <div class="panel-head">
          <h2>发送群消息</h2>
          <span class="muted">手动向指定 QQ 群发送文本消息</span>
        </div>
        <div class="inline-form">
          <el-select v-model="sendForm.group_id" filterable allow-create default-first-option
            placeholder="输入群名/群号搜索" style="width:280px">
            <el-option v-for="item in groups" :key="item.group_id" :value="item.group_id" :label="groupLabel(item)" />
          </el-select>
          <el-input v-model="sendForm.message" type="textarea" :rows="2" placeholder="要发送的文本内容" style="flex:1;min-width:260px" />
          <el-button type="primary" @click="run(sendMessage())">发送</el-button>
          <el-button @click="run(reloadGroups())">刷新群列表</el-button>
          <span class="muted">{{ botOnline ? '已获取机器人所在群列表' : '机器人未在线，仅显示白名单群' }}</span>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-head">
            <h2>私聊白名单</h2>
            <span class="muted">只有这些 QQ 可以私聊机器人</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('user')">
            <el-input v-model.number="inlineForms.user.user_id" type="number" placeholder="QQ 号" style="width:200px" />
            <el-button type="primary" native-type="submit">添加用户</el-button>
          </form>
          <div class="chips">
            <el-tag v-for="id in business.users" :key="id" closable @close="run(removeItem('移除该用户白名单？', '/admin/api/whitelist/users/' + id))">
              {{ id }}
            </el-tag>
            <span v-if="!business.users.length" class="muted">暂无</span>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <h2>群白名单</h2>
            <span class="muted">机器人只在这些群里工作</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('group')">
            <el-input v-model.number="inlineForms.group.group_id" type="number" placeholder="群号" style="width:200px" />
            <el-button type="primary" native-type="submit">添加群</el-button>
          </form>
          <div class="chips">
            <el-tag v-for="id in business.groups" :key="id" closable @close="run(removeItem('移除该群白名单？', '/admin/api/whitelist/groups/' + id))">
              {{ id }}
            </el-tag>
            <span v-if="!business.groups.length" class="muted">暂无</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h2>群欢迎语</h2>
          <span class="muted">新成员入群时自动发送</span>
        </div>
        <form class="inline-form" @submit.prevent="submitInline('welcome')">
          <el-input v-model.number="inlineForms.welcome.group_id" type="number" placeholder="群号" style="width:160px" />
          <el-input v-model="inlineForms.welcome.message" placeholder="欢迎语内容" style="width:320px" />
          <el-button type="primary" native-type="submit">保存欢迎语</el-button>
        </form>
        <el-table :data="business.welcome" v-if="business.welcome.length">
          <el-table-column label="群号" width="140"><template #default="{ row }"><span class="mono">{{ row.group_id }}</span></template></el-table-column>
          <el-table-column prop="message" label="欢迎语" min-width="280" show-overflow-tooltip />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openWelcomeEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="run(removeItem('删除该群欢迎语？', '/admin/api/welcome/' + row.group_id))">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-tip">暂无欢迎语</p>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-head">
            <h2>广告关键词</h2>
            <span class="muted">命中后会触发广告撤回判断</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('ad-keyword')">
            <el-input v-model="inlineForms['ad-keyword'].keyword" placeholder="新增广告关键词" style="width:220px" />
            <el-button type="primary" native-type="submit">添加关键词</el-button>
          </form>
          <div class="chips">
            <el-tag v-for="item in business.ad_keywords" :key="item.id" closable
              @close="run(removeItem('删除该广告关键词？', '/admin/api/ad-keywords/' + item.id))">
              {{ item.keyword }}
            </el-tag>
            <span v-if="!business.ad_keywords.length" class="muted">暂无</span>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <h2>广告撤回群</h2>
            <span class="muted">这些群会开启广告检测与自动撤回</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('ad-recall')">
            <el-input v-model.number="inlineForms['ad-recall'].group_id" type="number" placeholder="群号" style="width:200px" />
            <el-button type="primary" native-type="submit">开启撤回</el-button>
          </form>
          <div class="chips">
            <el-tag v-for="id in business.ad_recall_groups" :key="id" closable
              @close="run(removeItem('关闭该群的广告撤回？', '/admin/api/ad-recall-groups/' + id))">
              {{ id }}
            </el-tag>
            <span v-if="!business.ad_recall_groups.length" class="muted">暂无</span>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-head">
            <h2>知识库群绑定</h2>
            <span class="muted">群聊记录会入库到对应 RAGFlow 知识库</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('kb')">
            <el-input v-model.number="inlineForms.kb.group_id" type="number" placeholder="群号" style="width:150px" />
            <el-input v-model="inlineForms.kb.kb_id" placeholder="RAGFlow 知识库 ID" style="width:220px" />
            <el-button type="primary" native-type="submit">保存绑定</el-button>
          </form>
          <el-table :data="business.kb_groups" v-if="business.kb_groups.length">
            <el-table-column label="群号" width="130"><template #default="{ row }"><span class="mono">{{ row.group_id }}</span></template></el-table-column>
            <el-table-column label="知识库 ID" min-width="180"><template #default="{ row }"><span class="mono">{{ row.kb_id }}</span></template></el-table-column>
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="run(removeItem('移除该知识库绑定？', '/admin/api/kb-groups/' + row.group_id))">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-else class="empty-tip">暂无绑定</p>
        </div>

        <div class="panel">
          <div class="panel-head">
            <h2>全局提示词片段</h2>
            <span class="muted">对话时追加到系统提示词的关键词提示</span>
          </div>
          <form class="inline-form" @submit.prevent="submitInline('keyword')">
            <el-input v-model="inlineForms.keyword.content" placeholder="新增提示词内容" style="width:280px" />
            <el-button type="primary" native-type="submit">添加提示词</el-button>
          </form>
          <el-table :data="business.keywords" v-if="business.keywords.length">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button size="small" type="danger" @click="run(removeItem('删除该提示词？', '/admin/api/keywords/' + row.id))">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-else class="empty-tip">暂无提示词</p>
        </div>
      </div>

      <el-dialog v-model="welcomeDialog.visible" :title="'编辑群欢迎语 · ' + welcomeDialog.group_id" width="560px">
        <el-input v-model="welcomeDialog.message" type="textarea" :rows="6" placeholder="新成员入群时自动发送的内容" />
        <template #footer>
          <el-button @click="welcomeDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="run(saveWelcome())">保存</el-button>
        </template>
      </el-dialog>
    </div>
    <div v-else class="panel"><p class="empty-tip">加载中...</p></div>
  `,
};
