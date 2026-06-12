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

6. ⬜ **自掃郵票照片的浮水印(watermark)機制** — 日後以自行掃描的郵票圖替換爬圖時,需要一套
   浮水印作法,兼顧:(1) **美觀**——不破壞郵票本體辨識、不喧賓奪主;(2) **來源標示**——標註本站
   /掃描者,建立可追溯的出處;(3) **防濫用**——降低被原圖盜用轉載的誘因。
   - 可評估方向:半透明站名/印記角標、平鋪極淡水印、隅角朱印風標記(呼應視覺主題)、
     EXIF/IPTC 版權欄位、必要時不公開最高解析度原圖(對齊 backlog 3. 解析度規範與圖片版控決定)。

7. ⬜ **時間軸年份 → 該生肖年的跨地照片目錄頁** — 時間軸點下年份(生肖年:如 1998 年底發行的票算
   1999 年),進到一個列出「該生肖年各地發行」的照片目錄(版面類似單一生肖頁的卡片牆)。
   - 作法:新增 `/catalog/year/[zodiacYear].astro`,`getStaticPaths` 以 `zodiac_year` 分組;時間軸的
     年份標頭改連到此頁。與既有 zodiac/region 軸共用 `StampCard`。

8. ✅ **整理 TW／CN／HK 的敘述文字**（2026-06-12 完成）— 三區 `notes` 自動轉換原文已梳理成
   簡潔、一致、可讀的繁體敘述,並補上 `significance` 一句重點。
   - **CN**(47):自 5151sc 改寫,剝來源標記、剪干支通用段與離題生物學;結構欄位 opencc 轉繁;
     2016/2023 黃永玉名作經查證補 notes。**round-4(2016–2026)順帶補成正確的兩枚一套**(見下方修正)。
   - **TW**(58):自「郵票寶藏」改寫,剝「自動轉換」標記、剪干支套語與「印刷全張」行銷段,留設計概念＋三枚一句。
   - **HK**(86):significance 本季已備,剝所有標記、刪 31 檔 stampshk 行銷段,保留 newsletter 同日發行交叉引用。
   - **未做(刻意)**:`verified` **維持 false**——改寫文風不等於查證事實(D6),逐筆事實覆核另計。
   - **殘留**:HK 2002–2011 主票 notes 因移除 stampshk 而留空(設計細節原僅見於 stampshk;significance 仍可識別);
     TW/CN `items[].description` 仍有「特767.1」「金猴」等占位/簡名,屬資料層另議。

9. ⬜ **用 WNS 統一郵票本體圖** — WNS（wnsstamps.post）提供**品質／規格一致**的單枚郵票圖
   （`images/T180/{WNS}.jpg`），可作為港、日等 **2002+** 生肖票的標準化「郵票本體」圖源,
   小全張／首日封／郵戳仍用既有來源（官方／hkstmp／stampshk）。
   - **作法**:用 `wns-query` skill 取各枚 WNS 號 → 下載對應圖,重組 gallery（需定 item 圖與
     套圖 `images[]` 的並存策略,避免重複）。
   - **注意**:WNS 圖**只含郵票本體、不含完整小全張**；著作權屬發行郵政,UPU/WADP 允許下載但
     **須標註**（「© [發行郵政] via UPU/WADP WNS」）。
   - 依賴 `wns-query` skill（已建,`.claude/skills/wns-query/`）；規範見 `docs/id-scheme.md` §8。

10. 🔜 **先用 WNS 補強現有港日 entries（規格＋圖，順便實戰驗證 skill）** — 在做大遷移前,
    先用 `wns-query` 把 **2002 起**的香港、日本生肖票官方規格（尺寸／面值／齒孔／印製／設計者）
    與單枚郵票圖補進**現有** catalog entries,作為 id-scheme 遷移前的低風險暖身,同時檢驗
    `wns-query` 在實戰中的好用度（CDP proxy 穩定性、過濾命中率、欄位對應）。
    - **作法**:逐國 `--member "Hong Kong"`／`"Japan"` + `--year`／`--terms` 取每枚 WNS 號與
      規格 → 比對既有 entry 的 `items[]` → 補 `dimensions_mm`／`denomination`／`perforation`／
      `printer`／`designer`,WNS 號暫記 `notes`（schema 尚無 `items[].wns` 欄,待 item 11 擴）。
    - **範圍界定**:本項只補**規格與單枚圖**到既有 entry,不改 ID、不擴 schema;與 item 9
      （統一圖源策略）、item 11（遷移）分工。HK 主套票多數已補過,重點補 JP 缺口年
      （2002/2005/2008–2012）與校對。
    - **注意**:WNS 圖只含郵票本體;台灣不在 WNS。遇 skill 不順手就地修 `query.mjs` 並記錄。

