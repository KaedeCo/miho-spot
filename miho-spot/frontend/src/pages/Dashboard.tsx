import { useEffect, useState } from "react";
import { Button, Loading, MessagePlugin, Tag, Collapse, Tooltip } from "tdesign-react";
import { RefreshIcon, SearchIcon, ChartIcon, BrowseIcon, ThumbUpIcon, ThumbDownIcon, MinusCircleIcon, RocketIcon } from "tdesign-icons-react";
import StatCard from "../components/StatCard";
import SentimentChart from "../components/SentimentChart";
import HotTopicTable from "../components/HotTopicTable";
import type { DashboardData, HotTopic } from "../types";
import { getDashboardData, triggerHotCrawl, triggerSearchCrawl, checkTodaySearch, getDeepSeekAnalyzeStatus, deepSeekAnalyzeAll, getCrawlStatus } from "../services/api";

const { Panel } = Collapse;

const PLATFORMS = ["zhihu", "douyin", "tieba"] as const;
const PLATFORM_LABELS: Record<string, string> = { zhihu: "知乎", douyin: "抖音", tieba: "贴吧", bilibili: "B站", weibo: "微博", other: "其他" };

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [crawlingHot, setCrawlingHot] = useState(false);
  const [crawlingSearch, setCrawlingSearch] = useState(false);
  const [hotOpen, setHotOpen] = useState<string[]>([]);
  const [searchOpen, setSearchOpen] = useState<string[]>([]);
  const [todaySearched, setTodaySearched] = useState(false);
  const [dsStatus, setDsStatus] = useState({ analyzed: false, configured: false, gameRelated: 0 });
  const [dsAnalyzing, setDsAnalyzing] = useState(false);

  useEffect(() => { loadData(); checkToday(); checkDeepSeek(); }, []);

  const checkToday = async () => {
    try { const r = await checkTodaySearch(); setTodaySearched(r.exists); }
    catch { setTodaySearched(false); }
  };

  const checkDeepSeek = async () => {
    try { const r = await getDeepSeekAnalyzeStatus(); setDsStatus({ analyzed: r.analyzed, configured: r.deepseekConfigured, gameRelated: r.gameRelated }); }
    catch { setDsStatus({ analyzed: false, configured: false, gameRelated: 0 }); }
  };

  const loadData = async () => {
    setLoading(true);
    try { const r = await getDashboardData(); setData(r && (r.hotTopics?.length || r.searchTopics?.length) ? r : null); }
    catch { setData(null); }
    finally { setLoading(false); }
  };

  // Poll until condition is met (used for async background tasks)
  const waitFor = async (check: () => Promise<boolean>, timeout = 60000): Promise<boolean> => {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      try { if (await check()) return true; } catch {}
      await new Promise(r => setTimeout(r, 1500));
    }
    return false;
  };

  const handleHotCrawl = async () => {
    setCrawlingHot(true);
    try {
      await triggerHotCrawl();
      await waitFor(async () => { const s = await getCrawlStatus(); return s.hotTotal > 0; });
      await loadData();
      MessagePlugin.success("平台热搜爬取完成");
    }
    catch { MessagePlugin.warning("后端未连接"); }
    finally { setCrawlingHot(false); }
  };

  const handleSearchCrawl = async () => {
    setCrawlingSearch(true);
    try {
      await triggerSearchCrawl();
      // Poll for completion or error (Tophub is separate — no AICU retry logic)
      const ok = await waitFor(async () => {
        const s = await getCrawlStatus();
        if (s.searchError) throw new Error(`TOPHUB_ERR:${s.searchErrorCode}:${s.searchError}`);
        return s.searchTotal > 0;
      });
      if (!ok) {
        // Timed out — check if error was set
        const s = await getCrawlStatus();
        if (s.searchError) {
          MessagePlugin.error(`Tophub 搜索失败 [${s.searchErrorCode}]: ${s.searchError}`);
          return;
        }
        MessagePlugin.warning("搜索超时（60秒），请检查网络或API Key");
        return;
      }
      await loadData();
      await checkToday(); await checkDeepSeek();
      MessagePlugin.success("热点搜索完成");
    }
    catch (e: any) {
      const msg = String(e?.message || e);
      if (msg.startsWith("TOPHUB_ERR:")) {
        const parts = msg.split(":");
        MessagePlugin.error(`Tophub 搜索失败 [${parts[1]}]: ${parts.slice(2).join(":")}`);
      } else {
        MessagePlugin.error(msg || "搜索请求失败，请检查后端连接");
      }
    }
    finally { setCrawlingSearch(false); }
  };

  const handleDeepSeekAnalyze = async () => {
    setDsAnalyzing(true);
    try {
      const r = await deepSeekAnalyzeAll();
      if (r.ok) {
        MessagePlugin.success(r.message);
        await waitFor(async () => { const s = await getDeepSeekAnalyzeStatus(); return s.analyzed; }, 300000);
        await loadData(); await checkDeepSeek();
      } else {
        MessagePlugin.warning(r.message);
      }
    } catch { MessagePlugin.warning("后端未连接或DeepSeek未配置"); }
    finally { setDsAnalyzing(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-full"><Loading text="加载中..." size="large" /></div>;

  const s = data?.summary || { totalTopics: 0, gameRelated: 0, positive: 0, negative: 0, neutral: 0, irrelevant: 0 };
  const hotTopics: HotTopic[] = data?.hotTopics || [];
  const searchTopics: HotTopic[] = data?.searchTopics || [];

  const platformBreakdown = (topics: HotTopic[]) => PLATFORMS.map(p => ({
    key: p, label: PLATFORM_LABELS[p],
    count: topics.filter(t => t.platform === p).length,
    topics: topics.filter(t => t.platform === p),
  }));

  // Dynamic platform breakdown for search (Tophub /search returns cross-platform results)
  const searchPlatformBreakdown = (topics: HotTopic[]) => {
    const platforms = [...new Set(topics.map(t => t.platform))];
    return platforms.map(p => ({
      key: p, label: PLATFORM_LABELS[p] || p,
      count: topics.filter(t => t.platform === p).length,
      topics: topics.filter(t => t.platform === p),
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="text-2xl font-bold text-white">数据仪表盘</h1>
          <p className="text-sm text-[#94a3b8] mt-1">Miho-spot 米哈游舆情监测中心</p>
        </div>
        <div className="flex gap-3">
          <Button theme="primary" icon={<RefreshIcon />} loading={crawlingHot} onClick={handleHotCrawl} className="!bg-indigo-600">平台热搜</Button>
          <Tooltip content={todaySearched ? "今日已搜索，付费API不可重复调用" : "调用Tophub付费API搜索全站热点"}>
            <Button variant="outline" icon={<SearchIcon />} loading={crawlingSearch} disabled={todaySearched} onClick={handleSearchCrawl}>{todaySearched ? "今日已搜索" : "Tophub搜索"}</Button>
          </Tooltip>
          <Tooltip content={dsStatus.analyzed ? "今日已完成DeepSeek分析" : dsStatus.configured ? `对 ${dsStatus.gameRelated} 条二游热搜进行AI情感分析` : "请先在账号管理配置DeepSeek API Key"}>
            <Button variant="outline" icon={<RocketIcon />} loading={dsAnalyzing} disabled={dsStatus.analyzed || !dsStatus.configured} onClick={handleDeepSeekAnalyze} style={dsStatus.analyzed ? {} : { borderColor: "#6366f1", color: "#a78bfa" }}>
              {dsStatus.analyzed ? "已分析" : dsAnalyzing ? "分析中..." : "一键分析（DeepSeek）"}
            </Button>
          </Tooltip>
        </div>
      </div>

      <div className="glass-card p-4 border-l-4 border-l-indigo-500 animate-fade-in stagger-1 opacity-0" style={{ animationFillMode: "forwards" }}>
        <p className="text-sm text-[#a78bfa] italic">"从此以后，每个人都是社管，亦或者都不是社管。" — By Chronostasis</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard label="热搜总数" value={s.totalTopics} icon={<ChartIcon />} color="#6366f1" delay={0} />
        <StatCard label="二游相关" value={s.gameRelated} icon={<BrowseIcon />} color="#a78bfa" delay={0.1} />
        <StatCard label="正面" value={s.positive} icon={<ThumbUpIcon />} color="#22c55e" delay={0.2} />
        <StatCard label="负面" value={s.negative} icon={<ThumbDownIcon />} color="#ef4444" delay={0.3} />
        <StatCard label="中性" value={s.neutral} icon={<MinusCircleIcon />} color="#f59e0b" delay={0.4} />
        <StatCard label="无关" value={s.irrelevant} icon={<BrowseIcon />} color="#6b7280" delay={0.5} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SentimentChart data={s} title="情感分布总览" />
        <div className="glass-card p-5">
          <h3 className="text-base font-semibold text-white mb-4">平台分布</h3>
          {(() => {
            const all = [...hotTopics, ...searchTopics];
            const platforms = [...new Set(all.map(t => t.platform))];
            const allColors: Record<string, string> = { zhihu: "#0066ff", douyin: "#ff0050", tieba: "#3388ff", bilibili: "#fb7299", weibo: "#e6162d", other: "#6366f1" };
            return platforms.sort((a, b) => {
              const ca = all.filter(t => t.platform === a).length;
              const cb = all.filter(t => t.platform === b).length;
              return cb - ca;
            }).map(p => {
              const pc = all.filter(t => t.platform === p).length;
              const pct = all.length ? (pc / all.length) * 100 : 0;
              const color = allColors[p] || "#8b5cf6";
              return (
                <div key={p} className="mb-3">
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-[#e2e8f0]">{PLATFORM_LABELS[p] || p}</span>
                    <span className="text-[#94a3b8]">{pc} 条 ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="h-2 rounded-full bg-[#1a1a2e] overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color, boxShadow: `0 0 8px ${color}40` }} />
                  </div>
                </div>
              );
            });
          })()}
        </div>
      </div>

      {/* Platform Hot Topics - Collapsible */}
      <Collapse value={hotOpen} onChange={v => setHotOpen(v as string[])} expandIconPlacement="left" borderless>
        <Panel header={<span className="text-white font-semibold"><Tag theme="primary" variant="light" className="mr-2">平台热搜</Tag>三大平台热榜前50条 · {hotTopics.length} 条</span>} value="hot">
          <Collapse value={hotOpen.filter(k => k !== "hot")} onChange={v => setHotOpen(["hot", ...(v as string[])])} expandIconPlacement="left" borderless>
            {platformBreakdown(hotTopics).map(pb => (
              <Panel key={pb.key} header={<span className="text-sm text-[#94a3b8]">{pb.label} ({pb.count} 条)</span>} value={`hot-${pb.key}`}>
                <HotTopicTable topics={pb.topics} />
              </Panel>
            ))}
          </Collapse>
        </Panel>
      </Collapse>

      {/* Advanced Hot Search Results - Collapsible */}
      <Collapse value={searchOpen} onChange={v => setSearchOpen(v as string[])} expandIconPlacement="left" borderless>
        <Panel header={<span className="text-white font-semibold"><Tag theme="warning" variant="light" className="mr-2">热点搜索（高级）</Tag>Tophub 高级热点搜索结果 · {searchTopics.length} 条</span>} value="search">
          <Collapse value={searchOpen.filter(k => k !== "search")} onChange={v => setSearchOpen(["search", ...(v as string[])])} expandIconPlacement="left" borderless>
            {searchPlatformBreakdown(searchTopics).map(pb => (
              <Panel key={pb.key} header={<span className="text-sm text-[#94a3b8]">{pb.label} ({pb.count} 条)</span>} value={`search-${pb.key}`}>
                <HotTopicTable topics={pb.topics} />
              </Panel>
            ))}
          </Collapse>
        </Panel>
      </Collapse>
    </div>
  );
}
