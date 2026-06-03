# Miho-spot Changelog

## [v1.3.0] — 2026-06-03

### 全栈稳定性修复与数据流完善

#### 前端修复 (6 项)

- **图标导入修复**：`CheckIdentity.tsx` 中 `ListIcon`/`OrderedListIcon` → `ViewListIcon`（TDesign Icons React v0.6.4 中不存在前两者）
- **React Key 重复警告修复**（4 组件联动）：
  - `HotTopicTable.tsx`：TDesign Table `rowKey` 从简单字符串改为复合函数
  - `CheckIdentity.tsx`：Key 增加 `rpid-` 前缀 + index fallback
  - `HotTopics.tsx`：Key 增加 `topic-` 前缀 + index fallback
  - 后端 `routes.py` `/topics` 端点：`_hot_cache` + `_search_cache` 拼接时按 ID 去重
- **TDesign Input 事件修复**：`VideoAnalysis.tsx` 中 `onPressEnter` → `onEnter`
- **API 参数命名修复**：`api.ts` 中 `taskId` → `task_id`（修复 422 Unprocessable Entity）
- **缺失导入修复**：`WordCloud.tsx` 添加 `Tag` 组件导入
- **空 src 渲染修复**：`CheckIdentity.tsx` 中头像 `q.face` 为空时不渲染 `<img>`

#### 后端修复 (4 项)

- **SQLAlchemy 函数名修复**：identity-queue 端点的 `func.max` → `_sql_func.max`
- **KOL 热度排序 SQL 修复**：`_sql_func.desc("like_sum")` → `_sql_func.sum(VideoComment.like_count).desc()`
- **视频评论去重**：`_va_run_fetch` 中添加 `seen_rpids` 集合防止重复插入（UNIQUE 约束冲突）
- **视频分析面板动态定位**：从硬编码 `left-2` 改为根据 `kolPanelOpen` 值动态计算

#### 数据流完善 (3 项)

- **JSON→DB 自动同步**：新增 `sync_hot_topics_from_json()`，启动时扫描 `tophub_search/*.json`，支持 flat array 和 `{parsed_items}` 两种格式，按 ID 去重 Upsert 至 `hot_topics` 表
- **历史统计 DB 回补机制**：`_build_stats_from_json()` 新增智能回退——当 JSON 中 `parsed_items` 缺少 `sentiment`/`is_game_related` 字段时，自动从 `hot_topics` 表批量查询已分析数据回填
- **启动同步序列完善**：`main.py` 中 6 步同步管线（init_db → seed → sync_topics → sync_stats → load_hot_cache → load_search_cache）

#### 新增页面

- **VideoAnalysis (`/video-analysis`)**：B站视频舆情挖掘（评论拉取+KOL排名+词云）
- **WordCloud (`/wordcloud`)**：独立词云生成器
- **DeepAnalysis (`/deep-analysis`)**：深度分析话题探索页

#### 测试数据

- 修复前 2026-05-31: gameRelated=2, positive=1, negative=0, neutral=1
- 修复后 2026-05-31: gameRelated=135, positive=53, negative=31, neutral=51
- 其他日期（06-01/02/03）数据验证一致无变化

---

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
