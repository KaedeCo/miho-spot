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
  // === 米哈游系 ===
  mihoyo_game: "米哈游游戏",
  mihoyo_character: "米哈游角色",
  mihoyo_cv: "米哈游CV",
  // === 竞品 ===
  competitor: "竞品游戏",
  // === 通用 ===
  general: "二游圈通用",
  // === 舆论情感词 ===
  sentiment_neg: "负面情感词",
  sentiment_pos: "正面情感词",
  // === 社区/平台 ===
  platform: "社区/平台术语",
  // === 游戏机制 ===
  game_mechanic: "游戏系统/机制",
  // === 玩家群体 ===
  player_group: "玩家群体/称呼",
  // === 热梗 ===
  meme: "热梗/网络用语",
  // === 行业商业 ===
  industry: "行业/商业术语",
  // === ACG文化 ===
  acg: "二次元/ACG文化",
  // === B站用语 ===
  bili_slang: "B站/视频圈用语",
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

export interface BiliContentItem {
  type: "video" | "article";
  id: string;
  title: string;
  bvid: string;
  url: string;
  time: number;
  time_str: string;
  play: number;
  duration: number;
  cover: string;
}

export interface BiliSpectrum {
  score: number;
  score_x?: number;
  score_y?: number;
  mihoyo_attitude: string;
  active_areas: string;
  personality: string;
  summary: string;
}

export interface BiliProfileSummary {
  uid: number;
  name: string;
  face: string;
  score_x: number;
  score_y: number;
  summary: string;
  saved_at: string;
}

export interface BiliProfileDetail extends BiliProfileSummary {
  mihoyo_attitude: string;
  active_areas: string;
  personality: string;
}

export interface BiliProfileItems {
  ok: boolean;
  uid: number;
  items: any[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
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
  user_content?: BiliContentItem[];
  content_count?: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  spectrum?: BiliSpectrum;
  analyzed_at?: string;
}

// ========== Video Analysis Types ==========

export interface VaTask {
  id: string;
  bvid: string;
  title: string;
  status: "idle" | "fetching" | "fetched" | "analyzing" | "done" | "error";
  totalComments: number;
  matchedCount: number;
  analyzedCount: number;
  centroidX: number;
  centroidY: number;
  centroidXNoOrigin: number;  // centroid excluding (50,50) neutral center points
  centroidYNoOrigin: number;  // centroid excluding (50,50) neutral center points
  errorMsg: string;
  coverUrl: string;
  createdAt: string;
  updatedAt: string;
}

export interface VaHeatmapPoint {
  x: number;       // 0-100: anti↔pro mihoyo
  y: number;       // 0-100: rational↔emotional
  z: number;       // height = frequency count at this coordinate
  samples: string[]; // up to 3 sample comment contents
}

export interface VaResult {
  task: VaTask;
  points: VaHeatmapPoint[];
  totalPoints: number;
  totalAnalyzedComments: number;
}

export interface VaStatus {
  task_id: string | null;
  status: string;
  progress: string;
}

// ========== Saved Video Analysis Task Types ==========

export interface SavedVaTask {
  id: number;
  sourceTaskId: string;
  bvid: string;
  title: string;
  coverUrl: string;
  totalComments: number;
  matchedCount: number;
  analyzedCount: number;
  centroidX: number;
  centroidY: number;
  centroidXNoOrigin: number;
  centroidYNoOrigin: number;
  savedAt: string;
}

// ========== Word Cloud Types ==========

export interface WordCloudWord {
  text: string;
  count: number;
  weight: number; // for rendering font size
}

export interface WordCloudItem {
  id: number;
  savedVaTaskId: number;
  taskTitle: string;
  taskBvid: string;
  totalWords: number;
  words: WordCloudWord[];
  generatedAt: string;
}

// ========== Deep Analysis Types ==========

export interface DeepAnalysisItem {
  id: number;
  savedVaTaskId: number;
  taskTitle: string;
  status: "pending" | "running" | "done" | "error";
  overallTrend: string;
  kolViewpoints: string;
  oppositionAnalysis: string;
  errorMsg: string;
  createdAt: string;
  completedAt: string | null;
}

// ========== KOL User Types ==========

export interface KolUser {
  uid: number;
  name: string;
  face: string;
  likeSum: number;
  commentCount: number;
}

// ========== Identity Queue Types ==========

export interface IdentityQueueItem {
  id: number;
  uid: number;
  name: string;
  face: string;
  source: "manual" | "video_analysis_kol";
  sortOrder: number;
  status: "pending" | "running" | "done" | "error";
  addedAt: string;
}
