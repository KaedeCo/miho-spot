import { useState } from "react";
import { DateRangePicker, Select } from "tdesign-react";
import type { TimeRange } from "../types";

interface DateRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange, startDate?: string, endDate?: string) => void;
  className?: string;
}

export default function DateRangeSelector({ value, onChange, className = "" }: DateRangeSelectorProps) {
  const [showCustom, setShowCustom] = useState(value === "custom");

  const options = [
    { label: "过去7天", value: "7d" },
    { label: "过去30天", value: "30d" },
    { label: "自定义范围", value: "custom" },
  ];

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <span className="text-sm text-[#94a3b8] whitespace-nowrap">时间范围：</span>
      <Select
        value={value}
        onChange={(v) => {
          const val = v as TimeRange;
          setShowCustom(val === "custom");
          onChange(val);
        }}
        options={options}
        size="medium"
        style={{ width: 160 }}
      />
      {showCustom && (
        <DateRangePicker
          onChange={(dates) => {
            if (dates && dates.length === 2) {
              const start = typeof dates[0] === "string" ? dates[0] : (dates[0] as Date).toISOString().split("T")[0];
              const end = typeof dates[1] === "string" ? dates[1] : (dates[1] as Date).toISOString().split("T")[0];
              onChange("custom", start, end);
            }
          }}
          placeholder={["开始日期", "结束日期"]}
          size="medium"
          clearable
        />
      )}
    </div>
  );
}
