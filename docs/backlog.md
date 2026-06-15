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
- ✅ **Phase 2 靜態導論頁**（2026-06-15 完成）— `/about`(生肖郵票源流、干支基礎、發行年 ≠ 生肖年)、
  `/about-site`(本站定位、來源分級 D6、查證標記、勘誤回報走 GitHub Issues)。nav「關於」連 /about、
  footer 連 /about-site。設計見 `docs/superpowers/specs/2026-06-15-about-pages-and-homepage-design.md`。

## 使用者新增（2026-06-10)

1. ✅ **首頁特色郵票(featured + 隨機展示)**（2026-06-15 完成,策略 A）— 首頁精選區改成從
   「已查證且有真圖」的候選池(複用 `StampCard`)build 時全 render,前端 JS 隨機挑 3 套展示
   (每次載入換組;無 JS 時 CSS 顯示前 3)。**未加 `featured` schema 欄位**——池子隨 verified
   自動擴大,資料驅動。短期內池子全是台灣票(其他地區待查證)。

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
   - **版控決定**(2026-06-14 更新):**TW 圖改為納入版控**(212 張,interim 佔位,待正式掃描圖替換);
     `.gitignore` 改 `public/img/stamps/*` + `!public/img/stamps/tw/`,**其餘地區(cn/hk/jp)仍排除**。
     後果:GitHub Pages 上 TW 詳情頁顯示真圖;個別缺圖時 `<img onerror>` 切換到
     **`public/img/stamp-fallback.svg`**(郵政風佔位圖,**有**納入版控)。原決定為全部不納版控(版權考量)。
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

14. ✅ **詳情頁「上一套／下一套」連結**（2026-06-12 完成）— 同發行地依 `issue_date` 排序
    （同日以 id 穩定排序;`zodiac:null` 伴隨品**有**納入）,`getStaticPaths` 算好 prev/next 傳入。
    呈現:依使用者回饋放在 **breadcrumb 列右側**（「‹ 上一套｜下一套 ›」,hover tooltip 顯示套名＋年份）。

15. ✅ **lightbox 前後箭頭移到圖片兩側**（2026-06-12 完成）— `Gallery.astro` 加 `.lb-stage` 包圖,
    箭頭改貼圖片外緣兩側,張數計數移到圖片正下方;窄螢幕（≤640px）箭頭退回貼圖片內緣避免溢出。

16. ✅ **快速分享連結（FB／X／複製連結）**（2026-06-12 完成）— 詳情頁標題列右側三顆**圓形 icon 鈕**
    （經典金框、hover 印泥紅反白、即時 tooltip）:FB sharer／X intent（免 SDK）／
    `navigator.clipboard` 複製（成功切換勾勾圖示 1.5s,失敗 fallback `window.prompt`）。
    分享網址用 canonical 絕對網址。專題頁（features）日後上線時再沿用同一組樣式。

17. ✅ **Open Graph preview**（2026-06-12 完成）— `Base.astro` 加 props 化 OG／Twitter Card meta
    （`og:type`／`title`／`description`／`url`／`image`＋canonical link）,詳情頁傳 `article` 與
    `significance` 描述。`og:image` 用新製的 **`public/img/og-default.png`**（1200×630,郵票框＋
    「肖」戳記＋站名,SVG 源檔同目錄納版控,`rsvg-convert` 重生）——因郵票真圖不納版控,
    全站先共用預設卡;日後真圖上線可逐頁傳 `ogImage` 覆寫。

18. ⬜ **從 WNS 生肖索引預建 issue raw 骨架（已評估,待決）** — 用 `data/raw/wns/zodiac/records.json`
    （65 郵政、1,639 枚、約 462 個發行日）預先生成 `data/raw/<region>/<id>.json` 骨架
    （`id`＋`issue_date`＋`series_name` 線索＋`wns.numbers` 指標;規格本體留在 zodiac 索引,不內嵌）。
    - **機械可做**:member＋date 分組、Track B 區 ID 直接從日期算、WNS 前綴→region code 對映。
    - **雷區（勿全自動）**:(1) 同日多套拆分與 `-a/-b` 指派是判斷題,ID 錯了改名成本高;
      (2) 索引混有 CNY 節慶等非生肖票（269 筆 `animal:null` 待複核）,全量生成會違 D8;
      (3) WNS 缺口大（JP 2016+、CN 多數年、MY）,骨架只是「WNS 視角」,notes 須註明防假完整感。
    - **建議三步（各自可停）**:① dry-run 分組報告（不寫檔,綠=同日單聚類/黃=歧義）→
      ② 只對「標綠＋優先區」（`data/raw/` 已有目錄的 hk/jp/kr/mo/…;US 量大但無目錄,屆時議定）生成骨架,
      長尾單枚國家不開目錄 → ③（選配）優先郵政逐年 member 全量掃描補 `wns/<member>/<year>.json`,
      建檔到哪國再掃哪國。

