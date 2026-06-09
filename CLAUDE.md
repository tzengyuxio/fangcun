# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# 方寸裡的生肖 — Claude Code 專案指引

## 這個專案是什麼

「方寸裡的生肖」是一個**生肖郵票科普／參考站**。定位不是個人藏品展示，而是
涵蓋各郵政（台、中、港、澳、日、美…）發行的生肖郵票，追求**資料完整度與正確度**，
目標是成為可被引用的權威參考來源。

完整設計決策見 `docs/spec.md`（ADR 式設計筆記，D1–D9）。本檔只收**動手前必讀的鐵則**。

## 目前狀態

**已 scaffold;Phase 0、1、3、4 完成。** Astro 站骨架、版面、受 Zod 驗證的 Content Collections,
以及三軸索引／時間軸／詳情頁模板都已就緒（`npm run dev` 可預覽）。視覺設計見 **ADR-002**
（經典郵政圖鑑;含目標客群、配色、郵票卡／齒孔／郵戳元件)。

- **正式資料**（受 Zod 驗證，公信力骨幹）：`src/content/catalog/*.json`（Issue）＋
  `src/content/sources/sources.json`（分級來源）。現有 **60 套**：台灣 1968–2025 全五輪
  （自 `data/raw/post-tw` 轉換，`verified: false` 待複核，見 `scripts/convert_post_tw.py`）＋
  日本 1950 種子;`tw-1968-rooster-r1`（已查證）與 `jp-1950-tiger-r1` 示範 D5／D6。
- **採集素材**（未查證、各國 schema 不一，待轉成正式 catalog）：`data/raw/{region}/`，
  已涵蓋 16 個郵政、逾 400 套。爬蟲見 `scripts/`，來源地圖見 `docs/sources-research.md`。
- **待辦／後續**：功能與資料待辦見 `docs/backlog.md`;分階段 roadmap 見 `docs/build-plan.md`。

## 技術棧

- **Astro**（靜態網站，`output: 'static'`）。選型理由見 spec D9。
- **Content Collections + Zod**：把資料 schema 與查證骨幹變成 **build-time 保證**——
  欄位漏填、`tier` 拼錯、型別不符即 build 失敗。這是本站公信力的技術基礎，不可繞過。
- 部署：GitHub Pages（workflow 已備於 `.github/workflows/deploy.yml`）。
- 參考既有同類專案：`~/works/gongheli/web`（同為 Astro 靜態站 + GitHub Pages）。

## 核心鐵則（動資料／寫程式前必讀）

1. **資料驅動，單一來源（D2）**：網站由結構化資料生成。新增年份或勘誤**只改資料、
   不動版面**。三軸索引與詳情頁一律用 `getCollection()` + `getStaticPaths()` 生成。
2. **`zodiac_year` 與 `issue_date` 永遠分離（D5）**：賀歲票於生肖年前一年底發行，
   兩者常差一年。**排序／時間軸一律用 `issue_date`；生肖歸類一律用 `zodiac`／`zodiac_year`。
   永不混用。** 這是最容易出錯的地方。
3. **來源分級與查證（D6）**：每筆 Issue 透過 `sources[].ref` 連到分級過的 Source，
   `tier` 區分 `official`／`reference`／`secondary`，`verified` 標記是否經查證。
   這是全站公信力的骨幹，schema 不可弱化。**來源不足時的慣例**：仍可建檔但設
   `verified: false`，並在 `notes` 寫明缺什麼、待補哪種來源（見 `jp-1950-tiger-r1`
   的示範），而不是硬填或刪檔。
4. **核心資料庫只收生肖票（D8）**：非生肖藏品（古畫、特殊事件票等）不進 `/catalog/`；
   「我的收藏」`/collection/` 是 **v2** 的另立輕量展區，初期不做。
5. **`/about-site/` 是參考站與部落格的分水嶺**：編輯方針、來源分級說明、勘誤回報，
   務必保留。

## 目錄結構

```
src/
├── content.config.ts       # Content Collections + Zod schema 定義
├── content/
│   ├── catalog/*.json      # 郵票資料（受 Zod 驗證的 Issue,正式資料）
│   ├── sources/sources.json # 分級來源（受 Zod 驗證）
│   └── features/*.md       # 主題專題長文（frontmatter 受 Zod,待 Phase 5）
├── pages/
│   ├── index.astro         # 首頁
│   ├── about/              # 導論
│   ├── catalog/
│   │   ├── zodiac/[animal].astro
│   │   ├── region/[code].astro
│   │   ├── timeline.astro
│   │   └── issue/[id].astro   # 核心詳情頁模板
│   ├── features/
│   ├── guide/
│   └── about-site/
├── layouts/
└── styles/
```

正式資料權威來源是 `src/content/`（受 Zod 驗證）。`data/raw/` 為採集素材（未查證），
逐套人工查證後再轉入 `src/content/catalog/`——切勿未經查證直接灌入（違反 D6）。

## 常用指令（scaffold 後）

```sh
npm install        # 安裝相依
npm run dev        # 本機開發 http://localhost:4321
npm run build      # 產生 ./dist/（Zod 驗證在此把關）
npm run preview    # 預覽 build 結果
```

## 內容更新流程（D9）

- **文章**：新增 `src/content/features/*.md` → commit → CI 自動 build + 部署。
- **郵票資料**：新增／編輯 `src/content/catalog/*.json` → commit → 詳情頁、三軸索引、
  `/data/` 下載檔全自動重生。
- 手改檔 + git 即可，**不強制**額外工具。批量建檔再考慮選配的輸入小幫手腳本。

## 慣例

- 與使用者對話、網站文案、文件內容：**繁體中文**。
- 程式碼註解、變數命名、commit message：**英文**。
- Commit message 遵循 Conventional Commits（`feat:`/`fix:`/`docs:`…）。
- Issue slug 格式：`{region}-{issue_year}-{animal}-r{round}`，如 `tw-1968-rooster-r1`。

## 不要做什麼

- 不要把非生肖藏品塞進 `/catalog/`（見 D8）。
- 不要用 `issue_date` 做生肖歸類，也不要用 `zodiac_year` 排時間軸（見 D5）。
- 不要為了趕進度跳過 Zod 驗證或弱化 source schema——那會抽掉本站的價值地基。
- 未查證的來源（如未登入確認的 FB 社團連結）不要寫進 `sources`。
- 不要主動 commit；讓使用者決定。
