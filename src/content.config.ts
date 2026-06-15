import { defineCollection, reference, z } from 'astro:content';
import { glob, file } from 'astro/loaders';

// 公信力骨幹(D6):來源分級。三軸固定不變 -> 用嚴格 enum 防拼錯。
const TIER = z.enum(['official', 'reference', 'secondary']);
const ANIMAL = z.enum(['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬']);
const BRANCH = z.enum(['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']);

// 地區碼(ISO 風格)。新增郵政時擴充此清單。
const REGION = z.enum([
  'TW', 'CN', 'HK', 'MO', 'JP', 'KR', 'US', 'VN', 'MN', 'FR', 'IM', 'TH',
  'CA', 'CX', 'NZ', 'SG', 'MY', 'BT', 'PH', 'KP', 'GG', 'JE', 'LI', 'AU', 'GB', 'UN',
]);

// Source — 獨立維護、分級的來源(見 data-model.md)。
const sources = defineCollection({
  loader: file('src/content/sources/sources.json'),
  schema: z.object({
    title: z.string(),
    url: z.string().url(),
    tier: TIER,
    accessed_date: z.string().date(),
  }),
});

// Item — 套內品項(郵票/小全張/小型張)。
const item = z.object({
  type: z.enum(['stamp', 'souvenir_sheet', 'miniature_sheet', 'booklet']),
  denomination: z.object({ value: z.number().nullable(), currency: z.string() }).optional(),
  dimensions_mm: z.object({ w: z.number(), h: z.number() }).nullable().optional(),
  mintage: z.number().nullable().optional(),
  description: z.string().default(''),
  image: z.string().default(''),
  // UPU/WADP WNS official number for this single stamp (id-scheme §5, item-level).
  wns: z.string().optional(),
});

// Issue — 一套發行。zodiac/zodiac_year 用於生肖歸類,issue_date 用於排序/時間軸(D5,永不混用)。
// zodiac/zodiac_year 為 null = 全 12 生肖/主題票(郵展、生肖主題等),不對應單一生肖年。
const catalog = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/catalog' }),
  schema: z.object({
    region: z.object({ code: REGION, name: z.string() }),
    zodiac: z.object({ animal: ANIMAL, branch: BRANCH }).nullable(),
    zodiac_year: z.number().int().nullable(),
    issue_date: z.string().date(),
    round: z.number().int().positive().optional(),
    series_name: z.string().default(''),
    // Multi-catalogue map (id-scheme §5). local/scott kept for existing data;
    // commercial catalogues (SG/Michel/Yvert) + community (Colnect/Stampworld) optional.
    catalog_number: z
      .object({
        local: z.string().nullable(),
        scott: z.string().nullable(),
        sg: z.string().nullable().optional(),
        michel: z.string().nullable().optional(),
        yvert: z.string().nullable().optional(),
        colnect: z.string().nullable().optional(),
        stampworld: z.string().nullable().optional(),
      })
      .optional(),
    designer: z.string().default(''),
    printer: z.string().default(''),
    printing_process: z.string().default(''),
    perforation: z.string().default(''),
    items: z.array(item).min(1),
    significance: z.string().default(''),
    notes: z.string().default(''),
    images: z.array(z.string()).default([]),
    // referential integrity(D6):ref 必須指向存在的 Source,否則 build 失敗。
    // url(選配):指向該套在來源站的專屬頁,覆寫 Source 的共用 url。
    sources: z.array(z.object({ ref: reference('sources'), tier: TIER, url: z.string().url().optional() })).min(1),
    verified: z.boolean(),
    updated_at: z.string().date(),
  }),
});

export const collections = { sources, catalog };
