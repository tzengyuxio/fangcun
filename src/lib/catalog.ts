// 十二生肖(固定順序)與對應地支。
export const ANIMALS = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬'] as const;

export const ANIMAL_BRANCH: Record<string, string> = {
  鼠: '子', 牛: '丑', 虎: '寅', 兔: '卯', 龍: '辰', 蛇: '巳',
  馬: '午', 羊: '未', 猴: '申', 雞: '酉', 狗: '戌', 豬: '亥',
};

// 來源分級顯示名(對齊 data-model / spec D6)。
export const TIER_LABEL: Record<string, string> = {
  official: '官方一手',
  reference: '權威目錄',
  secondary: '二手',
};

export function year(isoDate: string): string {
  return isoDate.slice(0, 4);
}

// issue_date 用於排序/時間軸(D5):升冪比較。
export function byIssueDate(a: { data: { issue_date: string } }, b: { data: { issue_date: string } }): number {
  return a.data.issue_date < b.data.issue_date ? -1 : a.data.issue_date > b.data.issue_date ? 1 : 0;
}
