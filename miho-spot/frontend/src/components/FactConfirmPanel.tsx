import { useState } from 'react';

interface FactItem {
  id: string;
  content: string;
  source: string;
  evidence: string;
  table_fields: Record<string, string>;
  needs_confirmation: boolean;
}

interface Props {
  facts: FactItem[];
  onConfirm: (actions: { fact_id: string; action: string; modified_content?: string }[]) => void;
}

export default function FactConfirmPanel({ facts, onConfirm }: Props) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [submittedFacts, setSubmittedFacts] = useState<Set<string>>(new Set());

  const submitSingle = (factId: string, action: string) => {
    const modified = edits[factId];
    onConfirm([{
      fact_id: factId,
      action,
      modified_content: action === 'modify' ? (modified || undefined) : undefined,
    }]);
    setSubmittedFacts(prev => new Set([...prev, factId]));
  };

  const submitAll = (action: string) => {
    const allFacts = facts.filter(f => !submittedFacts.has(f.id));
    onConfirm(allFacts.map(f => ({
      fact_id: f.id,
      action,
      modified_content: action === 'modify' ? (edits[f.id] || undefined) : undefined,
    })));
    setSubmittedFacts(prev => {
      const s = new Set(prev);
      allFacts.forEach(f => s.add(f.id));
      return s;
    });
  };

  const remaining = facts.filter(f => !submittedFacts.has(f.id));

  if (remaining.length === 0) {
    return (
      <div className="shrink-0 border border-[#2a2a4a] rounded-lg bg-[#0a0a12] p-3 text-xs text-[#94a3b8]">
        ✓ 当前所有事实已确认。等待新事实发现...
      </div>
    );
  }

  return (
    <div className="shrink-0 max-h-[45vh] overflow-y-auto border border-[#2a2a4a] rounded-lg bg-[#0a0a12] p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#e0e0e0]">
          事实确认 ({remaining.length} 条待确认 / {facts.length} 条总计)
        </h3>
        <div className="flex gap-2">
          <button onClick={() => submitAll('confirm')}
            className="px-2 py-1 text-xs bg-green-900/30 text-green-400 rounded hover:bg-green-900/50">
            全部确认
          </button>
          <button onClick={() => submitAll('dispute')}
            className="px-2 py-1 text-xs bg-yellow-900/30 text-yellow-400 rounded hover:bg-yellow-900/50">
            全部争议
          </button>
        </div>
      </div>

      {remaining.map(fact => (
        <div key={fact.id} className="border border-[#1a1a3a] rounded p-3 space-y-3">
          {/* 来源标签 */}
          <div className="flex items-center gap-2 text-xs text-[#64748b]">
            <span className="px-1.5 py-0.5 bg-[#1a1a3a] rounded text-[10px]">{fact.source}</span>
            {fact.evidence && (
              <span className="text-[#555] text-[10px]">| {fact.evidence}</span>
            )}
          </div>

          {/* 事实内容 — 大字展示 */}
          <div className="text-sm text-[#e0e0e0] leading-relaxed bg-[#0a0a0f] rounded-lg p-3 border border-[#1a1a2e]">
            {fact.content}
          </div>

          {/* 可编辑区域 */}
          <textarea
            value={edits[fact.id] ?? fact.content}
            onChange={e => setEdits(prev => ({ ...prev, [fact.id]: e.target.value }))}
            className="w-full bg-transparent text-[#94a3b8] border border-[#1a1a3a] rounded-lg px-3 py-2 outline-none focus:border-[#4a4a8a] text-xs resize-y min-h-[40px]"
            placeholder="点击修改内容..."
            rows={2}
          />

          {/* 操作按钮 */}
          <div className="flex gap-2">
            <button onClick={() => submitSingle(fact.id, 'confirm')}
              className="flex-1 py-1.5 text-xs rounded font-medium bg-green-900/20 text-green-400 hover:bg-green-900/50 transition-colors">
              ✓ 确认
            </button>
            <button onClick={() => submitSingle(fact.id, 'dispute')}
              className="flex-1 py-1.5 text-xs rounded font-medium bg-yellow-900/20 text-yellow-400 hover:bg-yellow-900/50 transition-colors">
              ≈ 争议
            </button>
            <button onClick={() => submitSingle(fact.id, 'reject')}
              className="flex-1 py-1.5 text-xs rounded font-medium bg-red-900/20 text-red-400 hover:bg-red-900/50 transition-colors">
              ✗ 驳回
            </button>
            <button onClick={() => submitSingle(fact.id, 'modify')}
              className="flex-1 py-1.5 text-xs rounded font-medium bg-blue-900/20 text-blue-400 hover:bg-blue-900/50 transition-colors">
              📝 修改并确认
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
