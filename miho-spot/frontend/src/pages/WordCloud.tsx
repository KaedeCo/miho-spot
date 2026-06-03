import { useState, useEffect, useCallback, useRef } from "react";
import { Button, Loading, MessagePlugin, Dialog, Tag } from "tdesign-react";
import {
  RefreshIcon,
  DeleteIcon,
  CloudIcon,
  ChevronLeftIcon,
} from "tdesign-icons-react";
import {
  getSavedVaTasks, getWordClouds, generateWordCloud, deleteWordCloud, deleteSavedVaTask,
} from "../services/api";
import type { SavedVaTask, WordCloudItem, WordCloudWord } from "../types";

function WordCloudCanvas({ words }: { words: WordCloudWord[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || !words.length) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const container = canvas.parentElement;
    if (container) {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight || 450;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Simple spiral placement
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const placed: { x: number; y: number; w: number; h: number; text: string }[] = [];

    // Sort by weight descending for larger words first
    const sorted = [...words].sort((a, b) => b.weight - a.weight);
    const maxWeight = sorted[0]?.weight || 1;

    sorted.forEach((word) => {
      const fontSize = Math.max(12, Math.min(72, ((word.weight / maxWeight) * 60) + 14));
      ctx.font = `bold ${fontSize}px "Microsoft YaHei", sans-serif`;
      const metrics = ctx.measureText(word.text);
      const wordW = metrics.width + 16;
      const wordH = fontSize + 8;

      // Spiral placement from center
      let placedOk = false;
      for (let r = 0; r < 200 && !placedOk; r += 3) {
        for (let angle = 0; angle < Math.PI * 20 && !placedOk; angle += 0.3) {
          const tx = centerX + r * Math.cos(angle) - wordW / 2;
          const ty = centerY + r * Math.sin(angle) - wordH / 2;
          
          // Bounds check
          if (tx < 10 || ty < 10 || tx + wordW > canvas.width - 10 || ty + wordH > canvas.height - 10) continue;

          // Collision check
          let collision = false;
          for (const p of placed) {
            if (!(tx + wordW < p.x || tx > p.x + p.w || ty + wordH < p.y || ty > p.y + p.h)) {
              collision = true;
              break;
            }
          }
          if (!collision) {
            // Draw word with gradient color based on weight
            const hue = 220 + (word.weight / maxWeight) * 60; // blue to cyan range
            const lightness = 45 + (word.weight / maxWeight) * 25;
            ctx.fillStyle = `hsl(${hue}, 70%, ${lightness}%)`;
            ctx.fillText(word.text, tx + wordW / 2, ty + wordH / 2);
            placed.push({ x: tx, y: ty, w: wordW, h: wordH, text: word.text });
            placedOk = true;
            break;
          }
        }
      }

      // If not placed in spiral, just put at random edge
      if (!placedOk) {
        const hue = 220 + (word.weight / maxWeight) * 60;
        ctx.fillStyle = `hsla(${hue}, 70%, 55%, 0.6)`;
        ctx.fillText(
          word.text,
          30 + Math.random() * (canvas.width - 100),
          30 + Math.random() * (canvas.height - 80),
        );
      }
    });
  }, [words]);

  return (
    <div className="w-full rounded-xl bg-[#0a0a22] border border-white/[0.06] overflow-hidden" style={{ minHeight: 450 }}>
      <canvas ref={canvasRef} className="w-full" style={{ display: "block", height: 450 }} />
    </div>
  );
}

