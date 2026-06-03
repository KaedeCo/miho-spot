import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "tdesign-react";
import {
  DashboardIcon,
  ChartIcon,
  BookIcon,
  HistoryIcon,
  SettingIcon,
  SearchIcon,
  LocationIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlayCircleIcon,
  CloudIcon,
  FileSearchIcon,
} from "tdesign-icons-react";

const menuItems = [
  { path: "/", label: "数据仪表盘", icon: <DashboardIcon /> },
  { path: "/topics", label: "热搜监测", icon: <ChartIcon /> },
  { path: "/keywords", label: "关键词词典", icon: <BookIcon /> },
  { path: "/history", label: "历史统计", icon: <HistoryIcon /> },
  { path: "/identity", label: "查成分", icon: <SearchIcon /> },
  { path: "/spectrum", label: "二维光谱图", icon: <LocationIcon /> },
  { path: "/video-analysis", label: "视频分析", icon: <PlayCircleIcon /> },
  { path: "/word-cloud", label: "词云", icon: <CloudIcon /> },
  { path: "/deep-analysis", label: "深度分析", icon: <FileSearchIcon /> },
  { path: "/accounts", label: "账号管理", icon: <SettingIcon /> },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const activeKey = menuItems.find((item) => item.path === location.pathname)?.path || "/";

  return (
    <div
      className="h-screen flex flex-col glass-card border-r border-[#2a2a4a] transition-all duration-300"
      style={{ width: collapsed ? 72 : 240, borderRadius: 0 }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[#2a2a4a]">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shrink-0 animate-pulse-glow">
          M
        </div>
        {!collapsed && (
          <div className="animate-fade-in">
            <div className="text-sm font-semibold text-white">Miho-spot</div>
            <div className="text-[10px] text-[#94a3b8]">舆情监测系统</div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-6 px-4 space-y-3">
        {menuItems.map((item) => (
          <div
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`flex items-center gap-3 px-4 py-4 rounded-lg cursor-pointer transition-all duration-200 group ${
              activeKey === item.path
                ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"
                : "text-[#94a3b8] hover:text-[#e2e8f0] hover:bg-white/5"
            }`}
            title={item.label}
          >
            <span className="text-lg shrink-0">{item.icon}</span>
            {!collapsed && (
              <span className="text-sm whitespace-nowrap animate-fade-in">{item.label}</span>
            )}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-[#2a2a4a]">
        <Button
          variant="text"
          shape="square"
          size="small"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full text-[#94a3b8] hover:text-white"
        >
          {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
        </Button>
      </div>
    </div>
  );
}
