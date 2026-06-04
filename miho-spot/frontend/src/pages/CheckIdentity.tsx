import { useState, useCallback, useEffect, useRef } from "react";
import {
  Input, Button, Pagination, Tag, Loading, MessagePlugin, Card, Tooltip, Tabs,
} from "tdesign-react";
import {
  SearchIcon, UserIcon, TimeIcon, ThumbUpIcon, ChatIcon, LinkIcon, RefreshIcon,
  PlayCircleIcon, FileIcon, DeleteIcon, ChevronDownIcon, ChevronUpIcon, ViewListIcon,
} from "tdesign-icons-react";
import {
  getBiliUserInfo, getBiliAnalyzeStatus, getBiliAnalyzeResult, triggerBiliAnalyze, saveBiliProfile,
  getIdentityQueue, addToIdentityQueue, removeFromIdentityQueue, reorderIdentityQueue,
} from "../services/api";
import type { BiliUserInfo, BiliAnalyzeResult, BiliContentItem, IdentityQueueItem } from "../types";

const CATEGORY_META: Record<string, { color: string; label: string }> = {
  mihoyo_game: { color: "#6366f1", label: "米哈游游戏" },
  mihoyo_character: { color: "#a78bfa", label: "米哈游角色" },
  mihoyo_cv: { color: "#f59e0b", label: "米哈游CV" },
  competitor: { color: "#ef4444", label: "竞品游戏" },
  general: { color: "#6b7280", label: "二游圈通用" },
};

function ScoreCircle({ score }: { score: number }) {
  const hue = Math.max(0, (score / 100) * 120);
  const color = `hsl(${hue}, 75%, 48%)`;
  const bgColor = `hsl(${hue}, 25%, 12%)`;
  let label = "中立";
  if (score < 20) label = "强烈反对";
  else if (score < 40) label = "比较反对";
  else if (score < 60) label = "中立/客观";
  else if (score < 80) label = "比较支持";
  else label = "忠实粉丝";
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="text-4xl font-bold" style={{ color }}>{score}</div>
      <div className="text-xs text-gray-500">/ 100</div>
      <div className="px-3 py-1 rounded-full text-xs font-semibold" style={{ backgroundColor: bgColor, color }}>{label}</div>
    </div>
  );
}

