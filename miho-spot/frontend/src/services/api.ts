import type { DashboardData, HotTopic, AnalysisResult, DailyStats, KeywordEntry, AccountCredential, Platform, TimeRange, CategoryEntry } from "../types";

const BASE_URL = "/api";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
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
