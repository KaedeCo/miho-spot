import { useEffect, useState } from "react";
import { Loading } from "tdesign-react";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Area, AreaChart, Line, LineChart } from "recharts";
import SentimentChart from "../components/SentimentChart";
import DateRangeSelector from "../components/DateRangeSelector";
import type { DailyStats, TimeRange } from "../types";

const PLATFORM_COLORS: Record<string, string> = {
  zhihu: "#0066ff", douyin: "#ff0050", tieba: "#3388ff",
  bilibili: "#fb7299", weibo: "#e6162d", other: "#6366f1",
};
const PLATFORM_LABELS: Record<string, string> = {
  zhihu: "知乎", douyin: "抖音", tieba: "贴吧", bilibili: "B站", weibo: "微博", other: "其他",
};
const AUTO_COLORS = ["#8b5cf6", "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6", "#eab308"];
import { getDailyStats } from "../services/api";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload?.length) {
    return (
      <div className="glass-card px-4 py-3 !border-[#2a2a4a]">
        <p className="text-sm text-[#94a3b8] mb-1">{label}</p>
        {payload.map((p: any) => <p key={p.name} className="text-sm" style={{ color: p.color }}>{p.name}: {p.value}</p>)}
      </div>
    );
  }
  return null;
};

export default function History() {
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [data, setData] = useState<DailyStats[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, [timeRange, startDate, endDate]);

  const loadData = async () => {
    setLoading(true);
    try {
      const r = await getDailyStats(timeRange, startDate || undefined, endDate || undefined);
      setData(r || []);
    } catch { setData([]); }
    finally { setLoading(false); }
  };

  const handleRangeChange = (range: TimeRange, start?: string, end?: string) => {
    setTimeRange(range);
    if (start) setStartDate(start);
    if (end) setEndDate(end);
  };

  const summary = data.reduce((acc, d) => ({
    totalTopics: acc.totalTopics + d.totalTopics,
    gameRelated: acc.gameRelated + d.gameRelated,
    positive: acc.positive + d.positive,
    negative: acc.negative + d.negative,
    neutral: acc.neutral + d.neutral,
    irrelevant: acc.irrelevant + d.irrelevant,
  }), { totalTopics: 0, gameRelated: 0, positive: 0, negative: 0, neutral: 0, irrelevant: 0 });

  if (loading) return <div className="flex items-center justify-center h-full"><Loading text="加载中..." size="large" /></div>;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div><h1 className="text-2xl font-bold text-white">历史统计</h1><p className="text-sm text-[#94a3b8] mt-1">跨日数据追踪，分析舆情趋势变化</p></div>
      <DateRangeSelector value={timeRange} onChange={handleRangeChange} />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[{ label: "总热搜数", value: summary.totalTopics, color: "#6366f1" }, { label: "二游相关", value: summary.gameRelated, color: "#a78bfa" }, { label: "正面", value: summary.positive, color: "#22c55e" }, { label: "负面", value: summary.negative, color: "#ef4444" }, { label: "中性", value: summary.neutral, color: "#f59e0b" }, { label: "无关", value: summary.irrelevant, color: "#6b7280" }].map((item, idx) => (
          <div key={item.label} className="glass-card p-4 text-center animate-fade-in-up opacity-0" style={{ animationDelay: `${idx * 0.08}s`, animationFillMode: "forwards" }}>
            <div className="text-xs text-[#94a3b8]">{item.label}</div>
            <div className="text-2xl font-bold mt-1" style={{ color: item.color }}>{item.value}</div>
          </div>
        ))}
      </div>

      <div className="glass-card p-5">
        <h3 className="text-base font-semibold text-white mb-4">舆情趋势图</h3>
        <div className="overflow-x-auto">
          <div style={{ minWidth: data.length > 14 ? data.length * 50 : "100%" }}>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={data}>
                <defs>
                  <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} /><stop offset="100%" stopColor="#22c55e" stopOpacity={0} /></linearGradient>
                  <linearGradient id="ng" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} /><stop offset="100%" stopColor="#ef4444" stopOpacity={0} /></linearGradient>
                  <linearGradient id="nug" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} /><stop offset="100%" stopColor="#f59e0b" stopOpacity={0} /></linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickFormatter={v => v.slice(5)} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip content={<CustomTooltip />} />
                <Legend formatter={v => <span className="text-[#94a3b8] text-sm">{v}</span>} />
                <Area type="monotone" dataKey="positive" name="正面" stroke="#22c55e" fill="url(#pg)" strokeWidth={2} />
                <Area type="monotone" dataKey="negative" name="负面" stroke="#ef4444" fill="url(#ng)" strokeWidth={2} />
                <Area type="monotone" dataKey="neutral" name="中性" stroke="#f59e0b" fill="url(#nug)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-card p-5">
        <h3 className="text-base font-semibold text-white mb-4">平台分布趋势</h3>
        <div className="overflow-x-auto">
          <div style={{ minWidth: data.length > 14 ? data.length * 50 : "100%" }}>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickFormatter={v => v.slice(5)} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip content={<CustomTooltip />} />
                <Legend formatter={v => <span className="text-[#94a3b8] text-sm">{v}</span>} />
                {(() => {
                  const allKeys = [...new Set(data.flatMap(d => Object.keys(d.byPlatform || {})))];
                  let autoIdx = 0;
                  return allKeys.map(key => {
                    const color = PLATFORM_COLORS[key] || AUTO_COLORS[autoIdx++ % AUTO_COLORS.length];
                    const label = PLATFORM_LABELS[key] || key;
                    return <Line key={key} type="monotone" dataKey={`byPlatform.${key}.total`} name={label} stroke={color} strokeWidth={2} dot={false} />;
                  });
                })()}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <SentimentChart data={{ positive: summary.positive, negative: summary.negative, neutral: summary.neutral, irrelevant: summary.irrelevant }} title="时间段情感总览" />
    </div>
  );
}
