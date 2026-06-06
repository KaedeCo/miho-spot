import { useEffect, useState, useRef, useCallback } from "react";
import { Button, Tag, Loading, MessagePlugin, Tooltip } from "tdesign-react";
import { otListSaved, otGetSaved, clusterAnalyze, clusterBySaved, clusterDelete } from "../services/api";
import type { OtResult, SavedOtTask, ClusterGroup, ClusterResult } from "../types";

const GRID_SIZE = 101;
const HM_LEFT = 60;
const HM_TOP = 14;
const HM_SIZE = 580;
const GRAD_WIDTH = 14;
const CANVAS_W = HM_LEFT + HM_SIZE + GRAD_WIDTH + 16;
const CANVAS_H = HM_TOP + HM_SIZE + GRAD_WIDTH + 16;

function gridToCanvas(gx: number, gy: number): [number, number] {
  return [HM_LEFT + (gx / 100) * HM_SIZE, HM_TOP + HM_SIZE - (gy / 100) * HM_SIZE];
}

function heatColor(ratio: number): [number, number, number] {
  if (ratio < 0.5) return [Math.round(255 * ratio * 2), 255, 0];
  return [255, Math.round(255 * (1 - ratio) * 2), 0];
}

function rgbStr(r: number, g: number, b: number, a: number = 1): string {
  return `rgba(${r},${g},${b},${a})`;
}

