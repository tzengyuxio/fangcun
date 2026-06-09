# Backlog(待辦中樞)

集中記錄已規劃、尚未動工的工作。相關文件:分階段 roadmap 見 [`build-plan.md`](./build-plan.md);
資料**來源採集** backlog 見 [`sources-research.md`](./sources-research.md)(聖誕島/紐/菲/不丹/加/泰/朝、
美國 API key、Colnect API、歐洲第二三批)。

> 狀態圖示:⬜ 待辦 · 🔜 下一個要做 · ✅ 完成

## 近期(對話中已議定)

- 🔜 **真實郵票圖（台灣優先）** — 詳見下方「使用者新增 4.」。**compact 後第一個做。**
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
   - 依賴「真實郵票圖」先到位。

3. ⬜ **圖片解析度規範** — 定義掃描／原尺寸大圖規範。**暫定**原尺寸大圖要求 **100dpcm 或 200dpcm**
   (dots per cm;100dpcm ≈ 254dpi、200dpcm ≈ 508dpi),具體採用哪個**尚未決定**。
   - 縮圖／顯示用尺寸另定。

4. 🔜 **真實郵票圖 — 台灣先用 raw 既有爬圖** — 先把 `data/raw/post-tw/*/img/` 已爬的圖
   **複製**到網站 assets 資料夾(路徑待定:`src/assets/stamps/tw/` 經 astro 處理,或 `public/img/stamps/tw/`
   原樣輸出),catalog 的 `item.image` 指向這些本地圖,方便**日後以正式掃描圖替換**。
   詳情頁/卡片改顯示真圖(目前為生肖字佔位)。
   - 注意:raw `img/` 目前被 `.gitignore` 排除;複製到 assets 後是否納入版控需一併決定(對齊圖片
     解析度規範與版權考量;呼應 spec 的 `/data/` 授權待決問題)。
