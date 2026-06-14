# 設計：關於頁內容 ＋ 首頁精選改造

> 狀態:已批准方向,待寫實作計畫。日期 2026-06-15。
> 範圍:`/about/` 導論、新建 `/about-site/` 編輯方針、首頁精選區真實化（策略 A）。

## 背景與動機

網站已正式公開（GitHub Pages),但:

- `/about/` 仍是 placeholder（「🚧 籌備中」）。
- 首頁「精選郵票」是**假 demo**:`index.astro` 的 `demo[]` 顯示日本 1950 虎、中國 T46 猴,
  但這些**未查證、正式站根本沒有**;且只是文字方塊（`{s.animal}`）不是真圖。
- 三軸入口 `href` 全指向 `/catalog/`（未分流）。
- **現實限制**:目前 `verified` 只有 **TW 59 套**,其他地區尚未查證上線。故首頁精選
  短期內只能是台灣票(真圖已於 2026-06-14 補上並納版控)。

## 1. `/about/` — 認識生肖郵票（導論）

把 `src/pages/about/index.astro` 的 placeholder 換成真內容。**沿用 `.astro` 內嵌
（不引 markdown content collection)**,與現有檔一致、最小改動。

內容取自 spec「已查證事實」(docs/spec.md 131–138),四節:

1. **什麼是生肖郵票** — 1950-02-01 日本以虎年發行世界第一套;十二年一循環。
2. **干支與生肖** — 十二地支 ↔ 十二生肖;點出**各地變體**(越南 卯=貓、日本 亥=野豬),
   呼應 backlog item 5「地支為歸類主鍵」。
3. **發行年 ≠ 生肖年**(D5,最重要) — 賀歲票於生肖年前一年底發行;首套雞票 1968-11
   發行、1969 才是雞年。
4. **台灣脈絡** — 1968 首套雞票(世界首套雞年票、50 萬套);1968–1991 共 24 套、兩輪。

文風:繁體中文、參考站語氣(非部落格)。可適度連到 `/catalog/` 對應軸。

## 2. `/about-site/` — 關於本站（編輯方針）

新建 `src/pages/about-site/index.astro`。參考站公信力的分水嶺(CLAUDE.md 鐵則 5)。四節:

1. **本站定位** — 追求資料完整與正確、可被引用的參考來源(非個人藏品展示)。
2. **來源分級**(D6) — `official`／`reference`／`secondary` 三級的定義與判準。
3. **查證標記** — 「已查證／未經查證」的意義;未查證僅代表來源待補,非資料錯誤。
4. **勘誤回報** — 透過 **GitHub Issues**(repo `tzengyuxio/fangcun` 已公開)。

## 3. 首頁改造（策略 A:自動候選池 + 前端隨機）

改 `src/pages/index.astro`:

- **精選區**:移除 `demo[]` 假資料。build 時用 `getVisibleCatalog()` 篩出「已查證**且有
  真圖**」的套票,收成候選池(id、series_name、region、生肖、發行年、`primaryImage`),
  以 JSON 嵌入頁面(`<script type="application/json">` 或 data 屬性)。前端 JS 隨機挑 **3 套**
  渲染成精選卡(真圖、連到 `/catalog/issue/<id>/`)。
- 池子隨 `verified` 增加自動擴大(資料驅動,D2);短期內全是台灣票。
- 卡片視覺沿用現有首頁 `.plate` 樣式(`stamp-photo` 真圖,參考 Gallery/StampCard 既有 helper)。
- 邊界:候選池為空時退回隱藏精選區或顯示佔位(沿用 `stamp-fallback.svg`)。

- **三軸入口**:`/catalog/` 的三 section 加錨點 id(生肖／發行地／年份);首頁三軸 `href`
  分流到 `/catalog/#<anchor>`。
- **masthead／status**:保留(統計已是 `getVisibleCatalog()` 真資料)。

## 4. 導覽連結

- nav(`Base.astro`)維持精簡:「首頁／目錄／關於」,「關於」續連 `/about/`。
- **`/about-site/` 連結放 footer**(編輯方針／勘誤是慣例放頁尾的規範頁)。

## 檔案異動清單

- `src/pages/about/index.astro` — 換成導論內容。
- `src/pages/about-site/index.astro` — 新建。
- `src/pages/index.astro` — 精選區改前端隨機真圖、三軸 href 加錨點。
- `src/pages/catalog/index.astro` — 三 section 加錨點 id。
- `src/layouts/Base.astro` — footer 加 `/about-site/` 連結。

## 非範圍（YAGNI）

- 不引入 markdown content collection(features 才用)。
- 不改 catalog schema(不加 `featured` 欄位;策略 A 不需要)。
- `/data/` 開放下載授權待決,about-site 不深入。
- 變體生肖(item 5)僅在 about 文中敘述,不動 `ANIMAL` enum。

## 成功標準

- `/about/`、`/about-site/` 有完整繁中內容,build 通過。
- 首頁精選區顯示真實已查證套票的真圖,刷新會換組,點擊進詳情頁。
- 三軸入口分流到對應 section。footer 有 about-site 連結。
- `npm run build` 通過(Zod 驗證 + 無壞連結)。
