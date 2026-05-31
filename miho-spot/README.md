# Miho-spot 米哈游舆情监测系统

"从此以后，每个人都是社管，亦或者都不是社管。" — By Chronostasis

## 项目简介

Miho-spot 是一个基于多平台热搜爬取的舆情检测系统，旨在检测米哈游在三大平台（知乎、抖音、贴吧）上的热搜，通过情绪判断模块推导出米哈游风评波动。

后端使用 PyQt6 作为 GUI 框架，前端以 TDesign React 为主导技术。

## 功能特性

- **多平台热搜爬取**：自动爬取知乎、抖音、贴吧热榜
- **关键词过滤**：内置二游圈关键词词典，支持用户手动扩充
- **情感分析**：三级分类（正面/负面/无关），无关项关联游戏显示
- **深度分析**：爬取热搜下100条帖子/视频进行情感三分
- **数据可视化**：饼状图/柱状图切换，7天/30天/自定义时间统计
- **账号管理**：支持登录知乎、抖音、贴吧账号以提升爬取权限

## 技术栈

### 前端
- React 19 + TypeScript + Vite
- TDesign React v1.17
- Tailwind CSS v4
- Recharts v3
- React Router v7

### 后端
- Python 3.10+
- FastAPI（REST API）
- PyQt6（桌面 GUI）
- SQLite / SQLAlchemy（数据持久化）
- SnowNLP + jieba（情感分析）

## 快速开始

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 后端开发

```bash
cd backend
pip install -r requirements.txt

# 启动 API 服务
python launcher.py --server

# 启动桌面 GUI（需要 PyQt6）
python launcher.py --gui

# 同时启动
python launcher.py
```

API 文档访问：http://localhost:8000/docs

## 项目结构

```
miho-spot/
├── frontend/                # React 前端
│   ├── src/
│   │   ├── components/      # 通用组件
│   │   │   ├── Layout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── StatCard.tsx
│   │   │   ├── SentimentChart.tsx
│   │   │   ├── HotTopicTable.tsx
│   │   │   └── DateRangeSelector.tsx
│   │   ├── pages/           # 页面组件
│   │   │   ├── Dashboard.tsx    # 数据仪表盘
│   │   │   ├── HotTopics.tsx    # 热搜监测
│   │   │   ├── Keywords.tsx     # 关键词词典
│   │   │   ├── History.tsx      # 历史统计
│   │   │   └── Accounts.tsx     # 账号管理
│   │   ├── services/        # API 服务
│   │   ├── types/           # TypeScript 类型
│   │   └── data/            # 静态数据
│   └── package.json
├── backend/                 # Python 后端
│   ├── app/
│   │   ├── api/             # FastAPI 路由
│   │   ├── models/          # 数据库模型
│   │   ├── crawlers/        # 爬虫引擎
│   │   ├── sentiment/       # 情感分析
│   │   └── gui/             # PyQt6 桌面界面
│   ├── main.py              # FastAPI 入口
│   ├── launcher.py          # 启动器
│   └── requirements.txt
└── README.md
```

## 关键词词典

系统内置了丰富的二游圈关键词词典，涵盖以下类别：

- **米哈游游戏**：原神、崩坏：星穹铁道、崩坏3、绝区零等
- **米哈游角色**：钟离、胡桃、雷电将军、纳西妲、芙宁娜等
- **米哈游CV**：kinsen、花玲、林簌、多多poi等
- **竞品游戏**：明日方舟、鸣潮、无限暖暖、幻塔等
- **二游圈通用**：二游、抽卡、648、策划、流水等

用户可在前端"关键词词典"页面手动添加和管理关键词。
