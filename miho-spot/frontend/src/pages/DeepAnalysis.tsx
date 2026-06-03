import { useState, useEffect, useCallback, useRef } from "react";
import { Button, Loading, MessagePlugin, Tag } from "tdesign-react";
import {
  SearchIcon,
  RefreshIcon,
  DeleteIcon,
  FileSearchIcon,
  TimeIcon,
} from "tdesign-icons-react";
import { getSavedVaTasks, getDeepAnalyses, startDeepAnalysis, getDeepAnalysisStatus, deleteDeepAnalysis, getDeepAnalysisResult } from "../services/api";
import type { SavedVaTask, DeepAnalysisItem } from "../types";

export default function DeepAnalysisPage() {
  const [savedTasks, setSavedTasks] = useState<SavedVaTask[]>([]);
  const [analyses, setAnalyses] = useState<DeepAnalysisItem[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState<DeepAnalysisItem | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [tasksRes, analysesRes] = await Promise.all([getSavedVaTasks(), getDeepAnalyses()]);
      setSavedTasks(tasksRes.items);
      setAnalyses(analysesRes.items);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);

  const handleStart = async (savedId: number) => {
    setAnalyzing(true);
    try {
      const res = await startDeepAnalysis(savedId);
      if (res.ok) MessagePlugin.success("深度分析已启动");
      else MessagePlugin.error(res.message || "启动失败");

      // Poll for status
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const st = await getDeepAnalysisStatus();
          if (st.status !== "running") {
            if (pollRef.current) clearInterval(pollRef.current);
            setAnalyzing(false);
            loadData();
            // Auto-select the new analysis
            if (st.analysis_id) {
              const result = await getDeepAnalysisResult(st.analysis_id);
              setActiveAnalysis(result);
            }
          }
        } catch {}
      }, 3000);
    } catch (e: any) { MessagePlugin.error(e.message); setAnalyzing(false); }
  };

  const handleView = async (analysis: DeepAnalysisItem) => {
    try {
      const result = await getDeepAnalysisResult(analysis.id);
      setActiveAnalysis(result);
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDeepAnalysis(id);
      setAnalyses(analyses.filter((a) => a.id !== id));
      if (activeAnalysis?.id === id) setActiveAnalysis(null);
      MessagePlugin.success("已删除");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  const statusTag = (status: string) => {
    const map: Record<string, { theme: "primary" | "warning" | "success" | "danger" | "default"; label: string }> = {
      pending: { theme: "default", label: "等待中" },
      running: { theme: "warning", label: "分析中" },
      done: { theme: "success", label: "已完成" },
      error: { theme: "danger", label: "出错" },
    };
    const m = map[status] || map.pending;
    return <Tag size="small" variant="light" theme={m.theme}>{m.label}</Tag>;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">舆论深度分析</h1>
        <p className="text-sm text-gray-400 mt-1">选择已存储任务，提取关键评论，由DeepSeek AI进行舆论场深度解析</p>
      </div>

      {/* Task selection */}
      <div className="glass-card rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-gray-300">
            <FileSearchIcon size="18px" className="mr-1 inline-block align-text-bottom" />
            选择任务开始深度分析
          </span>
        </div>

        {loading ? (
          <Loading />
        ) : savedTasks.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            暂无已存储任务
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {savedTasks.map((task) => {
              const existing = analyses.find((a) => a.savedVaTaskId === task.id);
              return (
                <div key={task.id} className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-white/12 transition-all">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-200 truncate font-medium">{task.title || "无标题"}</div>
                      <div className="text-[10px] text-gray-500 mt-0.5">{task.totalComments}条评论</div>
                    </div>
                    {existing && statusTag(existing.status)}
                  </div>
                  <div className="mt-2 flex gap-1.5">
                    {existing?.status === "done" && (
                      <Button size="extra-small" variant="outline" onClick={() => handleView(existing!)} className="!text-[10px]">查看</Button>
                    )}
                    <Button
                      size="extra-small"
                      theme={existing ? "default" : "primary"}
                      loading={analyzing}
                      disabled={existing?.status === "running"}
                      onClick={() => handleStart(task.id)}
                      className="!text-[10px]"
                    >
                      {existing ? (existing.status === "running" ? "分析中..." : "重新分析") : "开始分析"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Active Analysis Display */}
      {activeAnalysis && activeAnalysis.status === "done" && (
        <div className="glass-card rounded-xl p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{activeAnalysis.taskTitle}</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                完成于 {activeAnalysis.completedAt?.slice(0, 16).replace("T", " ") || ""}
              </p>
            </div>
            <Button variant="outline" size="small" icon={<DeleteIcon />} onClick={() => handleDelete(activeAnalysis.id)}>
              删除
            </Button>
          </div>

          {/* Overall Trend */}
          <div>
            <h3 className="text-sm font-semibold text-indigo-400 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-4 bg-indigo-400 rounded-full"></span>
              舆论总体趋势
            </h3>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
              <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                {activeAnalysis.overallTrend || "暂无数据"}
              </p>
            </div>
          </div>

          {/* KOL Viewpoints */}
          <div>
            <h3 className="text-sm font-semibold text-emerald-400 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-4 bg-emerald-400 rounded-full"></span>
              高赞KOL持有观点
            </h3>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
              <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                {activeAnalysis.kolViewpoints || "暂无数据"}
              </p>
            </div>
          </div>

          {/* Opposition Analysis */}
          <div>
            <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-4 bg-amber-400 rounded-full"></span>
              对立面观点解析
            </h3>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
              <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                {activeAnalysis.oppositionAnalysis || "暂无数据"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Analysis History */}
      {analyses.length > 0 && !activeAnalysis && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">历史分析记录</h3>
          <div className="space-y-2">
            {analyses.map((a) => (
              <div key={a.id} className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors cursor-pointer"
                onClick={() => a.status === "done" && handleView(a)}>
                <div className="flex items-center gap-3">
                  {statusTag(a.status)}
                  <span className="text-xs text-gray-200">{a.taskTitle}</span>
                  <span className="text-[10px] text-gray-600">{a.createdAt.slice(0, 10)}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(a.id); }}
                  className="p-1 rounded hover:bg-red-500/20 opacity-0 group-hover:opacity-100"
                >
                  <DeleteIcon size="12px" className="text-gray-500 hover:text-red-400" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
