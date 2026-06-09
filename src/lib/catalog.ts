// 十二生肖(固定順序)與對應地支。
export const ANIMALS = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬'] as const;

// 生肖軸的「非單一生肖」分類:全 12 生肖/主題票(郵展、生肖主題等),不對應單一生肖年。
// THEME_KEY 同時當作 /catalog/zodiac/<key>/ 的路由參數。
export const THEME_KEY = '其他';
export const THEME_LABEL = '全12生肖';
export const THEME_SHORT = '主題'; // 卡片等窄欄位用的短標

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

// 取一筆 Issue 的代表圖:優先第一個有圖的品項,其次套圖。
export function primaryImage(d: { items?: { image?: string }[]; images?: string[] }): string | null {
  return d.items?.find((it) => it.image)?.image || d.images?.[0] || null;
}

// 把資料中的圖路徑轉成可用 src:遠端 URL 原樣,站內絕對路徑補上 base。
export function imgSrc(image: string | null | undefined, base: string): string | null {
  if (!image) return null;
  return /^https?:/.test(image) ? image : `${base}${image}`;
}

// 圖片載入失敗(如部署站無真圖)時的 fallback 圖。
export function fallbackSrc(base: string): string {
  return `${base}/img/stamp-fallback.svg`;
}
