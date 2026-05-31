interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  delay?: number;
}

export default function StatCard({ label, value, icon, color, delay = 0 }: StatCardProps) {
  return (
    <div
      className="glass-card p-5 animate-fade-in-up opacity-0"
      style={{ animationDelay: `${delay}s`, animationFillMode: "forwards" }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-[#94a3b8]">{label}</span>
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-lg"
          style={{ backgroundColor: `${color}15`, color }}
        >
          {icon}
        </div>
      </div>
      <div className="text-3xl font-bold text-white" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
