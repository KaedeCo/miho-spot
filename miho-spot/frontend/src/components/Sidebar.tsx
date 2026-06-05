import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button, Checkbox, MessagePlugin, Loading } from "tdesign-react";
import {
  DashboardIcon,
  ChartIcon,
  BookIcon,
  HistoryIcon,
  SettingIcon,
  SearchIcon,
  LocationIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlayCircleIcon,
  CloudIcon,
  FileSearchIcon,
  TimeIcon,
  UsergroupIcon,
  ChatBubbleIcon,
} from "tdesign-icons-react";
import { getPdfModules, generatePdfReport, getPdfProgress, downloadPdfReport, otListSaved, type PdfModule } from "../services/api";

const menuItems = [
  { path: "/", label: "数据仪表盘", icon: <DashboardIcon /> },
  { path: "/topics", label: "热搜监测", icon: <ChartIcon /> },
  { path: "/keywords", label: "关键词词典", icon: <BookIcon /> },
  { path: "/history", label: "历史统计", icon: <HistoryIcon /> },
  { path: "/identity", label: "查成分", icon: <SearchIcon /> },
  { path: "/spectrum", label: "二维光谱图", icon: <LocationIcon /> },
  { path: "/video-analysis", label: "视频分析", icon: <PlayCircleIcon /> },
  { path: "/opinion-timeline", label: "舆情推演", icon: <TimeIcon /> },
  { path: "/cluster-analysis", label: "聚类分群", icon: <UsergroupIcon /> },
  { path: "/word-cloud", label: "词云", icon: <CloudIcon /> },
  { path: "/deep-analysis", label: "深度分析", icon: <FileSearchIcon /> },
  { path: "/debate-hall", label: "舆情辩论厅", icon: <ChatBubbleIcon /> },
  { path: "/debate-replay", label: "辩论回放", icon: <TimeIcon /> },
  { path: "/accounts", label: "账号管理", icon: <SettingIcon /> },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const activeKey = menuItems.find((item) => item.path === location.pathname)?.path || "/";

  return (
    <div
      className="h-screen flex flex-col glass-card border-r border-[#2a2a4a] transition-all duration-300"
      style={{ width: collapsed ? 72 : 240, borderRadius: 0 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[#2a2a4a]">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shrink-0 animate-pulse-glow">
          M
        </div>
        {!collapsed && (
          <div className="animate-fade-in">
            <div className="text-sm font-semibold text-white">Miho-spot</div>
            <div className="text-[10px] text-[#94a3b8]">舆情监测系统</div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-6 px-4 space-y-3">
        {menuItems.map((item) => (
          <div
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`flex items-center gap-3 px-4 py-4 rounded-lg cursor-pointer transition-all duration-200 group ${
              activeKey === item.path
                ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"
                : "text-[#94a3b8] hover:text-[#e2e8f0] hover:bg-white/5"
            }`}
            title={item.label}
          >
            <span className="text-lg shrink-0">{item.icon}</span>
            {!collapsed && (
              <span className="text-sm whitespace-nowrap animate-fade-in">{item.label}</span>
            )}
          </div>
        ))}
      </nav>

      {/* PDF Report Panel */}
      {!collapsed && <PdfReportPanel />}

      {/* Collapse toggle */}
      <div className="p-3 border-t border-[#2a2a4a]">
        <Button
          variant="text"
          shape="square"
          size="small"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full text-[#94a3b8] hover:text-white"
        >
          {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
        </Button>
      </div>
    </div>
  );
}

/** PDF Report customization panel with progress bar */
function PdfReportPanel() {
  const [expanded, setExpanded] = useState(false);
  const [modules, setModules] = useState<PdfModule[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [savedList, setSavedList] = useState<any[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);

  // Progress state
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState({ step: 0, total: 1, message: "", error: "" });

  useEffect(() => {
    getPdfModules().then(r => setModules(r.modules || [])).catch(() => {});
    otListSaved().then(r => setSavedList(r.items || [])).catch(() => {});
    // Recover orphaned PDF job
    const saved = sessionStorage.getItem("pdf_active_job");
    if (saved) {
      setJobId(saved);
      setGenerating(true);
      setExpanded(true);
    }
  }, []);

  // Poll progress
  useEffect(() => {
    if (!jobId) return;
    const iv = setInterval(async () => {
      try {
        const p = await getPdfProgress(jobId);
        setProgress({ step: p.step, total: p.total, message: p.message, error: p.error || "" });
        if (p.status === "done") {
          clearInterval(iv);
          setGenerating(false);
          sessionStorage.removeItem("pdf_active_job");
          downloadPdfReport(jobId).then(() => {
            MessagePlugin.success("PDF已下载");
          }).catch(() => {});
          setJobId(null);
        } else if (p.status === "error") {
          clearInterval(iv);
          setGenerating(false);
          sessionStorage.removeItem("pdf_active_job");
          setJobId(null);
        }
      } catch { }
    }, 600);
    return () => clearInterval(iv);
  }, [jobId]);

  const toggle = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === modules.length) setSelected(new Set());
    else setSelected(new Set(modules.map(m => m.key)));
  };

  const handleGenerate = async () => {
    if (!savedId) { MessagePlugin.warning("请选择一个已保存的推演结果"); return; }
    if (selected.size === 0) { MessagePlugin.warning("请至少勾选一个模块"); return; }
    setGenerating(true);
    setProgress({ step: 0, total: selected.size + 3, message: "正在提交...", error: "" });
    try {
      const r = await generatePdfReport(savedId, Array.from(selected));
      setJobId(r.jobId);
      sessionStorage.setItem("pdf_active_job", r.jobId);
    } catch (e: any) {
      MessagePlugin.error(e.message || "提交失败");
      setGenerating(false);
    }
  };

  const pct = Math.min(100, Math.round((progress.step / Math.max(1, progress.total)) * 100));

  return (
    <div className="border-t border-[#2a2a4a]">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-white/5"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs font-semibold text-white">PDF报告定制</span>
        <span className="text-[10px] text-[#64748b]">{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <div className="px-3 pb-3 space-y-3 max-h-[50vh] overflow-y-auto">
          {/* Progress bar — always visible when generating */}
          {generating && (
            <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155] space-y-2">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#94a3b8]">{progress.message || "准备中..."}</span>
                <span className="text-white font-mono">{pct}%</span>
              </div>
              <div className="w-full h-2 bg-[#0f172a] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300 ease-out"
                  style={{
                    width: `${pct}%`,
                    background: progress.error
                      ? "#ef4444"
                      : "linear-gradient(to right, #6366f1, #8b5cf6)",
                  }}
                />
              </div>
              <div className="text-[9px] text-[#64748b]">
                步骤 {progress.step}/{progress.total}
              </div>
              {progress.error && (
                <div className="text-[10px] text-red-400 bg-red-500/10 rounded p-2 border border-red-500/20">
                  {progress.error}
                </div>
              )}
            </div>
          )}

          {/* Saved timeline selector */}
          <div>
            <label className="text-[10px] text-[#64748b]">选择推演结果</label>
            <select
              className="w-full mt-1 bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-xs text-white"
              value={savedId || ""}
              onChange={e => setSavedId(Number(e.target.value) || null)}
            >
              <option value="">-- 请选择 --</option>
              {savedList.map(s => (
                <option key={s.id} value={s.id}>{s.title || s.bvid} ({s.totalComments}评)</option>
              ))}
            </select>
          </div>

          {/* Module selector */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[#64748b]">
              选择模块 ({selected.size}/{modules.length})
            </span>
            <Button size="small" variant="text" className="!text-[10px] !p-0" onClick={selectAll}>
              {selected.size === modules.length ? "取消全选" : "全选"}
            </Button>
          </div>

          <div className="space-y-1 max-h-[220px] overflow-y-auto">
            {modules.map(m => (
              <div
                key={m.key}
                className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-colors ${selected.has(m.key) ? "bg-indigo-500/15 border border-indigo-500/30" : "hover:bg-white/5 border border-transparent"}`}
                onClick={() => toggle(m.key)}
              >
                <Checkbox
                  checked={selected.has(m.key)}
                  onChange={() => toggle(m.key)}
                  className="mt-0.5 shrink-0"
                />
                <div>
                  <div className="text-[11px] text-white font-medium">{m.label}</div>
                  <div className="text-[9px] text-[#64748b] leading-tight">{m.description}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Generate button */}
          <Button
            theme="primary"
            block
            size="small"
            loading={generating}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "生成中..." : "生成PDF报告"}
          </Button>
        </div>
      )}
    </div>
  );
}