19. ⬜ **Google Analytics 支援** — 全站加 GA4（gtag.js）流量分析。
    - 作法:`Base.astro` `<head>` 加 gtag snippet,Measurement ID 走 `PUBLIC_GA_ID` 環境變數
      （置 `.env`／CI variable,不寫死於版控）;**僅正式 build 載入**（`import.meta.env.PROD`
      且有設 ID 才輸出),避免本機開發污染數據。
    - 待決:是否需要 cookie／隱私聲明(可併入 `/about-site/` 編輯方針頁);GitHub Pages 為純靜態,
      無 server-side 方案,若日後想去第三方 cookie 可評估 GoatCounter／Plausible 等替代。

20. ⬜ **資料編輯體驗（JSON Schema 提示＋查證 CLI）** — 讓手改 catalog 更順手、減少記憶負擔
    （已評估,2026-06-13;改 `items[].type`、標 `verified` 等操作見討論）。
    - **(a) JSON Schema 編輯器提示（必做,近零成本）**:用 `zod-to-json-schema` 從
      `content.config.ts` 生成 JSON Schema,VS Code `json.schemas` 設定（或檔內 `$schema`）
      接上 → 欄位自動補全、必填提示、enum 下拉（`stamp`/`souvenir_sheet`…）、打錯即時紅線。
      Zod 改 schema 時重生(掛 npm script)。
    - **(b) `mark-verified <id>` CLI（選配）**:不只改 `verified`,還**檢查至少一個
      official/reference 來源**才放行（D6 程式化把關）,順手更新 `updated_at`。
      `new-issue` scaffold（算 canonical ID＋同日 `-a/-b` 提醒）可併入。
    - **不做**:git-based CMS（Sveltia/Keystatic）——schema 須在 CMS config 重複定義、
      與 Zod 雙份維護必漂移;單人工程師情境投資報酬不划算,有非工程協作者再評估。
    - 純欄位修改不包 CLI,(a) 已足;批次操作可用自然語言交辦＋Zod build 把關。

21. ⬜ **自掃圖匯入腳本** — 使用者把自掃圖放 repo 根 `incoming-scans/`(不納版控),檔名
    `<id>_<serial>.jpg`(底線接 serial,因 `<id>` 含 `-`);腳本落地到 `public/img/stamps/<cc>/`、
    更新 catalog `images[serial-1]`(serial=`images[]` 1-based;不足則 append),`<cc>` 由 id 推。
    - **待確認**:`images[]` 與 `items[].image` 是兩列表,自掃只動 `images[]` 還是要同步 `items`?
    - 約定見 memory [[fangcun-stamp-image-naming]]。圖↔品項非一對一(如 tw-sp81 八枚兩圖)。

22. ⬜ **現有 CN/JP/HK 爬圖歸類回填** — 三區現有圖是早期爬圖(CN=5151sc 數字檔名、JP=年份檔名、
    HK=hkstmp/stampshk 描述性檔名),既非 WNS 也無 `_alt` 標記,按「可接受來源」(中華郵政/WNS/自掃)
    多屬替代性質。需決定:遷進 `_alt/`(視為替代,正式站 fallback)還是另立來源類別,並回填。
    - 影響面大(67/67/148 張),獨立處理;與 _alt 機制(已建)分開。

## 維護 / 技術債

- ✅ **升級 `.github/workflows/deploy.yml` 的 actions 版本**（2026-06-12 完成）— 因 GitHub runner
  **2026-06-16 起預設改用 Node 24**(舊 Node-20 action 將被強制升級)。已升:`checkout@v4→v5`、
  `setup-node@v4→v5`(皆 Node 24)、`upload-pages-artifact@v3→v4`、`node-version 20→22`(LTS);
  `deploy-pages@v4` 已是最新故不動。YAML 驗證通過。

