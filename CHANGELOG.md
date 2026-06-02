# Miho-spot Changelog

## [v1.2.0] — 2026-06-02

### 🆕 新功能

#### 二维光谱图（Spectrum2D）
- 全新的二维光谱可视化页面 `/spectrum`，将已存储的用户画像以散点图形式呈现
- X 轴：米哈游态度（0=反对 → 100=支持），Y 轴：理性程度（0=感性 → 100=理性）
- 四象限标签：感性反对 / 感性支持 / 理性反对 / 理性支持
- 支持头像显示、悬停 tooltip、点击查看详情 Drawer
- 缩放滑块（50% ~ 250%），边缘渐变淡化效果
- SVG 渲染，响应式布局，深空主题配色
- 用户画像卡片导出为高清 PNG（html-to-image）
- 数据批量导出 JSON / 导入合并（跨设备迁移）

#### Bilibili 评论采集（AICU 接口）
- 新增基于 AICU 的 Bilibili 用户评论抓取模块（`app/bilibili/__init__.py`）
- 支持 40+ 种浏览器指纹轮换（curl_cffi impersonate）
- WAF 拦截自动重试 + 指数退避冷却机制（1s / 60s）
- 支持评论搜索 + 视频/专栏内容双维度采集
- 分页加载（评论每页100条，内容每页30条）

#### DeepSeek 人格分析
- 集成 DeepSeek API 对用户评论进行 AI 人格画像分析
- 输出维度：米哈游态度、活跃领域、性格推测、一句话总结
- 关键词匹配高亮展示
- 分析结果持久化存储到本地 SQLite

### 🔧 改进与优化

#### Tophub 搜索错误处理
- 修复 Tophub API 返回错误时前端无感知的沉默失败问题
- 新增全局错误状态变量 `_search_error` / `_search_error_code`
- `/api/crawl/status` 接口扩展返回错误信息字段
- 前端 Dashboard 可实时展示搜索任务的具体错误原因
- 与 AICU 重试策略完全隔离，互不影响

#### 前端优化
- Sidebar 导航栏新增"二维光谱图"入口项（LocationIcon 图标）
- Pagination 组件移除不合法的 `theme="primary"` 属性，修复 TypeScript 编译错误
- 移除未使用的 Card import，清理代码
- API 服务层新增：`getBiliProfiles`, `getBiliProfile`, `deleteBiliProfile`, `importBiliProfiles`, `exportBiliProfiles`
- 类型定义新增：`BiliProfileSummary`, `BiliProfileDetail`, `BiliProfileItems`

#### 打包系统升级
- 版本号从 v1.0 升级至 v1.2
- PyInstaller 打包配置新增 snownlp 完整数据文件（stopwords.txt, seg.marshal, sentiment.marshal 等）
- 新增 curl_cffi 依赖收集（`--collect-all curl_cffi`）
- 自动检测 snownlp 包路径，确保数据文件正确打包到 EXE 中
- 构建步骤从 4 步升级至 5 步（新增前端 build + snownlp 检测）
- 更新 release 信息提示文案

### 🐛 修复

- **snownlp FileNotFoundError**：修复打包后运行时缺少 `snownlp/normal/stopwords.txt` 等数据文件的问题，通过 `--add-data` 将整个 snownlp 包数据目录打入 EXE
- **TypeScript 编译错误**：修复 tdesign-react Pagination 组件 `theme` 属性类型不匹配（`"primary"` 不在允许值中）导致的 3 处 TS2322 错误
- **未使用导入**：移除 Spectrum2D 页面中未使用的 `Card` 组件导入（TS6133）

### 📦 依赖变更

**新增：**
- `curl_cffi` — 浏览器指纹模拟 HTTP 客户端（用于绕过 Bilibili WAF）
- `html-to-image` — DOM 转 PNG（用于用户画像卡片导出）

### ⚠️ 注意事项

- 本次更新**不包含任何预配置的 API 密钥**
- 用户需自行在"账号管理"页面填入：
  - Tophub API Key（热搜数据获取）
  - DeepSeek API Key（AI 人格分析）
- SQLite 数据库存储于 `%APPDATA%/Miho-spot/data/miho_spot.db`

---

## [v1.1.0] — Earlier Release

- 初始版本，包含基础舆情监测功能
- 热搜数据爬取（知乎、抖音、贴吧等平台）
- 关键词词典管理
- 历史统计仪表盘
