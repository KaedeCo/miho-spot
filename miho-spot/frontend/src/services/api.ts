import type { DashboardData, HotTopic, AnalysisResult, DailyStats, KeywordEntry, AccountCredential, Platform, TimeRange, CategoryEntry, BiliUserInfo, BiliAnalyzeStatus, BiliAnalyzeResult, BiliProfileSummary, BiliProfileDetail, BiliProfileItems, SavedVaTask, WordCloudItem, DeepAnalysisItem, KolUser, IdentityQueueItem, OtTask, OtStatus, OtResult, SavedOtTask } from "../types";

const BASE_URL = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit, timeoutMs: number = 120000): Promise<T> {
  const fullUrl = `${BASE_URL}${url}`;
  console.log(`[API] ${options?.method || "GET"} ${fullUrl}`);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(fullUrl, {
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    ...options,
  }).finally(() => clearTimeout(timer));
  if (!res.ok) {
    const text = await res.text().catch(() => "(empty)");
    console.error(`[API] ${res.status} ${fullUrl}: ${text.slice(0, 300)}`);
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  const text = await res.text();
  if (!text || text.trim().length === 0) {
    console.error(`[API] Empty response from ${fullUrl}`);
    throw new Error(`Empty response from server (${fullUrl}) - check backend is running`);
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    console.error(`[API] Invalid JSON from ${fullUrl}:`, text.slice(0, 500));
    throw new Error(`Invalid JSON response (${text.slice(0, 80)})`);
  }
}

export async function getDashboardData(): Promise<DashboardData> {
  return fetchJSON<DashboardData>("/dashboard");
}

export async function getHotTopics(platform?: Platform, source?: string): Promise<HotTopic[]> {
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (source) params.set("source", source);
  return fetchJSON<HotTopic[]>(`/topics?${params}`);
}

export async function triggerHotCrawl(): Promise<{ message: string }> {
  return fetchJSON("/crawl/hot", { method: "POST" });
}

export async function triggerSearchCrawl(keywords?: string[]): Promise<{ message: string }> {
  return fetchJSON("/crawl/search", {
    method: "POST",
    body: JSON.stringify(keywords || []),
  });
}

export async function getCrawlStatus(): Promise<any> {
  return fetchJSON("/crawl/status");
}

export async function getSearchKeywords(): Promise<{ keywords: string[] }> {
  return fetchJSON("/search/keywords");
}

export async function setSearchKeywords(keywords: string[]): Promise<{ keywords: string[] }> {
  return fetchJSON("/search/keywords", {
    method: "POST",
    body: JSON.stringify({ keywords }),
  });
}

export async function getTopicAnalysis(topicId: string): Promise<AnalysisResult> {
  return fetchJSON<AnalysisResult>(`/analysis/${topicId}`);
}

export async function getDailyStats(range: TimeRange, startDate?: string, endDate?: string): Promise<DailyStats[]> {
  const params = new URLSearchParams({ range });
  if (range === "custom" && startDate && endDate) {
    params.set("start", startDate);
    params.set("end", endDate);
  }
  return fetchJSON<DailyStats[]>(`/stats/daily?${params}`);
}

export async function getKeywords(): Promise<KeywordEntry[]> {
  return fetchJSON<KeywordEntry[]>("/keywords");
}

export async function addKeyword(keyword: Omit<KeywordEntry, "id" | "addedAt">): Promise<KeywordEntry> {
  return fetchJSON<KeywordEntry>("/keywords", { method: "POST", body: JSON.stringify(keyword) });
}

export async function updateKeyword(id: string, data: { keyword?: string; category?: string }): Promise<KeywordEntry> {
  return fetchJSON<KeywordEntry>(`/keywords/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteKeyword(id: string): Promise<void> {
  return fetchJSON(`/keywords/${id}`, { method: "DELETE" });
}

export async function exportKeywords(): Promise<Response> {
  return fetch("/api/keywords/export");
}

export async function importKeywords(data: { keywords: { keyword: string; category: string }[]; mode: string }): Promise<{ ok: boolean; added: number; skipped: number; total: number; message: string }> {
  return fetchJSON("/keywords/import", { method: "POST", body: JSON.stringify(data) });
}

export async function resetKeywords(): Promise<{ ok: boolean; total: number; message: string }> {
  return fetchJSON("/keywords/reset", { method: "POST" });
}

// Category management
export async function getCategories(): Promise<CategoryEntry> {
  return fetchJSON<CategoryEntry>("/categories");
}

export async function addCategory(data: { key: string; name: string }): Promise<CategoryEntry> {
  return fetchJSON<CategoryEntry>("/categories", { method: "POST", body: JSON.stringify(data) });
}

export async function updateCategory(catKey: string, data: { key?: string; name: string }): Promise<CategoryEntry> {
  return fetchJSON<CategoryEntry>(`/categories/${catKey}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteCategory(catKey: string): Promise<CategoryEntry> {
  return fetchJSON<CategoryEntry>(`/categories/${catKey}`, { method: "DELETE" });
}

// Tophub search files
export async function getSearchFiles(): Promise<{ files: { filename: string; size_kb: number; created: string }[]; data_dir: string; total: number }> {
  return fetchJSON("/tophub/search/files");
}

export async function getLatestSearch(): Promise<{ hasData: boolean; data?: any; message?: string }> {
  return fetchJSON("/tophub/search/latest");
}

export async function checkTodaySearch(): Promise<{ exists: boolean; today: string; message: string }> {
  return fetchJSON("/tophub/search/today");
}

// DeepSeek API
export async function verifyDeepSeek(apiKey: string): Promise<{ isValid: boolean; message: string }> {
  return fetchJSON("/deepseek/verify", { method: "POST", body: JSON.stringify({ apiKey }) });
}

export async function getDeepSeekStatus(): Promise<{ configured: boolean; isValid: boolean; message?: string }> {
  return fetchJSON("/deepseek/status");
}

export async function getDeepSeekAnalyzeStatus(): Promise<{ analyzed: boolean; today: string; deepseekConfigured: boolean; totalTopics: number; gameRelated: number; pendingAnalysis: number }> {
  return fetchJSON("/deepseek/analyze-status");
}

export async function deepSeekAnalyzeAll(): Promise<{ ok: boolean; message: string; totalTopics?: number; gameRelated?: number }> {
  return fetchJSON("/deepseek/analyze-all", { method: "POST" });
}

export async function getAccounts(): Promise<AccountCredential[]> {
  return fetchJSON<AccountCredential[]>("/accounts");
}

export async function saveAccount(account: AccountCredential): Promise<AccountCredential> {
  return fetchJSON<AccountCredential>("/accounts", { method: "POST", body: JSON.stringify(account) });
}

export async function verifyAccount(platform: Platform, cookie?: string): Promise<{ isValid: boolean; message?: string }> {
  return fetchJSON(`/accounts/${platform}/verify`, { method: "POST", body: JSON.stringify({ cookie: cookie || "" }) });
}

// ========== Bilibili "查成分" API ==========

export async function getBiliUserInfo(uid: number): Promise<{ ok: boolean; data?: BiliUserInfo; error?: string }> {
  return fetchJSON(`/bilibili/user/info?uid=${uid}`);
}

export async function getBiliAnalyzeStatus(uid: number): Promise<BiliAnalyzeStatus> {
  return fetchJSON(`/bilibili/analyze/status?uid=${uid}`);
}

export async function getBiliAnalyzeResult(uid: number, page: number = 1, pageSize: number = 100): Promise<BiliAnalyzeResult> {
  return fetchJSON(`/bilibili/analyze/result?uid=${uid}&page=${page}&page_size=${pageSize}`);
}

export async function triggerBiliAnalyze(uid: number, maxVideos: number = 50, maxComments: number = 500, monthsLimit: number = 6, maxTotal?: number): Promise<{ ok: boolean; message?: string; uid?: number; error?: string }> {
  return fetchJSON("/bilibili/analyze", {
    method: "POST",
    body: JSON.stringify({ uid, max_videos: maxVideos, max_comments_per_video: maxComments, months_limit: monthsLimit, max_total: maxTotal || null }),
  });
}

// Bilibili save & profiles
export async function saveBiliProfile(uid: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON("/bilibili/save", { method: "POST", body: JSON.stringify({ uid }) });
}

export async function getBiliProfiles(): Promise<{ ok: boolean; profiles: BiliProfileSummary[] }> {
  return fetchJSON("/bilibili/profiles");
}

export async function getBiliProfile(uid: number, tab: string = "comments", page: number = 1): Promise<BiliProfileDetail & BiliProfileItems> {
  return fetchJSON(`/bilibili/profile/${uid}?tab=${tab}&page=${page}`);
}

export async function deleteBiliProfile(uid: number): Promise<{ ok: boolean }> {
  return fetchJSON(`/bilibili/profile/${uid}`, { method: "DELETE" });
}

export async function exportBiliProfiles(): Promise<Response> {
  return fetch("/api/bilibili/export");
}

export async function importBiliProfiles(profiles: any[]): Promise<{ ok: boolean; imported: number; updated: number; total: number; message: string }> {
  return fetchJSON("/bilibili/import", { method: "POST", body: JSON.stringify({ profiles, mode: "merge" }) });
}

// ========== Video Analysis API ==========

export async function getVaTasks(): Promise<VaTask[]> {
  return fetchJSON<VaTask[]>("/video-analysis/tasks");
}

export async function vaFetchComments(url: string): Promise<{ ok: boolean; taskId?: string; bvid?: string; title?: string; message: string }> {
  return fetchJSON("/video-analysis/fetch", { method: "POST", body: JSON.stringify({ url }) });
}

export async function getVaStatus(): Promise<VaStatus> {
  return fetchJSON<VaStatus>("/video-analysis/status");
}

export async function vaAnalyze(taskId?: string): Promise<{ ok: boolean; taskId?: string; pendingCount?: number; message: string }> {
  return fetchJSON("/video-analysis/analyze", { method: "POST", body: JSON.stringify({ taskId: taskId || "" }) });
}

export async function getVaResult(taskId: string): Promise<VaResult> {
  return fetchJSON<VaResult>(`/video-analysis/result/${taskId}`);
}

export async function deleteVaTask(taskId: string): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/video-analysis/task/${taskId}`, { method: "DELETE" });
}

// ========== Saved Video Analysis Tasks ==========

export async function saveVaTask(taskId: string): Promise<{ ok: boolean; id?: number; message: string }> {
  return fetchJSON("/video-analysis/saved", { method: "POST", body: JSON.stringify({ taskId }) });
}

export async function getSavedVaTasks(): Promise<{ items: SavedVaTask[]; total: number }> {
  return fetchJSON("/video-analysis/saved");
}

export async function deleteSavedVaTask(savedId: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/video-analysis/saved/${savedId}`, { method: "DELETE" });
}

// ========== Word Cloud ==========

export async function generateWordCloud(savedTaskId: number): Promise<{ ok: boolean; id?: number; wordCount?: number; words?: any[]; message: string }> {
  return fetchJSON("/word-cloud/generate", { method: "POST", body: JSON.stringify({ savedTaskId }) });
}

export async function getWordClouds(): Promise<{ items: WordCloudItem[]; total: number }> {
  return fetchJSON("/word-cloud/list");
}

export async function deleteWordCloud(wcId: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/word-cloud/${wcId}`, { method: "DELETE" });
}

// ========== Deep Analysis ==========

export async function startDeepAnalysis(savedTaskId: number): Promise<{ ok: boolean; analysisId?: number; message: string }> {
  return fetchJSON("/deep-analysis/start", { method: "POST", body: JSON.stringify({ savedTaskId }) });
}

export async function getDeepAnalysisStatus(): Promise<{ status: string; progress: string; analysis_id: number | null }> {
  return fetchJSON("/deep-analysis/status");
}

export async function getDeepAnalyses(): Promise<{ items: DeepAnalysisItem[]; total: number }> {
  return fetchJSON("/deep-analysis/list");
}

export async function getDeepAnalysisResult(analysisId: number): Promise<DeepAnalysisItem & { rawResponse?: string }> {
  return fetchJSON(`/deep-analysis/result/${analysisId}`);
}

export async function deleteDeepAnalysis(analysisId: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/deep-analysis/${analysisId}`, { method: "DELETE" });
}

