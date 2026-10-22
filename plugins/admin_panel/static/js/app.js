import {
  api, session, fetchSession, setUnauthorizedHandler,
  toast, run,
} from "./api.js";
import { currentView, navigate, onRouteChange, viewPaths } from "./router.js";

import OverviewView from "./views/overview.js";
import ReportsView from "./views/reports.js";
import ChecksView from "./views/checks.js";
import ServicesView from "./views/services.js";
import BusinessView from "./views/business.js";
import PromptsView from "./views/prompts.js";
import LogsView from "./views/logs.js";
import TasksView from "./views/tasks.js";
import ConfigView from "./views/config.js";

const { createApp, ref, reactive, computed, onMounted } = Vue;

const VIEWS = {
  overview: OverviewView,
  reports: ReportsView,
  checks: ChecksView,
  services: ServicesView,
  business: BusinessView,
  prompts: PromptsView,
  logs: LogsView,
  tasks: TasksView,
  config: ConfigView,
};

const VIEW_META = {
  overview: { title: "运行概览", subtitle: "机器人、系统与外部服务状态", icon: "Monitor" },
  reports: { title: "数据报表", subtitle: "群活跃、AI 调用与开箱/修仙运营数据", icon: "TrendCharts" },
  checks: { title: "API Key 体检", subtitle: "检测当前配置的密钥与服务连通性", icon: "CircleCheck" },
  services: { title: "AI 服务", subtitle: "管理数据库中的多个 AI 服务配置", icon: "MagicStick" },
  business: { title: "业务数据", subtitle: "白名单、欢迎语、广告词与知识库群", icon: "Operation" },
  prompts: { title: "提示词管理", subtitle: "每个群的专属系统提示词，未配置则使用默认人格", icon: "EditPen" },
  logs: { title: "日志与记录", subtitle: "查看运行日志和群聊记录", icon: "Document" },
  tasks: { title: "任务与表情包", subtitle: "定时任务、手动操作与表情包库统计", icon: "Timer" },
  config: { title: "配置与备份", subtitle: "只读配置速览与数据库备份", icon: "Tools" },
};

const NAV_ORDER = [
  "overview", "reports", "checks", "services",
  "business", "prompts", "logs", "tasks", "config",
];

const app = createApp({
  setup() {
    const view = ref(currentView());
    const viewKey = ref(0);
    const loginForm = reactive({ password: "" });
    const loginError = ref("");
    const loggingIn = ref(false);
    const connState = computed(() => {
      if (!session.authenticated) return { cls: "bad", text: "未登录" };
      return { cls: "ok", text: "已登录" };
    });

    const currentMeta = computed(() => VIEW_META[view.value] || VIEW_META.overview);
    const currentComponent = computed(() => VIEWS[view.value] || OverviewView);

    function navigateTo(target) {
      if (!VIEWS[target]) target = "overview";
      navigate(target);
      view.value = target;
      viewKey.value += 1;
    }

    function refresh() {
      viewKey.value += 1;
    }

    function showLogin() {
      session.authenticated = false;
      loginForm.password = "";
    }

    async function doLogin() {
      loggingIn.value = true;
      loginError.value = "";
      try {
        const response = await fetch("/admin/api/login", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Admin-Request": "1" },
          body: JSON.stringify({ password: loginForm.password }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.detail || `登录失败 (${response.status})`);
        }
        session.authenticated = true;
        loginForm.password = "";
        viewKey.value += 1;
      } catch (error) {
        loginError.value = error.message || String(error);
      } finally {
        loggingIn.value = false;
      }
    }

    async function doLogout() {
      try {
        await api("/admin/api/logout", { method: "POST" });
      } catch (error) {
        // ignore
      }
      session.authenticated = false;
    }

    onMounted(async () => {
      setUnauthorizedHandler(showLogin);
      window.addEventListener("admin-unauthorized", showLogin);
      onRouteChange((target) => {
        view.value = target;
        viewKey.value += 1;
      });
      try {
        const data = await fetchSession();
        session.enabled = data.enabled;
        session.password_configured = data.password_configured;
        session.authenticated = data.authenticated;
      } catch (error) {
        toast(error.message, "error");
      }
      if (session.authenticated && window.location.pathname === "/admin") {
        navigate("overview", true);
      }
    });

    return {
      session,
      view,
      viewKey,
      navItems: NAV_ORDER.map((key) => ({ key, ...VIEW_META[key] })),
      currentMeta,
      currentComponent,
      loginForm,
      loginError,
      loggingIn,
      connState,
      navigateTo,
      refresh,
      doLogin,
      doLogout,
      run,
    };
  },
  template: `
    <div v-if="!session.authenticated" class="login-wrap">
      <div class="login-card">
        <div class="brand-mark">QQ BOT · ADMIN</div>
        <h1>管理面板</h1>
        <p class="sub">
          {{ session.enabled ? (session.password_configured ? '请输入管理密码' : '尚未配置 admin_panel_password，请在 .env 中设置后重启') : '管理面板未启用（admin_panel_enabled=false）' }}
        </p>
        <el-form @submit.prevent>
          <el-form-item>
            <el-input v-model="loginForm.password" type="password" show-password
              placeholder="管理密码" :disabled="!session.enabled || !session.password_configured"
              @keyup.enter="run(doLogin())" />
          </el-form-item>
          <el-button type="primary" :loading="loggingIn"
            :disabled="!session.enabled || !session.password_configured"
            @click="run(doLogin())">登录</el-button>
        </el-form>
        <p v-if="loginError" style="color:var(--bad);margin:12px 0 0;font-size:13px">{{ loginError }}</p>
      </div>
    </div>

    <div v-else class="layout">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-dot"></span>
          <div>
            <strong>QQ Bot</strong>
            <small>管理面板</small>
          </div>
        </div>
        <el-menu class="side-menu" :default-active="view" @select="navigateTo">
          <el-menu-item v-for="item in navItems" :key="item.key" :index="item.key">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </el-menu>
        <div class="sidebar-footer">
          <div class="conn" :class="connState.cls">
            <span class="dot"></span>
            <span>{{ connState.text }}</span>
          </div>
          <el-button size="small" @click="run(doLogout())">退出登录</el-button>
        </div>
      </aside>

      <main class="main">
        <header class="topbar">
          <div>
            <h1>{{ currentMeta.title }}</h1>
            <p class="sub">{{ currentMeta.subtitle }}</p>
          </div>
          <div class="topbar-actions">
            <el-button @click="refresh">刷新</el-button>
          </div>
        </header>
        <div class="page">
          <transition name="page-fade" mode="out-in">
            <component :is="currentComponent" :key="view + '-' + viewKey" @jump="navigateTo" />
          </transition>
        </div>
      </main>
    </div>
  `,
});

app.use(ElementPlus);
app.config.errorHandler = (error, instance, info) => {
  const name = (instance && instance.$options && instance.$options.name) || "unknown";
  console.error(`[admin] ${name} ${info}`, error);
};
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component);
}
app.mount("#app");
