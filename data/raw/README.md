# data/raw — 原始來源層

「網路原始來源」的落地處，相對於 `src/content/catalog/`（處理後的最終網站內容）。
目的：把各來源蒐集到的原始資料留底，**日後查證/建檔免重複上網搜尋或下載**。

## 核心原則：每個來源用它的「天然單位」存，issue 層用索引聚合

- 多數來源（5151sc、官網、hkstmp、stampshk、spb…）天然以**一套發行（issue）**為單位
  → **issue 中心**，見下方 §1。
- **WNS 是例外**：天然單位是「單枚郵票」、查詢單位是「會員國×年」 → **來源中心、按 member×year**，見 §2。
- 判準：新來源進來時問「它天然以什麼為單位？」按 issue 就進 issue 檔，否則自成一區再用索引接回。

## §1 issue 中心（多數來源）

```
data/raw/<region>/<canonical-id>.json            # 納版控；region = canonical-id 的地區碼（cn/hk/tw…）
data/raw/<region>/img/<canonical-id>/…           # 該套 web 來源圖；gitignore（本機備份）
data/raw/<region>/html/<canonical-id>/<source>.html  # 原始頁快照；gitignore（本機備份）
```

- 一個 `<canonical-id>.json` 收錄**這套票在不同時期、從不同來源**陸續蒐集到的資料；`sources` 下每個
  來源一個 key（不混血、保留 provenance）。HK 例：先 `hongkongpost`，後加 `hkstmp`、`stampshk`。
- **正負結果都記**：某來源查過但沒有 → `{"checked":"…","found":false}`。這就是「不要再 google」的關鍵——
  能分辨「還沒查」與「查了沒有」。
- 圖只記**檔名**；實體依本檔目錄慣例放（web 圖在 `<region>/img/<id>/`）。
- **`detail.html`＝原始頁快照（比 raw.json 更原始的一層）**：解析器改良時可離線重解析、來源站消失也還在。
  一套票可能多個來源頁，故按來源命名放 `html/<id>/<source>.html`（如 `hongkongpost.html`）。
  **保留、別丟**；`*.html` 已被 gitignore 涵蓋。issue 檔的來源 key 記檔名即可。
- 與 catalog `sources[]` 的分工：raw = 我們蒐集到的一切（含未採用、負結果）；catalog `sources[]` = 最終實際引用的。

範例見 [`cn/cn-2004-1.json`](./cn/cn-2004-1.json)。

## §2 WNS（唯一例外，stamp-unit 來源）

```
data/raw/wns/<member>/<year>.json   # 該年該會員國全部 WNS 記錄（wns-query --json 原樣）；納版控
data/raw/wns/<member>/coverage.json # 索引：各年筆數 + 生肖票 WNS 號；納版控
data/raw/wns/<member>/img/<WNS>.jpg # WNS 圖，按 WNS 號去重（跨 issue 共用）；gitignore
```

- 按 member×year 分片：可重現（一查詢=一檔）、天然分片、好維護;不做單一大 DB。
- **雙向查找**：
  - issue → WNS：issue 檔的 `sources.wns` 存 **`numbers:[…]` ＋ `found`**（指標＋查過沒），拿號去 `wns/<m>/<year>.json` 撈細節。
  - WNS → issue（少用）：WNS 號自帶 member+year，`fd/grep` 掃 `data/raw/<region>/*.json` 找含該號者;頻繁需要再**程式生成** `_index.json`，不手維護。
- WNS 圖與 web 圖**分兩類放**（鍵不同：WNS 圖鍵是 WNS 號、跨 issue 共用、可從 URL 重生）。

詳見 [`wns/README.md`](./wns/README.md)。

## §3 還沒有 canonical-id 的爬取資料（新國家／新網站）

canonical-id 是**算出來的**（`region + 志号|issue_date`，見 `docs/id-scheme.md`），**不是去來源查的**——
來源站不會有我們的 id，但會有算 id 所需的事實（你知道在爬哪國＝region；頁面通常有發行日或志号）。

- **能當場推導（最常見）** → 直接寫 `data/raw/<region>/<canonical-id>.json`。
  新國家（如印尼）：region=`id`、走 Track B、`issue_date`→`id-yyyymmdd`；台／中走志号。
- **一時算不出**（缺發行日/志号、同日相撞排序未定、想批量先爬後整理）→ 進**來源原生暫存**：
  ```
  data/raw/_inbox/<source>/<source-native-key>.json   # 以來源自己的 id 為鍵（5151sc pro_id / 爬取 URL / WNS 號）
  ```
  記 `pending_id: true` ＋已知線索（region、date、志号 candidate）；日後 curate 成 canonical 再搬進 issue 檔。
  （這正是舊 `cn-chinapost/<5151sc-code>/` 的角色——來源原生暫存；折進 `cn/<canonical-id>` 就是補上 canonical。）
- **region 都還沒定**（全新地區/幻想發行）→ 不是阻礙：id-scheme §1 涵蓋 ISO／非 ISO／保留區，指派並登錄 §4.1 即可。
- **永遠記「來源原生 key」**（`src_code`／`wns.numbers`／`url`）：pending 期間的穩定把手，也是**去重鍵**
  （同一頁再爬到不重複、不用又 google 一遍）。
- **推導邏輯共用**：算 canonical-id 的規則集中在 `scripts/`（目前 `migrate_ids.py`），讓爬蟲 ingest 與遷移
  **共用同一套**，避免兩邊長出不一致的 id。

## 圖片與版控

- **所有圖一律 gitignore**（`.gitignore` 規則 `data/raw/**/img/`），只是本機備份;`.json` 一律納版控。
- WNS 圖著作權屬發行郵政，UPU/WADP 允許下載，使用須標註「© <發行郵政> via UPU/WADP WNS」。

## 遷移狀態與規則

舊來源中心目錄（`hk-hongkongpost/`、`post-tw/`、`jp-japanpost/` …）為早期結構，**漸進遷移**：碰到某套票時，
把其 `raw.json` 內容折進對應 issue 檔的來源 key，並把 **`img/`、`detail.html` 一併搬進新結構**
（`<region>/img/<id>/`、`<region>/html/<id>/<source>.html`）。不強制一次性大遷移。

- **CN 已遷**（cn-chinapost → cn/，47 套，含 detail.html → `cn/html/<id>/5151sc.html`）；
  `cn-chinapost/` 僅留 4 個整輪珍藏冊（非 issue）與 `_index.json`。
- **⚠ 遷移一律「只搬不刪」**：本機 zsh／fish 都把 **`rm`／`rmdir` alias 成 `trash`**（移到垃圾桶）。
  所以「刪舊目錄」其實是丟垃圾桶——可救回，但極易遺漏 gitignored 的 `html`/`img`。
  CN 遷移時誤用 `rmdir` 把舊目錄連 detail.html 丟進 ~/.Trash，已全數救回;**後續遷移留著舊目錄當備份、不刪。**
  真要清理舊目錄，另開一次「確認所有 artifact（raw.json/img/html）都已搬妥」的審查再動。
