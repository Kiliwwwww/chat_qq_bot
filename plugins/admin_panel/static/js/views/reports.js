import { api, fmtNumber, shortDate, run, toast } from "../api.js";

const COLORS = [
  "#58a6ff", "#3fb950", "#d29922", "#f85149",
  "#a371f7", "#39c5cf", "#ff7b72", "#79c0ff",
];

function reportBase() {
  return {
    backgroundColor: "transparent",
    color: COLORS,
    animationDuration: 450,
    textStyle: {
      color: "#b6c2cf",
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif',
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#1a2430",
      borderColor: "#263241",
      textStyle: { color: "#e6edf3" },
      axisPointer: { type: "shadow" },
    },
    legend: {
      top: 4,
      right: 8,
      textStyle: { color: "#8291a3" },
      itemWidth: 10,
      itemHeight: 8,
    },
    grid: { left: 10, right: 20, top: 42, bottom: 10, containLabel: true },
  };
}

function axisStyle(extra = {}) {
  return Object.assign(
    {
      axisLine: { lineStyle: { color: "#263241" } },
      axisTick: { show: false },
      axisLabel: { color: "#8291a3", fontSize: 11 },
      splitLine: { lineStyle: { color: "rgba(38, 50, 65, 0.55)" } },
    },
    extra
  );
}

function categoryAxis(data, extra = {}) {
  return Object.assign(
    {
      type: "category",
      data,
      boundaryGap: true,
      axisLine: { lineStyle: { color: "#263241" } },
      axisTick: { show: false },
      axisLabel: { color: "#8291a3", fontSize: 11 },
      splitLine: { show: false },
    },
    extra
  );
}

function valueAxis(extra = {}) {
  return Object.assign({ type: "value" }, axisStyle(), extra);
}

function emptyChartOption(text) {
  return {
    backgroundColor: "transparent",
    graphic: [
      {
        type: "text",
        left: "center",
        top: "middle",
        style: { text, fill: "#8291a3", fontSize: 13 },
      },
    ],
  };
}

