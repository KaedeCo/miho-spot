import ReactMarkdown from 'react-markdown';

interface Props {
  report: string;
  sessionId?: string;
  onCopy: () => void;
  onClose: () => void;
}

export default function DebateReportPreview({ report, sessionId, onCopy, onClose }: Props) {
  const pdfDownloadUrl = sessionId ? `http://localhost:8000/api/debate/pdf/${sessionId}` : '';

  return (
    <div className="shrink-0 max-h-[50vh] overflow-y-auto border border-[#2a2a4a] rounded-lg bg-[#0a0a12] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#e0e0e0]">
          舆情深度分析报告
        </h3>
        <div className="flex gap-2">
          {pdfDownloadUrl && (
            <a
              href={pdfDownloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 text-xs bg-gradient-to-r from-[#2563eb] to-[#7c3aed] text-white rounded hover:opacity-90 transition-opacity font-medium"
            >
              📄 下载 PDF
            </a>
          )}
          <button
            onClick={onCopy}
            className="px-3 py-1 text-xs bg-[#1a1a3a] text-[#94a3b8] rounded hover:bg-[#2a2a4a] transition-colors"
          >
            📋 复制 Markdown
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1 text-xs bg-[#1a1a3a] text-[#94a3b8] rounded hover:bg-[#2a2a4a] transition-colors"
          >
            ✕ 关闭
          </button>
        </div>
      </div>
      <div className="markdown-body text-[#c0c0c0] text-sm leading-relaxed">
        <ReactMarkdown>
          {report || '报告生成中...'}
        </ReactMarkdown>
      </div>
    </div>
  );
}
