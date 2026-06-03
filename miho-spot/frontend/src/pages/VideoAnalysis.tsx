import { useState, useEffect, useCallback, useRef } from "react";
import { Loading, Button, Input, Tag, MessagePlugin, Dialog, Popup, Tooltip as TdTooltip } from "tdesign-react";
import {
  PlayCircleIcon,
  RefreshIcon,
  DeleteIcon,
  BookmarkIcon,
  CloseIcon,
  ThumbUpIcon,
  TimeIcon,
  SearchIcon,
} from "tdesign-icons-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import {
  getVaTasks, vaFetchComments, getVaStatus, vaAnalyze, getVaResult, deleteVaTask,
  saveVaTask, getSavedVaTasks, deleteSavedVaTask, getKolTopUsers, addToIdentityQueue,
} from "../services/api";
import type { VaTask, VaResult, VaHeatmapPoint, VaStatus, SavedVaTask, KolUser } from "../types";

/** Parsed progress info for the progress bar */
interface ProgressInfo {
  stage: "fetching" | "analyzing" | "rendering" | null;
  message: string;
  current: number;
  total: number;
  percent: number; // 0-100
}

const COLORS = {
  bg: "#0a0a20",
  grid: "#1a1a40",
  axisX: "#6366f1",
  axisY: "#8b5cf6",
  centroid: "#f59e0b",
  text: "#94a3b8",
};

