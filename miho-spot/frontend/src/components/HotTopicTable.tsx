import type { HotTopic } from "../types";
import { Tag, Table, Button } from "tdesign-react";
import { JumpIcon } from "tdesign-icons-react";

const SENTIMENT_CONFIG = {
  Positive: { label: "正面", theme: "success" as const, color: "#22c55e" },
  Negative: { label: "负面", theme: "danger" as const, color: "#ef4444" },
  Neutral: { label: "中性", theme: "warning" as const, color: "#f59e0b" },
  Irrelevant: { label: "无关", theme: "default" as const, color: "#6b7280" },
};

const PLATFORM_CONFIG: Record<string, { label: string; color: string }> = {
  zhihu: { label: "知乎", color: "#0066ff" },
  douyin: { label: "抖音", color: "#ff0050" },
  tieba: { label: "贴吧", color: "#3388ff" },
  bilibili: { label: "B站", color: "#fb7299" },
  weibo: { label: "微博", color: "#e6162d" },
};

interface HotTopicTableProps {
  topics: HotTopic[];
  onTopicClick?: (topic: HotTopic) => void;
  className?: string;
}

export default function HotTopicTable({ topics, onTopicClick, className = "" }: HotTopicTableProps) {
  const columns = [
    {
      colKey: "platform",
      title: "平台",
      width: 80,
      cell: ({ row }: any) => {
        const config = PLATFORM_CONFIG[row.platform];
        const c = config?.color || "#6b7280";
        return (
          <Tag style={{ backgroundColor: c + "20", color: c, border: "none" }} size="small">
            {config?.label || row.platform}
          </Tag>
        );
      },
    },
    {
      colKey: "rank",
      title: "排名",
      width: 60,
      cell: ({ row }: any) => (
        <span className={`font-bold ${row.rank <= 3 ? "text-yellow-400" : "text-[#94a3b8]"}`}>
          #{row.rank}
        </span>
      ),
    },
    {
      colKey: "title",
      title: "热搜标题",
      cell: ({ row }: any) => (
        <div className="max-w-md flex items-center gap-2">
          <a
            href={row.url && row.url !== "#" ? row.url : undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#e2e8f0] hover:text-indigo-400 transition-colors line-clamp-2 text-sm cursor-pointer"
            title={row.title}
            onClick={(e) => e.stopPropagation()}
          >
            {row.title}
          </a>
        </div>
      ),
    },
    {
      colKey: "heat",
      title: "热度",
      width: 100,
      cell: ({ row }: any) => (
        <span className="text-sm text-[#94a3b8]">{row.heat?.toLocaleString() || "-"}</span>
      ),
    },
    {
      colKey: "sentiment",
      title: "情感",
      width: 80,
      cell: ({ row }: any) => {
        const config = SENTIMENT_CONFIG[row.sentiment as keyof typeof SENTIMENT_CONFIG];
        return (
          <Tag theme={config?.theme || "default"} size="small" variant="light">
            {config?.label || row.sentiment}
          </Tag>
        );
      },
    },
    {
      colKey: "relatedGame",
      title: "关联游戏",
      width: 120,
      cell: ({ row }: any) => {
        if (row.sentiment === "Irrelevant" && row.relatedGame) {
          return (
            <Tag size="small" variant="outline" style={{ color: "#94a3b8" }}>
              {row.relatedGame}
            </Tag>
          );
        }
        return <span className="text-[#555] text-sm">-</span>;
      },
    },
    {
      colKey: "link",
      title: "原文",
      width: 60,
      cell: ({ row }: any) => (
        <a
          href={row.url && row.url !== "#" ? row.url : undefined}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          title="跳转到原文"
        >
          <Button variant="text" size="small" shape="square" icon={<JumpIcon />} className="!text-[#6366f1] hover:!text-[#a78bfa]" />
        </a>
      ),
    },
  ];

  return (
    <div className={`glass-card p-5 ${className}`}>
      <h3 className="text-base font-semibold text-white mb-4">热搜词条列表</h3>
      <Table
        data={topics}
        columns={columns}
        rowKey="id"
        size="medium"
        hover
        stripe
        bordered={false}
        onRowClick={({ row }: any) => onTopicClick?.(row)}
        tableLayout="auto"
        className="miho-table"
        empty="暂无热搜数据，请点击爬取按钮获取数据"
      />
    </div>
  );
}
