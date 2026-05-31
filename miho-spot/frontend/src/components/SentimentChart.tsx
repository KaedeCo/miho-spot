import { useState } from "react";
import { Radio } from "tdesign-react";
import { ChartPieIcon, ChartBarIcon } from "tdesign-icons-react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { ChartType } from "../types";

interface SentimentChartProps {
  data: {
    positive: number;
    negative: number;
    neutral: number;
    irrelevant: number;
  };
  title: string;
  className?: string;
}

const COLORS = {
  positive: "#22c55e",
  negative: "#ef4444",
  neutral: "#f59e0b",
  irrelevant: "#6b7280",
};



export default function SentimentChart({ data, title, className = "" }: SentimentChartProps) {
  const [chartType, setChartType] = useState<ChartType>("pie");

  const chartData = [
    { name: "正面", value: data.positive, color: COLORS.positive },
    { name: "负面", value: data.negative, color: COLORS.negative },
    { name: "中性", value: data.neutral, color: COLORS.neutral },
    { name: "无关", value: data.irrelevant, color: COLORS.irrelevant },
  ].filter((d) => d.value > 0);

  const total = data.positive + data.negative + data.neutral + data.irrelevant;

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return (
        <div className="glass-card px-4 py-3 !border-[#2a2a4a]">
          <p className="text-sm text-white font-medium">{p.name}</p>
          <p className="text-lg font-bold" style={{ color: p.color }}>
            {p.value} ({total > 0 ? ((p.value / total) * 100).toFixed(1) : 0}%)
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`glass-card p-5 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        <Radio.Group value={chartType} onChange={(v) => setChartType(v as ChartType)} size="small" variant="default-filled">
          <Radio.Button value="pie">
            <ChartPieIcon className="mr-1" /> 饼图
          </Radio.Button>
          <Radio.Button value="bar">
            <ChartBarIcon className="mr-1" /> 柱状图
          </Radio.Button>
        </Radio.Group>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        {chartType === "pie" ? (
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={110}
              paddingAngle={4}
              dataKey="value"
              animationBegin={0}
              animationDuration={800}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="bottom"
              iconType="circle"
              formatter={(value) => <span className="text-[#94a3b8] text-sm">{value}</span>}
            />
          </PieChart>
        ) : (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" />
            <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} animationBegin={0} animationDuration={800}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