export default function WordCloud() {
  const [savedTasks, setSavedTasks] = useState<SavedVaTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [wordClouds, setWordClouds] = useState<WordCloudItem[]>([]);
  const [activeCloud, setActiveCloud] = useState<WordCloudItem | null>(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadSavedTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSavedVaTasks();
      setSavedTasks(res.items);
      // Also load existing word clouds
      const wcRes = await getWordClouds();
      setWordClouds(wcRes.items);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadSavedTasks(); }, []);

  const handleGenerate = async (savedId: number) => {
    setSelectedTaskId(savedId);
    setGenerating(true);
    try {
      const res = await generateWordCloud(savedId);
      if (res.ok) {
        MessagePlugin.success(`词云已生成，共${res.wordCount}个关键词`);
        loadSavedTasks();
      } else {
        MessagePlugin.error(res.message || "生成失败");
      }
    } catch (e: any) { MessagePlugin.error(e.message); }
    setGenerating(false);
  };

  const handleViewCloud = (wc: WordCloudItem) => {
    setActiveCloud(wc);
    setSelectedTaskId(wc.savedVaTaskId);
  };

  const handleDeleteCloud = async (wcId: number) => {
    try {
      await deleteWordCloud(wcId);
      setWordClouds(wordClouds.filter((w) => w.id !== wcId));
      if (activeCloud?.id === wcId) setActiveCloud(null);
      MessagePlugin.success("已删除");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  const handleDeleteSaved = async (savedId: number) => {
    try {
      await deleteSavedVaTask(savedId);
      setSavedTasks(savedTasks.filter((s) => s.id !== savedId));
      setWordClouds(wordClouds.filter((w) => w.savedVaTaskId !== savedId));
      MessagePlugin.success("已删除");
    } catch (e: any) { MessagePlugin.error(e.message); }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white">词云分析</h1>
        <p className="text-sm text-gray-400 mt-1">基于已存储视频分析任务的评论内容，生成分词词云</p>
      </div>

      {/* Task selection area */}
      <div className="glass-card rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-gray-300">
            <CloudIcon size="18px" className="mr-1 inline-block align-text-bottom" />
            选择已存储任务生成词云
          </span>
          <Button variant="outline" size="small" onClick={loadSavedTasks} icon={<RefreshIcon />}>
            刷新列表
          </Button>
        </div>

        {loading ? (
          <Loading />
        ) : savedTasks.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            暂无已存储任务，请先在视频分析页面完成任务并存储
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {savedTasks.map((task) => {
              const hasCloud = wordClouds.some((w) => w.savedVaTaskId === task.id);
              const cloud = wordClouds.find((w) => w.savedVaTaskId === task.id);
              return (
                <div
                  key={task.id}
                  className={`p-3 rounded-lg border transition-all cursor-pointer ${
                    selectedTaskId === task.id ? "bg-indigo-500/15 border-indigo-500/30" : "bg-white/[0.03] border-white/[0.06] hover:border-white/12"
                  }`}
                  onClick={() => { setSelectedTaskId(task.id); if (cloud) setActiveCloud(cloud); }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-200 truncate font-medium">{task.title || "无标题"}</div>
                      <div className="text-[10px] text-gray-500 mt-0.5">{task.totalComments}条评论 · {task.matchedCount}匹配</div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      {hasCloud && (
                        <Button
                          size="extra-small" variant="outline"
                          onClick={(e) => { e.stopPropagation(); handleViewCloud(cloud!); }}
                          className="!text-[10px]"
                        >
                          查看
                        </Button>
                      )}
                      <Button
                        size="extra-small" theme={hasCloud ? "default" : "primary"}
                        loading={generating && selectedTaskId === task.id}
                        onClick={(e) => { e.stopPropagation(); handleGenerate(task.id); }}
                        className="!text-[10px]"
                      >
                        {hasCloud ? "重新生成" : "生成"}
                      </Button>
                      <button
                        className="p-0.5 rounded hover:bg-red-500/20"
                        onClick={(e) => { e.stopPropagation(); handleDeleteSaved(task.id); }}
                      >
                        <DeleteIcon size="12px" className="text-gray-500 hover:text-red-400" />
                      </button>
                    </div>
                  </div>
                  {hasCloud && cloud && (
                    <div className="mt-1.5 text-[10px] text-emerald-400/70">
                      已有词云 ({cloud.totalWords}个词)
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Word Cloud Display */}
      {activeCloud && activeCloud.words.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-white">{activeCloud.taskTitle}</h2>
              <p className="text-xs text-gray-500 mt-0.5">共 {activeCloud.totalWords} 个关键词 · 生成于 {activeCloud.generatedAt.slice(0, 16).replace("T", " ")}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="small" onClick={() => handleGenerate(activeCloud.savedVaTaskId)} icon={<RefreshIcon />} disabled={generating}>
                重新生成
              </Button>
              <Button variant="outline" size="small" onClick={() => handleDeleteCloud(activeCloud.id)} icon={<DeleteIcon />}>
                删除
              </Button>
            </div>
          </div>
          <WordCloudCanvas words={activeCloud.words} />

          {/* Word list */}
          <details className="mt-4">
            <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-300 transition-colors">
              查看全部关键词列表 ({activeCloud.words.length})
            </summary>
            <div className="mt-2 flex flex-wrap gap-2 max-h-40 overflow-y-auto pr-2">
              {activeCloud.words.map((w) => (
                <Tag key={w.text} size="small" variant="light" theme="primary">
                  {w.text} ({w.count})
                </Tag>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* All word clouds history */}
      {wordClouds.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">历史词云记录</h3>
          <div className="space-y-2">
            {wordClouds.map((wc) => (
              <div key={wc.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors">
                <div>
                  <span className="text-xs text-gray-200">{wc.taskTitle}</span>
                  <span className="text-[10px] text-gray-500 ml-2">{wc.totalWords}词 · {wc.generatedAt.slice(0, 10)}</span>
                </div>
                <div className="flex gap-1.5">
                  <Button size="extra-small" variant="outline" onClick={() => handleViewCloud(wc)} className="!text-[10px]">查看</Button>
                  <button onClick={() => handleDeleteCloud(wc.id)}>
                    <DeleteIcon size="12px" className="text-gray-500 hover:text-red-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
