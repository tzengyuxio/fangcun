---
name: wns-query
description: 查詢萬國郵聯（UPU/WADP）WNS 官方郵票資料庫（wnsstamps.post）。可用會員國、年份、月份、主題、自由字詞或 WNS 號過濾，一次回傳結構化記錄（WNS 號、發行日、主題、尺寸、面值幣別、齒孔、發行單位、印刷廠、印刷技術、設計者、發行量、官方圖片 URL）。用於為「方寸裡的生肖」catalog 採集官方規格／圖片，或查某套郵票的 WNS 號。Triggers on "WNS", "wnsstamps", "萬國郵聯郵票查詢", "查 WNS 號", "WNS member/year/theme filter".
---

# wns-query

直接打 WNS 後端 API（`/Home/autoStampSearch`），一次帶齊過濾條件取得 JSON，免去在 SPA 上反覆非同步載入。

## 前置：CDP proxy

WNS API 以瀏覽器指紋擋非瀏覽器客戶端（curl 會空回應），故本 skill 透過 **web-access 的 CDP proxy**（用你已登入的 Chrome）發頁內 `fetch`。使用前確保 proxy 就緒：

```bash
node ~/.claude/skills/web-access/scripts/check-deps.mjs   # 首次需在 Chrome 允許遠端偵錯
```

`query.mjs` 會自動嘗試拉起 proxy；若失敗，依其提示在 `chrome://inspect/#remote-debugging` 開啟「Allow remote debugging for this browser instance」。

## 用法

```bash
node .claude/skills/wns-query/query.mjs [選項]
```

| 選項 | 說明 |
|---|---|
| `--terms STR` | 自由字詞（對主題文字做 Partial 比對，如 `zodiac`、`horse`、`Lunar`）|
| `--member NAME` | 會員國／地區名稱（模糊比對 → GUID，如 `Hong Kong`、`Japan`、`China`）|
| `--year YYYY` | 發行年（2002 起）|
| `--month N` | 發行月 |
| `--theme NAME` | 主題分類（模糊比對 49 類，如 `Animals`）|
| `--wns WNSNUMBER` | 指定 WNS 號（如 `SG002.2026`）|
| `--page-size N` | 每頁筆數（預設 20）｜ `--page N` 翻頁（0 起）|
| `--sort asc\|desc` | 依日期排序（預設 desc）|
| `--json` | 輸出原始 JSON（供腳本接續處理）|

### 範例

```bash
# 2026 各國生肖票
node .claude/skills/wns-query/query.mjs --terms zodiac --year 2026

# 香港馬年相關（含金銀小型張）
node .claude/skills/wns-query/query.mjs --member "Hong Kong" --terms horse

# 查特定 WNS 號
node .claude/skills/wns-query/query.mjs --wns HK008.2026 --json
```

## 輸出欄位 → catalog 對應（WNS 為**單枚郵票**級）

> ⚠ WNS 以「單枚郵票」為單位，**無小全張／issue 層級**：一套四枚 + 兩小型張 = 6 個
> WNS 號。故每個 WNS 號對應到我們的**一枚 `items[]`**（子項目 `-s1`/`-s2`…），
> **不**對應 issue。issue canonical ID 仍用志號／日期（見 `docs/id-scheme.md`）。

| WNS 欄位 | catalog（item 級）|
|---|---|
| `wns`（如 `HK001.2026`）| 該枚 `items[].wns`（**不**進 issue canonical ID）|
| `date` | issue 的 `issue_date` |
| `subject` | `series_name`／`significance` 參考 |
| `w`×`h` | `items[].dimensions_mm` |
| `denom`+`cur` | `items[].denomination` |
| `perf` | `perforation` ｜ `tech` → `printing_process` |
| `printer` | `printer` ｜ `artist` → `designer` ｜ `engraver`/`qty` → notes／`mintage` |
| `img` | **單枚**郵票圖：`…/images/T180/{WNS}.jpg`。⚠ **只含郵票本體、不含完整小全張**——小全張／小型張整張圖須另取自官方站／hkstmp／stampshk |

## 注意

- 涵蓋 **2002 起**、UPU 會員及簽署 territories。**台灣不在內**（中華郵政非 UPU 會員）。
- 商業目錄號（Scott/SG）不在此；本庫為 UPU 官方認證號（tier `official`）。
- 來源分級與 canonical ID 規範見 `docs/id-scheme.md`。
- **翻頁是累積式**：`--page N` 回傳前 N+1 頁**累積**結果（非僅第 N 頁），`count` 達總數後
  持平——持平值即總筆數。累積請求超過約 **1,200 筆會回空**（`--page-size 1000` 以上同樣
  回空），總數大的詞請拆細關鍵詞，勿硬翻。
- `--terms` 是 subject 文字 Partial 比對：subject 不含該詞即漏（如 CN 生肖票用干支拼音
  「Wu Zi Year」、KR 用「New Year's Greetings」）。主題式盤點先查
  `data/raw/wns/zodiac/coverage.json` 的既有索引與盲區清單。