function Heatmap3D({ data }: { data: VaResult | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{ scene: THREE.Scene; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer; controls: OrbitControls; cleanup: () => void } | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data) return;
    const container = containerRef.current;

    // Cleanup previous
    if (sceneRef.current) sceneRef.current.cleanup();
    container.innerHTML = "";

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(COLORS.bg);

    // Camera
    const camera = new THREE.PerspectiveCamera(55, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(70, 80, 100);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 30;
    controls.maxDistance = 300;
    controls.maxPolarAngle = Math.PI / 2 - 0.02; // prevent going below floor

    // Lights — hemisphere with symmetrical sky/ground so back-side faces get equal ambient
    scene.add(new THREE.HemisphereLight(0x88aaff, 0x88aaff, 1.2));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.5);
    dirLight.position.set(50, 80, 50);
    scene.add(dirLight);

    // Floor grid (X=0..100, Y=0..100)
    const gridSize = 105;
    const gridDivisions = 10;
    const gridHelper = new THREE.GridHelper(gridSize, gridDivisions, COLORS.axisX, COLORS.grid);
    gridHelper.rotation.x = Math.PI / 2;
    gridHelper.position.set(50, 0, 50); // center at (50, 0, 50) so X/Y ranges 0..100 in world space
    scene.add(gridHelper);

    // Floor plane
    const floorGeo = new THREE.PlaneGeometry(gridSize, gridSize);
    const floorMat = new THREE.MeshBasicMaterial({ color: 0x0f0f28, transparent: true, opacity: 0.4, side: THREE.DoubleSide });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(50, -0.05, 50);
    scene.add(floor);

    // Axes lines
    function makeAxisLine(start: [number, number, number], end: [number, number, number], color: number) {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(...start), new THREE.Vector3(...end),
      ]);
      return new THREE.Line(geo, new THREE.LineBasicMaterial({ color }));
    }
    // X-axis (anti→pro mihoyo): along X direction at Y=0 edge
    scene.add(makeAxisLine([0, 0, -2], [100, 0, -2], 0x6366f1));
    // Y-axis (rational→emotional): along Z direction at X=-2 edge
    scene.add(makeAxisLine([-2, 0, 0], [-2, 0, 100], 0x8b5cf6));

    // Height scale: max Z determines height scaling
    const maxZ = Math.max(...data.points.map((p) => p.z), 1);
    const maxTerrainHeight = 40;

    // ===== Build continuous terrain surface instead of discrete bars =====

    // Step 1: Build a lookup map from data points for fast interpolation
    const dataMap = new Map<string, number>();
    for (const pt of data.points) {
      if (pt.z > 0) dataMap.set(`${pt.x},${pt.y}`, pt.z);
    }

    // GUARD: If no valid data points (e.g., fetched but not yet analyzed), skip terrain
    if (dataMap.size > 0 && maxZ > 1) {
    // Step 2: IDW interpolation — estimate z at any (x,y) from nearby data points
    function interpolateZ(gx: number, gy: number): number {
      // Exact match
      const key = `${gx},${gy}`;
      if (dataMap.has(key)) return dataMap.get(key)!;

      let sumWeight = 0;
      let sumValue = 0;
      const power = 2.5; // higher = sharper peaks around data points
      for (const [k, v] of dataMap) {
        const [dx, dy] = k.split(",").map(Number);
        const dist = Math.sqrt((gx - dx) ** 2 + (gy - dy) ** 2);
        if (dist < 0.1) return v; // essentially same point
        const w = 1 / (dist ** power);
        sumWeight += w;
        sumValue += w * v;
      }
      return sumWeight > 0 ? sumValue / sumWeight : 0;
    }

    // Step 3: Generate terrain grid mesh — centered at (50,0,50) to match grid/floor
    const gridRes = 120; // resolution: 120x120 vertices over the 100x100 space
    const terrainGeo = new THREE.PlaneGeometry(102, 102, gridRes - 1, gridRes - 1);
    terrainGeo.rotateX(-Math.PI / 2); // lay flat on XZ plane

    const posAttr = terrainGeo.attributes.position;
    const colorAttr = new Float32Array(posAttr.count * 3);

    for (let i = 0; i < posAttr.count; i++) {
      const vx = posAttr.getX(i);   // ranges ~-51..+51 (centered at origin)
      const vz = posAttr.getZ(i);   // ranges ~-51..+51
      // Map to data coordinate space 0..100
      const dx = Math.max(0, Math.min(100, vx + 51));
      const dy = Math.max(0, Math.min(100, vz + 51));

      const zVal = interpolateZ(dx, dy);
      const h = (zVal / maxZ) * maxTerrainHeight;
      posAttr.setY(i, h);

      // Color: low=green → mid=yellow → high=red (based on HEIGHT)
      const t = Math.min(zVal / maxZ, 1); // 0..1 normalized height
      let r: number, g: number, b: number;
      if (t < 0.5) {
        // green → yellow
        const s = t * 2;
        r = s; g = 0.85; b = 0.15;
      } else {
        // yellow → red
        const s = (t - 0.5) * 2;
        r = 1; g = 0.85 * (1 - s); b = 0.15 * (1 - s);
      }
      colorAttr[i * 3] = r;
      colorAttr[i * 3 + 1] = g;
      colorAttr[i * 3 + 2] = b;
    }

    terrainGeo.setAttribute("color", new THREE.BufferAttribute(colorAttr, 3));
    terrainGeo.computeVertexNormals(); // smooth shading for mountain look

    const terrainMat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      side: THREE.FrontSide,
      roughness: 0.6,
      metalness: 0.1,
    });
    const terrainMesh = new THREE.Mesh(terrainGeo, terrainMat);
    terrainMesh.position.set(50, 0, 50);
    scene.add(terrainMesh);

    // Back-side mesh — MeshBasicMaterial ignores lights, always shows vertex colors
    const backMat = new THREE.MeshBasicMaterial({
      vertexColors: true,
      side: THREE.BackSide,
    });
    const backMesh = new THREE.Mesh(terrainGeo, backMat);
    backMesh.position.set(50, 0, 50);
    scene.add(backMesh);

    // Step 4: Wireframe overlay on top for contour/definition feel
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      wireframe: true,
      transparent: true,
      opacity: 0.06,
      side: THREE.DoubleSide,
    });
    const wireMesh = new THREE.Mesh(terrainGeo.clone(), wireMat);
    wireMesh.position.set(50, 0.05, 50); // slight Y offset + same XY offset as terrain
    scene.add(wireMesh);

    // Step 5: Semi-transparent base plate under terrain
    const baseGeo = new THREE.PlaneGeometry(104, 104, gridRes - 1, gridRes - 1);
    baseGeo.rotateX(-Math.PI / 2);
    const basePos = baseGeo.attributes.position;
    for (let i = 0; i < basePos.count; i++) {
      const vx = basePos.getX(i);
      const vz = basePos.getZ(i);
      const dx = Math.max(0, Math.min(100, vx + 52));
      const dy = Math.max(0, Math.min(100, vz + 52));
      const zVal = interpolateZ(dx, dy);
      const h = (zVal / maxZ) * maxTerrainHeight;
      basePos.setY(i, Math.max(h - 0.3, 0)); // slightly below terrain
    }
    baseGeo.computeVertexNormals();
    const baseMat = new THREE.MeshLambertMaterial({
      color: 0x1a1a50,
      transparent: true,
      opacity: 0.35,
      side: THREE.DoubleSide,
    });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.set(50, 0, 50);
    scene.add(baseMesh);
    } // end guard: dataMap.size > 0

    // Centroid marker (golden sphere with ring) — uses NO-NEUTRAL centroid for accuracy
    const cxC = data.task.centroidXNoNeutral ?? data.task.centroidX;
    const cyC = data.task.centroidYNoNeutral ?? data.task.centroidY;
    if (cxC >= 0 && cyC >= 0) {
      const cx = cxC;
      const cy = cyC;

      // Sphere
      const cSphereGeo = new THREE.SphereGeometry(1.8, 24, 24);
      const cSphereMat = new THREE.MeshBasicMaterial({ color: COLORS.centroid });
      const cSphere = new THREE.Mesh(cSphereGeo, cSphereMat);
      cSphere.position.set(cx, maxTerrainHeight * 0.7, cy);
      scene.add(cSphere);

      // Vertical line from sphere down to floor
      const cLineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(cx, 0, cy),
        new THREE.Vector3(cx, maxTerrainHeight * 0.68, cy),
      ]);
      scene.add(new THREE.Line(cLineGeo, new THREE.LineBasicMaterial({ color: COLORS.centroid })));

      // Ring on floor
      const cRingGeo = new THREE.RingGeometry(2.5, 3.2, 32);
      const cRingMat = new THREE.MeshBasicMaterial({ color: COLORS.centroid, side: THREE.DoubleSide, transparent: true, opacity: 0.5 });
      const cRing = new THREE.Mesh(cRingGeo, cRingMat);
      cRing.rotation.x = -Math.PI / 2;
      cRing.position.set(cx, 0.01, cy);
      scene.add(cRing);
    }

    // Animation loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const handleResize = () => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    sceneRef.current = {
      scene, camera, renderer, controls,
      cleanup: () => {
        cancelAnimationFrame(animId);
        window.removeEventListener("resize", handleResize);
        controls.dispose();
        renderer.dispose();
        scene.clear();
      },
    };

    return () => {
      if (sceneRef.current) sceneRef.current.cleanup();
      sceneRef.current = null;
    };
  }, [data]);

  if (!data) return null;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: 500 }} className="rounded-xl overflow-hidden" />
  );
}

