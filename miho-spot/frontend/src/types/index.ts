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
