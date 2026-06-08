# 建置計畫（Build Plan）

給接手的 Claude Code session 照做的分階段 roadmap。每個 Phase 都附**驗證方式**，
有明確 success criteria 才能自行 loop 到完成。動手前先讀 `../CLAUDE.md` 的核心鐵則。

參考既有同類專案：`~/works/gongheli/web`（Astro 靜態站 + GitHub Pages）。

---

## Phase 0 — Scaffold Astro 專案

**目標**：建立可 `npm run dev` 的最小 Astro 站。

- [ ] 在 repo 根目錄 `npm create astro@latest -- --template minimal`（或手建 `package.json` 對齊 gongheli）。
- [ ] 設定 `astro.config.mjs`：`output: 'static'`、`site`、`base`（待使用者確認網域／路徑後填）。
- [ ] 建 `src/layouts/Base.astro`、`src/styles/global.css`。
- [ ] 保留／更新根目錄 `.gitignore`（已備）與 `.github/workflows/deploy.yml`（已備）。

**驗證**：`npm run dev` 起得來、首頁顯示佔位內容；`npm run build` 成功產生 `dist/`。

## Phase 1 — 資料層與 Zod 驗證骨幹（最關鍵）

**目標**：把 `data/` 種子資料接成受 Zod 驗證的 Content Collections。

- [ ] 寫 `src/content/config.ts`：定義 `catalog`、`sources` 兩個 data collection 與
      `features` content collection 的 Zod schema（對齊 `data-model.md` 的欄位表）。
- [ ] 把 `data/catalog/*.json` 移入 `src/content/catalog/`、`data/sources/sources.json`
      接到 `sources` collection。
- [ ] 加 build-time 自訂檢查：每筆 Issue 的 `sources[].ref` 必須指向存在的 Source，
      否則 `throw`（Zod 跨集合驗證的補強，見 data-model.md）。
- [ ] 故意塞一筆壞資料（漏欄位／`tier` 拼錯）確認 `npm run build` 會失敗，再移除。

**驗證**：種子資料通過 build；壞資料能讓 build 失敗（證明把關有效）。

## Phase 2 — 導論與靜態內容頁

**目標**：`/about/`、`/guide/`、`/about-site/` 上線。

- [ ] `/about/`：什麼是生肖郵票、票種源流（日本1950虎 → 台灣1968雞）、干支基礎、
      **發行年 ≠ 生肖年**（強調 D5 觀念）。素材見 spec「已查證事實」。
- [ ] `/guide/`：術語（小全張／小型張／首日封／四方連…）、保存與辨識基礎。
- [ ] `/about-site/`：編輯方針、來源分級說明（取自 `sources.md`）、勘誤回報。**參考站
      與部落格的分水嶺，必做**。

**驗證**：三頁可瀏覽、內文與 spec 一致、來源分級說明清楚。

## Phase 3 — `/catalog/` 三軸索引

**目標**：用資料生成生肖／發行地／年份三種入口。

- [ ] `/catalog/zodiac/[animal].astro`：`getStaticPaths()` 產生 12 個 landing，依
      `zodiac.animal` 歸類（**用 zodiac，不用 issue_date**，D5）。
- [ ] `/catalog/region/[code].astro`：依 `region.code` 分組。
- [ ] `/catalog/timeline.astro`：依 `issue_date` 排序的時間軸（**用 issue_date，不用
      zodiac_year**，D5）。
- [ ] `/catalog/` 索引首頁串起三軸入口。

**驗證**：種子資料（雞票、虎票）各自出現在正確的生肖／地區／時間軸位置；
雞票時間軸落在 1968、生肖歸類落在「雞」。

## Phase 4 — `/issue/[id]/` 詳情頁（核心模板）

**目標**：單筆發行詳情頁，全站最重要的模板。

- [ ] `getStaticPaths()` 為每筆 Issue 生成 `/catalog/issue/{id}/`。
- [ ] 呈現：region、zodiac、issue_date／zodiac_year（明確標示兩者差異）、items 陣列
      （可變數量渲染）、製作資訊、`significance`/`notes`、圖片、**來源列表含 tier 標記與
      `verified` 徽章**。

**驗證**：`/catalog/issue/tw-1968-rooster-r1/` 完整顯示；來源與查證標記可見。

## Phase 5 — 首頁與專題

- [ ] 首頁：定位說明 + 精選專題 + 三種入口。
- [ ] `/features/`：先寫一篇「世界第一套雞票：台灣 1968」（素材已查證）；
      「1980 庚申年猴票的傳奇」待補資料（見 spec 待決問題）。

**驗證**：首頁三入口可達；專題文章 frontmatter 通過 Zod。

## Phase 6 — 開放資料與部署（選配／收尾）

- [ ] `/data/`：輸出合併後的 JSON／CSV 供下載（呼應 D2，加 SEO 與公信力）。
- [ ] 確認 `.github/workflows/deploy.yml` 部署到 GitHub Pages 成功。
- [ ] 待使用者確認 `/data/` 授權條款（擬 CC BY）。

**驗證**：線上站可訪問、`/data/` 下載檔與站內資料一致。

---

## 暫不做（v2 / 範圍外）

- `/collection/`「我的收藏」非生肖藏品展區（D8，列為 v2）。
- TinaCMS／Decap 表單後台（D9，日後選項）。
- Facebook 粉絲頁營運（D7，發行季再啟動，與網站建置無關）。

## 跨 Phase 的鐵則提醒

- **D5**：生肖歸類用 `zodiac`/`zodiac_year`；排序／時間軸用 `issue_date`。永不混用。
- **D6**：來源分級與 `verified` 不可弱化，這是公信力地基。
- **D2**：所有頁面從資料生成，不要把資料寫死在版面裡。