export default function VideoAnalysis() {
  const [tasks, setTasks] = useState<VaTask[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [resultData, setResultData] = useState<VaResult | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [fetching, setFetching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [progressInfo, setProgressInfo] = useState<ProgressInfo | null>(null);
  const pollRef = useRef<number | null>(null);

  // New: saved tasks dialog
  const [savedDialogOpen, setSavedDialogOpen] = useState(false);
  const [savedTasks, setSavedTasks] = useState<SavedVaTask[]>([]);

  // New: KOL Top10 panel
  const [kolPanelOpen, setKolPanelOpen] = useState<"hot" | "time" | null>(null);
  const [kolUsers, setKolUsers] = useState<KolUser[]>([]);
  const [kolLoading, setKolLoading] = useState(false);

  // Parse backend progress string into structured ProgressInfo
  const parseProgress = useCallback((st: VaStatus): ProgressInfo | null => {
    if (!st || !st.status || st.status === "idle" || st.status === "done" || st.status === "error" || st.status === "fetched" || st.status === "running") {
      return null;
    }
    const stage: ProgressInfo["stage"] = st.status === "fetching" ? "fetching" : "analyzing";
    const msg = st.progress || "";
    // Try to extract "分析进度: 12/116" pattern
    const match = msg.match(/(\d+)\/(\d+)/);
    if (match) {
      const current = parseInt(match[1], 10);
      const total = parseInt(match[2], 10);
      return { stage, message: msg, current, total, percent: Math.round((current / Math.max(total, 1)) * 100) };
    }
    // For fetch stage without numbers — show indeterminate
    return { stage, message: msg, current: 0, total: 0, percent: 0 };
  }, []);

  // Load task list — NO auto-select
  const loadTasks = useCallback(async () => {
    setLoadingTasks(true);
    try {
      const list = await getVaTasks();
      setTasks(list);
      // Do NOT auto-select any task; let user pick manually
    } catch {}
    setLoadingTasks(false);
  }, []);

  // Poll status during fetch/analyze
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const st: VaStatus = await getVaStatus();
        // Update progress bar from server progress text
        const pi = parseProgress(st);
        if (pi) setProgressInfo(pi);

        if (st.status !== "fetching" && st.status !== "analyzing" && st.status !== "running") {
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          setProgressInfo(null);
          loadTasks();
          if (st.task_id && (st.status === "done" || st.status === "fetched")) {
            // Only auto-load result for the actively running task
            if (st.task_id === activeTaskId) {
              const tRes = await getVaResult(st.task_id);
              setResultData(tRes);
            }
          }
          setFetching(false);
          setAnalyzing(false);
        }
      } catch {}
    }, 2000);
  }, [loadTasks, parseProgress, activeTaskId]);

  // Handle fetch
  const handleFetch = async () => {
    const url = urlInput.trim();
    if (!url) { MessagePlugin.warning("请输入B站视频链接"); return; }

    setFetching(true);
    setResultData(null);
    setProgressInfo({ stage: "fetching", message: "正在解析视频链接...", current: 0, total: 0, percent: 0 });
    try {
      const res = await vaFetchComments(url);
      if (!res.ok) { MessagePlugin.error(res.message); setFetching(false); setProgressInfo(null); return; }
      MessagePlugin.info(res.message || "开始拉取评论...");
      startPolling();
      setActiveTaskId(res.taskId!);
    } catch (e: any) {
      MessagePlugin.error(e.message || "拉取失败");
      setFetching(false);
      setProgressInfo(null);
    }
  };

  // Handle analyze
  const handleAnalyze = async () => {
    if (!activeTaskId) return;
    setAnalyzing(true);
    setProgressInfo({ stage: "analyzing", message: "正在准备 AI 分析...", current: 0, total: 0, percent: 0 });
    try {
      const res = await vaAnalyze(activeTaskId);
      if (!res.ok) { MessagePlugin.error(res.message); setAnalyzing(false); setProgressInfo(null); return; }
      MessagePlugin.info(res.message || "开始AI分析...");
      startPolling();
    } catch (e: any) {
      MessagePlugin.error(e.message || "分析失败");
      setAnalyzing(false);
      setProgressInfo(null);
    }
  };

  // Load result for a specific task
  const handleSelectTask = async (taskId: string) => {
    setActiveTaskId(taskId);
    setResultData(null);
    // Show brief rendering indicator
    setProgressInfo({ stage: "rendering", message: "正在加载数据并渲染热力图...", current: 0, total: 0, percent: 50 });
    try {
      const res = await getVaResult(taskId);
      setProgressInfo({ stage: "rendering", message: "正在绘制三维场景...", current: 1, total: 1, percent: 100 });
      // Small delay so user sees the rendering phase
      await new Promise((r) => setTimeout(r, 300));
      setResultData(res);
      // Clear rendering progress after data is set (Heatmap3D useEffect will pick it up)
      setTimeout(() => setProgressInfo(null), 500);
    } catch { setResultData(null); setProgressInfo(null); }
  };

  // Delete task
  const handleDelete = async (taskId: string) => {
    try {
      await deleteVaTask(taskId);
      if (activeTaskId === taskId) { setActiveTaskId(null); setResultData(null); }
      MessagePlugin.success("已删除");
      loadTasks();
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  // Save task to archive
  const handleSaveTask = async () => {
    if (!activeTaskId || !activeTask?.status) return;
    if (activeTask.status !== "done") { MessagePlugin.warning("只能存储已完成的任务"); return; }
    try {
      const res = await saveVaTask(activeTaskId);
      MessagePlugin.success(res.message);
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  // Open saved tasks dialog
  const openSavedDialog = async () => {
    setSavedDialogOpen(true);
    try {
      const res = await getSavedVaTasks();
      setSavedTasks(res.items);
    } catch { setSavedTasks([]); }
  };

  // Delete saved task
  const handleDeleteSaved = async (savedId: number) => {
    try {
      await deleteSavedVaTask(savedId);
      setSavedTasks(savedTasks.filter((s) => s.id !== savedId));
      MessagePlugin.success("已删除");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  // KOL Top10 panel toggle
  const toggleKolPanel = async (sort: "hot" | "time") => {
    if (kolPanelOpen === sort) { setKolPanelOpen(null); return; }
    setKolPanelOpen(sort);
    if (!activeTaskId) { setKolUsers([]); return; }
    setKolLoading(true);
    try {
      const res = await getKolTopUsers(activeTaskId, sort);
      setKolUsers(res.users || []);
    } catch { setKolUsers([]); }
    setKolLoading(false);
  };

  // Import KOL to identity queue
  const importKolToQueue = async (user: KolUser) => {
    try {
      const res = await addToIdentityQueue(user.uid, user.name, user.face, "video_analysis_kol");
      MessagePlugin.success(`UID ${user.uid} 已加入查成分队列`);
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  // Initial load & cleanup
  useEffect(() => { loadTasks(); return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);
  useEffect(() => { startPolling(); return () => {}; }, [fetching, analyzing]);

  const activeTask = tasks.find((t) => t.id === activeTaskId);
  const isProcessing = fetching || analyzing || (activeTask?.status === "fetching" || activeTask?.status === "analyzing");

  /** Determine what to show in the always-visible progress bar */
  const progressStage: ProgressInfo["stage"] = progressInfo?.stage
    ?? (isProcessing ? (fetching ? "fetching" : "analyzing") : null);
  const progressMessage = progressInfo?.message
    ?? (isProcessing
        ? fetching ? "正在处理..." : "正在分析..."
        : "就绪 — 输入视频链接开始分析");
  const hasDeterminateProgress = (progressInfo?.total ?? 0) > 0;

  // ---- Render ----
  return (
    <div className="flex flex-col h-[calc(100vh-0.5rem)] p-4 max-w-[1700px] mx-auto animate-fade-in">
      {/* Header + Input */}
      <div className="shrink-0 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">视频分析</h1>
            <p className="text-indigo-400 text-sm mt-0.5 font-mono">Bilibili video comment sentiment spectrum — 3D heat map</p>
          </div>
          {activeTask && activeTask.status === "done" && (
            <Tag variant="outline" theme="success" size="large">
              质心 ({(activeTask.centroidXNoNeutral ?? activeTask.centroidX).toFixed(1)}, {(activeTask.centroidYNoNeutral ?? activeTask.centroidY).toFixed(1)})
            </Tag>
          )}
        </div>

        {/* Input Row */}
        <div className="flex items-center gap-3 glass-card rounded-lg px-4 py-3">
          <PlayCircleIcon className="text-indigo-400 text-lg shrink-0" />
          <Input
            placeholder="输入B站视频链接，例如 https://www.bilibili.com/video/BV1oqVB6BECd"
            value={urlInput}
            onChange={(v) => setUrlInput(v)}
            clearable
            size="large"
            onEnter={handleFetch}
            className="flex-1"
            style={{ background: "rgba(255,255,255,0.04)" }}
          />
          <Button theme="primary" size="large" onClick={handleFetch} loading={fetching} disabled={isProcessing}>
            拉取评论
          </Button>
          {activeTask && activeTask.status === "fetched" && (
            <Button theme="success" size="large" onClick={handleAnalyze} loading={analyzing} disabled={isProcessing}>
              AI分析坐标
            </Button>
          )}
          {activeTask && activeTask.status === "done" && (
            <Button size="small" variant="outline" icon={<RefreshIcon />} onClick={() => handleAnalyze()}>
              重新分析
            </Button>
          )}
        </div>

        {/* ========== ALWAYS-VISIBLE Progress Bar ========== */}
        <div className={`glass-card rounded-lg px-5 py-2.5 space-y-1.5 transition-opacity ${isProcessing ? "" : "opacity-60"}`}>
          <div className="flex items-center gap-3">
            {isProcessing ? <Loading size="small" /> : <span className="w-4 block" />}
            <span className={`text-sm ${isProcessing
                ? (progressStage === "analyzing" ? "text-purple-400 font-medium" : "text-blue-400 font-medium")
                : "text-gray-500"
              }`}>
              {activeTask?.status === "error" ? `错误: ${activeTask.errorMsg}` : progressMessage}
            </span>
            {hasDeterminateProgress && progressInfo && (
              <span className="ml-auto text-xs font-mono text-gray-400 tabular-nums">
                {progressInfo.percent}%
              </span>
            )}
          </div>

          {/* Bar track */}
          <div className="h-2 bg-white/10 rounded-full overflow-hidden relative">
            {hasDeterminateProgress && progressInfo ? (
              <div
                className="h-full rounded-full transition-all duration-500 ease-out absolute left-0 top-0"
                style={{
                  width: `${Math.min(progressInfo.percent, 100)}%`,
                  background: progressStage === "fetching"
                    ? "linear-gradient(90deg, #3b82f6, #60a5fa)"
                    : progressStage === "rendering"
                      ? "linear-gradient(90deg, #10b981, #34d399)"
                      : "linear-gradient(90deg, #8b5cf6, #a78bfa)",
                }}
              />
            ) : isProcessing ? (
              /* Indeterminate sliding bar */
              <div
                className="h-full rounded-full absolute left-0 top-0"
                style={{
                  width: "40%",
                  background: progressStage === "fetching"
                    ? "linear-gradient(90deg, #3b82f6, #60a5fa)"
                    : "linear-gradient(90deg, #8b5cf6, #a78bfa)",
                  animation: "indeterminate-slide 1.5s ease-in-out infinite",
                }}
              />
            ) : null}
          </div>

          {/* Detail line when processing */}
          {(hasDeterminateProgress || (activeTask && activeTask.totalComments > 0)) && (
            <div className="text-[11px] text-gray-500 flex gap-4 pl-1">
              {hasDeterminateProgress && progressInfo && (
                <>
                  <span>进度: {progressInfo.current} / {progressInfo.total}</span>
                  <span>剩余: {Math.max(0, progressInfo.total - progressInfo.current)}</span>
                </>
              )}
              {!isProcessing && activeTask && activeTask.totalComments > 0 && (
                <>
                  <span>共{activeTask.totalComments}条</span>
                  <span>匹配{activeTask.matchedCount}条</span>
                  <span>已分析{activeTask.analyzedCount}条</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main body: Content area + Right sidebar task list */}
      <div className="flex flex-1 min-h-0 gap-3 mt-3">

        {/* ====== LEFT: Main content area ====== */}
        <div className="flex-1 min-w-0 flex flex-col">
          {loadingTasks && (
            <div className="flex-1 glass-card rounded-xl flex items-center justify-center"><Loading size="large" /></div>
          )}

          {!loadingTasks && !resultData && (
            <div className="flex-1 glass-card rounded-xl flex flex-col items-center justify-center gap-4">
              <PlayCircleIcon className="w-16 h-16 text-gray-600" />
              <p className="text-gray-400 text-lg">暂无分析结果</p>
              <p className="text-gray-500 text-sm text-center max-w-md">
                输入B站视频链接后点击&quot;拉取评论&quot;，系统将获取热度排序和时间排序的各500条评论及其楼中楼，
                然后通过关键词匹配和DeepSeek AI分析生成三维情感热力图。
              </p>
            </div>
          )}

          {/* 3D Heatmap Display */}
          {resultData && (
            <div className="flex-1 flex flex-col min-h-0 gap-3">
              {/* Stats bar above heatmap */}
              <div className="flex items-center gap-4 px-2 shrink-0 text-xs text-[#94a3b8]">
                <span><strong>视频:</strong> {resultData.task.title}</span>
                <span><strong>总评论:</strong> {resultData.task.totalComments}</span>
                <span><strong>匹配关键词:</strong> {resultData.task.matchedCount}</span>
                <span><strong>AI分析:</strong> {resultData.task.analyzedCount}</span>
                <span><strong>数据点:</strong> {resultData.totalPoints}</span>
                <span className="text-amber-400"><strong>舆论质心:</strong> ({resultData.task.centroidX.toFixed(1)}, {resultData.task.centroidY.toFixed(1)})</span>
                {(resultData.task as any).centroidXNoNeutral != null && (
                  <span className="text-emerald-400/80"><strong>质心(去中性):</strong> ({(resultData.task as any).centroidXNoNeutral.toFixed(1)}, {(resultData.task as any).centroidYNoNeutral.toFixed(1)})</span>
                )}
              </div>

              {/* Legend */}
              <div className="flex items-center gap-4 px-2 shrink-0 text-[11px] text-[#666]">
                <span>X轴: <strong className="text-[#6366f1]">反对</strong>(0) &larr;&rarr; <strong className="text-green-400">支持</strong>(100)</span>
                <span>Y轴: <strong className="text-blue-400">理性</strong>(0) &larr;&rarr; <strong className="text-pink-400">感性</strong>(100)</span>
                <span>Z轴高度: 同一坐标点的评论数量</span>
                <span className="text-amber-400">★ 舆论质心</span>
              </div>

              {/* Heatmap canvas */}
              <div className="flex-1 glass-card rounded-xl overflow-hidden relative" style={{ minHeight: 480 }}>
                {/* KOL Top10 buttons: top-left (hot), top-right (time) */}
                {activeTask?.status === "done" && (
                  <>
                    <div className="absolute top-2 left-2 z-10 flex gap-1.5">
                      <Button
                        size="small" variant={kolPanelOpen === "hot" ? "base" : "outline"}
                        theme={kolPanelOpen === "hot" ? "primary" : "default"}
                        onClick={() => toggleKolPanel("hot")}
                        className="!text-xs !px-2 !py-0.5 bg-black/50 border-white/20 backdrop-blur-sm"
                      >
                        <ThumbUpIcon size="14px" /> 热度Top10
                      </Button>
                    </div>
                    <div className="absolute top-2 right-16 z-10 flex gap-1.5">
                      <Button
                        size="small" variant={kolPanelOpen === "time" ? "base" : "outline"}
                        theme={kolPanelOpen === "time" ? "primary" : "default"}
                        onClick={() => toggleKolPanel("time")}
                        className="!text-xs !px-2 !py-0.5 bg-black/50 border-white/20 backdrop-blur-sm"
                      >
                        <TimeIcon size="14px" /> 时间Top10
                      </Button>
                    </div>
                  </>
                )}

                {/* KOL Top10 panel */}
                {kolPanelOpen && (
                  <div className={`absolute top-10 z-10 w-64 max-h-[60%] bg-black/80 backdrop-blur-md rounded-lg border border-white/10 shadow-xl overflow-hidden ${kolPanelOpen === "time" ? "right-2" : "left-2"}`}>
                    <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
                      <span className="text-xs font-semibold text-white">
                        {kolPanelOpen === "hot" ? "热度Top10用户" : "最新Top10用户"}
                      </span>
                      <Button
                        variant="text" shape="square" size="small"
                        onClick={() => setKolPanelOpen(null)}
                        className="!text-gray-400 hover:!text-white !p-0"
                      >
                        <CloseIcon size="14px" />
                      </Button>
                    </div>
                    <div className="overflow-y-auto max-h-[calc(100%-36px)]">
                      {kolLoading ? (
                        <div className="flex items-center justify-center py-6"><Loading size="small" /></div>
                      ) : kolUsers.length === 0 ? (
                        <div className="text-center py-4 text-xs text-gray-500">暂无数据</div>
                      ) : kolUsers.map((u, i) => (
                        <div key={u.uid} className="flex items-center gap-2 px-3 py-2 hover:bg-white/5 transition-colors">
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${i < 3 ? "bg-amber-500/30 text-amber-300" : "bg-gray-700 text-gray-400"}`}>
                            {i + 1}
                          </span>
                          <img src={u.face} alt="" className="w-7 h-7 rounded-full shrink-0 object-cover"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs text-gray-200 truncate">{u.name}</div>
                            <div className="text-[10px] text-gray-500">UID:{u.uid} · {u.likeSum}赞</div>
                          </div>
                          <Button size="extra-small" variant="outline" theme="primary"
                            onClick={() => importKolToQueue(u)}
                            className="!text-[10px] !px-1.5 !py-0 shrink-0"
                          >
                            查成分
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Heatmap3D data={resultData} />

                {/* Overlay centroid label */}
                {resultData.task.centroidX >= 0 && (
                  <div className="absolute bottom-3 right-4 pointer-events-none">
                    <div className="bg-black/60 backdrop-blur-sm rounded-lg px-3 py-2 border border-amber-500/30 text-xs space-y-1">
                      <div className="text-amber-400 font-bold">舆论质心</div>
                      <div className="text-gray-300">
                        主(去中性): <strong className="text-emerald-400">{((resultData.task as any).centroidXNoNeutral ?? resultData.task.centroidX).toFixed(1)}</strong>, <strong className="text-emerald-400">{((resultData.task as any).centroidYNoNeutral ?? resultData.task.centroidY).toFixed(1)}</strong>
                      </div>
                      <div className="text-gray-500 text-[10px]">
                        全量: ({resultData.task.centroidX.toFixed(1)}, {resultData.task.centroidY.toFixed(1)})
                        {" · "}
                        {((resultData.task as any).centroidXNoNeutral ?? resultData.task.centroidX) > 60 ? "整体偏向支持米哈游" :
                         ((resultData.task as any).centroidXNoNeutral ?? resultData.task.centroidX) < 40 ? "整体偏向反对米哈游" : "态度中立"}
                        {" · "}
                        {((resultData.task as any).centroidYNoNeutral ?? resultData.task.centroidY) > 60 ? "感性情绪为主" :
                         ((resultData.task as any).centroidYNoNeutral ?? resultData.task.centroidY) < 40 ? "理性分析为主" : "理性感性均衡"}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ====== RIGHT: Task Sidebar ====== */}
        <div className="w-64 shrink-0 glass-card rounded-xl p-3 flex flex-col max-h-full overflow-hidden">
          <div className="flex items-center justify-between mb-2 px-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">任务列表</span>
            <span className="text-[10px] text-gray-600">{tasks.length} 个</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
            {tasks.length === 0 && (
              <div className="text-center text-gray-600 text-xs py-8">
                暂无任务
              </div>
            )}

            {tasks.map((t) => {
              const isActive = t.id === activeTaskId;
              const statusColor: Record<string, string> = {
                done: "text-emerald-400", fetched: "text-blue-400",
                analyzing: "text-purple-400", fetching: "text-cyan-400",
                error: "text-red-400", idle: "text-gray-500",
              };
              const statusLabel: Record<string, string> = {
                done: "已完成", fetched: "待分析",
                analyzing: "AI分析中", fetching: "拉取中",
                error: "出错", idle: "等待",
              };

              return (
                <div
                  key={t.id}
                  onClick={() => handleSelectTask(t.id)}
                  className={`group rounded-lg px-2.5 py-2 cursor-pointer transition-all border ${
                    isActive
                      ? "bg-indigo-500/15 border-indigo-500/30 shadow-sm shadow-indigo-500/10"
                      : "bg-white/[0.03] border-transparent hover:bg-white/[0.06]"
                  }`}
                >
                  {/* Title row */}
                  <div className="flex items-start justify-between gap-1">
                    <span className={`text-xs leading-snug line-clamp-2 ${isActive ? "text-indigo-200 font-medium" : "text-gray-300"}`}>
                      {t.title.length > 30 ? t.title.slice(0, 30) + "..." : t.title}
                    </span>
                    {/* Delete button - only show on hover or when active */}
                    <button
                      className="shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 p-0.5 rounded hover:bg-red-500/20 transition-all"
                      onClick={(e) => { e.stopPropagation(); if (window.confirm("确定删除此任务？")) handleDelete(t.id); }}
                    >
                      <DeleteIcon size="12px" className="text-gray-500 hover:text-red-400" />
                    </button>
                  </div>

                  {/* Status badge + stats */}
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <span className={`text-[10px] font-medium ${statusColor[t.status] || "text-gray-500"}`}>
                      {statusLabel[t.status] || t.status}
                    </span>
                    {t.status === "done" && t.analyzedCount > 0 && (
                      <span className="text-[10px] text-gray-500">{t.analyzedCount} 条已分析</span>
                    )}
                    {(t.status === "fetched" || t.status === "fetching") && t.matchedCount > 0 && (
                      <span className="text-[10px] text-gray-500">{t.matchedCount} 条匹配</span>
                    )}
                  </div>

                  {/* Error message */}
                  {t.status === "error" && t.errorMsg && (
                    <p className="text-[10px] text-red-400/80 mt-1 line-clamp-2">{t.errorMsg}</p>
                  )}

                  {/* Centroid hint for done tasks */}
                  {t.status === "done" && (
                    <div className="mt-1.5 text-[10px] text-amber-400/70 font-mono">
                      质心({(t.centroidXNoNeutral ?? t.centroidX).toFixed(0)}, {(t.centroidYNoNeutral ?? t.centroidY).toFixed(0)})
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Saved tasks button + save active task */}
          <div className="border-t border-[#2a2a4a] pt-2 mt-2 space-y-1.5">
            {activeTask?.status === "done" && (
              <Button
                variant="outline" size="small"
                onClick={handleSaveTask}
                className="w-full !text-xs !py-1.5 !border-indigo-500/30 !text-indigo-400 hover:!bg-indigo-500/10"
              >
                <BookmarkIcon size="14px" /> 存储此任务
              </Button>
            )}
            <Button
              variant="outline" size="small"
              onClick={openSavedDialog}
              className="w-full !text-xs !py-1.5"
            >
              查看已存储任务 ({savedTasks.length})
            </Button>
          </div>
        </div>
      </div>

      {/* Saved Tasks Dialog */}
      <Dialog
        header="已存储任务"
        visible={savedDialogOpen}
        onClose={() => setSavedDialogOpen(false)}
        footer={false}
        width="600px"
        className="!bg-[#0d0d2b] !border-[#2a2a4a]"
      >
        <div className="max-h-[60vh] overflow-y-auto space-y-2 pr-1">
          {savedTasks.length === 0 && (
            <div className="text-center py-8 text-gray-500 text-sm">暂无已存储的任务，完成分析后可点击"存储此任务"</div>
          )}
          {savedTasks.map((s) => (
            <div key={s.id} className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-white/12 transition-all group">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white font-medium truncate">{s.title || "无标题"}</div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>评论{s.totalComments} · 匹配{s.matchedCount}</span>
                    <span>质心({s.centroidXNoOrigin?.toFixed(1) ?? s.centroidX.toFixed(1)}, {s.centroidYNoOrigin?.toFixed(1) ?? s.centroidY.toFixed(1)})</span>
                  </div>
                  <div className="text-[10px] text-gray-600 mt-0.5">存储于 {s.savedAt.slice(0, 16).replace("T", " ")}</div>
                </div>
                <button
                  className="shrink-0 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 transition-all"
                  onClick={() => handleDeleteSaved(s.id)}
                >
                  <DeleteIcon size="14px" className="text-gray-500 hover:text-red-400" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </Dialog>
    </div>
  );
}

/* Indeterminate progress bar slide animation */
const _indeterminateStyle = (
  <style>{`
    @keyframes indeterminate-slide {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(400%); }
    }
  `}</style>
);
