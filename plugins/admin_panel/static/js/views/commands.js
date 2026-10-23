import { api, run } from "../api.js";

const PERMISSION_TYPES = {
  "所有人": "success",
  "管理员": "danger",
  "管理员或群管理员": "warning",
  "白名单用户": "info",
  "所有人（查看）/ 管理员（修改）": "warning",
};

export default {
  name: "CommandsView",
  setup() {
    const { ref, computed, onMounted } = Vue;

    const data = ref({ groups: [], notes: [], total: 0 });
    const keyword = ref("");

    const filteredGroups = computed(() => {
      const needle = keyword.value.trim().toLowerCase();
      const groups = [];
      for (const group of data.value.groups || []) {
        const commands = (group.commands || []).filter((item) => {
          if (!needle) return true;
          const haystack = [
            item.command,
            (item.aliases || []).join(" "),
            item.usage,
            item.description,
            item.notes,
            item.scope,
            item.permission,
          ].join(" ").toLowerCase();
          return haystack.includes(needle);
        });
        if (commands.length) {
          groups.push(Object.assign({}, group, { commands }));
        }
      }
      return groups;
    });

    const filteredCount = computed(() =>
      filteredGroups.value.reduce((sum, group) => sum + group.commands.length, 0)
    );

    function permissionType(value) {
      return PERMISSION_TYPES[value] || "info";
    }

    function commandText(item) {
      return item.keyword ? item.command : "/" + item.command;
    }

    function aliasText(item) {
      return (item.aliases || []).map((alias) => "/" + alias).join(" / ");
    }

    async function load() {
      data.value = await api("/admin/api/commands");
    }

    onMounted(() => {
      run(load());
    });

    return {
      data,
      keyword,
      filteredGroups,
      filteredCount,
      permissionType,
      commandText,
      aliasText,
      run,
    };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head">
          <h2>命令帮助</h2>
          <el-tag type="info">共 {{ data.total }} 条</el-tag>
        </div>
        <p class="hint" style="margin-top:0">
          这里汇总了机器人当前注册的全部聊天命令。搜索支持命令、别名、用法、说明和权限。
        </p>
        <el-input v-model="keyword" clearable placeholder="搜索命令、别名、用法或说明"
          style="max-width:420px" />
        <div class="toolbar" style="margin-top:10px">
          <span class="muted">当前显示 {{ filteredCount }} / {{ data.total }} 条</span>
        </div>
        <div class="chips" style="margin-top:4px" v-if="(data.notes || []).length">
          <span class="chip" v-for="note in data.notes" :key="note">{{ note }}</span>
        </div>
      </div>

      <div class="panel" v-if="keyword && !filteredGroups.length">
        <p class="empty-tip">没有找到匹配的命令</p>
      </div>

      <div class="panel" v-for="group in filteredGroups" :key="group.name">
        <div class="panel-head">
          <h2>{{ group.name }}</h2>
          <span class="muted">{{ group.commands.length }} 条</span>
        </div>
        <p class="hint" style="margin-top:0" v-if="group.description">{{ group.description }}</p>
        <el-table :data="group.commands">
          <el-table-column label="命令" min-width="170">
            <template #default="{ row }">
              <span class="mono">{{ commandText(row) }}</span>
              <div v-if="row.aliases && row.aliases.length" class="muted" style="font-size:12px">
                别名：{{ aliasText(row) }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="用法" min-width="250">
            <template #default="{ row }"><span class="mono">{{ row.usage }}</span></template>
          </el-table-column>
          <el-table-column label="说明" min-width="260">
            <template #default="{ row }">
              <div>{{ row.description }}</div>
              <div v-if="row.notes" class="muted" style="font-size:12px">{{ row.notes }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="scope" label="场景" width="110" />
          <el-table-column label="权限" width="170">
            <template #default="{ row }">
              <el-tag :type="permissionType(row.permission)" size="small">{{ row.permission }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  `,
};