export default {
  name: "ReportsView",
  setup() {
    const { ref, reactive, onMounted, onBeforeUnmount, nextTick } = Vue;

    const days = ref(7);
    const groupId = ref("all");
    const groupOptions = ref([]);
    const meta = ref("");
    const notes = ref("");
    const loading = ref(false);
    const cards = ref([]);
    const errors = ref([]);
    const charts = reactive({});

    const CHART_IDS = [
      "chart-group-daily", "chart-group-users", "chart-group-heatmap", "chart-group-ranking",
      "chart-ai-daily", "chart-ai-models", "chart-ai-hourly",
      "chart-lottery-daily", "chart-lottery-rarity",
      "chart-xiuxian-realm", "chart-xiuxian-battles",
    ];

    function renderChart(id, option) {
      const element = document.getElementById(id);
      if (!element || !window.echarts) return;
      if (charts[id]) {
        charts[id].dispose();
        delete charts[id];
      }
      const chart = window.echarts.init(element, null, { renderer: "canvas" });
      chart.setOption(option, true);
      charts[id] = chart;
    }

    function disposeCharts() {
      Object.keys(charts).forEach((id) => {
        charts[id].dispose();
        delete charts[id];
      });
    }

    function renderAll(group, ai, ops) {
      const groupDaily = group.daily || [];
      const dateLabels = groupDaily.map((item) => shortDate(item.date));

      renderChart("chart-group-daily", Object.assign(reportBase(), {
        xAxis: categoryAxis(dateLabels),
        yAxis: valueAxis(),
        series: [{
          name: "消息数",
          type: "bar",
          data: groupDaily.map((item) => item.count),
          barMaxWidth: 24,
          itemStyle: { color: "#58a6ff", borderRadius: [4, 4, 0, 0] },
        }],
      }));

      const topUsers = (group.top_users || []).slice(0, 10);
      if (topUsers.length) {
        renderChart("chart-group-users", Object.assign(reportBase(), {
          grid: { left: 10, right: 28, top: 16, bottom: 10, containLabel: true },
          xAxis: valueAxis(),
          yAxis: categoryAxis(topUsers.map((item) => item.name).reverse(), {
            axisLabel: { color: "#8291a3", fontSize: 11, width: 110, overflow: "truncate" },
          }),
          series: [{
            name: "发言数",
            type: "bar",
            data: topUsers.map((item) => item.count).reverse(),
            barMaxWidth: 18,
            itemStyle: { color: "#39c5cf", borderRadius: [0, 4, 4, 0] },
          }],
        }));
      } else {
        renderChart("chart-group-users", emptyChartOption("暂无发言数据"));
      }

      const heatmap = group.heatmap || [];
      const heatMax = Math.max(1, ...heatmap.map((item) => Number(item[2]) || 0));
      renderChart("chart-group-heatmap", Object.assign(reportBase(), {
        grid: { left: 48, right: 20, top: 12, bottom: 64, containLabel: false },
        tooltip: {
          trigger: "item",
          backgroundColor: "#1a2430",
          borderColor: "#263241",
          textStyle: { color: "#e6edf3" },
          formatter: (params) =>
            `${dateLabels[params.value[0]]} ${String(params.value[1]).padStart(2, "0")}:00<br/>消息 ${params.value[2]}`,
        },
        xAxis: categoryAxis(dateLabels, {
          splitArea: { show: true, areaStyle: { color: ["rgba(255,255,255,0.015)", "transparent"] } },
        }),
        yAxis: categoryAxis(Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0")), {
          splitArea: { show: true, areaStyle: { color: ["rgba(255,255,255,0.015)", "transparent"] } },
        }),
        visualMap: {
          min: 0,
          max: heatMax,
          calculable: true,
          orient: "horizontal",
          left: "center",
          bottom: 8,
          textStyle: { color: "#8291a3" },
          inRange: { color: ["#0f2639", "#1f6feb", "#3fb950"] },
        },
        series: [{
          name: "消息数",
          type: "heatmap",
          data: heatmap,
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.5)" } },
        }],
      }));

      const ranking = (group.group_ranking || []).slice(0, 10);
      if (ranking.length) {
        renderChart("chart-group-ranking", Object.assign(reportBase(), {
          xAxis: categoryAxis(ranking.map((item) => String(item.group_id))),
          yAxis: valueAxis(),
          series: [{
            name: "消息数",
            type: "bar",
            data: ranking.map((item) => item.count),
            barMaxWidth: 26,
            itemStyle: { color: "#a371f7", borderRadius: [4, 4, 0, 0] },
          }],
        }));
      } else {
        renderChart("chart-group-ranking", emptyChartOption("暂无群活跃数据"));
      }

      const aiDaily = ai.daily || [];
      renderChart("chart-ai-daily", Object.assign(reportBase(), {
        tooltip: {
          trigger: "axis",
          backgroundColor: "#1a2430",
          borderColor: "#263241",
          textStyle: { color: "#e6edf3" },
          axisPointer: { type: "cross" },
        },
        xAxis: categoryAxis(aiDaily.map((item) => shortDate(item.date))),
        yAxis: [valueAxis({ name: "次数" }), valueAxis({ name: "秒", splitLine: { show: false } })],
        series: [
          { name: "成功", type: "bar", stack: "total", data: aiDaily.map((item) => item.success), itemStyle: { color: "#3fb950" } },
          { name: "失败", type: "bar", stack: "total", data: aiDaily.map((item) => item.failure), itemStyle: { color: "#f85149" } },
          {
            name: "平均耗时",
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            symbolSize: 5,
            data: aiDaily.map((item) => item.average_latency),
            lineStyle: { color: "#d29922" },
            itemStyle: { color: "#d29922" },
          },
        ],
      }));

      const models = ai.models || [];
      if (models.length) {
        renderChart("chart-ai-models", Object.assign(reportBase(), {
          tooltip: {
            trigger: "item",
            backgroundColor: "#1a2430",
            borderColor: "#263241",
            textStyle: { color: "#e6edf3" },
          },
          series: [{
            name: "模型调用",
            type: "pie",
            radius: ["42%", "68%"],
            center: ["50%", "54%"],
            itemStyle: { borderColor: "#151d27", borderWidth: 2 },
            label: { color: "#b6c2cf" },
            data: models.map((item) => ({ name: item.model, value: item.count })),
          }],
        }));
      } else {
        renderChart("chart-ai-models", emptyChartOption("暂无模型调用数据"));
      }

      const aiHourly = ai.hourly || [];
      renderChart("chart-ai-hourly", Object.assign(reportBase(), {
        xAxis: categoryAxis(aiHourly.map((item) => String(item.hour).padStart(2, "0"))),
        yAxis: valueAxis(),
        series: [{
          name: "调用次数",
          type: "bar",
          data: aiHourly.map((item) => item.count),
          barMaxWidth: 20,
          itemStyle: { color: "#58a6ff", borderRadius: [3, 3, 0, 0] },
        }],
      }));

      errors.value = ai.errors || [];

      const lottery = ops.lottery || {};
      const lotteryDaily = lottery.daily || [];
      if (lottery.available && lotteryDaily.length) {
        renderChart("chart-lottery-daily", Object.assign(reportBase(), {
          xAxis: categoryAxis(lotteryDaily.map((item) => shortDate(item.date))),
          yAxis: [valueAxis({ name: "次数" }), valueAxis({ name: "人数", splitLine: { show: false } })],
          series: [
            {
              name: "开箱次数",
              type: "bar",
              data: lotteryDaily.map((item) => item.draws),
              barMaxWidth: 24,
              itemStyle: { color: "#d29922", borderRadius: [4, 4, 0, 0] },
            },
            {
              name: "参与人数",
              type: "line",
              yAxisIndex: 1,
              smooth: true,
              symbolSize: 5,
              data: lotteryDaily.map((item) => item.users),
              lineStyle: { color: "#58a6ff" },
              itemStyle: { color: "#58a6ff" },
            },
          ],
        }));
      } else {
        renderChart("chart-lottery-daily", emptyChartOption("暂无开箱数据"));
      }

      const rarity = lottery.rarity || [];
      if (rarity.length) {
        renderChart("chart-lottery-rarity", Object.assign(reportBase(), {
          tooltip: {
            trigger: "item",
            backgroundColor: "#1a2430",
            borderColor: "#263241",
            textStyle: { color: "#e6edf3" },
          },
          series: [{
            name: "稀有度",
            type: "pie",
            radius: ["42%", "68%"],
            center: ["50%", "54%"],
            itemStyle: { borderColor: "#151d27", borderWidth: 2 },
            label: { color: "#b6c2cf" },
            data: rarity.map((item) => ({ name: item.rarity, value: item.count })),
          }],
        }));
      } else {
        renderChart("chart-lottery-rarity", emptyChartOption("暂无开箱数据"));
      }

      const xiuxian = ops.xiuxian || {};
      const realms = xiuxian.realms || [];
      if (realms.length) {
        renderChart("chart-xiuxian-realm", Object.assign(reportBase(), {
          xAxis: categoryAxis(realms.map((item) => item.name)),
          yAxis: valueAxis(),
          series: [{
            name: "玩家数",
            type: "bar",
            data: realms.map((item) => item.count),
            barMaxWidth: 26,
            itemStyle: { color: "#3fb950", borderRadius: [4, 4, 0, 0] },
          }],
        }));
      } else {
        renderChart("chart-xiuxian-realm", emptyChartOption("暂无修仙玩家"));
      }

      const battles = xiuxian.daily_battles || [];
      if (xiuxian.available && battles.some((item) => item.battles > 0)) {
        renderChart("chart-xiuxian-battles", Object.assign(reportBase(), {
          xAxis: categoryAxis(battles.map((item) => shortDate(item.date))),
          yAxis: valueAxis(),
          series: [{
            name: "战斗次数",
            type: "line",
            smooth: true,
            symbolSize: 5,
            data: battles.map((item) => item.battles),
            lineStyle: { color: "#f85149" },
            areaStyle: { color: "rgba(248, 81, 73, 0.12)" },
            itemStyle: { color: "#f85149" },
          }],
        }));
      } else {
        renderChart("chart-xiuxian-battles", emptyChartOption("暂无战斗数据"));
      }
    }

    async function load() {
      if (!window.echarts) throw new Error("ECharts 资源未加载");
      loading.value = true;
      meta.value = "正在统计，请稍候...";
      disposeCharts();
      try {
        const [group, ai, ops] = await Promise.all([
          api(`/admin/api/reports/group-activity?days=${days.value}&group_id=${encodeURIComponent(groupId.value)}`),
          api(`/admin/api/reports/ai-usage?days=${days.value}`),
          api(`/admin/api/reports/operations?days=${days.value}`),
        ]);
        groupOptions.value = group.groups || [];
        const aiSummary = ai.summary || {};
        const lottery = (ops.lottery || {}).summary || {};
        const xiuxian = (ops.xiuxian || {}).summary || {};
        cards.value = [
          { label: "群消息总数", value: fmtNumber((group.summary || {}).messages), sub: `${fmtNumber((group.summary || {}).active_groups)} 个活跃群` },
          { label: "活跃用户", value: fmtNumber((group.summary || {}).active_users), sub: `日均 ${fmtNumber((group.summary || {}).average_daily)} 条` },
          { label: "AI 请求", value: fmtNumber(aiSummary.attempts), sub: `成功 ${fmtNumber(aiSummary.success)} / 失败 ${fmtNumber(aiSummary.failure)}` },
          { label: "AI 成功率", value: `${fmtNumber(aiSummary.success_rate)}%`, sub: `平均 ${fmtNumber(aiSummary.average_latency)} 秒` },
          { label: "开箱次数", value: fmtNumber(lottery.draws), sub: `${fmtNumber(lottery.users)} 人参与` },
          { label: "开箱总价值", value: fmtNumber(lottery.total_value), sub: `最高 ${fmtNumber(lottery.max_value)}` },
          { label: "修仙玩家", value: fmtNumber(xiuxian.players), sub: `${fmtNumber(xiuxian.groups)} 个群` },
          { label: "修仙战斗", value: fmtNumber(xiuxian.battles), sub: `${fmtNumber(xiuxian.active_battle_users)} 人参与` },
        ];
        await nextTick();
        renderAll(group, ai, ops);
        const range = `${group.start} 至 ${group.end}`;
        const groupText = groupId.value === "all" ? "全部群" : `群 ${groupId.value}`;
        meta.value = `${range} · ${days.value} 天 · ${groupText}`;
        notes.value = [group.note, ai.note, ops.note].filter(Boolean).join(" ");
      } catch (error) {
        meta.value = "统计失败";
        throw error;
      } finally {
        loading.value = false;
      }
    }

    function onResize() {
      Object.values(charts).forEach((chart) => chart.resize());
    }

    onMounted(() => {
      window.addEventListener("resize", onResize);
      run(load());
    });
    onBeforeUnmount(() => {
      window.removeEventListener("resize", onResize);
      disposeCharts();
    });

    return { days, groupId, groupOptions, meta, notes, loading, cards, errors, load };
  },
  template: `
    <div>
      <div class="toolbar">
        <el-select v-model="days" style="width:140px" @change="load">
          <el-option :value="7" label="最近 7 天" />
          <el-option :value="14" label="最近 14 天" />
          <el-option :value="30" label="最近 30 天" />
        </el-select>
        <el-select v-model="groupId" style="width:180px" @change="load">
          <el-option value="all" label="全部群" />
          <el-option v-for="gid in groupOptions" :key="gid" :value="String(gid)" :label="String(gid)" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">刷新报表</el-button>
        <span class="muted">{{ meta }}</span>
      </div>

      <div class="stat-grid">
        <div class="stat-card" v-for="item in cards" :key="item.label">
          <div class="label">{{ item.label }}</div>
          <div class="value" :class="{ small: String(item.value).length > 12 }">{{ item.value }}</div>
          <div class="sub" v-if="item.sub">{{ item.sub }}</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel"><div class="panel-head"><h2>群消息趋势</h2></div><div id="chart-group-daily" class="chart-box"></div></div>
        <div class="panel"><div class="panel-head"><h2>发言用户 Top 10</h2></div><div id="chart-group-users" class="chart-box"></div></div>
      </div>
      <div class="panel"><div class="panel-head"><h2>群活跃时段热力图</h2></div><div id="chart-group-heatmap" class="chart-box tall"></div></div>
      <div class="panel"><div class="panel-head"><h2>群活跃排行</h2></div><div id="chart-group-ranking" class="chart-box"></div></div>
      <div class="grid-2">
        <div class="panel"><div class="panel-head"><h2>AI 每日请求</h2></div><div id="chart-ai-daily" class="chart-box"></div></div>
        <div class="panel"><div class="panel-head"><h2>AI 模型分布</h2></div><div id="chart-ai-models" class="chart-box"></div></div>
      </div>
      <div class="grid-2">
        <div class="panel"><div class="panel-head"><h2>AI 24 小时调用</h2></div><div id="chart-ai-hourly" class="chart-box"></div></div>
        <div class="panel">
          <div class="panel-head"><h2>AI 错误 Top 10</h2></div>
          <div v-if="errors.length">
            <div class="kv-row" v-for="item in errors" :key="item.message">
              <span class="kv-label" style="flex:1;text-align:left">{{ item.message }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
          <p v-else class="empty-tip">暂无错误</p>
        </div>
      </div>
      <div class="grid-2">
        <div class="panel"><div class="panel-head"><h2>开箱每日趋势</h2></div><div id="chart-lottery-daily" class="chart-box"></div></div>
        <div class="panel"><div class="panel-head"><h2>开箱稀有度</h2></div><div id="chart-lottery-rarity" class="chart-box"></div></div>
      </div>
      <div class="grid-2">
        <div class="panel"><div class="panel-head"><h2>修仙境界分布</h2></div><div id="chart-xiuxian-realm" class="chart-box"></div></div>
        <div class="panel"><div class="panel-head"><h2>修仙每日战斗</h2></div><div id="chart-xiuxian-battles" class="chart-box"></div></div>
      </div>
      <p class="hint">{{ notes }}</p>
    </div>
  `,
};
