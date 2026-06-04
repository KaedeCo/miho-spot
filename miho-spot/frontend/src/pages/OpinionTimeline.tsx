import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Input, Button, Tag, Loading, MessagePlugin, Tooltip } from "tdesign-react";
import { otFetch, otStatus, otAnalyze, otResult, otSave, otListSaved, otGetSaved, otDeleteSaved, otDeleteTask, otSaveNodes } from "../services/api";
import type { OtResult, OtCentroidTrailPoint, SavedOtTask } from "../types";

const GRID_SIZE = 101;
const HM_LEFT = 60;   // left margin for Y axis + gradient
const HM_TOP = 14;    // top margin
const HM_SIZE = 580;  // plot area size
const GRAD_WIDTH = 14; // axis gradient strip width
const CANVAS_W = HM_LEFT + HM_SIZE + GRAD_WIDTH + 16;  // ~670
const CANVAS_H = HM_TOP + HM_SIZE + GRAD_WIDTH + 16;   // ~620

/** Helper: grid coords (0-100) → canvas px. Y flipped so 0=bottom. */
function gridToCanvas(gx: number, gy: number): [number, number] {
  return [HM_LEFT + (gx / 100) * HM_SIZE, HM_TOP + HM_SIZE - (gy / 100) * HM_SIZE];
}

/** Heatmap color: green (low) → yellow → red (high) */
function heatColor(ratio: number): [number, number, number] {
  if (ratio < 0.5) return [Math.round(255 * ratio * 2), 255, 0];
  return [255, Math.round(255 * (1 - ratio) * 2), 0];
}

function rgbStr(r: number, g: number, b: number, a: number = 1): string {
  return `rgba(${r},${g},${b},${a})`;
}

