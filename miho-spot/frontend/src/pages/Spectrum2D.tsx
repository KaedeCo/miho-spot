import { useState, useEffect, useCallback, useRef } from "react";
import { Loading, Pagination, Drawer, Tag, Tabs, Button, MessagePlugin, Dialog, Slider } from "tdesign-react";
import { TimeIcon, FileIcon, DownloadIcon, UploadIcon, ImageIcon } from "tdesign-icons-react";
import { toPng } from "html-to-image";
import { getBiliProfiles, getBiliProfile, deleteBiliProfile, importBiliProfiles } from "../services/api";
import type { BiliProfileSummary, BiliProfileDetail, BiliProfileItems } from "../types";

const CARD_STYLE = {
  width: 600, bg: "#0f0f23", card: "#1a1a2e", border: "#2a2a4a",
  accent: "#6366f1", green: "#22c55e", red: "#ef4444", text: "#e2e8f0", sub: "#94a3b8", mint: "#a78bfa",
};

async function imageUrlToDataUri(url: string): Promise<string> {
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.readAsDataURL(blob);
    });
  } catch { return ""; }
}

async function renderCard(detail: BiliProfileDetail & { comment_count?: number; content_count?: number }) {
  const w = CARD_STYLE.width;
  const name = detail.name || "Unknown";
  const uid = detail.uid;
  const sx = detail.score_x ?? 50;
  const sy = detail.score_y ?? 50;

  const faceSrc = await imageUrlToDataUri(detail.face || "");

  // Outer container — fixed overlay, NOT part of screenshot
  const container = document.createElement("div");
  container.style.cssText = `position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.55);backdrop-filter:blur(4px);z-index:99999;font-family:"Segoe UI",system-ui,sans-serif;`;

  const summaryBlock = detail.summary
    ? `<div style="border-top:1px solid ${CARD_STYLE.border};margin-top:18px;padding-top:16px;font-size:15px;font-weight:600;color:${CARD_STYLE.accent};text-align:center;">${detail.summary}</div>`
    : "";
  const faceBlock = faceSrc
    ? `<img src="${faceSrc}" style="width:56px;height:56px;border-radius:50%;border:2px solid ${CARD_STYLE.accent};" />`
    : `<div style="width:56px;height:56px;border-radius:50%;border:2px solid ${CARD_STYLE.accent};background:${CARD_STYLE.border};display:flex;align-items:center;justify-content:center;color:${CARD_STYLE.sub};font-size:20px;">?</div>`;

  // Close button — placed above the card, right-aligned, NOT part of screenshot
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "\u2715 关闭";
  Object.assign(closeBtn.style, {
    background: "rgba(255,255,255,0.08)", color: "#aaa", border: "1px solid rgba(255,255,255,0.15)",
    borderRadius: "8px", padding: "6px 16px", cursor: "pointer", fontSize: "13px",
    fontFamily: "inherit", marginLeft: "auto",
  });
  closeBtn.onmouseenter = () => { closeBtn.style.background = "rgba(255,80,80,0.25)"; closeBtn.style.color = "#fff"; };
  closeBtn.onmouseleave = () => { closeBtn.style.background = "rgba(255,255,255,0.08)"; closeBtn.style.color = "#aaa"; };
  closeBtn.onclick = () => document.body.removeChild(container);

  // Top row: spacer + close button (right-aligned)
  const topRow = document.createElement("div");
  topRow.style.cssText = `display:flex;width:${w + 24}px;align-items:center;margin-bottom:8px;`;
  topRow.appendChild(closeBtn);

  // The element that gets screenshotted — outer glow frame + rounded corners
  const screenshotDiv = document.createElement("div");
  screenshotDiv.id = "miho-card-screenshot";
  screenshotDiv.style.cssText = `
    width:${w}px;
    background:linear-gradient(135deg,#2a2050 0%,#16163a 50%,#1a1a3e 100%);
    border-radius:18px;
    padding:6px;
    box-shadow:
      0 0 0 1px rgba(99,102,241,0.35),
      0 0 20px rgba(99,102,241,0.15),
      0 8px 32px rgba(0,0,0,0.5);
  `;
  screenshotDiv.innerHTML = `<div id="miho-card-inner" style="border-radius:14px;padding:28px 26px;background:${CARD_STYLE.card};">
    ${faceBlock ? `<div style="display:flex;align-items:center;gap:20px;margin-bottom:22px;">
      ${faceBlock}
      <div style="flex:1;min-width:0;">
        <div style="font-size:20px;font-weight:700;color:#fff;">${name}</div>
        <div style="font-size:12px;color:${CARD_STYLE.sub};margin-top:2px;">UID: ${uid} \u00b7 评论 ${detail.comment_count ?? 0} \u00b7 视频/专栏 ${detail.content_count ?? 0}</div>
      </div>
      <div style="text-align:center;flex-shrink:0;">
        <div style="font-size:12px;color:${CARD_STYLE.sub};margin-bottom:2px;">米哈游态度</div>
        <div style="font-size:36px;font-weight:800;color:${sx >= 50 ? CARD_STYLE.green : CARD_STYLE.red};">${sx}</div>
        <div style="font-size:12px;color:${CARD_STYLE.sub};margin-top:8px;">理性感性</div>
        <div style="font-size:28px;font-weight:700;color:${CARD_STYLE.mint};">${sy}</div>
      </div>
    </div>` : ""}
    <div style="border-top:1px solid ${CARD_STYLE.border};padding-top:18px;display:flex;flex-direction:column;gap:16px;">
      <div><div style="font-size:13px;font-weight:700;color:${CARD_STYLE.accent};margin-bottom:4px;">米哈游态度</div><div style="font-size:14px;line-height:1.6;color:${CARD_STYLE.text};">${detail.mihoyo_attitude || "--"}</div></div>
      <div><div style="font-size:13px;font-weight:700;color:${CARD_STYLE.green};margin-bottom:4px;">活跃领域</div><div style="font-size:14px;line-height:1.6;color:${CARD_STYLE.text};">${detail.active_areas || "--"}</div></div>
      <div><div style="font-size:13px;font-weight:700;color:${CARD_STYLE.mint};margin-bottom:4px;">性格推测</div><div style="font-size:14px;line-height:1.6;color:${CARD_STYLE.text};">${detail.personality || "--"}</div></div>
    </div>
    ${summaryBlock}
    <div style="border-top:1px solid ${CARD_STYLE.border}40;margin-top:20px;padding-top:14px;font-size:10px;color:#555;text-align:right;font-family:Cascadia Code,Consolas,monospace;">Powered by Miho-Spot, KaedeCo@Github. For study use!</div>
  </div>`;

  // Container uses flex-column layout: [topRow][card]
  container.style.flexDirection = "column";
  container.appendChild(topRow);
  container.appendChild(screenshotDiv);
  document.body.appendChild(container);

  // Wait for layout + image render
  await new Promise(r => setTimeout(r, 500));

  try {
    const dataUrl = await toPng(screenshotDiv, {
      width: w + 12,
      pixelRatio: 2,
      backgroundColor: "transparent",
    });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `miho_${uid}_${name}.png`;
    a.click();
  } catch (e) {
    console.error("Card render error:", e);
    throw e;
  }
  // Container stays open — user clicks close button
}

