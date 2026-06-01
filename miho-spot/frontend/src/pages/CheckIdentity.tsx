import { useState, useCallback, useEffect, useRef } from "react";
import {
  Input, Button, Pagination, Tag, Loading, MessagePlugin, Card, Tooltip,
} from "tdesign-react";
import {
  SearchIcon, UserIcon, TimeIcon, ThumbUpIcon, ChatIcon, LinkIcon, RefreshIcon,
} from "tdesign-icons-react";
import {
  getBiliUserInfo, getBiliAnalyzeStatus, getBiliAnalyzeResult, triggerBiliAnalyze,
} from "../services/api";
import type { BiliUserInfo, BiliAnalyzeResult } from "../types";

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

export default function CheckIdentity() {
  const [uid, setUid] = useState("");
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [userInfo, setUserInfo] = useState<BiliUserInfo | null>(null);
  const [result, setResult] = useState<BiliAnalyzeResult | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);

  const handleSearch = useCallback(async () => {
    const uidNum = parseInt(uid.trim());
    if (!uidNum || uidNum <= 0) { MessagePlugin.warning("请输入有效的B站用户UID"); return; }
    setError(""); setResult(null); setUserInfo(null); setPage(1);

    setLoading(true);
    try {
      const infoRes = await getBiliUserInfo(uidNum);
      if (!infoRes.ok || !infoRes.data) { setError(infoRes.error || "获取用户信息失败"); setLoading(false); return; }
      setUserInfo(infoRes.data);
    } catch (e: any) { setError(`获取用户信息失败: ${e.message}`); setLoading(false); return; }
    setLoading(false);

    // Always trigger fresh analysis (don't rely on stale cache)
    setAnalyzing(true);
    setResult(null); // clear old cached result before polling
    try {
      const triggerRes = await triggerBiliAnalyze(uidNum);
      if (!triggerRes.ok) { setError(triggerRes.error || "触发分析失败"); setAnalyzing(false); return; }
      MessagePlugin.info(triggerRes.message || "分析已启动");
      pollRef.current = setInterval(async () => {
        try {
          const status = await getBiliAnalyzeStatus(uidNum);
          if (status.status === "done") { clearInterval(pollRef.current!); setAnalyzing(false); await loadResult(uidNum, 1); }
          else if (status.status === "error") { clearInterval(pollRef.current!); setAnalyzing(false); setError("分析过程出错，请重试"); }
        } catch {}
      }, 2000);
    } catch (e: any) { setAnalyzing(false); setError(`触发分析失败: ${e.message}`); }
  }, [uid]);

  const loadResult = useCallback(async (uidNum: number, pageNum: number) => {
    try {
      const res = await getBiliAnalyzeResult(uidNum, pageNum, 100);
      if (res.ok) { setResult(res); setPage(pageNum); }
      else { setError(res.error || "加载结果失败"); }
    } catch (e: any) { setError(`加载结果失败: ${e.message}`); }
  }, []);

  const handlePageChange = useCallback((pageInfo: { current: number }) => {
    const uidNum = parseInt(uid.trim());
    if (uidNum) loadResult(uidNum, pageInfo.current);
  }, [uid, loadResult]);

  const handleRefetch = useCallback(async () => {
    const uidNum = parseInt(uid.trim()); if (!uidNum) return;
    setAnalyzing(true); setResult(null);
    try {
      await triggerBiliAnalyze(uidNum);
      pollRef.current = setInterval(async () => {
        try {
          const status = await getBiliAnalyzeStatus(uidNum);
          if (status.status === "done") { clearInterval(pollRef.current!); setAnalyzing(false); await loadResult(uidNum, 1); }
          else if (status.status === "error") { clearInterval(pollRef.current!); setAnalyzing(false); setError("分析过程出错"); }
        } catch {}
      }, 2000);
    } catch (e: any) { setAnalyzing(false); setError(e.message); }
  }, [uid, loadResult]);

  const totalComments = result?.total_comments ?? 0;
  const matchedCount = result?.matched_count ?? 0;
  const spectrum = result?.spectrum;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">查成分</h1>
        <p className="text-sm text-gray-400 mt-1">输入B站用户UID，分析其对米哈游的态度、活跃领域与人格特征</p>
      </div>

      {/* Search */}
      <div className="glass-card p-5 rounded-xl">
        <div className="flex items-center gap-3">
          <Input value={uid} onChange={(v) => setUid(v as string)} placeholder="输入B站用户UID" size="large"
            disabled={analyzing} className="flex-1" prefixIcon={<UserIcon />}
            onKeydown={(e: any) => { if (e.key === "Enter") handleSearch(); }} />
          <Button size="large" theme="primary" icon={<SearchIcon />} onClick={handleSearch}
            loading={loading} disabled={analyzing || !uid.trim()}>开始分析</Button>
        </div>
      </div>

      {error && <div className="glass-card p-4 rounded-xl border border-red-500/30 bg-red-500/5 text-red-400">{error}</div>}
      {analyzing && <div className="glass-card p-8 rounded-xl flex flex-col items-center gap-4"><Loading size="large" text="正在扫描视频评论数据..." /><p className="text-xs text-gray-500">此过程可能需要1-3分钟</p></div>}

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
              <span className="text-gray-500 text-xs">共 {totalComments} 条评论 · {matchedCount} 条命中关键词</span>
            </div>
          </div>
          <Tooltip content="重新分析"><Button variant="outline" shape="square" icon={<RefreshIcon />} onClick={handleRefetch} disabled={analyzing} size="small" /></Tooltip>
        </div>
      )}

      {/* Personality Analysis Card */}
      {spectrum && result?.status === "done" && (
        <Card bordered className="glass-card rounded-xl overflow-hidden" style={{ background: "transparent" }}>
          <div className="p-6 space-y-5">
            <div className="flex items-start gap-6">
              <ScoreCircle score={spectrum.score} />
              <div className="flex-1 space-y-3">
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">米哈游态度</div>
                  <div className="text-sm text-gray-200 leading-relaxed">{spectrum.mihoyo_attitude}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">主要活跃领域</div>
                  <div className="text-sm text-gray-200 leading-relaxed">{spectrum.active_areas}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">性格推测</div>
                  <div className="text-sm text-gray-200 leading-relaxed">{spectrum.personality}</div>
                </div>
                {spectrum.summary && (
                  <div className="text-indigo-400 text-sm font-medium mt-2">{spectrum.summary}</div>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* All Comments - always show if there's any data at all */}
      {totalComments > 0 && (
        <Card bordered className="glass-card rounded-xl overflow-hidden" style={{ background: "transparent" }}>
          <div className="p-5 pb-0 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">全部评论</h2>
              <p className="text-xs text-gray-400">共 {totalComments} 条 · 第 {result?.page || 1}/{result?.total_pages || 1} 页</p>
            </div>
            {matchedCount > 0 ? (
              <Tag theme="primary" variant="light">命中 {matchedCount} 条</Tag>
            ) : (
              <Tag theme="default" variant="light">无关键词命中</Tag>
            )}
          </div>
          <div className="p-5 space-y-3">
            {(result?.comments || []).map((c) => (
              <div key={c.rpid} className={`p-4 rounded-lg border transition-colors ${c.matched_keywords?.length ? "bg-purple-500/[0.04] border-purple-500/20" : "bg-white/[0.03] border-white/[0.06] hover:border-white/[0.12]"}`}>
                <div className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap break-words">{c.content}</div>
                <div className="flex items-center gap-4 mt-2 flex-wrap">
                  <span className="flex items-center gap-1 text-xs text-gray-500"><TimeIcon size="12px" />{c.time_str}</span>
                  {c.likes > 0 && <span className="flex items-center gap-1 text-xs text-gray-500"><ThumbUpIcon size="12px" />{c.likes}</span>}
                  {c.reply_count > 0 && <span className="flex items-center gap-1 text-xs text-gray-500"><ChatIcon size="12px" />{c.reply_count}</span>}
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
          {result?.total_pages && result.total_pages > 1 && (
            <div className="p-5 pt-0 flex justify-center">
              <Pagination current={page} total={totalComments} pageSize={100} onChange={handlePageChange} showPageSize={false} showJumper theme="primary" />
            </div>
          )}
        </Card>
      )}

      {/* Empty State - only when truly zero comments */}
      {result && result.status === "done" && totalComments === 0 && (
        <div className="glass-card p-12 rounded-xl flex flex-col items-center gap-3 text-center">
          <ChatIcon size="32px" className="text-gray-600" />
          <p className="text-gray-400 text-lg">该用户无评论数据</p>
          <p className="text-gray-500 text-sm">AICU 数据库可能暂无此用户的评论记录</p>
        </div>
      )}
    </div>
  );
}
