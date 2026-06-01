// Sentiment types
export type Sentiment = "Positive" | "Negative" | "Neutral" | "Irrelevant";

export type Platform = "zhihu" | "douyin" | "tieba" | "tophub" | "bilibili" | "weibo" | string;

export type ChartType = "pie" | "bar";

export type TimeRange = "7d" | "30d" | "custom";

// Hot topic from platform heat list
export interface HotTopic {
  id: string;
  platform: Platform;
  title: string;
  rank: number;
  heat: number;
  url: string;
  fetchedAt: string;
  sentiment: Sentiment;
  relatedGame?: string;
  isGameRelated: boolean;
  source?: string;
}

// Individual post/video under a hot topic
export interface PostItem {
  id: string;
  topicId: string;
  platform: Platform;
  content: string;
  author: string;
  likes: number;
  comments: number;
  timestamp: string;
  sentiment: Sentiment;
  url: string;
}

// Daily statistics
export interface DailyStats {
  date: string;
  totalTopics: number;
  gameRelated: number;
  positive: number;
  negative: number;
  neutral: number;
  irrelevant: number;
  byPlatform: Record<string, PlatformStats>;
}

export interface PlatformStats {
  total: number;
  positive: number;
  negative: number;
  neutral: number;
  irrelevant: number;
}

// Keyword dictionary entry
export interface KeywordEntry {
  id: string;
  keyword: string;
  category: "mihoyo_game" | "mihoyo_character" | "mihoyo_cv" | "competitor" | "general";
  addedAt: string;
  addedBy: "system" | "user";
}

// Keyword categories (defaults, can be overridden by backend)
export const KEYWORD_CATEGORIES = {
  mihoyo_game: "米哈游游戏",
  mihoyo_character: "米哈游角色",
  mihoyo_cv: "米哈游CV",
  competitor: "竞品游戏",
  general: "二游圈通用",
} as const;

export interface CategoryEntry {
  categories: Record<string, { name: string; order: number }>;
}

// User account credential
export interface AccountCredential {
  platform: Platform;
  username: string;
  cookie: string;
  isValid: boolean;
  lastVerified: string;
}

// API Responses
export interface DashboardData {
  summary: {
    totalTopics: number;
    gameRelated: number;
    positive: number;
    negative: number;
    neutral: number;
    irrelevant: number;
  };
  topics: HotTopic[];
  hotTopics: HotTopic[];
  searchTopics: HotTopic[];
  dailyStats: DailyStats[];
}

export interface AnalysisResult {
  topicId: string;
  topic: HotTopic;
  posts: PostItem[];
  postSentimentDistribution: {
    positive: number;
    negative: number;
    neutral: number;
  };
}

// ========== Bilibili "查成分" Types ==========

export interface BiliUserInfo {
  uid: number;
  name: string;
  face: string;
  sign: string;
  level: number;
  sex: string;
  home_url: string;
}

export interface BiliComment {
  rpid: number;
  content: string;
  ctime: number;
  time_str: string;
  video_title: string;
  video_bvid: string;
  video_aid: number;
  video_url: string;
  comment_url: string;
  likes: number;
  reply_count: number;
  matched_keywords?: string[];
  matched_categories?: string[];
}

export interface BiliSpectrum {
  score: number;
  mihoyo_attitude: string;
  active_areas: string;
  personality: string;
  summary: string;
}

export interface BiliAnalyzeStatus {
  exists: boolean;
  status?: string;
  uid: number;
  total_comments?: number;
  matched_count?: number;
  score?: number;
  analyzed_at?: string;
}

export interface BiliAnalyzeResult {
  ok: boolean;
  error?: string;
  status?: string;
  uid?: number;
  user_info?: BiliUserInfo;
  total_comments?: number;
  matched_count?: number;
  comments?: BiliComment[];
  page?: number;
  page_size?: number;
  total_pages?: number;
  spectrum?: BiliSpectrum;
  analyzed_at?: string;
}
