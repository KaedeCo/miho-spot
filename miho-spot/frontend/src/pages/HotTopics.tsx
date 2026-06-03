import { useEffect, useState } from "react";
import { Button, Loading, Tag, Tabs, Input, MessagePlugin } from "tdesign-react";
import { RefreshIcon, SearchIcon, JumpIcon } from "tdesign-icons-react";
import type { HotTopic } from "../types";
import { getHotTopics, triggerHotCrawl, triggerSearchCrawl, getCrawlStatus } from "../services/api";

const PLATFORM_LABELS: Record<string, string> = { zhihu: "知乎", douyin: "抖音", tieba: "贴吧", bilibili: "B站", weibo: "微博", other: "其他" };
const SENTIMENT_COLORS: Record<string, string> = { Positive: "#22c55e", Negative: "#ef4444", Neutral: "#f59e0b", Irrelevant: "#6b7280" };
const SENTIMENT_LABELS: Record<string, string> = { Positive: "正面", Negative: "负面", Neutral: "中性", Irrelevant: "无关" };

export default function HotTopics() {
  const [topics, setTopics] = useState<HotTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("zhihu");
  const [searchText, setSearchText] = useState("");
  const [crawlingHot, setCrawlingHot] = useState(false);
  const [crawlingSearch, setCrawlingSearch] = useState(false);

  useEffect(() => { loadTopics(); }, []);

  const loadTopics = async () => {
    setLoading(true);
    try {
      const r = await getHotTopics();
      if (r?.length) setTopics(r);
    } catch {}
    finally { setLoading(false); }
  };

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
    try { await triggerHotCrawl(); await waitFor(async () => { const s = await getCrawlStatus(); return s.hotTotal > 0; }); await loadTopics(); MessagePlugin.success("完成"); }
    catch { MessagePlugin.warning("后端未连接"); }
    finally { setCrawlingHot(false); }
  };

  const handleSearchCrawl = async () => {
    setCrawlingSearch(true);
    try {
      await triggerSearchCrawl();
      const ok = await waitFor(async () => {
        const s = await getCrawlStatus();
        if (s.searchError) throw new Error(s.searchError);  // stop on error
        return s.searchTotal > 0;
      });
      if (ok) {
        await loadTopics();
        MessagePlugin.success("完成");
      } else {
        MessagePlugin.warning("搜索超时，请重试");
      }
    } catch (e: any) {
      MessagePlugin.warning(e?.message || "后端未连接");
    } finally {
      setCrawlingSearch(false);
    }
  };

  const allPlatforms = [...new Set(topics.map(t => t.platform))];
  const platformTopics = topics.filter(t => t.platform === activeTab);
  const filtered = searchText
    ? platformTopics.filter(t => t.title.toLowerCase().includes(searchText.toLowerCase()))
    : platformTopics;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">热搜监测</h1>
          <p className="text-sm text-[#94a3b8] mt-1">实时监测各大平台热搜，支持本地搜索过滤</p>
        </div>
        <div className="flex gap-3">
          <Button theme="primary" icon={<RefreshIcon />} loading={crawlingHot} onClick={handleHotCrawl}>平台热搜</Button>
          <Button variant="outline" icon={<SearchIcon />} loading={crawlingSearch} onClick={handleSearchCrawl}>Tophub搜索</Button>
        </div>
      </div>

      <Tabs value={activeTab} onChange={v => setActiveTab(v as string)}>
        {allPlatforms.map(p => (
          <Tabs.TabPanel key={p} value={p} label={`${PLATFORM_LABELS[p] || p} (${topics.filter(t => t.platform === p).length})`} />
        ))}
      </Tabs>

      <div className="flex items-center gap-3">
        <Input
          prefixIcon={<SearchIcon />}
          placeholder="搜索热搜标题..."
          value={searchText}
          onChange={v => setSearchText(v as string)}
          style={{ width: 360 }}
          clearable
        />
        <span className="text-xs text-[#64748b]">{filtered.length} 条结果</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loading text="加载中..." size="large" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((topic, idx) => (
            <div
              key={topic.id ? `topic-${topic.id}` : `idx-${idx}`}
              className="glass-card p-4 animate-fade-in-up opacity-0"
              style={{ animationDelay: `${idx * 0.03}s`, animationFillMode: "forwards" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold text-yellow-400">#{topic.rank}</span>
                <Tag size="small" variant="light" theme="default">{PLATFORM_LABELS[topic.platform] || topic.platform}</Tag>
                <Tag size="small" style={{ backgroundColor: (SENTIMENT_COLORS[topic.sentiment] || "#6b7280") + "20", color: SENTIMENT_COLORS[topic.sentiment], border: "none" }}>
                  {SENTIMENT_LABELS[topic.sentiment] || topic.sentiment}
                </Tag>
              </div>
              <p className="text-sm text-[#e2e8f0] line-clamp-2 mb-2" title={topic.title}>{topic.title}</p>
              <div className="flex items-center justify-between text-xs text-[#94a3b8]">
                <span>热度 {topic.heat?.toLocaleString()}</span>
                <div className="flex items-center gap-2">
                  {topic.relatedGame && <span className="text-indigo-400">{topic.relatedGame}</span>}
                  <a href={topic.url && topic.url !== "#" ? topic.url : undefined} target="_blank" rel="noopener noreferrer" className="flex items-center gap-0.5 text-[#6366f1] hover:text-[#a78bfa]"><JumpIcon style={{ fontSize: 12 }} /><span>原文</span></a>
                </div>
              </div>
            </div>
          ))}
          {filtered.length === 0 && <div className="col-span-full text-center py-8 text-sm text-[#64748b]">暂无数据，请点击"平台热搜"或"Tophub搜索"获取数据</div>}
        </div>
      )}
    </div>
  );
}