// ========== KOL Top Users ==========

export async function getKolTopUsers(taskId: string, sort: "hot" | "time" = "hot"): Promise<{ users: KolUser[]; sort: string; taskId: string; error?: string }> {
  return fetchJSON(`/video-analysis/kol-top?task_id=${taskId}&sort=${sort}`);
}

// ========== Identity Queue ==========

export async function getIdentityQueue(): Promise<{ items: IdentityQueueItem[]; total: number }> {
  return fetchJSON("/identity-queue");
}

export async function addToIdentityQueue(uid: number, name?: string, face?: string, source?: string): Promise<{ ok: boolean; id?: number; message: string }> {
  return fetchJSON("/identity-queue", { method: "POST", body: JSON.stringify({ uid, name: name || "", face: face || "", source: source || "manual" }) });
}

export async function removeFromIdentityQueue(qId: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/identity-queue/${qId}`, { method: "DELETE" });
}

export async function reorderIdentityQueue(orderedIds: number[]): Promise<{ ok: boolean; message: string }> {
  return fetchJSON("/identity-queue/reorder", { method: "PUT", body: JSON.stringify({ orderedIds }) });
}

// ========== Opinion Timeline API (舆情推演) ==========

export async function otFetch(url: string): Promise<{ ok: boolean; taskId?: string; bvid?: string; message: string }> {
  return fetchJSON("/opinion-timeline/fetch", { method: "POST", body: JSON.stringify({ url }) });
}

export async function otStatus(): Promise<OtStatus> {
  return fetchJSON<OtStatus>("/opinion-timeline/status");
}

export async function otAnalyze(taskId: string): Promise<{ ok: boolean; taskId?: string; message: string }> {
  return fetchJSON("/opinion-timeline/analyze", { method: "POST", body: JSON.stringify({ taskId }) });
}

export async function otResult(taskId: string): Promise<OtResult> {
  return fetchJSON<OtResult>(`/opinion-timeline/result/${taskId}`);
}

export async function otListTasks(): Promise<{ items: OtTask[]; total: number }> {
  return fetchJSON("/opinion-timeline/tasks");
}

export async function otDeleteTask(taskId: string): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/opinion-timeline/task/${taskId}`, { method: "DELETE" });
}

