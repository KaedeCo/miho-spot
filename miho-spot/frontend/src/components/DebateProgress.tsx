interface Props {
  currentRound: number;
  totalRounds: number;
  roundLabel: string;
  searchTrack: { current_track: string; volcano_calls: number; tavily_calls: number };
}

interface Props {
  currentRound: number;
  totalRounds: number;
  roundLabel: string;
  searchTrack: { current_track: string; volcano_calls: number; tavily_calls: number };
  pendingFactCount?: number;
}

export default function DebateProgress({ currentRound, totalRounds, roundLabel, searchTrack, pendingFactCount }: Props) {
  const pct = totalRounds > 0 ? Math.round((currentRound / totalRounds) * 100) : 0;

  return (
    <div className="shrink-0 space-y-2">
      <div className="flex items-center justify-between text-xs text-[#94a3b8]">
        <span>
          辩论轮次: {currentRound}/{totalRounds} — {roundLabel}
          {pendingFactCount != null && pendingFactCount > 0 && (
            <span className="ml-2 text-yellow-400">[待确认事实: {pendingFactCount}]</span>
          )}
        </span>
        <span className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${searchTrack.current_track === 'volcano' ? 'bg-orange-400' : searchTrack.current_track === 'tavily' ? 'bg-blue-400' : 'bg-gray-500'}`} />
          搜索轨: {searchTrack.current_track === 'volcano' ? '火山' : searchTrack.current_track === 'tavily' ? 'Tavily' : '-'}
          {searchTrack.current_track !== '-' && (
            <span className="text-[#555]">
              (火山{searchTrack.volcano_calls}次 / Tavily{searchTrack.tavily_calls}次)
            </span>
          )}
        </span>
      </div>
      <div className="h-2 bg-[#1a1a2e] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out bg-gradient-to-r from-[#2563eb] via-[#7c3aed] to-[#ec4899]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