export default function Spectrum2D() {
  const [profiles, setProfiles] = useState<BiliProfileSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<BiliProfileSummary | null>(null);
  const [detail, setDetail] = useState<(BiliProfileDetail & BiliProfileItems) | null>(null);
  const [detailTab, setDetailTab] = useState("comments");
  const [detailPage, setDetailPage] = useState(1);
  const [detailLoading, setDetailLoading] = useState(false);
  const [commentCount, setCommentCount] = useState(0);
  const [contentCount, setContentCount] = useState(0);
  const [hovered, setHovered] = useState<BiliProfileSummary | null>(null);
  const [importDlg, setImportDlg] = useState(false);
  const [zoom, setZoom] = useState(1);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadProfiles = useCallback(async () => {
    setLoading(true);
    try { const res = await getBiliProfiles(); if (res.ok) setProfiles(res.profiles); } catch {}
    setLoading(false);
  }, []);
  useEffect(() => { loadProfiles(); }, [loadProfiles]);

  const loadDetail = useCallback(async (p: BiliProfileSummary, tab: string, pg: number) => {
    setDetailLoading(true);
    try {
      const res = await getBiliProfile(p.uid, tab, pg);
      if (res.ok) {
        setDetail({ ...res, ...p, mihoyo_attitude: res.mihoyo_attitude || "", active_areas: res.active_areas || "", personality: res.personality || "" });
        setDetailPage(pg);
        if (tab === "comments") setCommentCount(res.total || 0); else setContentCount(res.total || 0);
      }
    } catch {}
    setDetailLoading(false);
  }, []);

  const openProfile = (p: BiliProfileSummary) => {
    setSelected(p); setDetailTab("comments"); setDetailPage(1); setCommentCount(0); setContentCount(0);
    loadDetail(p, "comments", 1);
  };
  const handleDelete = async () => { if (!selected) return; await deleteBiliProfile(selected.uid); setSelected(null); setDetail(null); loadProfiles(); };
  const handleExport = async () => {
    try {
      const resp = await fetch("/api/bilibili/export");
      if (!resp.ok) throw new Error("failed");
      const blob = await resp.blob(); const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "miho_profiles.json"; a.click();
      URL.revokeObjectURL(url); MessagePlugin.success("已导出");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };
  const handleImport = async () => {
    if (!fileRef.current?.files?.length) return;
    try { const text = await fileRef.current.files[0].text(); const data = JSON.parse(text);
      const res = await importBiliProfiles(data.profiles || []);
      MessagePlugin.success(res.message || "导入成功"); setImportDlg(false); loadProfiles();
    } catch (e: any) { MessagePlugin.error(e.message || "导入失败"); }
  };

  const pad = { t: 25, r: 50, b: 65, l: 55 };
  const baseW = 900, baseH = 680;
  const W = baseW * zoom, H = baseH * zoom;
  const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
  const tx = (v: number) => pad.l + (v / 100) * pw;
  const ty = (v: number) => pad.t + ph - (v / 100) * ph;

  return (
    <div className="flex flex-col h-[calc(100vh-0.5rem)] p-4 max-w-[1400px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-2 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-white">二维光谱图</h1>
          <p className="text-indigo-400 text-sm mt-0.5 font-mono">High-Orbit Ion Cannon standing by, waiting for instructions.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="small" variant="outline" icon={<DownloadIcon />} onClick={handleExport} disabled={profiles.length === 0}>导出</Button>
          <Button size="small" variant="outline" icon={<UploadIcon />} onClick={() => setImportDlg(true)}>导入</Button>
        </div>
      </div>

      {loading && <div className="flex-1 glass-card rounded-xl flex items-center justify-center"><Loading size="large" /></div>}

      {!loading && profiles.length === 0 && (
        <div className="flex-1 glass-card rounded-xl flex flex-col items-center justify-center gap-3">
          <p className="text-gray-400 text-lg">暂无存储数据</p>
          <p className="text-gray-500 text-sm">请在"查成分"页面分析用户后点击"存储数据"</p>
        </div>
      )}

      {!loading && profiles.length > 0 && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 flex items-center justify-center overflow-auto p-2">
            <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "100%", maxWidth: `${W}px`, maxHeight: `${H}px` }}>
              <defs>
                {/* Edge fade masks */}
                <radialGradient id="fadeX0" cx="0%" cy="50%" r="100%">
                  <stop offset="0%" stopColor="#0a0a20" stopOpacity={0} />
                  <stop offset="8%" stopColor="#0a0a20" stopOpacity={1} />
                </radialGradient>
                <radialGradient id="fadeX100" cx="100%" cy="50%" r="100%">
                  <stop offset="0%" stopColor="#0a0a20" stopOpacity={1} />
                  <stop offset="8%" stopColor="#0a0a20" stopOpacity={0} />
                </radialGradient>
                <radialGradient id="fadeY0" cx="50%" cy="100%" r="100%">
                  <stop offset="0%" stopColor="#0a0a20" stopOpacity={1} />
                  <stop offset="8%" stopColor="#0a0a20" stopOpacity={0} />
                </radialGradient>
                <radialGradient id="fadeY100" cx="50%" cy="0%" r="100%">
                  <stop offset="0%" stopColor="#0a0a20" stopOpacity={0} />
                  <stop offset="8%" stopColor="#0a0a20" stopOpacity={1} />
                </radialGradient>

                {/* X-axis: red(0) -> yellow(50) -> green(100) */}
                <linearGradient id="gradX" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#ef4444" />
                  <stop offset="25%" stopColor="#f97316" />
                  <stop offset="50%" stopColor="#eab308" />
                  <stop offset="75%" stopColor="#84cc16" />
                  <stop offset="100%" stopColor="#22c55e" />
                </linearGradient>
                {/* Y-axis label: horizontal gradient blue(left) -> pink(right) — for rotated text this reads up the axis */}
                <linearGradient id="gradY" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#3b82f6" />
                  <stop offset="40%" stopColor="#8b5cf6" />
                  <stop offset="70%" stopColor="#ec4899" />
                  <stop offset="100%" stopColor="#f472b6" />
                </linearGradient>
              </defs>

              {/* Main background */}
              <rect x={0} y={0} width={W} height={H} fill="#0a0a20" rx={12} />

              {/* Fade edges - drawn FIRST so grid lines are visible on top */}
              <rect x={pad.l} y={pad.t} width={pw} height={ph} fill="url(#fadeX0)" opacity={0.5} />
              <rect x={pad.l} y={pad.t} width={pw} height={ph} fill="url(#fadeX100)" opacity={0.5} />
              <rect x={pad.l} y={pad.t} width={pw} height={ph} fill="url(#fadeY0)" opacity={0.5} />
              <rect x={pad.l} y={pad.t} width={pw} height={ph} fill="url(#fadeY100)" opacity={0.5} />

              {/* Plot area border */}
              <rect x={pad.l} y={pad.t} width={pw} height={ph} fill="none" stroke="#1a1a40" strokeWidth={1} rx={4} />

              {/* Grid: every 10 units, drawn LAST so they're on top */}
              {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((v) => {
                const isCenter = v === 50;
                return (
                  <g key={v}>
                    <line x1={tx(v)} y1={pad.t} x2={tx(v)} y2={pad.t + ph}
                      stroke={isCenter ? "#f59e0b" : "#2a2a50"}
                      strokeWidth={isCenter ? 2 : 0.8}
                      strokeDasharray={isCenter ? "12,5" : "5,8"}
                      opacity={isCenter ? 0.7 : 0.5} />
                    <line x1={pad.l} y1={ty(v)} x2={pad.l + pw} y2={ty(v)}
                      stroke={isCenter ? "#8b5cf6" : "#2a2a50"}
                      strokeWidth={isCenter ? 2 : 0.8}
                      strokeDasharray={isCenter ? "12,5" : "5,8"}
                      opacity={isCenter ? 0.7 : 0.5} />
                    {v % 20 === 0 && (
                      <>
                        <text x={tx(v)} y={pad.t + ph + 22} textAnchor="middle" fill="#888" fontSize={13} fontWeight={700}>{v}</text>
                        <text x={pad.l - 12} y={ty(v) + 5} textAnchor="end" fill="#888" fontSize={13} fontWeight={700}>{v}</text>
                      </>
                    )}
                  </g>
                );
              })}

              {/* Axis labels with gradient */}
              <text x={pad.l + pw / 2} y={H - 10} textAnchor="middle" fill="url(#gradX)" fontSize={13} fontWeight={700}>
                ← 反对米哈游 · 米哈游态度 · 支持米哈游 →
              </text>
              <text x={14} y={pad.t + ph / 2} textAnchor="middle" fill="url(#gradY)" fontSize={13} fontWeight={700}
                transform={`rotate(-90, 14, ${pad.t + ph / 2})`}>← 理性客观 · 理性程度 · 感性情绪 →</text>

              {/* Quadrant labels: bottom=理性(Y≈7), top=感性(Y≈93) */}
              <text x={tx(20)} y={ty(93)} textAnchor="middle" fill="#777" fontSize={11} fontWeight={600}>感性反对</text>
              <text x={tx(80)} y={ty(93)} textAnchor="middle" fill="#777" fontSize={11} fontWeight={600}>感性支持</text>
              <text x={tx(20)} y={ty(7)}  textAnchor="middle" fill="#777" fontSize={11} fontWeight={600}>理性反对</text>
              <text x={tx(80)} y={ty(7)}  textAnchor="middle" fill="#777" fontSize={11} fontWeight={600}>理性支持</text>

              {/* User points */}
              {profiles.map((p) => {
                const x = tx(p.score_x), y = ty(p.score_y);
                const isSel = selected?.uid === p.uid;
                return (
                  <g key={p.uid}>
                    {/* Click target */}
                    <circle cx={x} cy={y} r={16} fill="transparent" style={{ cursor: "pointer" }}
                      onMouseEnter={() => setHovered(p)}
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => openProfile(p)} />
                    {/* Selection ring */}
                    {isSel && <circle cx={x} cy={y} r={17} fill="none" stroke="#6366f1" strokeWidth={2} opacity={0.7} />}
                    {/* Avatar */}
                    <clipPath id={`c-${p.uid}`}><circle cx={x} cy={y} r={13} /></clipPath>
                    <image href={p.face} x={x - 13} y={y - 13} width={26} height={26}
                      clipPath={`url(#c-${p.uid})`} preserveAspectRatio="xMidYMid slice"
                      style={{ pointerEvents: "none" }} />
                    <circle cx={x} cy={y} r={13} fill="none" stroke={isSel ? "#6366f1" : "#666"} strokeWidth={1.5}
                      style={{ pointerEvents: "none" }} />
                  </g>
                );
              })}

              {/* Hover tooltips — rendered LAST so they're on top of everything */}
              {hovered && (() => {
                const p = hovered;
                const x = tx(p.score_x), y = ty(p.score_y);
                const lines = [`${p.name}`, `UID:${p.uid}  (${p.score_x}, ${p.score_y})`];
                const lineH = 14;
                const boxW = 140, boxH = lines.length * lineH + 14;
                let bx = x + 20, by = y - boxH / 2;
                if (bx + boxW > pad.l + pw) bx = x - boxW - 20;
                if (by < pad.t) by = pad.t + 4;
                if (by + boxH > pad.t + ph) by = pad.t + ph - boxH - 4;
                return (
                  <g style={{ pointerEvents: "none" }}>
                    <rect x={bx} y={by} width={boxW} height={boxH} rx={6}
                      fill="#1a1a2e" stroke="#555" strokeWidth={1} opacity={0.95} />
                    {lines.map((ln, i) => (
                      <text key={i} x={bx + 10} y={by + lineH * i + 16} fill="#eee" fontSize={11} fontWeight={i === 0 ? 600 : 400}>{ln}</text>
                    ))}
                  </g>
                );
              })()}
            </svg>
          </div>

          {/* Zoom slider */}
          <div className="flex justify-center items-center gap-3 py-2 shrink-0">
            <span className="text-xs text-gray-500">🔍</span>
            <Slider value={zoom} min={0.5} max={2.5} step={0.1} onChange={(v) => setZoom(v as number)}
              style={{ width: 200 }} />
            <span className="text-xs text-gray-500">{(zoom * 100).toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* Profile Drawer */}
      {selected && (
        <Drawer visible={true} onClose={() => { setSelected(null); setDetail(null); }}
          header={<div className="flex items-center gap-3"><img src={selected.face} alt="" className="w-8 h-8 rounded-full" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} /><span className="text-white text-base font-semibold">{selected.name}</span><Tag size="small" theme="primary" variant="light">({selected.score_x}, {selected.score_y})</Tag></div>}
          size="500px" footer={false} destroyOnClose>
          {detailLoading && <div className="flex justify-center py-8"><Loading /></div>}
          {detail && !detailLoading && (
            <div className="space-y-4">
              <div className="p-3 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs space-y-1.5">
                <div><span className="text-gray-500">米哈游态度: </span><span className="text-gray-200">{detail.mihoyo_attitude}</span></div>
                <div><span className="text-gray-500">活跃领域: </span><span className="text-gray-200">{detail.active_areas}</span></div>
                <div><span className="text-gray-500">性格: </span><span className="text-gray-200">{detail.personality}</span></div>
                {detail.summary && <div className="text-indigo-400">{detail.summary}</div>}
              </div>
              <Tabs value={detailTab} onChange={(v) => { setDetailTab(v as string); setDetailPage(1); loadDetail(selected, v as string, 1); }} theme="card">
                <Tabs.TabPanel value="comments" label={`评论 (${commentCount || detail?.total || 0})`}>
                  <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                    {(detail.items || []).map((c: any, i: number) => (
                      <div key={c.rpid || i} className={`p-3 rounded-lg text-sm border ${c.matched_keywords?.length ? "bg-purple-500/[0.04] border-purple-500/20" : "bg-white/[0.02] border-white/[0.04]"}`}>
                        <div className="text-gray-200 leading-relaxed break-words">{c.content}</div>
                        <div className="flex items-center gap-3 mt-1.5"><span className="text-xs text-gray-500"><TimeIcon size="12px" /> {c.time_str}</span></div>
                        {c.matched_keywords?.length > 0 && <div className="flex gap-1 mt-1 flex-wrap">{c.matched_keywords.slice(0, 5).map((kw: string) => <Tag key={kw} size="small" variant="light" theme="primary">{kw}</Tag>)}</div>}
                      </div>
                    ))}
                  </div>
                  {detail.total_pages > 1 && <div className="flex justify-center pt-2"><Pagination current={detailPage} total={commentCount || detail.total} pageSize={100} onChange={(pi) => { loadDetail(selected, "comments", pi.current); }} size="small" showPageSize={false} /></div>}
                </Tabs.TabPanel>
                <Tabs.TabPanel value="content" label={`视频/专栏 (${contentCount || detail?.total || 0})`}>
                  <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                    {(detail.items || []).map((c: any, i: number) => (
                      <div key={`${c.type}-${c.id}-${i}`} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] flex gap-3">
                        {c.type === "video" ? (c.cover ? <img src={c.cover + "@160w_100h.jpg"} alt="" className="w-20 h-12 rounded object-cover shrink-0 bg-gray-800" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} /> : <FileIcon size="16px" className="text-indigo-400 shrink-0 mt-1" />) : <FileIcon size="16px" className="text-indigo-400 shrink-0 mt-1" />}
                        <div className="min-w-0 flex-1">
                          <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-gray-200 text-xs leading-relaxed hover:text-indigo-400 transition-colors line-clamp-2">{c.title}</a>
                          <div className="flex items-center gap-2 mt-1">
                            <Tag size="small" variant="light" theme={c.type === "video" ? "primary" : "warning"}>{c.type === "video" ? "视频" : "专栏"}</Tag>
                            <span className="text-xs text-gray-500">{c.time_str}</span>
                            {c.play > 0 && <span className="text-xs text-gray-500">{(c.play / 10000).toFixed(1)}万</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  {detail.total_pages > 1 && <div className="flex justify-center pt-2"><Pagination current={detailPage} total={contentCount || detail.total} pageSize={30} onChange={(pi) => { loadDetail(selected, "content", pi.current); }} size="small" showPageSize={false} /></div>}
                </Tabs.TabPanel>
              </Tabs>
              <div className="flex justify-between items-center pt-3 border-t border-white/[0.06] mt-3">
                <Button size="small" variant="outline" icon={<ImageIcon />}
                  onClick={async () => {
                    try {
                      await renderCard({ ...detail, comment_count: commentCount, content_count: contentCount } as any);
                      MessagePlugin.success("卡片已导出");
                    } catch { MessagePlugin.error("导出失败"); }
                  }}>导出卡片</Button>
                <Tag theme="danger" variant="outline" onClick={handleDelete} style={{ cursor: "pointer" }}>删除</Tag>
              </div>
            </div>
          )}
        </Drawer>
      )}

      <Dialog visible={importDlg} header="导入数据" onClose={() => setImportDlg(false)}
        footer={<><Button variant="outline" onClick={() => setImportDlg(false)}>取消</Button><Button theme="primary" onClick={handleImport}>导入</Button></>}>
        <p className="text-sm text-gray-400 mb-3">选择之前导出的 JSON 文件，新数据将合并到现有数据中。</p>
        <input ref={fileRef} type="file" accept=".json" />
      </Dialog>
    </div>
  );
}
