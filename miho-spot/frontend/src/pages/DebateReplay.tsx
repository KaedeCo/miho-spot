import { useState, useEffect } from 'react';
import { debateApi } from '../services/api';
import ReactMarkdown from 'react-markdown';

interface AgentData {
  output?: string;
  tool_calls?: any;
}

interface RoundData {
  round: number;
  agents: Record<string, AgentData>;
  summary?: { round: number; agent: string; timestamp: string };
}

interface SessionData {
  ok: boolean;
  topic: string;
  rounds: RoundData[];
  fact_check: any;
  supervisor_report: any;
  pdf_path: string;
}

const AGENT_COLORS: Record<string, string> = {
  A1: '#7cb8ff',
  A2: '#f59e0b',
  A3: '#34d399',
  SUPERVISOR: '#c084fc',
};
const AGENT_LABELS: Record<string, string> = {
  A1: '私有数据专家',
  A2: '官媒分析专家',
  A3: '公域扫描专家',
  SUPERVISOR: '监督 Agent',
};

export default function DebateReplay() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [data, setData] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadSessions(); }, []);

  const loadSessions = async () => {
    try {
      const r = await debateApi.listSessions();
      setSessions(r.sessions || []);
    } catch {}
  };

  const loadReplay = async (sessionId: string) => {
    setLoading(true);
    try {
      const r = await fetch(`/api/debate/replay/${sessionId}`);
      if (!r.ok) { setData(null); setLoading(false); return; }
      const d = await r.json();
      setData(d.ok && d.rounds ? d : null);
      setSelectedSession(sessionId);
    } catch { setData(null); }
    setLoading(false);
  };

  return (
    <div className="h-full flex flex-col p-4 gap-4 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0">
        <h1 className="text-xl font-bold text-white">辩论回放</h1>
        <select
          value={selectedSession}
          onChange={e => loadReplay(e.target.value)}
          className="px-3 py-1.5 bg-[#0a0a0f] border border-[#2a2a4a] rounded-lg text-[#e0e0e0] text-sm focus:outline-none"
        >
          <option value="">选择历史辩论...</option>
          {sessions.map((s: any) => (
            <option key={s.id} value={s.id}>
              [{s.status}] {s.topic?.substring(0, 50)} — {s.createdAt?.substring(0, 10)}
            </option>
          ))}
        </select>
        {loading && <span className="text-xs text-[#94a3b8]">加载中...</span>}
      </div>

      {data && (
        <div className="flex-1 overflow-y-auto space-y-5 pr-2">
          {/* 主题 */}
          <div className="bg-[#0a0a12] border border-[#2a2a4a] rounded-lg p-4">
            <h2 className="text-sm font-semibold text-[#e0e0e0]">{data.topic}</h2>
          </div>

          {/* 时间轴 */}
          {(data.rounds || []).map(round => (
            <div key={round.round} className="relative ml-2">
              {/* 轮次标记线 */}
              <div className="absolute left-[13px] top-7 bottom-0 w-0.5 bg-[#2a2a4a]" />
              <div
                className="absolute left-0 top-3 w-7 h-7 rounded-full flex items-center justify-center text-[11px] text-white font-bold"
                style={{ background: 'linear-gradient(135deg, #2563eb, #7c3aed)' }}
              >
                {round.round}
              </div>

              <div className="ml-11 space-y-3">
                {Object.entries(round.agents).map(([agentId, agentData]) => (
                  <div
                    key={agentId}
                    className="border rounded-lg overflow-hidden"
                    style={{ borderColor: AGENT_COLORS[agentId] + '30', background: '#0a0a0f' }}
                  >
                    {/* 发言者横栏 - 醒目 */}
                    <div
                      className="flex items-center gap-3 px-4 py-2.5"
                      style={{
                        background: `linear-gradient(90deg, ${AGENT_COLORS[agentId]}15, transparent)`,
                        borderLeft: `3px solid ${AGENT_COLORS[agentId]}`,
                      }}
                    >
                      <span
                        className="text-[13px] font-bold tracking-wide"
                        style={{ color: AGENT_COLORS[agentId] }}
                      >
                        {agentId === 'SUPERVISOR' ? '监督 Agent' : agentId}
                      </span>
                      <span className="text-[11px] text-[#64748b] font-medium">
                        {AGENT_LABELS[agentId]}
                      </span>
                      <span
                        className="ml-auto text-[9px] px-1.5 py-0.5 rounded"
                        style={{ background: AGENT_COLORS[agentId] + '15', color: AGENT_COLORS[agentId] + 'aa' }}
                      >
                        第 {round.round} 轮
                      </span>
                    </div>

                    {/* 内容区 */}
                    <div className="px-4 py-3">
                      {agentData.output ? (
                        <div className="text-xs text-[#94a3b8] leading-relaxed max-h-[400px] overflow-y-auto">
                          <ReactMarkdown>
                            {agentData.output}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="text-xs text-[#555] italic">（无输出记录）</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* 监督报告 */}
          {data.supervisor_report?.report && (
            <div className="relative ml-2">
              <div className="absolute left-0 top-3 w-8 h-8 rounded-full bg-[#c084fc] flex items-center justify-center text-[11px] text-white font-bold">
                S
              </div>
              <div className="ml-11 border border-[#c084fc30] rounded-lg overflow-hidden" style={{ background: '#0a0a0f' }}>
                <div
                  className="flex items-center gap-3 px-4 py-2.5"
                  style={{
                    background: 'linear-gradient(90deg, #c084fc15, transparent)',
                    borderLeft: '3px solid #c084fc',
                  }}
                >
                  <span className="text-[13px] font-bold text-[#c084fc] tracking-wide">最终报告</span>
                  <span className="text-[11px] text-[#64748b]">
                    综合辩论意见
                  </span>
                  {data.pdf_path && (
                    <a
                      href={`/api/debate/pdf/${selectedSession}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto px-3 py-1 text-[11px] bg-gradient-to-r from-[#2563eb] to-[#7c3aed] text-white rounded font-medium hover:opacity-90 transition-opacity"
                    >
                      PDF 下载
                    </a>
                  )}
                </div>
                <div className="px-4 py-3 text-xs text-[#94a3b8] leading-relaxed max-h-[500px] overflow-y-auto">
                  <ReactMarkdown>
                    {data.supervisor_report.report}
                  </ReactMarkdown>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {!data && !loading && (
        <div className="flex-1 flex items-center justify-center text-[#64748b] text-sm">
          选择一场已保存的辩论查看回放
        </div>
      )}
    </div>
  );
}
