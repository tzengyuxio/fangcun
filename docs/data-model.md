# 資料模型 — Issue / Item / Source（Schema v0.1）

本站的單一資料來源。核心實體為「一套發行」（**Issue**），底下掛多個「品項」
（**Item**，含郵票、小全張等）。來源（**Source**）獨立維護並分級。

> 規格層級見 spec D4 / D6。資料見 `../src/content/catalog/`、`../src/content/sources/`。

## Issue — 一套發行

一筆 Issue = 某郵政、某生肖年的一套發行。

```jsonc
{
  "id": "tw-1968-rooster-r1",        // slug：地區-發行年-生肖-輪次
  "region": { "code": "TW", "name": "中華郵政" },
  "zodiac": { "animal": "雞", "branch": "酉" },
  "zodiac_year": 1969,               // ⚠ 生肖年（酉雞年實際所屬）
  "issue_date": "1968-11-12",        // ⚠ 實際發行日（可能早生肖年一年）
  "round": 1,                        // 該地區第幾輪
  "series_name": "新年郵票",
  "catalog_number": { "local": "特55", "scott": null },
  "designer": "",
  "printer": "",
  "printing_process": "",            // 影寫版／平版…
  "perforation": "",                 // 齒孔
  "items": [ /* Item，見下 */ ],
  "significance": "世界第一套雞年生肖郵票",   // 專題/亮點，可空
  "notes": "",                       // 設計理念、背景
  "images": ["/img/tw-1968-rooster-set.jpg"],
  "sources": [
    { "ref": "post-stamphouse", "tier": "official" }
  ],
  "verified": true,                  // 是否經查證
  "updated_at": "2026-06-07"
}
```

### 欄位說明與不變量

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `id` | string | ✓ | slug，格式 `{region}-{issue_year}-{animal}-r{round}`，全站唯一 |
| `region.code` | enum | ✓ | `TW`/`CN`/`HK`/`MO`/`JP`/`US`…（ISO 風格地區碼） |
| `region.name` | string | ✓ | 發行郵政全名 |
| `zodiac.animal` | enum | ✓ | 鼠牛虎兔龍蛇馬羊猴雞狗豬（12 擇一） |
| `zodiac.branch` | enum | ✓ | 子丑寅卯辰巳午未申酉戌亥（12 擇一） |
| `zodiac_year` | int | ✓ | **生肖年**，用於生肖歸類（見 D5） |
| `issue_date` | date | ✓ | **實際發行日**（ISO `YYYY-MM-DD`），用於排序／時間軸（見 D5） |
| `round` | int | ✓ | 該地區第幾輪十二生肖 |
| `series_name` | string |  | 系列名（如「新年郵票」） |
| `catalog_number.local` | string\|null |  | 在地目錄編號（如「特55」） |
| `catalog_number.scott` | string\|null |  | Scott 編號 |
| `designer`/`printer`/`printing_process`/`perforation` | string |  | 製作資訊，可留空待補 |
| `items` | Item[] | ✓ | 至少一個品項 |
| `significance` | string |  | 亮點／專題用一句話 |
| `notes` | string |  | 設計理念、背景 |
| `images` | string[] |  | 整套圖（路徑或檔名） |
| `sources` | {ref,tier}[] | ✓ | 至少一個來源，`ref` 須存在於 sources |
| `verified` | bool | ✓ | 是否經查證 |
| `updated_at` | date | ✓ | 最後更新日 |

**關鍵不變量（D5）**：`zodiac_year` 與 `issue_date` 永不混用。賀歲票於生肖年前一年
底發行，兩者常差一年（如 tw-1968-rooster：發行 1968-11、生肖年 1969）。

## Item — 品項

```jsonc
{
  "type": "stamp",                   // stamp | souvenir_sheet（小全張）| miniature_sheet（小型張）
  "denomination": { "value": 1, "currency": "TWD" },
  "dimensions_mm": { "w": 26, "h": 30 },
  "mintage": 500000,                 // 發行量（可在套層級或品項層級）
  "description": "雄雞報曉",
  "image": "/img/tw-1968-rooster-stamp.jpg"
}
```

`type` enum：`stamp` | `souvenir_sheet` | `miniature_sheet`（後續可擴充首日封等）。

## Source — 來源（獨立維護，分級）

每筆 Issue 以 `ref` 引用 Source。

```jsonc
{
  "id": "post-stamphouse",
  "title": "中華郵政 郵票寶藏",
  "url": "https://www.post.gov.tw/...",
  "tier": "official",                // official | reference | secondary
  "accessed_date": "2026-06-07"
}
```

`tier` 分級（公信力骨幹，見 D6）：

| tier | 意義 | 例 |
|---|---|---|
| `official` | 一手官方 | 中華郵政官網、i集郵 |
| `reference` | 權威目錄 | Scott、各國集郵目錄 |
| `secondary` | 二手新聞／部落格／百科 | 新聞報導、維基百科 |

## Zod / Content Collections 對應指引（scaffold 時實作）

已在 `src/content.config.ts` 把上述 schema 寫成 Zod，build-time 驗證把關（Phase 1 已實作）：

- `region.code`、`zodiac.animal`、`zodiac.branch`、`item.type`、`source.tier` 一律用
  `z.enum([...])`，避免拼錯。
- `issue_date`、`updated_at`、`accessed_date` 用 `z.string().date()`（或 `z.coerce.date()`）。
- `sources[].ref` 的 referential integrity（必須指向存在的 Source）Zod 無法跨集合驗證——
  建議在 build 時加一段 `getCollection()` 後的自訂檢查，找不到 ref 就 `throw`。
- 兩個 collection：`catalog`（type `data`，吃 `*.json`）與 `sources`（type `data`）；
  專題文章 `features` 為 type `content`（吃 `*.md`，frontmatter 受 Zod 驗證）。

> 範例 Zod 骨架（僅示意，scaffold 時補全並對齊上表）：

```ts
const issue = z.object({
  id: z.string(),
  region: z.object({ code: z.enum(['TW','CN','HK','MO','JP','US']), name: z.string() }),
  zodiac: z.object({
    animal: z.enum(['鼠','牛','虎','兔','龍','蛇','馬','羊','猴','雞','狗','豬']),
    branch: z.enum(['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']),
  }),
  zodiac_year: z.number().int(),
  issue_date: z.string().date(),
  round: z.number().int().positive(),
  // …其餘欄位見上表
  sources: z.array(z.object({ ref: z.string(), tier: z.enum(['official','reference','secondary']) })).min(1),
  verified: z.boolean(),
  updated_at: z.string().date(),
});
```