function ContentList({ items }: { items: BiliContentItem[] }) {
  if (!items.length) return <div className="text-center text-gray-500 py-8">该用户暂无公开视频或专栏</div>;
  return (
    <div className="space-y-3">
      {items.map((c, i) => (
        <div key={`${c.type}-${c.id}-${i}`} className="p-4 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.12] transition-colors flex gap-3">
          {c.type === "video" ? (
            c.cover ? <img src={c.cover + "@160w_100h.jpg"} alt="" className="w-24 h-14 rounded object-cover shrink-0 bg-gray-800" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} /> : null
          ) : (
            <div className="w-14 h-14 rounded bg-indigo-500/10 flex items-center justify-center shrink-0"><FileIcon size="20px" className="text-indigo-400" /></div>
          )}
          <div className="flex-1 min-w-0">
            <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-gray-200 text-sm leading-relaxed hover:text-indigo-400 transition-colors line-clamp-2">{c.title}</a>
            <div className="flex items-center gap-3 mt-1.5">
              <Tag size="small" variant="light" theme={c.type === "video" ? "primary" : "warning"}>{c.type === "video" ? "视频" : "专栏"}</Tag>
              <span className="text-xs text-gray-500"><TimeIcon size="12px" /> {c.time_str}</span>
              {c.play > 0 && <span className="text-xs text-gray-500"><PlayCircleIcon size="12px" /> {(c.play / 10000).toFixed(1)}万</span>}
              {c.type === "video" && c.duration > 0 && <span className="text-xs text-gray-500">{Math.floor(c.duration / 60)}:{String(c.duration % 60).padStart(2, "0")}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CheckIdentity() {
  const [uid, setUid] = useState("");
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [userInfo, setUserInfo] = useState<BiliUserInfo | null>(null);
  const [result, setResult] = useState<BiliAnalyzeResult | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [tabValue, setTabValue] = useState("comments");
  const [maxTotal, setMaxTotal] = useState<number | "unlimited">(500);
  const [progressStep, setProgressStep] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Identity queue
  const [queueItems, setQueueItems] = useState<IdentityQueueItem[]>([]);
  const [showQueue, setShowQueue] = useState(true);
  const [queueRunning, setQueueRunning] = useState(false);
  const queueRef = useRef<HTMLDivElement | null>(null);
  const dragItemRef = useRef<number | null>(null);
  const stopRef = useRef(false);

  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);

  const loadResult = useCallback(async (uidNum: number, pageNum: number) => {
    try {
      const res = await getBiliAnalyzeResult(uidNum, pageNum, 100);
      if (res.ok) { setResult(res); setPage(pageNum); }
      else { setError(res.error || "加载结果失败"); }
    } catch (e: any) { setError(`加载结果失败: ${e.message}`); }
  }, []);

  const handleSearch = useCallback(async () => {
    const uidNum = parseInt(uid.trim());
    if (!uidNum || uidNum <= 0) { MessagePlugin.warning("请输入有效的B站用户UID"); return; }
    setError(""); setResult(null); setUserInfo(null); setPage(1); setTabValue("comments");

    setLoading(true);
    try {
      const infoRes = await getBiliUserInfo(uidNum);
      if (!infoRes.ok || !infoRes.data) { setError(infoRes.error || "获取用户信息失败"); setLoading(false); return; }
      setUserInfo(infoRes.data);
    } catch (e: any) { setError(`获取用户信息失败: ${e.message}`); setLoading(false); return; }
    setLoading(false);

    setAnalyzing(true); setResult(null);
    try {
      const mt = maxTotal === "unlimited" ? undefined : maxTotal;
      const triggerRes = await triggerBiliAnalyze(uidNum, 50, 500, 6, mt);
      if (!triggerRes.ok) { setError(triggerRes.error || "触发分析失败"); setAnalyzing(false); return; }
      MessagePlugin.info(triggerRes.message || "分析已启动");
      setProgressStep(0); setProgressMsg("正在获取用户信息...");
      pollRef.current = setInterval(async () => {
        try {
          const status = await getBiliAnalyzeStatus(uidNum);
          setProgressStep(status.progress_step || 0);
          setProgressMsg(status.progress_msg || "");
          if (status.status === "done") { clearInterval(pollRef.current!); setAnalyzing(false); await loadResult(uidNum, 1); }
          else if (status.status === "error") { clearInterval(pollRef.current!); setAnalyzing(false); setError("分析过程出错，请重试"); }
        } catch {}
      }, 1500);
    } catch (e: any) { setAnalyzing(false); setError(`触发分析失败: ${e.message}`); }
  }, [uid, loadResult]);

  const handlePageChange = useCallback((pageInfo: { current: number }) => {
    const uidNum = parseInt(uid.trim());
    if (uidNum) loadResult(uidNum, pageInfo.current);
  }, [uid, loadResult]);

  const handleSave = useCallback(async () => {
    const uidNum = parseInt(uid.trim());
    if (!uidNum) return;
    try {
      const res = await saveBiliProfile(uidNum);
      MessagePlugin.success(res.message || "已存储");
    } catch (e: any) { MessagePlugin.error(e.message || "存储失败"); }
  }, [uid]);

  const handleRefetch = useCallback(async () => {
    const uidNum = parseInt(uid.trim()); if (!uidNum) return;
    setAnalyzing(true); setResult(null);
    const mt = maxTotal === "unlimited" ? undefined : maxTotal;
    try {
      await triggerBiliAnalyze(uidNum, 50, 500, 6, mt);
      setProgressStep(0); setProgressMsg("正在获取用户信息...");
      pollRef.current = setInterval(async () => {
        try {
          const status = await getBiliAnalyzeStatus(uidNum);
          setProgressStep(status.progress_step || 0);
          setProgressMsg(status.progress_msg || "");
          if (status.status === "done") { clearInterval(pollRef.current!); setAnalyzing(false); await loadResult(uidNum, 1); }
          else if (status.status === "error") { clearInterval(pollRef.current!); setAnalyzing(false); setError("分析过程出错"); }
        } catch {}
      }, 1500);
    } catch (e: any) { setAnalyzing(false); setError(e.message); }
  }, [uid, loadResult, maxTotal]);

  // Queue management
  const loadQueue = useCallback(async () => {
    try {
      const res = await getIdentityQueue();
      setQueueItems(res.items);
    } catch {}
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  const handleAddToQueue = async () => {
    const uidNum = parseInt(uid.trim());
    if (!uidNum || uidNum <= 0) { MessagePlugin.warning("请输入有效的UID"); return; }
    try {
      const res = await addToIdentityQueue(uidNum);
      MessagePlugin.success(res.message);
      loadQueue();
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleRemoveFromQueue = async (qId: number) => {
    try {
      await removeFromIdentityQueue(qId);
      setQueueItems(queueItems.filter((q) => q.id !== qId));
      MessagePlugin.success("已移除");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  /** Process all pending queue items sequentially, stop on user request or errors */
  const handleProcessQueue = async () => {
    const pending = queueItems.filter(q => q.status === "pending");
    if (!pending.length) { MessagePlugin.warning("队列中没有待处理的任务"); return; }

    setQueueRunning(true);
    stopRef.current = false;
    MessagePlugin.info(`开始处理 ${pending.length} 个队列任务`);

    for (const item of pending) {
      if (stopRef.current) break;

      // Mark as running
      setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "running" as const } : q));

      try {
        const mt = maxTotal === "unlimited" ? undefined : maxTotal;
        setProgressStep(0);
        setProgressMsg(`队列任务: ${item.name || `UID:${item.uid}`} 开始...`);
        const triggerRes = await triggerBiliAnalyze(item.uid, 50, 500, 6, mt);
        if (!triggerRes.ok) {
          setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "error" as const } : q));
          continue;
        }

        // Poll for completion
        await new Promise<void>((resolve) => {
          const iv = setInterval(async () => {
            if (stopRef.current) {
              clearInterval(iv);
              setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "pending" as const } : q));
              resolve(); return;
            }
            try {
              const status = await getBiliAnalyzeStatus(item.uid);
              setProgressStep(status.progress_step || 0);
              setProgressMsg(status.progress_msg || `队列任务: ${item.name || `UID:${item.uid}`}`);
              if (status.status === "done") {
                clearInterval(iv);
                // Auto-save to DB so avatar appears on spectrum
                try { await saveBiliProfile(item.uid); } catch {}
                setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "done" as const } : q));
                resolve();
              } else if (status.status === "error") {
                clearInterval(iv);
                setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "error" as const } : q));
                resolve();
              }
            } catch { }
          }, 2000);
        });
      } catch {
        setQueueItems(prev => prev.map(q => q.id === item.id ? { ...q, status: "error" as const } : q));
      }
    }

    // If stopped, revert any running item back to pending
    if (stopRef.current) {
      setQueueItems(prev => prev.map(q => q.status === "running" ? { ...q, status: "pending" as const } : q));
    }
    setQueueRunning(false);
    if (stopRef.current) {
      MessagePlugin.info("队列处理已手动停止");
    } else {
      MessagePlugin.success("队列任务处理完毕");
    }
  };

  const handleStopQueue = () => {
    stopRef.current = true;
    MessagePlugin.warning("正在停止队列...");
  };

  const handleDragStart = (e: React.DragEvent, id: number) => {
    dragItemRef.current = id;
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = async (e: React.DragEvent, targetId: number) => {
    e.preventDefault();
    if (!dragItemRef.current || dragItemRef.current === targetId) return;
    const items = [...queueItems];
    const dragIdx = items.findIndex((q) => q.id === dragItemRef.current);
    const targetIdx = items.findIndex((q) => q.id === targetId);
    if (dragIdx < 0 || targetIdx < 0) return;
    // Reorder
    const [removed] = items.splice(dragIdx, 1);
    items.splice(targetIdx, 0, removed);
    // Update sort order and persist
    const orderedIds = items.map((q) => q.id);
    setQueueItems(items);
    try { await reorderIdentityQueue(orderedIds); } catch {}
    dragItemRef.current = null;
  };

  const totalComments = result?.total_comments ?? 0;
  const matchedCount = result?.matched_count ?? 0;
  const contentCount = result?.content_count ?? 0;
  const spectrum = result?.spectrum;
  const userContent = result?.user_content ?? [];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">查成分</h1>
        <p className="text-sm text-gray-400 mt-1">输入B站用户UID，分析评论+创作内容，生成人格画像</p>
      </div>

      {/* Search */}
      <div className="glass-card p-5 rounded-xl space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Input value={uid} onChange={(v) => setUid(v as string)} placeholder="输入B站用户UID" size="large"
            disabled={analyzing || queueRunning} className="flex-1 min-w-[200px]" prefixIcon={<UserIcon />}
            onKeydown={(e: any) => { if (e.key === "Enter") handleSearch(); }} />
          <select
            className="bg-[#1e293b] border border-[#334155] rounded px-2 py-2 text-sm text-white"
            value={String(maxTotal)}
            onChange={e => setMaxTotal(e.target.value === "unlimited" ? "unlimited" : Number(e.target.value))}
            disabled={analyzing || queueRunning}
          >
            <option value="100">100条</option>
            <option value="200">200条</option>
            <option value="500">500条</option>
            <option value="1000">1000条</option>
            <option value="unlimited">不限</option>
          </select>
          <Button size="large" theme="primary" icon={<SearchIcon />} onClick={handleSearch}
            loading={loading} disabled={analyzing || queueRunning || !uid.trim()}>开始分析</Button>
          <Button size="large" variant="outline" icon={<ViewListIcon />}
            onClick={handleAddToQueue} disabled={!uid.trim() || queueRunning}
            title="将UID加入查成分队列">加入队列</Button>
          {queueItems.length > 0 && !queueRunning && (
            <Button size="large" theme="warning" icon={<PlayCircleIcon />}
              onClick={handleProcessQueue}>
              执行队列 ({queueItems.filter(q => q.status === "pending").length})
            </Button>
          )}
          {queueRunning && (
            <Button size="large" theme="danger" onClick={handleStopQueue}>
              停止队列
            </Button>
          )}
        </div>
        {/* Progress bar — show for both manual and queue analysis */}
        {(analyzing || queueRunning) && (
          <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155] space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[#94a3b8]">{progressMsg || "准备中..."}</span>
              <span className="text-white font-mono">{Math.min(100, Math.round((progressStep / 5) * 100))}%</span>
            </div>
            <div className="w-full h-2 bg-[#0f172a] rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{
                width: `${Math.min(100, (progressStep / 5) * 100)}%`,
                background: "linear-gradient(to right, #6366f1, #a855f7)",
              }} />
            </div>
            <div className="text-[10px] text-[#64748b]">步骤 {progressStep}/5</div>
          </div>
        )}
      </div>

      {/* Identity Queue Panel */}
      <div className="glass-card rounded-xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-white/[0.03] transition-colors"
          onClick={() => setShowQueue(!showQueue)}
        >
          <span className="text-sm font-semibold text-gray-300">
            <ViewListIcon size="18px" className="mr-1.5 inline-block align-text-bottom" />
            查成分任务队列 ({queueItems.length})
          </span>
          <span className="text-gray-500">{showQueue ? <ChevronUpIcon size="16px" /> : <ChevronDownIcon size="16px" />}</span>
        </button>
        {showQueue && (
          <div className="border-t border-[#2a2a4a] max-h-64 overflow-y-auto" ref={queueRef}>
            {queueItems.length === 0 ? (
              <div className="text-center py-6 text-gray-600 text-xs">队列为空，可输入UID后点击"加入队列"</div>
            ) : queueItems.map((q, idx) => (
              <div
                key={q.id}
                draggable
                onDragStart={(e) => handleDragStart(e, q.id)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, q.id)}
                className={`flex items-center gap-3 px-4 py-2.5 border-b border-white/[0.03] hover:bg-white/[0.04] transition-colors cursor-grab active:cursor-grabbing ${q.status === "running" ? "bg-purple-500/10" : ""}`}
              >
                <span className="w-5 h-5 flex items-center justify-center rounded bg-gray-800 text-gray-400 text-[10px] font-mono shrink-0">
                  #{idx + 1}
                </span>
                {q.face ? <img src={q.face} alt="" className="w-7 h-7 rounded-full shrink-0 object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} /> : <div className="w-7 h-7 rounded-full shrink-0 bg-gray-700" />}
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-200 truncate">{q.name || `UID:${q.uid}`}</div>
                  <div className="text-[10px] text-gray-500">UID:{q.uid} · {q.source === "video_analysis_kol" ? "视频分析KOL" : "手动添加"} · {q.addedAt.slice(11, 16)}</div>
                </div>
                {q.status === "pending" && <Tag size="small" variant="light" theme="default" className="shrink-0">排队中</Tag>}
                {q.status === "running" && <Tag size="small" variant="light" theme="warning" className="shrink-0"><Loading size="12px" /> 分析中</Tag>}
                {q.status === "done" && <Tag size="small" variant="light" theme="success" className="shrink-0">完成</Tag>}
                {q.status === "error" && <Tag size="small" variant="light" theme="danger" className="shrink-0">出错</Tag>}
                {(q.status === "pending") && (
                  <button
                    className="p-1 rounded hover:bg-red-500/20 shrink-0"
                    onClick={() => handleRemoveFromQueue(q.id)}
                  >
                    <DeleteIcon size="14px" className="text-gray-500 hover:text-red-400" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {error && <div className="glass-card p-4 rounded-xl border border-red-500/30 bg-red-500/5 text-red-400">{error}</div>}

      {/* User Info */}
      {userInfo && result && (
        <div className="glass-card p-5 rounded-xl flex items-center gap-4">
          <img src={userInfo.face} alt="" className="w-14 h-14 rounded-full border-2 border-indigo-500/30"
            onError={(e) => { (e.target as HTMLImageElement).src = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%236366f1'><circle cx='12' cy='12' r='10'/></svg>"; }} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-white text-lg font-semibold truncate">{userInfo.name}</span>
              <Tag size="small" theme="primary" variant="light">UID: {userInfo.uid}</Tag>
            </div>
            <div className="flex items-center gap-3 mt-1.5">
              <a href={userInfo.home_url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1"><LinkIcon size="14px" />用户主页</a>
              <span className="text-gray-500 text-xs">评论 {totalComments} · 视频/专栏 {contentCount} · 命中 {matchedCount}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {result?.status === "done" && <Button size="small" variant="outline" onClick={handleSave}>存储数据</Button>}
            <Tooltip content="重新分析"><Button variant="outline" shape="square" icon={<RefreshIcon />} onClick={handleRefetch} disabled={analyzing} size="small" /></Tooltip>
          </div>
        </div>
      )}

      {/* Personality Analysis */}
      {spectrum && result?.status === "done" && (
        <Card bordered className="glass-card rounded-xl overflow-hidden" style={{ background: "transparent" }}>
          <div className="p-6 space-y-5">
            <div className="flex items-start gap-6">
              <ScoreCircle score={spectrum.score} />
              <div className="flex-1 space-y-3">
                <div><div className="text-xs text-gray-500 uppercase tracking-wide mb-1">米哈游态度</div><div className="text-sm text-gray-200 leading-relaxed">{spectrum.mihoyo_attitude}</div></div>
                <div><div className="text-xs text-gray-500 uppercase tracking-wide mb-1">主要活跃领域</div><div className="text-sm text-gray-200 leading-relaxed">{spectrum.active_areas}</div></div>
                <div><div className="text-xs text-gray-500 uppercase tracking-wide mb-1">性格推测</div><div className="text-sm text-gray-200 leading-relaxed">{spectrum.personality}</div></div>
                {spectrum.summary && <div className="text-indigo-400 text-sm font-medium mt-2">{spectrum.summary}</div>}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Tabs: Comments | Content */}
      {result && result.status === "done" && (
        <Card bordered className="glass-card rounded-xl overflow-hidden" style={{ background: "transparent" }}>
          <Tabs value={tabValue} onChange={(v) => setTabValue(v as string)} theme="card" className="px-5 pt-4">
            <Tabs.TabPanel value="comments" label={`评论 (${totalComments})`}>
              <div className="pb-2">
                {totalComments > 0 ? (
                  <div className="space-y-3 pt-2">
                    {matchedCount > 0 && <div className="text-xs text-gray-400 mb-1">命中 {matchedCount} 条关键词</div>}
                    {(result.comments || []).map((c, ci) => (
                      <div key={c.rpid ? `rpid-${c.rpid}` : `idx-${ci}`} className={`p-4 rounded-lg border transition-colors ${c.matched_keywords?.length ? "bg-purple-500/[0.04] border-purple-500/20" : "bg-white/[0.03] border-white/[0.06] hover:border-white/[0.12]"}`}>
                        <div className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap break-words">{c.content}</div>
                        <div className="flex items-center gap-4 mt-2 flex-wrap">
                          <span className="flex items-center gap-1 text-xs text-gray-500"><TimeIcon size="12px" />{c.time_str}</span>
                          {c.likes > 0 && <span className="flex items-center gap-1 text-xs text-gray-500"><ThumbUpIcon size="12px" />{c.likes}</span>}
                        </div>
                        {c.matched_keywords && c.matched_keywords.length > 0 && (
                          <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                            {c.matched_keywords.slice(0, 8).map((kw) => <Tag key={kw} size="small" variant="light" theme="primary">{kw}</Tag>)}
                            {c.matched_categories?.map((cat) => {
                              const meta = CATEGORY_META[cat];
                              return meta ? <Tag key={cat} size="small" variant="outline" style={{ borderColor: meta.color, color: meta.color }}>{meta.label}</Tag> : null;
                            })}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center text-gray-500 py-8">该用户暂无评论数据</div>
                )}
                {result.total_pages && result.total_pages > 1 && (
                  <div className="flex justify-center pt-4 pb-2">
                    <Pagination current={page} total={totalComments} pageSize={100} onChange={handlePageChange} showPageSize={false} showJumper />
                  </div>
                )}
              </div>
            </Tabs.TabPanel>
            <Tabs.TabPanel value="content" label={`视频/专栏 (${contentCount})`}>
              <div className="pb-2 pt-2">
                <ContentList items={userContent} />
              </div>
            </Tabs.TabPanel>
          </Tabs>
        </Card>
      )}

      {/* Truly empty */}
      {result && result.status === "done" && totalComments === 0 && contentCount === 0 && (
        <div className="glass-card p-12 rounded-xl flex flex-col items-center gap-3 text-center">
          <ChatIcon size="32px" className="text-gray-600" />
          <p className="text-gray-400 text-lg">该用户无任何数据</p>
        </div>
      )}
    </div>
  );
}
