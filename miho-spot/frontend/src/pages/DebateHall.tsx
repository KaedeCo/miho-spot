import { useState, useCallback, useRef } from 'react';
import AgentTerminal from '../components/AgentTerminal';
import DebateProgress from '../components/DebateProgress';
import FactConfirmPanel from '../components/FactConfirmPanel';
import DebateReportPreview from '../components/DebateReportPreview';
import { debateApi } from '../services/api';

interface AgentOutput {
  A1: string;
  A2: string;
  A3: string;
}

interface PendingFact {
  id: string;
  content: string;
  source: string;
  evidence: string;
  table_fields: Record<string, string>;
  needs_confirmation: boolean;
}

interface SearchTrack {
  current_track: string;
  volcano_calls: number;
  tavily_calls: number;
}

export default function DebateHall() {
  const [topic, setTopic] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle'); // idle | running | waiting_facts | done | error
  const [currentRound, setCurrentRound] = useState(0);
  const [totalRounds, setTotalRounds] = useState(8);
  const [roundLabel, setRoundLabel] = useState('');
  const [agentOutputs, setAgentOutputs] = useState<AgentOutput>({ A1: '', A2: '', A3: '' });
  const [pendingFacts, setPendingFacts] = useState<PendingFact[]>([]);
  const [finalReport, setFinalReport] = useState<string>('');
  const [error, setError] = useState('');
  const [searchTrack, setSearchTrack] = useState<SearchTrack>({ current_track: '-', volcano_calls: 0, tavily_calls: 0 });
  const [pdfPath, setPdfPath] = useState('');
  const [showReport, setShowReport] = useState(false);

  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [agentThinking, setAgentThinking] = useState<Record<string, string>>({});
  const [toolCalls, setToolCalls] = useState<Record<string, string[]>>({});
  const [isStreaming, setIsStreaming] = useState<Record<string, boolean>>({});

  const eventSourceRef = useRef<EventSource | null>(null);

  const startDebate = useCallback(async () => {
    if (!topic.trim()) return;
    setStatus('running');
    setError('');
    setAgentOutputs({ A1: '', A2: '', A3: '' });
    setPendingFacts([]);
    setFinalReport('');
    setShowReport(false);
    setToolCalls({});
    setIsStreaming({});

    try {
      const res = await debateApi.create(topic.trim());
      if (!res.ok) throw new Error('创建辩论失败');
      setSessionId(res.sessionId);
      setSearchTrack({ current_track: res.searchTrack, volcano_calls: 0, tavily_calls: 0 });

      // 建立 SSE 连接
      const es = new EventSource(`http://localhost:8000/api/debate/stream/${res.sessionId}`);
      eventSourceRef.current = es;

      es.addEventListener('round_start', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setCurrentRound(d.round);
        setTotalRounds(d.total_rounds);
        setRoundLabel(d.label);
        setActiveAgent(d.agent !== 'ALL' ? d.agent : null);
      });

      es.addEventListener('agent_thinking', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setAgentThinking(prev => ({ ...prev, [d.agent]: d.message }));
      });

      es.addEventListener('tool_call', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setToolCalls(prev => ({
          ...prev,
          [d.agent]: [...(prev[d.agent] || []), `[tool] ${d.tool}(${JSON.stringify(d.args)})`],
        }));
      });

      es.addEventListener('tool_result', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setToolCalls(prev => ({
          ...prev,
          [d.agent]: [...(prev[d.agent] || []), `  -> ${d.result_summary}`],
        }));
      });

      es.addEventListener('file_transfer', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        // 紫色系统消息：文件在agent之间传递
        const msg = `[transfer] ${d.from_agent} ⇒ ${d.to_agent}: ${d.files?.join(', ') || ''}`;
        const targetAgent = d.from_agent; // 显示在发送方的终端
        setToolCalls(prev => ({
          ...prev,
          [targetAgent]: [...(prev[targetAgent] || []), msg],
        }));
        if (d.to_agent !== targetAgent) {
          setToolCalls(prev2 => ({
            ...prev2,
            [d.to_agent]: [...(prev2[d.to_agent] || []), `[receive] ← ${d.from_agent}: ${d.files?.join(', ') || ''}`],
          }));
        }
      });

      es.addEventListener('facts_extracted', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        const msg = `[facts] 提取了 ${d.count} 条事实: ${d.facts?.map((f: any) => f.content?.substring(0, 40)).join(' | ') || ''}`;
        setToolCalls(prev => ({
          ...prev,
          [d.agent]: [...(prev[d.agent] || []), msg],
        }));
      });

      es.addEventListener('agent_output', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setIsStreaming(prev => ({ ...prev, [d.agent]: d.type === 'partial' }));
        if (d.type === 'partial') {
          setAgentOutputs(prev => ({
            ...prev,
            [d.agent]: prev[d.agent as keyof AgentOutput] + d.content,
          }));
        } else {
          // complete - 非文本事件忽略
        }
      });

      es.addEventListener('new_facts', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        // 按 ID 去重——避免同一事实重复出现
        setPendingFacts(prev => {
          const existingIds = new Set(prev.map(f => f.id));
          const newOnes = (d.facts || []).filter((f: any) => !existingIds.has(f.id));
          return [...prev, ...newOnes];
        });
      });

      es.addEventListener('waiting_for_facts', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setStatus('waiting_facts');
      });

      es.addEventListener('volcano_quota_exhausted', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setSearchTrack(prev => ({ ...prev, current_track: 'tavily' }));
        setToolCalls(prev => ({
          ...prev,
          A2: [...(prev.A2 || []), `[system] ${d.message}`],
          A3: [...(prev.A3 || []), `[system] ${d.message}`],
        }));
      });

      es.addEventListener('round_complete', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setIsStreaming({ A1: false, A2: false, A3: false });
      });

      es.addEventListener('debate_complete', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setFinalReport(d.report?.content || d.report?.report || '');
        setPdfPath(d.pdf_path || '');
        setStatus('done');
        setShowReport(true);
        es.close();
        eventSourceRef.current = null;
      });

      es.addEventListener('round_error', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setError(`第${d.round}轮 ${d.agent} 出错: ${d.error?.substring(0, 150)}`);
      });

      es.addEventListener('debate_error', (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setError(d.error || '辩论过程发生错误');
        setStatus('error');
        // 显示不完整报告
        if (d.partial_report?.content) {
          setFinalReport(typeof d.partial_report.content === 'string'
            ? d.partial_report.content
            : JSON.stringify(d.partial_report.content, null, 2));
          setShowReport(true);
        }
        setIsStreaming({ A1: false, A2: false, A3: false });
        es.close();
        eventSourceRef.current = null;
      });

      es.onerror = () => {
        if (status !== 'done' && status !== 'error') {
          setError('SSE 连接中断');
          setStatus('error');
        }
      };

    } catch (err: any) {
      setError(err.message || '启动辩论失败');
      setStatus('error');
    }
  }, [topic, status]);

  const handleFactConfirm = useCallback(async (actions: { fact_id: string; action: string; modified_content?: string }[]) => {
    if (!sessionId) return;
    try {
      await debateApi.confirmFacts(sessionId, actions);
      const submittedIds = new Set(actions.map(a => a.fact_id));
      setPendingFacts(prev => prev.filter(f => !submittedIds.has(f.id)));
      if (status === 'waiting_facts') setStatus('running');
    } catch (err: any) {
      setError(err.message || '事实确认失败');
    }
  }, [sessionId, status]);

  const handleSave = useCallback(async () => {
    if (!sessionId) return;
    try {
      await debateApi.save(sessionId);
      alert('辩论进度已保存');
    } catch (err: any) {
      setError(err.message || '保存失败');
    }
  }, [sessionId]);

  const handleCopyReport = useCallback(() => {
    navigator.clipboard.writeText(finalReport);
    alert('报告已复制到剪贴板');
  }, [finalReport]);

  return (
    <div className="h-full flex flex-col p-4 gap-3 overflow-hidden">
      {/* 顶部控制栏 */}
      <div className="flex items-center gap-3 shrink-0">
        <input
          type="text"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="输入辩论主题（如：原神 4.7 版本争议分析）"
          className="flex-1 px-4 py-2 bg-[#0a0a0f] border border-[#2a2a4a] rounded-lg text-[#e0e0e0] placeholder-[#555] focus:outline-none focus:border-[#4a4a8a] text-sm"
          disabled={status === 'running' || status === 'waiting_facts'}
          onKeyDown={e => { if (e.key === 'Enter' && status === 'idle') startDebate(); }}
        />
        <button
          onClick={startDebate}
          disabled={!topic.trim() || status === 'running' || status === 'waiting_facts'}
          className="px-5 py-2 bg-gradient-to-r from-[#2563eb] to-[#7c3aed] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
        >
          {status === 'idle' ? '开始辩论' : status === 'running' ? '辩论中...' : status === 'waiting_facts' ? '等待确认...' : '开始辩论'}
        </button>
        <button
          onClick={handleSave}
          disabled={!sessionId || status === 'idle'}
          className="px-4 py-2 border border-[#2a2a4a] text-[#94a3b8] rounded-lg text-sm hover:bg-[#1a1a2e] disabled:opacity-30 transition-colors"
        >
          💾 保存
        </button>
      </div>

      {/* 进度条 */}
      {(status === 'running' || status === 'waiting_facts') && (
        <DebateProgress
          currentRound={currentRound}
          totalRounds={totalRounds}
          roundLabel={roundLabel}
          searchTrack={searchTrack}
        />
      )}

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-red-300 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-3 underline">关闭</button>
        </div>
      )}

      {/* 三个智能体终端 */}
      <div className="flex-1 flex gap-3 min-h-0">
        {(['A1', 'A2', 'A3'] as const).map(agentId => (
          <div key={agentId} className="flex-1 flex flex-col min-w-0">
            <div className="text-xs text-[#64748b] mb-1 px-1 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${activeAgent === agentId ? 'bg-green-400 animate-pulse' : status === 'running' ? 'bg-yellow-600' : 'bg-gray-600'}`} />
              <span className="font-semibold">
                {agentId === 'A1' ? '私有数据专家' : agentId === 'A2' ? '官媒分析专家' : '公域扫描专家'}
              </span>
              {agentThinking[agentId] && (
                <span className="text-[#555] italic ml-auto truncate">{agentThinking[agentId]}</span>
              )}
            </div>
            <AgentTerminal
              agentId={agentId}
              content={agentOutputs[agentId]}
              toolCalls={toolCalls[agentId] || []}
              isStreaming={isStreaming[agentId] || false}
            />
          </div>
        ))}
      </div>

      {/* 事实确认面板 — 有事实就显示，不限于 waiting_facts */}
      {pendingFacts.filter(f => f.needs_confirmation).length > 0 && (
        <FactConfirmPanel
          facts={pendingFacts.filter(f => f.needs_confirmation)}
          onConfirm={handleFactConfirm}
        />
      )}

      {/* 最终报告 */}
      {showReport && finalReport && (
        <DebateReportPreview
          report={finalReport}
          sessionId={sessionId || undefined}
          onCopy={handleCopyReport}
          onClose={() => setShowReport(false)}
        />
      )}
    </div>
  );
}
