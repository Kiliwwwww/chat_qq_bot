import {
  api, toast, run, fmtBytes, fetchSession, highlightHtml,
} from "../api.js";

export default {
  name: "LogsView",
  setup() {
    const { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } = Vue;

    const source = ref("logs");
    const mode = ref("live");
    const files = ref([]);
    const selectedLog = ref("");
    const fileSearch = ref("");
    const lines = ref(200);
    const keyword = ref("");
    const level = ref("");
    const autoScroll = ref(true);
    const liveStatus = ref("idle");
    const metaText = ref("");
    const logLines = ref([]);

    let stream = null;
    let retryTimer = null;
    let filterTimer = null;

    const statusMap = {
      idle: { label: "未连接", type: "info" },
      running: { label: "连接中", type: "warning" },
      ok: { label: "实时中", type: "success" },
      fail: { label: "连接中断", type: "danger" },
    };

    const statusInfo = computed(() => statusMap[liveStatus.value] || statusMap.idle);

    const filteredFiles = computed(() => {
      const query = fileSearch.value.trim().toLowerCase();
      return files.value.filter((file) => !query || file.name.toLowerCase().includes(query));
    });

    const displayLines = computed(() => {
      const key = keyword.value.trim().toLowerCase();
      const lv = source.value === "logs" ? level.value : "";
      return logLines.value
        .filter((line) => {
          if (lv && !line.toUpperCase().includes(lv)) return false;
          if (key && !line.toLowerCase().includes(key)) return false;
          return true;
        })
        .slice(-2000);
    });

    function lineHtml(line) {
      return highlightHtml(line, keyword.value.trim());
    }

    function renderMeta(extra) {
      if (extra) {
        metaText.value = extra;
        return;
      }
      const key = keyword.value.trim().toLowerCase();
      const lv = source.value === "logs" ? level.value : "";
      const filteredCount = logLines.value.filter((line) => {
        if (lv && !line.toUpperCase().includes(lv)) return false;
        if (key && !line.toLowerCase().includes(key)) return false;
        return true;
      }).length;
      const displayCount = displayLines.value.length;
      const modeText = mode.value === "live" ? "实时" : "全文";
      const suffix = filteredCount > displayCount ? ` · 仅显示最近 ${displayCount} 行` : "";
      const name = selectedLog.value || "未选择文件";
      metaText.value = `${name} · ${modeText} · 匹配 ${filteredCount} 行 / 缓存 ${logLines.value.length} 行${suffix}`;
    }

    async function scrollToBottomIfNear() {
      await nextTick();
      const content = document.getElementById("logContent");
      if (!content || !autoScroll.value) return;
      const nearBottom = content.scrollHeight - content.scrollTop - content.clientHeight < 80;
      if (nearBottom) content.scrollTop = content.scrollHeight;
    }

    function stopStream() {
      if (stream) {
        stream.close();
        stream = null;
      }
      clearTimeout(retryTimer);
      retryTimer = null;
      liveStatus.value = "idle";
    }

    async function loadFiles() {
      stopStream();
      const data = await api(`/admin/api/${source.value}/files`);
      files.value = data.files || [];
      const visible = filteredFiles.value;
      if (!visible.some((file) => file.name === selectedLog.value)) {
        selectedLog.value = visible.length ? visible[0].name : "";
      }
      logLines.value = [];
      metaText.value = "";
      if (selectedLog.value) await loadCurrent();
    }

    function refreshSelection() {
      const visible = filteredFiles.value;
      if (!visible.some((file) => file.name === selectedLog.value)) {
        selectedLog.value = visible.length ? visible[0].name : "";
      }
    }

    function startStream() {
      stopStream();
      const name = selectedLog.value;
      if (!name) {
        logLines.value = [];
        renderMeta("没有可实时读取的文件");
        return;
      }
      logLines.value = [];
      liveStatus.value = "running";
      const initial = Math.max(1, Math.min(5000, Number(lines.value) || 200));
      const query = new URLSearchParams({ initial_lines: String(initial) });
      const es = new EventSource(
        `/admin/api/${source.value}/stream/${encodeURIComponent(name)}?${query.toString()}`
      );
      stream = es;

      es.addEventListener("ready", () => {
        if (stream !== es) return;
        liveStatus.value = "ok";
        logLines.value = [];
      });
      es.addEventListener("initial", (event) => {
        if (stream !== es) return;
        try {
          const data = JSON.parse(event.data);
          logLines.value = Array.isArray(data.lines) ? data.lines : [];
          renderMeta();
          scrollToBottomIfNear();
        } catch (error) {
          liveStatus.value = "fail";
        }
      });
      es.addEventListener("lines", (event) => {
        if (stream !== es) return;
        try {
          const data = JSON.parse(event.data);
          if (Array.isArray(data.lines) && data.lines.length) {
            logLines.value = logLines.value.concat(data.lines).slice(-5000);
            renderMeta();
            scrollToBottomIfNear();
          }
        } catch (error) {
          liveStatus.value = "fail";
        }
      });
      es.addEventListener("reset", (event) => {
        if (stream !== es) return;
        logLines.value = [];
        try {
          const data = JSON.parse(event.data);
          toast(data.message || "日志文件已切换", "info");
        } catch (error) {
          toast("日志文件已切换", "info");
        }
      });
      es.addEventListener("error", () => {
        if (stream !== es) return;
        liveStatus.value = "fail";
        metaText.value = "日志流已断开，正在尝试重连";
        clearTimeout(retryTimer);
        retryTimer = setTimeout(async () => {
          if (stream !== es) return;
          try {
            const sessionData = await fetchSession();
            if (!sessionData.authenticated) {
              window.dispatchEvent(new CustomEvent("admin-unauthorized"));
            }
          } catch (error) {
            // ignore
          }
        }, 1500);
      });
    }

    async function loadFull() {
      stopStream();
      const name = selectedLog.value;
      if (!name) {
        logLines.value = [];
        renderMeta("没有可加载的文件");
        return;
      }
      const take = Math.max(1, Math.min(5000, Number(lines.value) || 200));
      const key = keyword.value.trim();
      const lv = source.value === "logs" ? level.value : "";
      const query = new URLSearchParams({
        lines: String(take),
        keyword: key,
        level: lv,
        full: "true",
      });
      liveStatus.value = "running";
      metaText.value = key || lv ? "正在全文件搜索..." : "正在读取文件末尾...";
      try {
        const data = await api(`/admin/api/${source.value}/file/${encodeURIComponent(name)}?${query.toString()}`);
        const text = data.content ? data.content.split("\n") : [];
        if (text.length && text[text.length - 1] === "") text.pop();
        logLines.value = text;
        const modeText = data.mode === "search" ? "全文搜索" : "全文";
        let truncatedText = "";
        if (data.mode === "search" && data.truncated) {
          truncatedText = ` · 仅显示最近 ${data.returned_lines} 条匹配`;
        } else if (data.mode !== "search" && data.truncated) {
          truncatedText = " · 已截取末尾 512KB";
        }
        renderMeta(`${name} · ${modeText} · 显示 ${data.returned_lines} 行 · 匹配 ${data.matched_lines} 行${truncatedText}`);
      } finally {
        liveStatus.value = "idle";
      }
    }

    function loadCurrent() {
      return mode.value === "live" ? startStream() : loadFull();
    }

    function switchMode(value) {
      mode.value = value;
      logLines.value = [];
      stopStream();
      run(loadCurrent());
    }

    function switchSource(value) {
      source.value = value;
      files.value = [];
      selectedLog.value = "";
      fileSearch.value = "";
      run(loadFiles());
    }

    function onKeywordInput() {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => {
        if (mode.value === "full" && selectedLog.value) {
          run(loadFull());
        } else {
          renderMeta();
        }
      }, mode.value === "full" ? 450 : 120);
    }

    function clearBuffer() {
      logLines.value = [];
      renderMeta();
    }

    onMounted(() => run(loadFiles()));
    onBeforeUnmount(() => {
      stopStream();
      clearTimeout(filterTimer);
    });

    return {
      source,
      mode,
      files,
      selectedLog,
      fileSearch,
      lines,
      keyword,
      level,
      autoScroll,
      liveStatus,
      statusInfo,
      metaText,
      filteredFiles,
      displayLines,
      logLines,
      lineHtml,
      loadFiles,
      loadFull,
      refreshSelection,
      loadCurrent,
      switchMode,
      switchSource,
      onKeywordInput,
      clearBuffer,
      stopStream,
      fmtBytes,
      run,
    };
  },
  template: `
    <div>
      <div class="panel">
        <div class="panel-head">
          <h2>日志查看</h2>
          <div class="toolbar" style="margin-bottom:0">
            <el-tag :type="statusInfo.type" size="small">{{ statusInfo.label }}</el-tag>
            <el-radio-group :model-value="mode" size="small" @change="switchMode">
              <el-radio-button value="live">实时</el-radio-button>
              <el-radio-button value="full">全文</el-radio-button>
            </el-radio-group>
            <el-radio-group :model-value="source" size="small" @change="switchSource">
              <el-radio-button value="logs">运行日志</el-radio-button>
              <el-radio-button value="chatlogs">聊天记录</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <div class="toolbar">
          <el-input v-model="fileSearch" placeholder="输入文件名筛选" style="width:200px" clearable @input="refreshSelection" />
          <el-select v-model="selectedLog" filterable placeholder="选择文件" style="width:300px" @change="run(loadCurrent())">
            <el-option v-for="file in filteredFiles" :key="file.name" :value="file.name"
              :label="file.name + ' (' + fmtBytes(file.size) + ')'" />
          </el-select>
          <el-input-number v-model="lines" :min="1" :max="5000" style="width:130px" />
          <span class="muted">{{ mode === 'live' ? '初始行数' : '行数' }}</span>
          <el-input v-model="keyword" placeholder="搜索关键字，支持高亮" style="width:220px" clearable @input="onKeywordInput" />
          <el-select v-if="source === 'logs'" v-model="level" style="width:120px" @change="run(loadCurrent())">
            <el-option value="" label="全部级别" />
            <el-option value="ERROR" label="ERROR" />
            <el-option value="WARNING" label="WARNING" />
            <el-option value="INFO" label="INFO" />
            <el-option value="DEBUG" label="DEBUG" />
          </el-select>
          <el-button v-if="mode === 'live'" type="primary" @click="run(loadCurrent())">开始实时</el-button>
          <el-button v-else type="primary" @click="run(loadFull())">加载全文</el-button>
          <el-button v-if="mode === 'live'" type="danger" @click="stopStream(); metaText = '已停止实时读取'">停止</el-button>
          <el-button @click="clearBuffer">清空显示</el-button>
          <span class="spacer"></span>
          <el-checkbox v-if="mode === 'live'" v-model="autoScroll">自动滚动</el-checkbox>
        </div>

        <p class="hint" style="margin-top:0">{{ metaText }}</p>
        <div id="logContent" class="log-view">
          <template v-if="displayLines.length">
            <div class="log-line" v-for="(line, index) in displayLines" :key="index" v-html="lineHtml(line)"></div>
          </template>
          <div v-else class="log-line system">
            {{ logLines.length ? '当前过滤条件下没有匹配的日志' : (mode === 'live' ? '等待新日志输出...' : '(空)') }}
          </div>
        </div>
      </div>
      <p class="hint">
        实时模式会持续接收新日志，适合盯着运行状态；全文模式无关键字时读取文件末尾快照，有关键字或级别时会在整个文件中搜索并返回最近匹配。实时模式最多保留最近 5000 行。
      </p>
    </div>
  `,
};
