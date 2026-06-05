import requests, os, json

token = os.environ.get("GITHUB_TOKEN", "")
if not token:
    print("No GITHUB_TOKEN. Please set it and retry.")
    exit(1)

headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
owner, repo = "KaedeCo", "miho-spot"

# Get latest commit SHA
r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/commits/main", headers=headers)
sha = r.json()["sha"]

body = """## v1.4 — 聚类分群 + PDF报告定制 + 全链路体验升级 (2026-06-04)

Miho-spot v1.4 围绕"舆情深度分析→结构化报告输出"的全链路闭环，新增三大核心功能模块与多项体验优化。

---

### 🧩 聚类分群（`/cluster-analysis`）

基于舆情推演的评论坐标数据，通过**加权凝聚聚类算法**自动将评论群体划分为数个有统计意义的子群体，DeepSeek AI 为每个群体生成完整画像。

- 自动过滤占比低于5%的噪声小群
- 每个群体输出：关键词定义、核心主张、三大论据、物质基础
- 蓝色虚线框包围 + 悬停气泡 + 点击详情面板
- 结果持久化至 `cluster_analyses` 表，重启不丢

---

### 📄 PDF报告定制（侧边栏 + 深度分析页）

用户自由勾选**九个分析模块**，生成符合中国本科学位论文格式的结构化PDF报告。

- **九大模块**：事件总览 / 舆论地形图 / 情感阵营分布 / 质心漂移轨迹 / 群体聚类画廊 / 高赞对立面 / 词云争议词 / 用户图谱 / AI综合研判
- **学位论文格式**：A4标准边距 / 三号章标题 / 小四号正文1.5倍行距 / 封面+摘要+目录+参考文献
- **离线优先**：8个模块本地数据渲染，无API消耗
- **渐进式降级**：图片溢出→纯文字模式，单模块失败不影响全局
- **常驻进度条** + 异步job模型 + 浏览器自动下载

---

### 🧵 查成分队列增强

- **评论上限选择**：100/200/500/1000/不限，避免全量拉取触发WAF
- **常驻进度条**：五阶段实时进度（用户信息→拉取→匹配→AI分析→完成）
- **自动持久化**：队列完成后自动写入 `bili_user_profiles`，重启不丢，光谱图立即可见
- **手动停止**：运行中可随时终止，状态复位为"排队中"
- **上限前移**：限制直接作用于拉取函数内部，选100条仅拉1页（8秒）

---

### 🔐 B站Cookie多字段配置

五字段独立输入（SESSDATA必填 / bili_jct推荐 / buvid3推荐 / DedeUserID可选 / DedeUserID__ckMd5可选），含五步图文化获取教程，一键验证返回用户名+等级+大会员状态。

---

### 🔄 跨页任务恢复

切页后回来自动重连运行中的任务。视频分析 / 舆情推演 / PDF报告三管齐下，基于浏览器原生 `sessionStorage`，零后端改动。

---

### 📊 其他改进

- 二维热力图渲染全面升级：轴渐变、网格线、分界线、光晕+三角标记+等高线
- 时间轴节点标记系统：右键创建 + 五角星显示 + 持久化
- 视频分析3D热力图三面网格 + 刻度标注
- 数据库自动迁移机制：`ALTER TABLE ADD COLUMN` 补列不删库
- Markdown→PDF格式转换（AI摘要中粗体/斜体/列表正确渲染）
- 表格单元格自动换行 + 自适应行高
- 争议关键词本地计算（反对vs支持阵营词频差）
- 15个文件，+4664行代码

---

> **v1.3稳定性**已确认无遗留Bug，v1.4新增功能全部通过前端/后端两端测试。
"""

data = {
    "tag_name": "v1.4",
    "target_commitish": "main",
    "name": "v1.4 — 聚类分群 + PDF报告定制 + 全链路体验升级",
    "body": body,
    "draft": False,
    "prerelease": False,
}

r = requests.post(f"https://api.github.com/repos/{owner}/{repo}/releases", headers=headers, json=data)
if r.status_code == 201:
    print(f"✅ Release created: {r.json()['html_url']}")
else:
    print(f"❌ Failed: {r.status_code}")
    print(r.text[:500])