export async function otSave(taskId: string, nodeIndices?: number[]): Promise<{ ok: boolean; id?: number; message: string }> {
  return fetchJSON("/opinion-timeline/saved", { method: "POST", body: JSON.stringify({ taskId, nodeIndices }) });
}

export async function otListSaved(): Promise<{ items: SavedOtTask[]; total: number }> {
  return fetchJSON("/opinion-timeline/saved");
}

export async function otGetSaved(savedId: number): Promise<OtResult> {
  return fetchJSON<OtResult>(`/opinion-timeline/saved/${savedId}`);
}

export async function otDeleteSaved(savedId: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/opinion-timeline/saved/${savedId}`, { method: "DELETE" });
}

export async function otSaveNodes(savedId: number, nodeIndices: number[]): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/opinion-timeline/saved/${savedId}/nodes`, { method: "POST", body: JSON.stringify({ nodeIndices }) });
}

// ========== Cluster Analysis API ==========
import type { ClusterResult } from "../types";

export async function clusterAnalyze(savedId: number): Promise<{ ok: boolean; id?: number; clusterCount: number; clusters: any[] }> {
  return fetchJSON("/cluster/analyze", { method: "POST", body: JSON.stringify({ savedId }) });
}

export async function clusterGet(id: number): Promise<ClusterResult> {
  return fetchJSON(`/cluster/result/${id}`);
}

