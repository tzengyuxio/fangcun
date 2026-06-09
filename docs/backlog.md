# Backlog(待辦中樞)

集中記錄已規劃、尚未動工的工作。相關文件:分階段 roadmap 見 [`build-plan.md`](./build-plan.md);
資料**來源採集** backlog 見 [`sources-research.md`](./sources-research.md)(聖誕島/紐/菲/不丹/加/泰/朝、
美國 API key、Colnect API、歐洲第二三批)。

> 狀態圖示:⬜ 待辦 · 🔜 下一個要做 · ✅ 完成

## 近期(對話中已議定)

- ✅ **真實郵票圖（台灣優先）** — 已完成,詳見下方「使用者新增 4.」。
- ⬜ **轉更多郵政 raw → catalog** — 比照 `scripts/convert_post_tw.py`,逐郵政(日 → 韓 → 中 …)寫
  轉換邏輯。各國 raw schema 不一、生肖推導來源不同(台灣靠發行日+「年肖屬X」;他國需另找線索),
  須逐一處理並沿用 D6(`verified: false` 待複核)、D8(只收生肖票)。
- ⬜ **Phase 2 靜態導論頁** — `/about`(生肖郵票源流、干支基礎、發行年 ≠ 生肖年)、
  `/about-site`(編輯方針、來源分級說明)。見 build-plan Phase 2。

## 使用者新增（2026-06-10)

1. ⬜ **首頁特色郵票(featured + 隨機展示)** — 挑一套郵票呈現照片 + 基本資訊(年份、發行地、
   生肖…),可隨機展示。SSG 作法:build 時把候選郵票放入清單(全部抽樣一定數量,或在 catalog
   schema 加 `featured` 欄位篩選),首頁 render 時用前端 JS 從清單隨機挑一組呈現。
   - 影響:catalog schema 可能新增 `featured: boolean`(選配)。

2. ⬜ **詳情頁多圖陳列 + 放大** — 一套常有多張照片,需多圖呈現:主圖位置 + 底下縮圖點擊切換
   (類 Amazon 商品圖);游標移到主圖可放大檢視(hover zoom 或 lightbox)。
   - 依賴「真實郵票圖」先到位 → **已解除**;目前詳情頁只顯示單張代表圖(`primaryImage`),
     `images[]`／各 `items[].image` 已是本地路徑,可直接接多圖 gallery。

3. ⬜ **圖片解析度規範** — 定義掃描／原尺寸大圖規範。**暫定**原尺寸大圖要求 **100dpcm 或 200dpcm**
   (dots per cm;100dpcm ≈ 254dpi、200dpcm ≈ 508dpi),具體採用哪個**尚未決定**。
   - 縮圖／顯示用尺寸另定。

4. ✅ **真實郵票圖 — 台灣先用 raw 既有爬圖**(2026-06-10 完成)
   - **路徑**:採 `public/img/stamps/tw/`(原樣輸出,非 `src/assets/`)——catalog 是 JSON、圖名動態,
     且站用 `passthroughImageService` 本不做最佳化,public 直出最契合並沿用既有 `/img/...` 慣例。
   - **版控決定**:212 張官方爬圖**不納入版控**(`.gitignore` 排除 `public/img/stamps/`,屬版權圖)。
     後果:本機 `npm run dev/build` 有真圖 → 顯示真圖;GitHub Pages 無真圖 → 圖 404 →
     `<img onerror>` 切換到 **`public/img/stamp-fallback.svg`**(郵政風佔位圖,**有**納入版控)。
   - **重建方式**:`uv run scripts/link_tw_images.py`(攤平複製 raw D/S 圖到 public、並把 catalog 的
     post.gov.tw URL 改寫成本地路徑)。冪等。
   - **改動**:`StampCard.astro`、`issue/[id].astro` 改用 `<img class="stamp-photo">`;
     helper 收在 `src/lib/catalog.ts`(`primaryImage`／`imgSrc`／`fallbackSrc`)。
   - **後續**:日後以正式掃描圖替換時,丟同名檔到 `public/img/stamps/tw/` 即可;若屆時要讓 Pages
     也顯示真圖,需重新評估版控/版權(對齊下方 3. 解析度規範與 spec `/data/` 授權待決問題)。

5. ⬜ **生肖以「地支」為歸類主鍵(支援各地變體動物)** — 不變的是 **地支(子丑寅…,永遠 12)**;
   「動物」是各地文化標籤、會變:越南 卯=**貓**(非兔)、丑常作**水牛**;日本 亥=**猪/野豬**(非家豬);
   部分地區 未=**綿羊** vs 山羊。目前 `content.config.ts` 的 `ANIMAL` 鎖死 12-enum,會擋掉貓/野豬。
   - **方向**:生肖索引改以 `branch` 為主鍵(12 格固定),`animal` 退化為「可隨發行地不同的顯示名」;
     放寬 `ANIMAL` enum 或改加 `animal_local` 欄位。
   - **時機**:等第一個變體郵政(越南)入庫時再動;現無變體資料,先記著。

## 維護 / 技術債

- ⬜ **升級 `.github/workflows/deploy.yml` 的 actions 版本** — `actions/checkout@v4`、
  `actions/setup-node@v4`、`actions/upload-artifact@v4`、`actions/upload-pages-artifact@v3`、
  `actions/deploy-pages@v4` 目前跑 Node 20;GitHub 公告 **2026-06-16 起強制 Node 24**,屆時舊版
  action 可能 break。升級到各 action 支援 Node 24 的版本(多為 v5/最新)即可。

