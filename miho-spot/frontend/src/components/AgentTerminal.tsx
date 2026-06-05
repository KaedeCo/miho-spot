import { useEffect, useRef, useMemo } from 'react';

interface Props {
  agentId: string;
  content: string;
  toolCalls: string[];
  isStreaming: boolean;
}

function splitLines(text: string): string[] {
  if (!text) return [];
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
}

/** 简易内联 markdown 渲染：**bold** → <b>bold</b> */
function renderInlineMd(line: string): string {
  return line
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<i>$1</i>');
}

export default function AgentTerminal({ agentId, content, toolCalls, isStreaming }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content, toolCalls]);

  const lines = useMemo(() => splitLines(content), [content]);

  return (
    <div
      className="agent-terminal flex-1 overflow-y-auto font-mono text-[12px] leading-[1.65]"
      ref={scrollRef}
    >
      {/* 工具调用 / 文件传递 / 事实提取 — 颜色分层 */}
      {toolCalls.map((call, i) => {
        let colorClass = 'text-[#6b7280]';
        if (call.startsWith('[transfer]') || call.startsWith('[receive]')) {
          colorClass = 'text-[#c084fc]';
        } else if (call.startsWith('[facts]')) {
          colorClass = 'text-[#34d399]';
        } else if (call.startsWith('[system]')) {
          colorClass = 'text-[#fbbf24]';
        }
        return (
          <div key={`tool-${i}`} className={`${colorClass} text-[11px] mb-0.5`}>
            {call}
          </div>
        );
      })}

      {/* 辩论内容 — 浅蓝色，## 标题用亮色 */}
      {lines.map((line, i) => {
        const isHeading = line.startsWith('## ') || line.startsWith('### ');
        const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
        return (
          <div
            key={i}
            className={`min-h-[1.65em] ${
              isHeading ? 'text-[#fbbf24] font-bold text-[13px] mt-1' :
              isBullet ? 'text-[#93c5fd]' :
              'text-[#7cb8ff]'
            }`}
            dangerouslySetInnerHTML={{ __html: renderInlineMd(line) || '&nbsp;' }}
          />
        );
      })}

      {isStreaming && lines.length > 0 && (
        <span className="text-[#00ff41] font-bold animate-pulse">▌</span>
      )}
      {lines.length === 0 && isStreaming && (
        <div className="text-[#00ff41] font-bold animate-pulse">▌</div>
      )}
    </div>
  );
}
