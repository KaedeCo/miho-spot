import type { DashboardData, HotTopic, AnalysisResult, DailyStats, KeywordEntry, AccountCredential, Platform, TimeRange, CategoryEntry, BiliUserInfo, BiliAnalyzeStatus, BiliAnalyzeResult, BiliProfileSummary, BiliProfileDetail, BiliProfileItems } from "../types";

const BASE_URL = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const fullUrl = `${BASE_URL}${url}`;
  console.log(`[API] ${options?.method || "GET"} ${fullUrl}`);
  const res = await fetch(fullUrl, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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

export async function triggerBiliAnalyze(uid: number, maxVideos: number = 50, maxComments: number = 500, monthsLimit: number = 6): Promise<{ ok: boolean; message?: string; uid?: number; error?: string }> {
  return fetchJSON("/bilibili/analyze", {
    method: "POST",
    body: JSON.stringify({ uid, max_videos: maxVideos, max_comments_per_video: maxComments, months_limit: monthsLimit }),
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
