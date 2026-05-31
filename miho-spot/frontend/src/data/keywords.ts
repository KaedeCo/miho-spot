import type { KeywordEntry } from "../types";

export const DEFAULT_KEYWORDS: Omit<KeywordEntry, "id" | "addedAt" | "addedBy">[] = [
  // 米哈游本体
  { keyword: "米哈游", category: "mihoyo_game" },
  { keyword: "miHoYo", category: "mihoyo_game" },
  { keyword: "米忽悠", category: "mihoyo_game" },
  { keyword: "mhy", category: "mihoyo_game" },

  // 米哈游游戏
  { keyword: "原神", category: "mihoyo_game" },
  { keyword: "Genshin Impact", category: "mihoyo_game" },
  { keyword: "崩坏：星穹铁道", category: "mihoyo_game" },
  { keyword: "星穹铁道", category: "mihoyo_game" },
  { keyword: "崩坏3", category: "mihoyo_game" },
  { keyword: "崩坏三", category: "mihoyo_game" },
  { keyword: "绝区零", category: "mihoyo_game" },
  { keyword: "Zenless Zone Zero", category: "mihoyo_game" },
  { keyword: "未定事件簿", category: "mihoyo_game" },

  // 米哈游角色 - 原神
  { keyword: "钟离", category: "mihoyo_character" },
  { keyword: "胡桃", category: "mihoyo_character" },
  { keyword: "雷电将军", category: "mihoyo_character" },
  { keyword: "纳西妲", category: "mihoyo_character" },
  { keyword: "芙宁娜", category: "mihoyo_character" },
  { keyword: "那维莱特", category: "mihoyo_character" },
  { keyword: "散兵", category: "mihoyo_character" },
  { keyword: "万叶", category: "mihoyo_character" },
  { keyword: "可莉", category: "mihoyo_character" },
  { keyword: "达达利亚", category: "mihoyo_character" },
  { keyword: "派蒙", category: "mihoyo_character" },

  // 米哈游角色 - 星穹铁道
  { keyword: "三月七", category: "mihoyo_character" },
  { keyword: "丹恒", category: "mihoyo_character" },
  { keyword: "景元", category: "mihoyo_character" },
  { keyword: "卡芙卡", category: "mihoyo_character" },
  { keyword: "银狼", category: "mihoyo_character" },
  { keyword: "刃", category: "mihoyo_character" },
  { keyword: "流萤", category: "mihoyo_character" },
  { keyword: "知更鸟", category: "mihoyo_character" },

  // 米哈游角色 - 崩坏3
  { keyword: "琪亚娜", category: "mihoyo_character" },
  { keyword: "布洛妮娅", category: "mihoyo_character" },
  { keyword: "芽衣", category: "mihoyo_character" },
  { keyword: "八重樱", category: "mihoyo_character" },
  { keyword: "爱莉希雅", category: "mihoyo_character" },

  // 米哈游CV
  { keyword: "kinsen", category: "mihoyo_cv" },
  { keyword: "花玲", category: "mihoyo_cv" },
  { keyword: "林簌", category: "mihoyo_cv" },
  { keyword: "多多poi", category: "mihoyo_cv" },
  { keyword: "陶典", category: "mihoyo_cv" },
  { keyword: "Mace", category: "mihoyo_cv" },
  { keyword: "菊花花", category: "mihoyo_cv" },
  { keyword: "彭博", category: "mihoyo_cv" },
  { keyword: "赵路", category: "mihoyo_cv" },

  // 竞品游戏
  { keyword: "明日方舟", category: "competitor" },
  { keyword: "Arknights", category: "competitor" },
  { keyword: "鸣潮", category: "competitor" },
  { keyword: "Wuthering Waves", category: "competitor" },
  { keyword: "无限暖暖", category: "competitor" },
  { keyword: "幻塔", category: "competitor" },
  { keyword: "少女前线2", category: "competitor" },
  { keyword: "重返未来1999", category: "competitor" },
  { keyword: "蔚蓝档案", category: "competitor" },
  { keyword: "碧蓝航线", category: "competitor" },
  { keyword: "无期迷途", category: "competitor" },
  { keyword: "明日方舟终末地", category: "competitor" },

  // 二游圈通用
  { keyword: "二游", category: "general" },
  { keyword: "二次元手游", category: "general" },
  { keyword: "gacha", category: "general" },
  { keyword: "抽卡", category: "general" },
  { keyword: "648", category: "general" },
  { keyword: "保底", category: "general" },
  { keyword: "策划", category: "general" },
  { keyword: "版本更新", category: "general" },
  { keyword: "前瞻直播", category: "general" },
  { keyword: "角色PV", category: "general" },
  { keyword: "流水", category: "general" },
  { keyword: "卡池", category: "general" },
  { keyword: "命座", category: "general" },
  { keyword: "专武", category: "general" },
  { keyword: "数值膨胀", category: "general" },
];

export function getKeywordCategory(keyword: string): string {
  const found = DEFAULT_KEYWORDS.find((k) => k.keyword === keyword);
  return found?.category ?? "general";
}