export async function clusterBySaved(savedId: number): Promise<ClusterResult> {
  return fetchJSON(`/cluster/by-saved/${savedId}`);
}

export async function clusterList(): Promise<{ items: any[]; total: number }> {
  return fetchJSON("/cluster/list");
}

export async function clusterDelete(id: number): Promise<{ ok: boolean; message: string }> {
  return fetchJSON(`/cluster/${id}`, { method: "DELETE" });
}

// ========== PDF Report API ==========

export interface PdfModule {
  key: string;
  label: string;
  description: string;
}

export async function getPdfModules(): Promise<{ modules: PdfModule[] }> {
  return fetchJSON("/pdf-report/modules");
}

export interface PdfJobProgress {
  status: string;
  step: number;
  total: number;
  message: string;
  error?: string;
}

export async function generatePdfReport(savedId: number, modules: string[]): Promise<{ jobId: string }> {
  return fetchJSON("/pdf-report/generate", {
    method: "POST",
    body: JSON.stringify({ savedId, modules }),
  });
}

export async function getPdfProgress(jobId: string): Promise<PdfJobProgress> {
  return fetchJSON(`/pdf-report/progress/${jobId}`);
}

export async function downloadPdfReport(jobId: string): Promise<void> {
  const resp = await fetch(`/api/pdf-report/download/${jobId}`);
  if (!resp.ok) throw new Error("下载失败");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `miho_spot_report_${jobId.slice(0, 8)}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ======================================================================
//  Search API Keys (Volcano + Tavily)
// ======================================================================

export async function verifyVolcano(apiKey: string, endpointId: string) {
  const resp = await fetch('/api/search/verify-volcano', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiKey, endpointId }),
  });
  return resp.json();
}

export async function verifyTavily(apiKey: string) {
  const resp = await fetch('/api/search/verify-tavily', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiKey }),
  });
  return resp.json();
}

export async function getSearchStatus() {
  const resp = await fetch('/api/search/status');
  return resp.json();
}

export async function testVolcanoSearch() {
  const resp = await fetch('/api/search/test-volcano', { method: 'POST' });
  return resp.json();
}

export async function testTavilySearch() {
  const resp = await fetch('/api/search/test-tavily', { method: 'POST' });
  return resp.json();
}

// ======================================================================
//  Agent Swiss Tournament Debate API
// ======================================================================

export const debateApi = {
  create: async (topic: string) => {
    const resp = await fetch('/api/debate/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    });
    if (!resp.ok) throw new Error('创建辩论失败');
    return resp.json();
  },

  confirmFacts: async (sessionId: string, actions: any[]) => {
    const resp = await fetch(`/api/debate/confirm-facts/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actions }),
    });
    if (!resp.ok) throw new Error('事实确认失败');
    return resp.json();
  },

  save: async (sessionId: string) => {
    const resp = await fetch(`/api/debate/save/${sessionId}`, { method: 'POST' });
    if (!resp.ok) throw new Error('保存失败');
    return resp.json();
  },

  getReport: async (sessionId: string) => {
    const resp = await fetch(`/api/debate/report/${sessionId}`);
    if (!resp.ok) throw new Error('获取报告失败');
    return resp.json();
  },

  listSessions: async () => {
    const resp = await fetch('/api/debate/sessions');
    if (!resp.ok) throw new Error('获取会话列表失败');
    return resp.json();
  },

  deleteSession: async (sessionId: string) => {
    const resp = await fetch(`/api/debate/session/${sessionId}`, { method: 'DELETE' });
    if (!resp.ok) throw new Error('删除失败');
    return resp.json();
  },
};