export default function ClusterAnalysisPage() {
  const [savedList, setSavedList] = useState<SavedOtTask[]>([]);
  const [showSaved, setShowSaved] = useState(true);
  const [result, setResult] = useState<OtResult | null>(null);

  // Cluster state
  const [clusterResult, setClusterResult] = useState<ClusterResult | null>(null);
  const [clustering, setClustering] = useState(false);
  const [hoveredCluster, setHoveredCluster] = useState<ClusterGroup | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<ClusterGroup | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const [zoom, setZoom] = useState(1);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Comment enhancer presets (localStorage + backend DB 双持久化)
  const [showCommentEnhancer, setShowCommentEnhancer] = useState(false);
  const [ceStyle, setCeStyle] = useState(() => localStorage.getItem("miho_ce_style") || "理性");
  const [ceStance, setCeStance] = useState(() => localStorage.getItem("miho_ce_stance") || "挺米");
  const [ce诉求, setCe诉求] = useState(() => localStorage.getItem("miho_ce_su") || "");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => { loadSavedList(); }, []);
  useEffect(() => {
    // 从后端恢复 presets（覆盖 localStorage 初始值）
    fetch("/api/comment/presets")
      .then(r => r.json())
      .then(d => {
        if (d.style) { setCeStyle(d.style); localStorage.setItem("miho_ce_style", d.style); }
        if (d.stance) { setCeStance(d.stance); localStorage.setItem("miho_ce_stance", d.stance); }
        if (d.诉求) { setCe诉求(d.诉求); localStorage.setItem("miho_ce_su", d.诉求); }
      })
      .catch(() => {});
  }, []);

  // 修改时同步保存到 localStorage + 后端
  useEffect(() => { localStorage.setItem("miho_ce_style", ceStyle); }, [ceStyle]);
  useEffect(() => { localStorage.setItem("miho_ce_stance", ceStance); }, [ceStance]);
  useEffect(() => { localStorage.setItem("miho_ce_su", ce诉求); }, [ce诉求]);
  const syncPresetsToBackend = async () => {
    try {
      await fetch("/api/comment/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style: ceStyle, stance: ceStance, 诉求: ce诉求 }),
      });
    } catch {}
  };
  useEffect(() => { syncPresetsToBackend(); }, [ceStyle, ceStance, ce诉求]);

  const handleDownloadScript = async () => {
    setDownloading(true);
    try {
      // 先确保最新 preset 已同步到后端
      await fetch("/api/comment/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style: ceStyle, stance: ceStance, 诉求: ce诉求 }),
      });
      const resp = await fetch("/api/comment/script");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'miho-spot-comment-enhancer.user.js';
      a.click();
      URL.revokeObjectURL(url);
      MessagePlugin.success("脚本已下载！请按安装教程导入浏览器");
    } catch { MessagePlugin.error("下载失败"); }
    setDownloading(false);
  };

  const loadSavedList = async () => {
    try { const r = await otListSaved(); setSavedList(r.items || []); } catch { }
  };

  const handleLoadSaved = async (sid: number) => {
    setResult(null); setClusterResult(null); setSelectedCluster(null);
    try {
      const r = await otGetSaved(sid);
      setResult(r);
      // Try loading existing cluster analysis
      try {
        const cr = await clusterBySaved(sid);
        if (cr.id) setClusterResult(cr);
      } catch { }
      setShowSaved(false);
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleCluster = async () => {
    if (!result?.task?.id) return;
    // Find saved ID from the list
    const saved = savedList.find(s => s.sourceTaskId === result.task.id);
    if (!saved) { MessagePlugin.warning("请先保存推演结果"); return; }

    setClustering(true);
    try {
      const r = await clusterAnalyze(saved.id);
      if (r.ok && r.id) {
        MessagePlugin.success(`生成 ${r.clusterCount} 个聚类分群`);
        const cr = await clusterBySaved(saved.id);
        setClusterResult(cr);
      }
    } catch (e: any) { MessagePlugin.error(e.message); }
    finally { setClustering(false); }
  };

  // Canvas rendering
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !result?.heatmapGrid) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const grid = result.heatmapGrid;
    canvas.width = CANVAS_W;
    canvas.height = CANVAS_H;
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    const cellW = HM_SIZE / GRID_SIZE;
    const cellH = HM_SIZE / GRID_SIZE;
    const plotRight = HM_LEFT + HM_SIZE;
    const plotBottom = HM_TOP + HM_SIZE;

    let maxCount = 0;
    for (let x = 0; x < GRID_SIZE; x++)
      for (let y = 0; y < GRID_SIZE; y++)
        if (grid[x][y] > maxCount) maxCount = grid[x][y];
    if (maxCount === 0) maxCount = 1;

    // Background
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(HM_LEFT, HM_TOP, HM_SIZE, HM_SIZE);

    // Gradient axes
    const xGradY = plotBottom + 2;
    const xGrad = ctx.createLinearGradient(HM_LEFT, 0, plotRight, 0);
    xGrad.addColorStop(0, "#ef4444"); xGrad.addColorStop(0.5, "#eab308"); xGrad.addColorStop(1, "#22c55e");
    ctx.fillStyle = xGrad;
    ctx.fillRect(HM_LEFT, xGradY, HM_SIZE, GRAD_WIDTH);

    const yGradX = HM_LEFT - GRAD_WIDTH - 2;
    const yGrad = ctx.createLinearGradient(0, plotBottom, 0, HM_TOP);
    yGrad.addColorStop(0, "#3b82f6"); yGrad.addColorStop(1, "#ec4899");
    ctx.fillStyle = yGrad;
    ctx.fillRect(yGradX, HM_TOP, GRAD_WIDTH, HM_SIZE);

    // Heatmap cells (bloom + triangles)
    for (let x = 0; x < GRID_SIZE; x++) {
      for (let y = 0; y < GRID_SIZE; y++) {
        const count = grid[x][y] || 0;
        if (count === 0) continue;
        const [cx, cy] = gridToCanvas(x, y);
        const ratio = count / maxCount;
        const [cr, cg, cb] = heatColor(ratio);

        // Bloom halo
        const haloR = Math.max(3, ratio * cellW * 4);
        const hg = ctx.createRadialGradient(cx, cy, 0, cx, cy, haloR);
        hg.addColorStop(0, rgbStr(cr, cg, cb, 0.55));
        hg.addColorStop(0.5, rgbStr(cr, cg, cb, 0.2));
        hg.addColorStop(1, rgbStr(cr, cg, cb, 0));
        ctx.fillStyle = hg;
        ctx.beginPath();
        for (let s = 0; s < 6; s++) {
          const a = (s / 6) * Math.PI * 2;
          const j = haloR * (0.7 + 0.3 * ((x * 7 + y * 13 + s * 3) % 10) / 10);
          const sx = cx + Math.cos(a) * j, sy = cy + Math.sin(a) * j;
          s === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
        }
        ctx.closePath(); ctx.fill();

        // Triangle marker
        const ts = 4;
        ctx.fillStyle = rgbStr(cr, cg, cb, 0.9);
        ctx.beginPath();
        ctx.moveTo(cx, cy - ts);
        ctx.lineTo(cx - ts * 0.87, cy + ts * 0.5);
        ctx.lineTo(cx + ts * 0.87, cy + ts * 0.5);
        ctx.closePath(); ctx.fill();
      }
    }

    // Grid lines
    ctx.strokeStyle = "rgba(148,163,184,0.12)"; ctx.lineWidth = 0.5;
    for (let i = 0; i <= 100; i += 10) {
      const [, ly] = gridToCanvas(0, i); const [lx] = gridToCanvas(i, 0);
      ctx.beginPath(); ctx.moveTo(lx, HM_TOP); ctx.lineTo(lx, plotBottom); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(HM_LEFT, ly); ctx.lineTo(plotRight, ly); ctx.stroke();
    }

    // Divider lines
    ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 1.5; ctx.setLineDash([]);
    const midX = HM_LEFT + HM_SIZE / 2; const midY = HM_TOP + HM_SIZE / 2;
    ctx.beginPath(); ctx.moveTo(midX, HM_TOP); ctx.lineTo(midX, plotBottom); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(HM_LEFT, midY); ctx.lineTo(plotRight, midY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(midX - 6, midY); ctx.lineTo(midX + 6, midY);
    ctx.moveTo(midX, midY - 6); ctx.lineTo(midX, midY + 6); ctx.stroke();

    // Tick labels (inside)
    ctx.font = "bold 9px sans-serif";
    for (let i = 0; i <= 100; i += 10) {
      const [, ly] = gridToCanvas(0, i);
      ctx.beginPath(); ctx.moveTo(HM_LEFT, ly); ctx.lineTo(HM_LEFT + 5, ly);
      ctx.strokeStyle = "#64748b"; ctx.lineWidth = 0.5; ctx.stroke();
      if (i > 0) { ctx.fillStyle = "#cbd5e1"; ctx.textAlign = "right"; ctx.textBaseline = "middle"; ctx.fillText(i.toString(), HM_LEFT + 8, ly); }

      const [lx] = gridToCanvas(i, 0);
      ctx.beginPath(); ctx.moveTo(lx, plotBottom); ctx.lineTo(lx, plotBottom - 5); ctx.stroke();
      ctx.fillStyle = "#cbd5e1"; ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.fillText(i.toString(), lx, plotBottom - 7);
    }

    // ---- Cluster boundaries (blue dashed boxes) ----
    if (clusterResult?.clusters) {
      for (const c of clusterResult.clusters) {
        const b = c.boundary;
        if (!b || b.length < 4) continue;
        const [bx0, by0] = gridToCanvas(b[0][0], b[0][1]);
        const [bx1, by1] = gridToCanvas(b[1][0], b[1][1]);
        const [bx2, by2] = gridToCanvas(b[2][0], b[2][1]);
        const [bx3, by3] = gridToCanvas(b[3][0], b[3][1]);

        const isHovered = hoveredCluster?.id === c.id;
        const isSelected = selectedCluster?.id === c.id;

        ctx.save();
        ctx.strokeStyle = isSelected ? "#60a5fa" : isHovered ? "#93c5fd" : "rgba(59,130,246,0.6)";
        ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.8;
        ctx.setLineDash([8, 5]);

        // Draw polygon
        ctx.beginPath();
        ctx.moveTo(bx0, by0); ctx.lineTo(bx1, by1);
        ctx.lineTo(bx2, by2); ctx.lineTo(bx3, by3);
        ctx.closePath(); ctx.stroke();

        // Fill with very faint blue
        ctx.fillStyle = "rgba(59,130,246,0.06)";
        ctx.fill();

        // Cluster ID label
        ctx.fillStyle = "#60a5fa"; ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "left"; ctx.textBaseline = "bottom";
        ctx.fillText(`C${c.id}`, bx0 + 3, by0 - 3);

        ctx.restore();
      }
    }
  }, [result, clusterResult, hoveredCluster, selectedCluster]);

  useEffect(() => { draw(); }, [draw, zoom]);

  // Canvas mouse handlers for cluster interaction
  const handleCanvasMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!clusterResult?.clusters || !result) return;
    const rect = e.currentTarget.getBoundingClientRect();
    // Account for zoom
    const scaleX = CANVAS_W / rect.width;
    const scaleY = CANVAS_H / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    for (const c of clusterResult.clusters) {
      const b = c.boundary;
      if (!b || b.length < 4) continue;
      const [lox, hiy] = gridToCanvas(b[0][0], b[0][1]);
      const [hix, loy] = gridToCanvas(b[2][0], b[2][1]);
      if (cx >= lox && cx <= hix && cy >= loy && cy <= hiy) {
        setHoveredCluster(c);
        setTooltipPos({ x: e.clientX, y: e.clientY });
        return;
      }
    }
    setHoveredCluster(null);
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!clusterResult?.clusters) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = CANVAS_W / rect.width;
    const scaleY = CANVAS_H / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    for (const c of clusterResult.clusters) {
      const b = c.boundary;
      if (!b || b.length < 4) continue;
      const [lox, hiy] = gridToCanvas(b[0][0], b[0][1]);
      const [hix, loy] = gridToCanvas(b[2][0], b[2][1]);
      if (cx >= lox && cx <= hix && cy >= loy && cy <= hiy) {
        setSelectedCluster(c);
        return;
      }
    }
    setSelectedCluster(null);
  };

  const canvasContainerStyle: React.CSSProperties = { display: "flex", justifyContent: "center", position: "relative" };
  const canvasStyle: React.CSSProperties = {
    width: CANVAS_W * zoom,
    height: CANVAS_H * zoom,
    cursor: "crosshair",
    transition: "width 0.2s, height 0.2s",
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 space-y-4 animate-fade-in-up p-4 overflow-auto">
        <div>
          <h1 className="text-2xl font-bold text-white">聚类分群</h1>
          <p className="text-sm text-[#94a3b8] mt-1">
            基于舆情推演结果，通过加权聚类将评论群体划分，DeepSeek AI 自动生成群体画像
          </p>
        </div>

        {/* Load saved result */}
        {!result && (
          <div className="glass-card p-6 text-center space-y-3">
            <p className="text-sm text-[#94a3b8]">从右侧栏加载已保存的舆情推演结果</p>
          </div>
        )}

        {/* Controls */}
        {result && (
          <div className="glass-card p-4 flex flex-wrap items-center gap-3">
            <Tag theme="primary" variant="light">{result.task.title || result.task.bvid}</Tag>
            <Button theme="primary" onClick={handleCluster} loading={clustering}>
              {clusterResult?.id ? "重新分群" : "聚类分群"}
            </Button>
            {clusterResult?.id && (
              <>
                <Button variant="outline" onClick={async () => {
                  if (clusterResult.id) { await clusterDelete(clusterResult.id); }
                  setClusterResult(null);
                  MessagePlugin.success("已删除分群结果");
                }}>
                  删除分群
                </Button>
                <Tag theme="success" variant="light">{clusterResult.clusterCount} 个群体</Tag>
              </>
            )}
            <span className="text-xs text-[#64748b] ml-auto">
              {result.task.totalComments} 评论 | {result.task.analyzedCount} 分析
            </span>
          </div>
        )}

        {/* 评论增强面板 */}
        <div className="glass-card p-4 space-y-3">
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setShowCommentEnhancer(!showCommentEnhancer)}>
            <div className="flex items-center gap-2">
              <span className="text-white font-semibold">💬 评论增强（B站话术生成）</span>
              <Tag theme="warning" variant="light" size="small">需油猴脚本</Tag>
            </div>
            <span className="text-[#64748b] text-xs">{showCommentEnhancer ? "▲" : "▼"}</span>
          </div>

          {showCommentEnhancer && (
            <>
              <div className="text-xs text-[#64748b] leading-relaxed">
                下载油猴脚本后，打开任意B站视频页面，脚本将自动为评论区每条评论标注立场标签（挺米/反米）和风格标签（理性/感性）。选中评论后可一键生成 DeepSeek 话术并填入回复框。
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#94a3b8] mb-1 block">话术风格</label>
                  <select value={ceStyle} onChange={e => setCeStyle(e.target.value)}
                    className="w-full bg-[#0a0a0f] border border-[#2a2a4a] rounded px-2 py-1.5 text-sm text-[#e0e0e0]">
                    <option value="理性">理性分析</option>
                    <option value="感性">情感共鸣</option>
                    <option value="幽默">幽默反击</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[#94a3b8] mb-1 block">立场倾向</label>
                  <select value={ceStance} onChange={e => setCeStance(e.target.value)}
                    className="w-full bg-[#0a0a0f] border border-[#2a2a4a] rounded px-2 py-1.5 text-sm text-[#e0e0e0]">
                    <option value="挺米">挺米</option>
                    <option value="反米">反米</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs text-[#94a3b8] mb-1 block">自定义诉求（选填）</label>
                <input type="text" value={ce诉求} onChange={e => setCe诉求(e.target.value)}
                  placeholder="例如：反驳关于玛薇卡服装设计的观点"
                  className="w-full bg-[#0a0a0f] border border-[#2a2a4a] rounded px-2 py-1.5 text-sm text-[#e0e0e0] placeholder:text-[#555]" />
              </div>

              <div className="flex gap-3">
                <Button theme="primary" onClick={handleDownloadScript} loading={downloading}>
                  📥 下载油猴脚本
                </Button>
                <Button variant="outline" onClick={() => {
                  MessagePlugin.info("安装方法：\n1. 浏览器安装 Tampermonkey 扩展\n2. 打开 Tampermonkey 管理面板\n3. 拖入下载的 .user.js 文件\n4. 打开任意 B站视频页面即可");
                }}>
                  📖 安装教程
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Heatmap */}
        {result?.heatmapGrid && (
          <div className="glass-card p-4">
            <div style={canvasContainerStyle}>
              <canvas
                ref={canvasRef}
                style={canvasStyle}
                onMouseMove={handleCanvasMove}
                onClick={handleCanvasClick}
                onMouseLeave={() => setHoveredCluster(null)}
              />
              {/* Hover tooltip */}
              {hoveredCluster && hoveredCluster.deepseek && (
                <div
                  style={{
                    position: "fixed",
                    left: tooltipPos.x + 16,
                    top: tooltipPos.y - 10,
                    maxWidth: 320,
                    background: "rgba(15,23,42,0.95)",
                    border: "1px solid #3b82f6",
                    borderRadius: 8,
                    padding: "10px 14px",
                    zIndex: 50,
                    pointerEvents: "none",
                  }}
                >
                  <p className="text-xs text-white leading-relaxed">{hoveredCluster.deepseek.definition}</p>
                </div>
              )}
            </div>

            {/* Cluster detail panel */}
            {selectedCluster && selectedCluster.deepseek && (
              <div className="mt-4 glass-card p-4 border-l-4 border-l-blue-500">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-base font-semibold text-white">
                    群体 C{selectedCluster.id}
                    <span className="text-xs text-[#94a3b8] ml-2 font-normal">
                      ({selectedCluster.percentage}% · {selectedCluster.memberCount}条)
                    </span>
                  </h3>
                  <Button size="small" variant="text" onClick={() => setSelectedCluster(null)}>关闭</Button>
                </div>
                <div className="space-y-3 text-sm">
                  <div>
                    <span className="text-blue-400 font-semibold">核心主张：</span>
                    <span className="text-[#e2e8f0]">{selectedCluster.deepseek.coreClaim}</span>
                  </div>
                  <div>
                    <span className="text-blue-400 font-semibold block mb-1">三大论据：</span>
                    <ul className="list-disc list-inside space-y-1 text-[#94a3b8]">
                      {selectedCluster.deepseek.arguments.filter(Boolean).map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <span className="text-blue-400 font-semibold">物质基础：</span>
                    <span className="text-[#94a3b8]">{selectedCluster.deepseek.materialBasis}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-center gap-3 mt-3">
              <Button size="small" variant="outline" onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}>-</Button>
              <span className="text-xs text-[#94a3b8]">{Math.round(zoom * 100)}%</span>
              <Button size="small" variant="outline" onClick={() => setZoom(Math.min(3, zoom + 0.25))}>+</Button>
              <Button size="small" variant="outline" onClick={() => setZoom(1)}>重置</Button>
            </div>
          </div>
        )}
      </div>

      {/* Right sidebar — saved results */}
      <div
        className={`h-full glass-card border-l border-[#2a2a4a] transition-all duration-300 overflow-y-auto ${showSaved ? "w-72" : "w-10"}`}
        style={{ borderRadius: 0 }}
      >
        <div className="flex items-center justify-center py-3 cursor-pointer hover:bg-white/5"
          onClick={() => setShowSaved(!showSaved)}>
          <span className="text-sm text-[#94a3b8]" style={{ writingMode: showSaved ? "horizontal-tb" : "vertical-lr" }}>
            {showSaved ? "▼ 收起" : "已存储"}
          </span>
        </div>
        {showSaved && (
          <div className="px-3 pb-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-white">已存储结果</span>
              <Button size="small" variant="text" onClick={loadSavedList}>刷新</Button>
            </div>
            {savedList.map((s) => (
              <div key={s.id} className="glass-card p-3 text-xs space-y-1 cursor-pointer hover:bg-white/5"
                onClick={() => handleLoadSaved(s.id)}>
                <div className="text-white font-medium truncate">{s.title || s.bvid}</div>
                <div className="text-[#64748b]">评论: {s.totalComments} | 分析: {s.analyzedCount}</div>
                <div className="text-[#94a3b8]">质心: ({s.centroidX?.toFixed(1)}, {s.centroidY?.toFixed(1)})</div>
                <div className="text-[#64748b]">{s.savedAt?.slice(0, 10)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
