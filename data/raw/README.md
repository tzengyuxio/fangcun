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
data/raw/<region>/<canonical-id>.json     # 納版控；region = canonical-id 的地區碼（cn/hk/tw…）
data/raw/<region>/img/<canonical-id>/…    # 該套 web 來源圖；gitignore（本機備份）
```

- 一個 `<canonical-id>.json` 收錄**這套票在不同時期、從不同來源**陸續蒐集到的資料；`sources` 下每個
  來源一個 key（不混血、保留 provenance）。HK 例：先 `hongkongpost`，後加 `hkstmp`、`stampshk`。
- **正負結果都記**：某來源查過但沒有 → `{"checked":"…","found":false}`。這就是「不要再 google」的關鍵——
  能分辨「還沒查」與「查了沒有」。
- 圖只記**檔名**；實體依本檔目錄慣例放（web 圖在 `<region>/img/<id>/`）。
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

## 圖片與版控

- **所有圖一律 gitignore**（`.gitignore` 規則 `data/raw/**/img/`），只是本機備份;`.json` 一律納版控。
- WNS 圖著作權屬發行郵政，UPU/WADP 允許下載，使用須標註「© <發行郵政> via UPU/WADP WNS」。

## 遷移狀態

舊的來源中心目錄（`cn-chinapost/`、`hk-hongkongpost/`、`post-tw/` …）為早期結構，**漸進遷移**：
新資料走上述結構;碰到某套票時再把其舊 `raw.json` 內容搬進對應 issue 檔的來源 key。不強制一次性大遷移。