export default function OpinionTimeline() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState("");
  const [result, setResult] = useState<OtResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  // Timeline slider
  const [timeIndex, setTimeIndex] = useState(-1);
  const [maxTimeIndex, setMaxTimeIndex] = useState(0);

  // Node system: user right-clicks on slider to create landmark nodes
  const [nodeIndices, setNodeIndices] = useState<number[]>([]);
  const [savedId, setSavedId] = useState<number | null>(null); // current saved record ID

  // Saved results
  const [savedList, setSavedList] = useState<SavedOtTask[]>([]);
  const [showSaved, setShowSaved] = useState(false);

  // Zoom
  const [zoom, setZoom] = useState(1);

  // Help tooltip
  const [helpVisible, setHelpVisible] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sliderRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadSavedList(); }, []);
  // Recover orphaned task
  useEffect(() => {
    const saved = sessionStorage.getItem("ot_active_task");
    if (saved) { setTaskId(saved); setStatus("fetching"); }
  }, []);

  const loadSavedList = async () => {
    try { const r = await otListSaved(); setSavedList(r.items || []); } catch { }
  };

  // --- Fetch / Analyze / Save (unchanged business logic) ---
  const handleFetch = async () => {
    if (!url.trim()) { MessagePlugin.warning("请输入视频地址"); return; }
    setLoading(true); setResult(null); setNodeIndices([]);
    try {
      const r = await otFetch(url.trim());
      if (r.ok && r.taskId) {
        setTaskId(r.taskId); setStatus("fetching"); setProgress("开始拉取...");
        sessionStorage.setItem("ot_active_task", r.taskId);
        startPolling(r.taskId);
      }
    } catch (e: any) { MessagePlugin.error(e.message); setLoading(false); }
  };

  const startPolling = (tid: string) => {
    setPolling(true);
    const iv = setInterval(async () => {
      try {
        const s = await otStatus();
        if (s.task_id !== tid) return;
        setStatus(s.status); setProgress(s.progress);
        if (s.status === "fetched") {
          clearInterval(iv); setPolling(false); setLoading(false);
          await handleAnalyze(tid);
        } else if (s.status === "done") {
          clearInterval(iv); setPolling(false); setLoading(false);
          sessionStorage.removeItem("ot_active_task");
          loadResult(tid);
        } else if (s.status === "error") {
          clearInterval(iv); setPolling(false); setLoading(false);
          sessionStorage.removeItem("ot_active_task");
          MessagePlugin.error(s.progress || "任务失败");
        }
      } catch { }
    }, 1500);
  };

  const handleAnalyze = async (tid: string) => {
    setLoading(true); setStatus("analyzing"); setProgress("开始AI分析...");
    try {
      const r = await otAnalyze(tid);
      if (r.ok) startPolling(tid);
    } catch (e: any) { MessagePlugin.error(e.message); setLoading(false); }
  };

  const loadResult = async (tid: string) => {
    try {
      const r = await otResult(tid);
      setResult(r);
      const trailLen = (r.centroidTrail || []).length;
      setMaxTimeIndex(trailLen > 0 ? trailLen - 1 : 0);
      setTimeIndex(trailLen > 0 ? trailLen - 1 : -1);
      setNodeIndices([]);
      setLoading(false);
    } catch (e: any) { MessagePlugin.error(e.message); setLoading(false); }
  };

  const handleSave = async () => {
    if (!taskId) return;
    try {
      const r = await otSave(taskId, nodeIndices);
      if (r.id) setSavedId(r.id);
      MessagePlugin.success("结果及节点已保存");
      loadSavedList();
    }
    catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleLoadSaved = async (sid: number) => {
    setLoading(true);
    try {
      const r = await otGetSaved(sid);
      setResult(r); setTaskId(r.task.id); setStatus("done");
      const trailLen = (r.centroidTrail || []).length;
      setMaxTimeIndex(trailLen > 0 ? trailLen - 1 : 0);
      setTimeIndex(trailLen > 0 ? trailLen - 1 : -1);
      // Restore saved nodes
      setNodeIndices(r.task.nodeIndices || []);
      setSavedId(sid);
      setShowSaved(false);
    } catch (e: any) { MessagePlugin.error(e.message); }
    finally { setLoading(false); }
  };

  const handleDeleteSaved = async (savedId: number) => {
    try { await otDeleteSaved(savedId); loadSavedList(); MessagePlugin.success("已删除"); }
    catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleDeleteTask = async () => {
    if (!taskId) return;
    try { await otDeleteTask(taskId); setResult(null); setTaskId(null); setStatus("idle"); setNodeIndices([]); MessagePlugin.success("已删除"); }
    catch (e: any) { MessagePlugin.error(e.message); }
  };

  // --- Slider right-click → create node ---
  const handleSliderContext = (e: React.MouseEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (!result?.centroidTrail?.length) return;
    const slider = e.currentTarget;
    const rect = slider.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(-1 + ratio * (result.centroidTrail.length)); // map from [0,1] to [-1, trail_len-1]
    const clamped = Math.max(0, Math.min(result.centroidTrail.length - 1, idx));
    setNodeIndices(prev => {
      if (prev.includes(clamped)) return prev; // no duplicates
      const next = [...prev, clamped].sort((a, b) => a - b);
      return next;
    });
    MessagePlugin.success(`已标记节点: ${result.centroidTrail[clamped]?.t || ""}`);
  };

  const handleClearNodes = () => { setNodeIndices([]); };

  // ============================================================
  //  Canvas Rendering — complete overhaul
  // ============================================================
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !result?.heatmapGrid) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const grid = result.heatmapGrid;
    const trail = result.centroidTrail || [];

    // Set canvas buffer dimensions
    canvas.width = CANVAS_W;
    canvas.height = CANVAS_H;

    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    const cellW = HM_SIZE / GRID_SIZE;
    const cellH = HM_SIZE / GRID_SIZE;

    // Find max count
    let maxCount = 0;
    for (let x = 0; x < GRID_SIZE; x++)
      for (let y = 0; y < GRID_SIZE; y++)
        if (grid[x][y] > maxCount) maxCount = grid[x][y];
    if (maxCount === 0) maxCount = 1;

    const plotRight = HM_LEFT + HM_SIZE;
    const plotBottom = HM_TOP + HM_SIZE;

    // --- Draw background grid (dark) ---
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(HM_LEFT, HM_TOP, HM_SIZE, HM_SIZE);

    // ============================================================
    //  R1: Axes with color gradients
    // ============================================================

    // X-axis gradient (bottom): Red → Green (反对米哈游 → 支持米哈游)
    const xGradY = plotBottom + 2;
    const xGrad = ctx.createLinearGradient(HM_LEFT, 0, plotRight, 0);
    xGrad.addColorStop(0, "#ef4444");   // red = 反米
    xGrad.addColorStop(0.5, "#eab308"); // yellow = neutral
    xGrad.addColorStop(1, "#22c55e");   // green = 挺米
    ctx.fillStyle = xGrad;
    ctx.fillRect(HM_LEFT, xGradY, HM_SIZE, GRAD_WIDTH);

    // Y-axis gradient (left): Blue → Pink (理性 → 感性)
    const yGradX = HM_LEFT - GRAD_WIDTH - 2;
    const yGrad = ctx.createLinearGradient(0, plotBottom, 0, HM_TOP);
    yGrad.addColorStop(0, "#3b82f6");   // blue = 理性
    yGrad.addColorStop(0.5, "#a855f7"); // purple = middle
    yGrad.addColorStop(1, "#ec4899");   // pink = 感性
    ctx.fillStyle = yGrad;
    ctx.fillRect(yGradX, HM_TOP, GRAD_WIDTH, HM_SIZE);

    // ============================================================
    //  R4: Draw heatmap cells with bloom/halo + triangle markers
    // ============================================================

    // First pass: draw bloom halos for non-zero cells
    for (let x = 0; x < GRID_SIZE; x++) {
      for (let y = 0; y < GRID_SIZE; y++) {
        const count = grid[x][y] || 0;
        if (count === 0) continue;
        const ratio = count / maxCount;
        const [cr, cg, cb] = heatColor(ratio);
        const [cx, cy] = gridToCanvas(x, y);

        // Draw irregular bloom halo
        const haloRadius = Math.max(3, ratio * cellW * 4);
        const haloGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, haloRadius);
        haloGrad.addColorStop(0, rgbStr(cr, cg, cb, 0.55));
        haloGrad.addColorStop(0.5, rgbStr(cr, cg, cb, 0.2));
        haloGrad.addColorStop(1, rgbStr(cr, cg, cb, 0));
        ctx.fillStyle = haloGrad;

        // Irregular shape: use a slightly distorted circle
        ctx.beginPath();
        const segments = 6;
        for (let s = 0; s < segments; s++) {
          const angle = (s / segments) * Math.PI * 2;
          const rJitter = haloRadius * (0.7 + 0.3 * ((x * 7 + y * 13 + s * 3) % 10) / 10);
          const sx = cx + Math.cos(angle) * rJitter;
          const sy = cy + Math.sin(angle) * rJitter;
          if (s === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        }
        ctx.closePath();
        ctx.fill();
      }
    }

    // Second pass: triangle markers at data points
    for (let x = 0; x < GRID_SIZE; x++) {
      for (let y = 0; y < GRID_SIZE; y++) {
        const count = grid[x][y] || 0;
        if (count === 0) continue;
        const ratio = count / maxCount;
        const [cr, cg, cb] = heatColor(ratio);
        const [cx, cy] = gridToCanvas(x, y);

        const triSize = 4;
        ctx.fillStyle = rgbStr(cr, cg, cb, 0.9);
        ctx.beginPath();
        ctx.moveTo(cx, cy - triSize);
        ctx.lineTo(cx - triSize * 0.87, cy + triSize * 0.5);
        ctx.lineTo(cx + triSize * 0.87, cy + triSize * 0.5);
        ctx.closePath();
        ctx.fill();
      }
    }

    // ============================================================
    //  R4 (contour): Dashed contour-like lines at density thresholds
    // ============================================================
    const thresholds = [0.25, 0.5, 0.75];
    const contourColors = ["rgba(255,255,255,0.15)", "rgba(255,255,255,0.25)", "rgba(255,255,255,0.4)"];

    for (let ti = 0; ti < thresholds.length; ti++) {
      const thresh = thresholds[ti] * maxCount;
      ctx.save();
      ctx.strokeStyle = contourColors[ti];
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);

      // Scan for density boundaries: cell above thresh, neighbor below
      for (let x = 0; x < GRID_SIZE; x++) {
        for (let y = 0; y < GRID_SIZE; y++) {
          if ((grid[x][y] || 0) < thresh) continue;
          const [cx, cy] = gridToCanvas(x, y);

          // Check 4 neighbors: if any below threshold, draw a boundary segment
          const dirs: [number, number, number, number, number, number][] = [
            [-1, 0, cx - cellW / 2, cy - cellH / 2, cx, cy - cellH / 2],
            [1, 0, cx, cy - cellH / 2, cx + cellW / 2, cy - cellH / 2],
            [0, -1, cx - cellW / 2, cy - cellH / 2, cx - cellW / 2, cy],
            [0, 1, cx - cellW / 2, cy, cx - cellW / 2, cy + cellH / 2],
          ];

          for (const [dx, dy, x1, y1, x2, y2] of dirs) {
            const nx = x + dx, ny = y + dy;
            if (nx < 0 || nx >= GRID_SIZE || ny < 0 || ny >= GRID_SIZE) continue;
            if ((grid[nx][ny] || 0) < thresh) {
              ctx.beginPath();
              ctx.moveTo(x1, y1);
              ctx.lineTo(x2, y2);
              ctx.stroke();
            }
          }
        }
      }
      ctx.restore();
    }

    // ============================================================
    //  R2: Grid lines every 10 units
    // ============================================================
    ctx.strokeStyle = "rgba(148,163,184,0.12)";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 100; i += 10) {
      const [, ly] = gridToCanvas(0, i);
      const [lx] = gridToCanvas(i, 0);

      // Vertical grid lines
      ctx.beginPath();
      ctx.moveTo(lx, HM_TOP);
      ctx.lineTo(lx, plotBottom);
      ctx.stroke();

      // Horizontal grid lines
      ctx.beginPath();
      ctx.moveTo(HM_LEFT, ly);
      ctx.lineTo(plotRight, ly);
      ctx.stroke();
    }

    // ============================================================
    //  R3: Prominent divider lines at X=50, Y=50
    // ============================================================
    const midX = HM_LEFT + 0.5 * HM_SIZE;
    const midY = HM_TOP + 0.5 * HM_SIZE;

    ctx.strokeStyle = "rgba(255,255,255,0.35)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);

    // Vertical divider (X=50)
    ctx.beginPath();
    ctx.moveTo(midX, HM_TOP);
    ctx.lineTo(midX, plotBottom);
    ctx.stroke();

    // Horizontal divider (Y=50)
    ctx.beginPath();
    ctx.moveTo(HM_LEFT, midY);
    ctx.lineTo(plotRight, midY);
    ctx.stroke();

    // Small "+" at center
    ctx.beginPath();
    ctx.moveTo(midX - 6, midY);
    ctx.lineTo(midX + 6, midY);
    ctx.moveTo(midX, midY - 6);
    ctx.lineTo(midX, midY + 6);
    ctx.stroke();

    // ============================================================
    //  Axes tick marks and labels (inside plot area, bold light)
    // ============================================================
    ctx.font = "bold 9px sans-serif";
    ctx.textBaseline = "top";

    // --- Y-axis ticks (inside, left edge) ---
    for (let i = 0; i <= 100; i += 10) {
      const [, ly] = gridToCanvas(0, i);

      // Tick mark extending inward
      ctx.beginPath();
      ctx.moveTo(HM_LEFT, ly);
      ctx.lineTo(HM_LEFT + 5, ly);
      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Label at left edge, inside
      ctx.fillStyle = "#cbd5e1";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      if (i === 0) {
        // Only draw 0 once at bottom-left
      } else {
        ctx.fillText(i.toString(), HM_LEFT + 8, ly);
      }
    }

    // --- X-axis ticks (inside, bottom edge) ---
    for (let i = 0; i <= 100; i += 10) {
      const [lx] = gridToCanvas(i, 0);

      // Tick mark extending inward
      ctx.beginPath();
      ctx.moveTo(lx, plotBottom);
      ctx.lineTo(lx, plotBottom - 5);
      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Label at bottom edge, inside
      ctx.fillStyle = "#cbd5e1";
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText(i.toString(), lx, plotBottom - 7);
    }

    // ============================================================
    //  R6/R7: Draw centroid trajectory through node landmarks
    // ============================================================

    if (trail.length > 1) {
      // Build the path: start → node1 → node2 → ... → last
      const pathPoints: OtCentroidTrailPoint[] = [trail[0]];
      for (const ni of nodeIndices) {
        if (ni < trail.length) pathPoints.push(trail[ni]);
      }

      if (pathPoints.length > 1) {
        // Draw trajectory with border (dark outline + gold dashed inner)
        ctx.save();
        ctx.beginPath();
        for (let i = 0; i < pathPoints.length; i++) {
          const [px, py] = gridToCanvas(pathPoints[i].x, pathPoints[i].y);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }

        // Outer border (dark, thicker)
        ctx.strokeStyle = "rgba(0,0,0,0.7)";
        ctx.lineWidth = 4;
        ctx.setLineDash([]);
        ctx.stroke();

        // Inner gold dashed line
        ctx.strokeStyle = "rgba(255, 215, 0, 0.85)";
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 5]);
        ctx.stroke();
        ctx.restore();
      }

      // --- Current time position dot (R5: small golden centroid) ---
      if (timeIndex >= 0 && timeIndex < trail.length) {
        const tp = trail[timeIndex];
        const [cx, cy] = gridToCanvas(tp.x, tp.y);
        const dotR = 5;

        // Gold dot with white border
        ctx.beginPath();
        ctx.arc(cx, cy, dotR + 2, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(cx, cy, dotR, 0, Math.PI * 2);
        ctx.fillStyle = "#FFD700";
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([]);
        ctx.stroke();
      }

      // --- R7: Star markers at node positions ---
      const drawStar = (cx: number, cy: number, r: number) => {
        const spikes = 5;
        const outerR = r;
        const innerR = r * 0.4;
        ctx.beginPath();
        for (let i = 0; i < spikes * 2; i++) {
          const angle = (Math.PI / 2 * -1) + (i * Math.PI) / spikes;
          const radius = i % 2 === 0 ? outerR : innerR;
          const sx = cx + Math.cos(angle) * radius;
          const sy = cy + Math.sin(angle) * radius;
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        }
        ctx.closePath();
        ctx.fill();
      };

      for (let ni = 0; ni < nodeIndices.length; ni++) {
        const idx = nodeIndices[ni];
        if (idx >= trail.length) continue;
        const [px, py] = gridToCanvas(trail[idx].x, trail[idx].y);

        // Star border (dark)
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        drawStar(px, py, 8);

        // Gold star
        ctx.fillStyle = "#FFD700";
        drawStar(px, py, 6);

        // Node number label
        ctx.fillStyle = "#fff";
        ctx.font = "bold 8px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillText(`${ni + 1}`, px, py - 8);
      }

      // Default final centroid star if no nodes defined
      if (nodeIndices.length === 0 && trail.length > 0) {
        const last = trail[trail.length - 1];
        const [px, py] = gridToCanvas(last.x, last.y);
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        drawStar(px, py, 8);
        ctx.fillStyle = "#FFD700";
        drawStar(px, py, 6);
      }
    }

  }, [result, timeIndex, nodeIndices]);

  useEffect(() => { draw(); }, [draw, zoom]);

  // Canvas CSS
  const canvasContainerStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "center",
    overflow: "hidden",
  };

  const canvasStyle: React.CSSProperties = {
    width: CANVAS_W * zoom,
    height: CANVAS_H * zoom,
    cursor: "crosshair",
    transition: "width 0.2s, height 0.2s",
  };

  // --- Status tag ---
  const statusTag = (s: string) => {
    const map: Record<string, { theme: any; text: string }> = {
      idle: { theme: "default", text: "空闲" },
      fetching: { theme: "primary", text: "拉取中" },
      fetched: { theme: "warning", text: "待分析" },
      analyzing: { theme: "primary", text: "分析中" },
      done: { theme: "success", text: "完成" },
      error: { theme: "danger", text: "错误" },
    };
    const m = map[s] || { theme: "default", text: s };
    return <Tag theme={m.theme} variant="light">{m.text}</Tag>;
  };

  // --- Get current centroid ---
  const getCurrentCentroid = () => {
    if (!result) return null;
    const trail = result.centroidTrail || [];
    if (timeIndex >= 0 && timeIndex < trail.length) {
      return trail[timeIndex];
    }
    return null;
  };

  const centroid = getCurrentCentroid();

  return (
    <div className="flex h-full">
      {/* Main content */}
      <div className="flex-1 space-y-4 animate-fade-in-up p-4 overflow-auto">
        <div>
          <h1 className="text-2xl font-bold text-white">舆情推演</h1>
          <p className="text-sm text-[#94a3b8] mt-1">
            输入B站视频链接，全量拉取时间序评论，AI坐标分析后生成二维舆情地形图与质心漂移动画
          </p>
        </div>

        {/* Input + Controls */}
        <div className="glass-card p-4 flex flex-wrap items-center gap-3">
          <Input
            value={url}
            onChange={(v) => setUrl(v as string)}
            placeholder="粘贴B站视频链接 (如 https://www.bilibili.com/video/BV...)"
            className="flex-1"
            style={{ minWidth: 320 }}
            onEnter={handleFetch}
          />
          <Button theme="primary" onClick={handleFetch} loading={loading && status !== "done"}>
            开始全量拉取
          </Button>
          {status === "fetched" && (
            <Button theme="warning" onClick={() => taskId && handleAnalyze(taskId)}>
              开始AI分析
            </Button>
          )}
          {status === "done" && result && (
            <>
              <Button theme="success" onClick={handleSave}>保存结果</Button>
              <Button variant="outline" onClick={handleDeleteTask}>删除</Button>
              <Button theme="primary" onClick={() => navigate("/cluster-analysis")}>
                跳转至聚类分群
              </Button>
            </>
          )}
        </div>

        {/* Progress */}
        {(polling || loading) && status !== "done" && (
          <div className="glass-card p-4">
            <div className="flex items-center gap-3">
              {statusTag(status)}
              <span className="text-sm text-[#94a3b8]">{progress}</span>
              <Loading size="small" />
            </div>
          </div>
        )}

        {/* Heatmap */}
        {result?.heatmapGrid && (
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-white">
                  二维舆论热力图
                  {result.task?.title && <span className="text-sm text-[#94a3b8] ml-2 font-normal">— {result.task.title}</span>}
                </h3>
                {/* R8: Help icon with tooltip */}
                <Tooltip
                  visible={helpVisible}
                  onVisibleChange={setHelpVisible}
                  trigger="hover"
                  showArrow
                  content={
                    <div className="text-xs leading-relaxed space-y-1.5 py-1">
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-0 h-0 border-l-[5px] border-r-[5px] border-b-[7px] border-l-transparent border-r-transparent border-b-[#f59e0b]" />
                        <span>三角形 — 评论数据点，颜色越红密度越高</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-yellow-400 text-[14px] leading-none">★</span>
                        <span>五角星 — 用户标记的节点时刻质心</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#FFD700] border border-white" />
                        <span>金色圆点 — 当前时间轴滑块位置的质心</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-5 h-0 border-t-2 border-dashed border-yellow-400" />
                        <span>金色虚线 — 从开始到各节点的质心漂移轨迹</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-block w-5 h-0 border-t border-dashed border-white/30" />
                        <span>白色虚线 — 密度等值线（等高线）</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[#64748b]">+</span>
                        <span>十字线 — X=50 / Y=50 中立分界线</span>
                      </div>
                      <div className="mt-2 text-[#64748b] border-t border-[#334155] pt-2">
                        <div className="flex items-center gap-2">
                          <span className="inline-block w-4 h-3 rounded-sm" style={{ background: "linear-gradient(to right, #ef4444, #22c55e)" }} />
                          <span>横轴渐变: 红=反对米哈游 → 绿=支持米哈游</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="inline-block w-3 h-4 rounded-sm" style={{ background: "linear-gradient(to top, #3b82f6, #ec4899)" }} />
                          <span>纵轴渐变: 蓝=理性 → 粉=感性</span>
                        </div>
                      </div>
                      <div className="mt-2 text-[#64748b] border-t border-[#334155] pt-2">
                        <p>💡 在时间轴上右键点击可标记节点，</p>
                        <p>&nbsp;&nbsp;&nbsp;&nbsp;质心轨迹将依次经过各节点。</p>
                      </div>
                    </div>
                  }
                >
                  <span
                    className="inline-flex items-center justify-center w-5 h-5 rounded-full border border-[#64748b] text-[#94a3b8] text-[11px] font-bold cursor-help hover:border-[#94a3b8] hover:text-white transition-colors"
                  >i</span>
                </Tooltip>
              </div>
              <div className="flex items-center gap-2 text-xs text-[#94a3b8]">
                质心: {centroid
                  ? `(${centroid.x.toFixed(1)}, ${centroid.y.toFixed(1)})`
                  : `(${result.task.centroidX?.toFixed(1) ?? "—"}, ${result.task.centroidY?.toFixed(1) ?? "—"})`}
                <span className="mx-1">|</span>
                总评论: {result.task.totalComments}
                <span className="mx-1">|</span>
                分析: {result.task.analyzedCount}
                {nodeIndices.length > 0 &&
                  <><span className="mx-1">|</span>节点: {nodeIndices.length}</>
                }
              </div>
            </div>

            <div style={canvasContainerStyle}>
              <canvas
                ref={canvasRef}
                style={canvasStyle}
              />
            </div>

            {/* Zoom controls */}
            <div className="flex items-center justify-center gap-3 mt-3">
              <Button size="small" variant="outline" onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}>-</Button>
              <span className="text-xs text-[#94a3b8]">{Math.round(zoom * 100)}%</span>
              <Button size="small" variant="outline" onClick={() => setZoom(Math.min(3, zoom + 0.25))}>+</Button>
              <Button size="small" variant="outline" onClick={() => setZoom(1)}>重置</Button>
            </div>
          </div>
        )}

        {/* Timeline slider — R6: with draggable handle + right-click nodes */}
        {result && (result.centroidTrail || []).length > 1 && (
          <div className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-white">
                时间轴 — 舆论质心漂移
              </h3>
              <div className="flex items-center gap-2">
                {nodeIndices.length > 0 && savedId && (
                  <Button size="small" theme="primary" onClick={async () => {
                    try {
                      await otSaveNodes(savedId, nodeIndices);
                      MessagePlugin.success(`已持久化 ${nodeIndices.length} 个节点`);
                    } catch (e: any) { MessagePlugin.error("保存节点失败"); }
                  }}>
                    保存节点 ({nodeIndices.length})
                  </Button>
                )}
                {nodeIndices.length > 0 && (
                  <Button size="small" variant="outline" onClick={handleClearNodes}>
                    清除节点
                  </Button>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3 mb-2">
              <Tag theme="warning" variant="light" size="small">
                {centroid ? centroid.t : "最终质心"}
              </Tag>
              <span className="text-xs text-[#94a3b8]">
                {centroid
                  ? `(${centroid.x.toFixed(1)}, ${centroid.y.toFixed(1)}) — ${centroid.count}条评论`
                  : `(${result.task.centroidX?.toFixed(1) ?? "—"}, ${result.task.centroidY?.toFixed(1) ?? "—"}) — 全部评论`}
              </span>
            </div>

            {/* Custom slider with node markers */}
            <div style={{ position: "relative", width: "100%" }}>
              <input
                ref={sliderRef}
                type="range"
                min={-1}
                max={result.centroidTrail.length - 1}
                value={timeIndex}
                onChange={(e) => setTimeIndex(parseInt(e.target.value))}
                onContextMenu={handleSliderContext}
                style={{
                  width: "100%",
                  height: 10,
                  accentColor: "#FFD700",
                  borderRadius: 5,
                  cursor: "pointer",
                  background: "linear-gradient(to right, #22c55e, #eab308, #ef4444)",
                  WebkitAppearance: "none",
                  appearance: "none",
                }}
              />

              {/* Visible circular thumb indicator */}
              <div
                style={{
                  position: "absolute",
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                  left: `${((timeIndex + 1) / result.centroidTrail.length) * 100}%`,
                  width: 18,
                  height: 18,
                  borderRadius: "50%",
                  background: "radial-gradient(circle at 40% 35%, #ffe680, #FFD700 50%, #b8960b)",
                  border: "2px solid #fff",
                  boxShadow: "0 0 8px rgba(255,215,0,0.6), 0 2px 4px rgba(0,0,0,0.4)",
                  pointerEvents: "none",
                  zIndex: 3,
                  transition: "left 0.1s ease-out",
                }}
              />

              {/* Node markers on top of slider */}
              {result && nodeIndices.length > 0 && (
                <div
                  style={{
                    position: "absolute",
                    top: 0, left: 0, right: 0, bottom: 0,
                    pointerEvents: "none",
                  }}
                >
                  {nodeIndices.map((ni, i) => {
                    const ratio = (ni + 1) / result.centroidTrail.length;
                    return (
                      <div
                        key={ni}
                        style={{
                          position: "absolute",
                          left: `${ratio * 100}%`,
                          top: "50%",
                          transform: "translate(-50%, -50%)",
                          width: 10,
                          height: 10,
                          background: "#FFD700",
                          borderRadius: "50%",
                          boxShadow: "0 0 4px rgba(0,0,0,0.5)",
                          zIndex: 2,
                        }}
                        title={`节点 ${i + 1}: ${result.centroidTrail[ni]?.t}`}
                      />
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex justify-between text-[10px] text-[#64748b] mt-2">
              <span>{result.centroidTrail[0]?.t || "开始"}</span>
              <span className="text-[#FFD700] text-[10px]">右键标记节点 ← 拖动滑块查看质心位置</span>
              <span>{result.centroidTrail[result.centroidTrail.length - 1]?.t || "结束"}</span>
            </div>

            {/* Node list display */}
            {nodeIndices.length > 0 && result && (
              <div className="mt-3 flex flex-wrap gap-2">
                {nodeIndices.map((ni, i) => {
                  const tp = result.centroidTrail[ni];
                  return (
                    <Tag key={ni} theme="warning" variant="outline" size="small">
                      节点{i + 1}: {tp?.t} ({tp?.x.toFixed(0)},{tp?.y.toFixed(0)})
                    </Tag>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Legend */}
        {result?.heatmapGrid && (
          <div className="glass-card p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-[#94a3b8]">
              <span>评论密度:</span>
              <div className="w-32 h-3 rounded" style={{ background: "linear-gradient(to right, #00ff00, #ffff00, #ff0000)" }} />
              <span>低</span><span className="ml-auto">高</span>

              <span className="ml-4 flex items-center gap-1">
                <span className="inline-block w-0 h-0 border-l-[5px] border-r-[5px] border-b-[7px] border-l-transparent border-r-transparent border-b-[#f59e0b]" /> 数据点
              </span>
              <span className="ml-2 flex items-center gap-1">
                <span className="text-yellow-400 text-[12px] leading-none">★</span> 节点质心
              </span>
              <span className="ml-2 flex items-center gap-1">
                <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#FFD700]" /> 当前质心
              </span>
              <span className="ml-2 flex items-center gap-1">
                <span className="inline-block w-5 h-0 border-t-2 border-dashed border-yellow-400" /> 漂移轨迹
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Right sidebar — saved results */}
      <div
        className={`h-full glass-card border-l border-[#2a2a4a] transition-all duration-300 overflow-y-auto ${showSaved ? "w-72" : "w-10"}`}
        style={{ borderRadius: 0 }}
      >
        <div
          className="flex items-center justify-center py-3 cursor-pointer hover:bg-white/5"
          onClick={() => setShowSaved(!showSaved)}
          title="已存储的推演结果"
        >
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
            {savedList.length === 0 && (
              <p className="text-xs text-[#64748b]">暂无存储</p>
            )}
            {savedList.map((s) => (
              <div key={s.id} className="glass-card p-3 text-xs space-y-1">
                <div className="text-white font-medium truncate">{s.title || s.bvid}</div>
                <div className="text-[#64748b]">评论: {s.totalComments} | 分析: {s.analyzedCount}</div>
                <div className="text-[#94a3b8]">质心: ({s.centroidX?.toFixed(1)}, {s.centroidY?.toFixed(1)})</div>
                <div className="text-[#64748b]">{s.savedAt?.slice(0, 10)}</div>
                <div className="flex gap-2 mt-2">
                  <Button size="small" theme="primary" onClick={() => handleLoadSaved(s.id)}>加载</Button>
                  <Button size="small" variant="outline" onClick={() => handleDeleteSaved(s.id)}>删除</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