11. ✅ **id-scheme 遷移（一次性改名腳本）**（2026-06-11 完成 a/b，c 暫緩）— 依
    `docs/id-scheme.md` 把 267 條從舊式 `{region}-{year}-{animal}-r{round}` 遷至 canonical
    `<region>-<designator>`，由 `scripts/migrate_ids.py` 一次完成。
    - **(a) ✅ schema 擴充**（`src/content.config.ts`）:`catalog_number` 擴成
      `{local,scott,sg,michel,yvert,colnect,stampworld}`;`items[]` 增 `wns` 欄（皆選填）。
    - **(b) ✅ 改名腳本**:台／中 Track A（`tw-sp55`／`cn-t46`／`cn-1992-1`,去補零／去 `2004-1T` 尾碼）,
      港日 Track B（`<region>-<yyyymmdd>`,同日相撞**主票優先 -a**、伴隨品 -b/-c/-d 按 series_name）。
      文字級改寫同步更新檔內 `id` 與 notes 跨檔引用（如「見 hk-20050130-a」）。build（Zod）通過。
    - **(c) ⬜ 舊 URL 重導 — 暫緩**:站未正式上線、無外部入站連結,待真正上線前再做
      （`/catalog/issue/<old-id>/` → 新 canonical,Astro redirects 或佔位頁）。
      `migrate_ids.py` 已能輸出 old→new map 供生成重導表。
    - **後續**:子項目 token（`s`/`ss`/`ms`/`fdc`/`pmk`…,§3）本次未展,issue 級 ID 已足;
      `items[].wns` 欄已備,待 item 10 用 WNS 補強時填入。

12. ⬜ **顯示支援 RWD（響應式設計）** — 確保全站各頁在手機／平板／桌機皆良好顯示:三軸索引、
    時間軸、詳情頁、卡片牆、lightbox、footer 等。檢查斷點、卡片網格 reflow、圖片縮放、導覽列在
    窄螢幕的行為。目前版面以桌機為主，需補行動裝置適配。

13. ✅ **CN 郵票照片改用 WNS 圖源**（2026-06-12 完成可行部分）— 盤點全 47 筆 CN 圖源、實測 WNS-China
    覆蓋，詳見 **[`cn-image-sources.md`](./cn-image-sources.md)**。
    - **盤點結果**:浮水印(5151sc)= 1980–2006（27 筆）;2007–2026（20 筆）已是 spb 官方無浮水印。
    - **⚠ WNS 幾乎無能為力（已逐年實測）**:27 筆浮水印圖中 WNS 僅能替 **1 筆**——
      1980–2001 不在 WNS（始於 2002）;2002／2003 雖在 WNS 年內但**生肖票未提交**;2005／2006 該年 WNS 全空。
      唯一可替的是 **cn-2004-1（CN001.2004 甲申猴）已替換**（填 `items[].wns`、`sources` 加 `un-wns`）。
    - **拆合圖**:round-2（1992–2003）為「2 枚合圖」，但這些年 WNS 無生肖票、5151sc 無分圖 → **目前無分圖來源**，維持現況。
    - **其餘 26 筆去浮水印 WNS 走不通**,替代方向見文件結論（官方老票多無線上高清／自掃 backlog #6／暫保留標註來源）。
    - **注意**:WNS 圖僅 T180（180px）尺寸、只含郵票本體;著作權屬發行郵政，須標註「© 中國郵政 via UPU/WADP WNS」。

14. ⬜ **詳情頁「上一套／下一套」連結** — 在 issue 詳情頁加前後導覽,初步想法為**同一發行地**的前一個／
    下一個發行套票(按 `issue_date` 排序;`zodiac:null` 伴隨品要不要納入待定)。
    - 作法:`getStaticPaths` 時把同 region 依 `issue_date` 排序的清單算好,傳 prev/next 的 `id` 與 `name` 給頁面。

15. ⬜ **lightbox 前後箭頭移到圖片兩側** — 目前 photolightbox 的左右箭頭在整個頁面左右兩側,離圖片太遠、
    滑鼠要移很遠。改為貼在圖片(lightbox 內容)兩側。改 `src/components/Gallery.astro` 的箭頭定位
    （由 viewport 兩側改為相對 lightbox 圖片容器定位）。

## 維護 / 技術債

- ✅ **升級 `.github/workflows/deploy.yml` 的 actions 版本**（2026-06-12 完成）— 因 GitHub runner
  **2026-06-16 起預設改用 Node 24**(舊 Node-20 action 將被強制升級)。已升:`checkout@v4→v5`、
  `setup-node@v4→v5`(皆 Node 24)、`upload-pages-artifact@v3→v4`、`node-version 20→22`(LTS);
  `deploy-pages@v4` 已是最新故不動。YAML 驗證通過。

