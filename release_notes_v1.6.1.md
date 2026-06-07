## v1.6.1 — 桌面完整打包版 (2026-06-07)

> "从此以后，每个人都是社管，亦或者都不是社管。" — By Chronostasis

v1.6.1 是一次全面的桌面打包修复版本。v1.6 虽然功能完备，但 PyInstaller 打包后的单文件 EXE 存在多项遗漏：前端为旧版构建、SPA 路由无法访问、多个核心依赖未打包、B站评论拉取受限、PDF 报告章节截断、油猴脚本无法导出等。v1.6.1 逐一修复了这些问题，打包后的 EXE 功能完整度与开发模式一致。

---

### 打包系统修复

**前端重新构建。** v1.6 发布时打包的前端 dist 是 6 月 3 日的旧版，缺少 6 月 5 日新增的 4 个侧边栏菜单（舆情推演、聚类分群、舆情辩论厅、辩论回放）。v1.6.1 使用最新源码重新构建前端，14 个页面入口全部可见。

**SPA 路由修复。** `StaticFiles(html=True)` 只能处理目录型路径（如 `/`），对 `/opinion-timeline` 这类 SPA 路径直接返回 404。v1.6.1 改为 `/assets` 独立挂载 + `/{catch_all:path}` catch-all 路由，所有前端路由交由 React Router 处理。

**首次启动种子数据。** 打包版的数据目录在 EXE 旁首次为空。v1.6.1 新增启动逻辑：从 `_MEIPASS` 内嵌资源自动复制 `categories.json`、`hot_crawl.json`、`paper/` 到外部 `data/` 目录。

**分类自动合并。** `_load_categories()` 现在用 `_CATEGORY_DEFAULTS`（14 个分类）逐项检查已有文件，缺失的自动补全。升级旧版本不会丢失用户自定义分类。

**油猴脚本导出。** `comment_script_template.js` 通过 `--add-data` 打入 EXE，`routes.py` 在 frozen 模式下使用 `sys._MEIPASS` 替代不可靠的 `__file__` 路径解析。

**缺失依赖全量打包。** 以下依赖在 v1.6 打包时被遗漏或主动排除：reportlab（PDF 引擎）、matplotlib + numpy（图表）、scipy.ndimage（PDF 高斯模糊）、wordcloud（词云）、duckduckgo_search/ddgs（辩论搜索引擎）、PIL（图片处理）。现在全部通过 `--collect-all` 打包，EXE 大小从 199 MB 增长至 265 MB。

---

### B站视频分析修复

**Cookie 策略优化。** `_get_bilibili_cookie()` 原先要求 `is_valid=True` 才返回 Cookie，用户配了 Cookie 但忘点"验证"按钮则整个 Cookie 策略被跳过。现在有 SESSDATA 即可使用，未验证状态仅记录警告日志。

**DIRECT 模式重试增强。** 无 Cookie 时 -352 错误的重试次数从 5 次增至 12 次，延迟添加 0.5-2.5 秒随机 jitter，上限 45 秒。增加实际拉取成功率。

**明确诊断日志。** 无 Cookie 时打印 "No B站 Cookie configured — go to 账号管理 → 添加B站Cookie"，UAPIS 代理失败时打印具体错误信息，方便排查问题。

---

### PDF 报告修复

**时间轴推演章节截断。** `module_trail()` 把 DeepSeek AI 分析文本塞进单个 ReportLab `Paragraph` flowable，长文本在页面边界被硬截断出现半句话。修复为按 `\n\n` 拆分为多个小 `Paragraph`，每个独立参与页面排版。

---

### 完整修复清单

| # | 问题 | 修复 |
|---|------|------|
| 1 | 前端 dist 为 6/3 旧版，缺 4 个菜单 | 最新源码重新构建 |
| 2 | SPA 路由返回 404 | catch-all 路由替代 StaticFiles |
| 3 | 首次运行 data/ 为空 | 从 _MEIPASS 复制种子文件 |
| 4 | 分类升级不补全 | _load_categories 合并逻辑 |
| 5 | 油猴脚本 500 错误 | JS 模板打包 + frozen 路径 |
| 6 | PDF/词云/辩论功能缺失 | 全量依赖打包（+scipy） |
| 7 | B站评论只拉 6 条 | Cookie 策略 + -352 重试 |
| 8 | PDF 末尾半句话截断 | AI 文本多 Paragraph 拆分 |
| 9 | 分类不全（7 个 vs 14 个） | 分类合并 + 种子复制 |

---

### 技术细节

**PyInstaller 命令新增参数：**
- `--add-data`：前端 dist（最新构建）、snownlp、jieba、app/data、app/paper、app/debate/comment_script_template.js
- `--collect-all`：starlette、PyQt6、curl_cffi、reportlab、matplotlib、numpy、scipy、wordcloud、duckduckgo_search、Pillow
- `--hidden-import`：所有子模块显式声明（uvicorn、httpx、lxml、scipy.ndimage 等）
- `excludes`：移除 matplotlib/numpy/scipy 的黑名单

**修改的文件：**
- `miho-spot-desktop/main.py` — SPA 路由 + 种子数据复制
- `miho-spot/backend/app/api/routes.py` — Cookie 策略 + 分类合并 + 油猴脚本路径
- `miho-spot/backend/app/pdf_report.py` — Paragraph 拆分
- `miho-spot/frontend/dist/` — 重新构建

**桌面版使用：**
1. 双击 `dist/Miho-spot-Backend.exe`（265 MB）
2. 点击"打开前端"按钮或浏览器访问显示的端口
3. 在账号管理页面配置 DeepSeek API Key + B站 Cookie
4. 14 个功能入口全部可用

---

### 已知限制

- EXE 首次启动较慢（解压内嵌资源到临时目录），后续启动正常
- 油猴脚本中的 API_BASE 使用 localhost，如需远程访问需手动修改
- scipy 的子模块 torch 兼容层在打包时产生 warning，不影响运行
- Qt6WebEngineCore.dll 等 3D 组件库在打包时产生 warning，GUI 基本功能不受影响
