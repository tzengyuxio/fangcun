# 郵票編號規範（Canonical Issue ID Scheme）

> 狀態：**v1 已落地**（2026-06）。全部 267 條已由 `scripts/migrate_ids.py` 從舊式
> `{region}-{year}-{animal}-r{round}` 遷至 canonical。本規範定義全站郵票的 canonical 識別碼，
> 供檔名、`id` 欄位、索引與 canonical URL（`/catalog/issue/<id>/`）使用。**通用於所有郵票，不限生肖。**

## 設計目標

- 每套發行（issue）一個**穩定、唯一、URL 安全**的 canonical ID。
- **生肖無關**：不含生肖動物、不含賀歲輪次。
- canonical ID 只用**永不變動的官方識別子**（地區自編志號 ＞ 發行日期）；商業／社群目錄號
  （Scott/SG/Michel/Yvert）會隨版本改、各家不一，**一律不進 ID**，只作參考。
- 可涵蓋 ISO 區碼外的郵政、地方郵政與幻想發行。

> **單位釐清**：本站以「**一套發行（issue）**」為核心單位（含套票數枚 + 小全張／小型張等，
> 由 `items[]` 承載）。注意 **WNS 是「單枚郵票」層級**（一套發行對應多個 WNS 號、且不含
> 小全張層級），故 WNS **不作 issue 級 canonical ID**，而存於 item 層（見 §5、§8）。

## 總則

- 全小寫，字元集 **`[a-z0-9-]`**（英數字、連字號），無空白、無中日文、無句點。
- 結構：**`<region>-<designator>`**（子項目再加後綴，見 §3）。
- 一經指派即**凍結**（穩定性優先）。

---

## 1. 地區段 `<region>`

| 情形 | 規則 | 例 |
|---|---|---|
| 有 ISO 3166-1 alpha-2 | 一律採用（小寫）| `tw` `cn` `hk` `mo` `jp` `us` `gb` |
| 屬地／特殊郵政 | 用其 ISO territory 碼 | `im` `gg` `je` `cx` |
| 跨國／無國別官方郵政 | 沿用慣用碼 | 聯合國郵政 → `un` |
| **非 ISO／地方／幻想發行** | 自 ISO 使用者保留區（`aa`、`qm`–`qz`、`xa`–`xz`、`zz`）指派，登錄於 §4.1 | 幻想／私營 → `xa`…；未定 → `zz` |

---

## 2. 識別段 `<designator>` — 兩軌（依優先序）

canonical ID（issue 級）只用永不變動的官方識別子。**選軌優先序：A ＞ B**。

### 2.1 Track A（優先）：地區自編官方志號

地區自己替郵票編號（多印於票上）時採用。實務上僅 **中國、台灣** 有此制。

1. 類別字 → 穩定 ASCII token（見 §4）。
2. 接其流水號，**不補零**（忠於來源；排序交給 `issue_date`）。

| 官方志號 | canonical |
|---|---|
| 台灣 特55 | `tw-sp55` |
| 台灣 特786 | `tw-sp786` |
| 中國 T46 | `cn-t46` |
| 中國 2016-1 | `cn-2016-1` |

### 2.2 Track B（後備）：發行日期

無自編志號時（香港、日本、韓、澳、越、美、英…）採用：
`<region>-<yyyymmdd>`（取 `issue_date`，8 位、無 dash）。

| 發行 | canonical |
|---|---|
| 日本 年賀 1950-01-01 | `jp-19500101` |
| 香港 馬年 2026-01-05 | `hk-20260105` |

**同日相撞尾碼**：同地區同日多套相撞時加 `-a`、`-b`…，順序規則（確定性、永不重排）：
**主生肖票（`zodiac` 非 null）優先佔 `-a`**，其餘伴隨品（金銀／絨面／銀箔小型張、十二生肖小版張等
`zodiac` 為 null 者）接於其後，以 `series_name` 字典序排定。一經指派即凍結;日後若同日再添新品，
**append 下一個字母**，不回頭重排既有者。

> **實例**：香港 2023-01-10 同日發行「兔年」特別郵票（主票）、「靈兔瑞龍」金銀小型張、
> 「鼠牛虎兔」銀箔燙壓小型張、十二生肖小型張 → 主票佔 `hk-20230110-a`，其餘依 `series_name`
> 凍結為 `-b`／`-c`／`-d`。

> 兩軌可由形態區分：A 含字母 token 或 `YYYY-N`；B 為 8 位數字。

---

## 3. 子項目標記

issue ID 標識「一套發行」。套內／周邊品項以**封閉 token 後綴**標識：

| 品項 | token | | 品項 | token |
|---|---|---|---|---|
| 郵票 stamp | `s`（多枚 `s1`/`s2`）| | 四方連 block-of-4 | `b4` |
| 小全張 souvenir sheet | `ss` | | 首日封 FDC | `fdc`（珍藏版 `fdc2`）|
| 小型張 miniature sheet | `ms` | | 郵戳 postmark | `pmk` |
| 小版張 pane | `pn` | | 套摺 pres. pack | `pp` |
| 版票 full sheet | `sht` | | | |

子項目 ID＝**`<issue-id>-<token>[index]`**，如 `cn-t46-s`、`hk-20260105-a-ss`、`tw-sp55-fdc`。

> **WNS 對應在此層**：WNS 是單枚郵票號，對應到 `-s1`/`-s2`… 各枚；存於 item 的 `wns` 欄
> （見 §5）。一套四枚 + 兩小型張 = 6 個 WNS 號，皆掛在各自 item，**不**升為 issue ID。

**變體層級**（刷色／齒孔／水印）預留後綴 **`-v…`**，本版不實作（變體複雜度集中於古典票）。

---

## 4. 地區編碼對照表

| 地區 | 官方志號 | 類別（字 → token）| 主軌 | WNS(item級) | 參考 |
|---|---|---|---|---|---|
| 🇹🇼 台灣 | 中華郵政志號 | 紀→`comm`、特→`sp`、常→`def`、航→`air`、欠→`due`、軍→`mil`、慈→`cha`、郵資票→`pl` | **A** | ✗（非 UPU）| post.gov.tw |
| 🇨🇳 中國 | 志号 | J→`j`、T→`t`、年票→`YYYY-N`；舊：纪→`ji`、特→`te`、文→`w`、编号→`n`、普→`p` | **A** | ✓ | spb.gov.cn |
| 🇭🇰 香港 | — | — | **B** | ✓ | hongkongpost |
| 🇲🇴 澳門 | — | — | B | ✓ | macaupost |
| 🇯🇵 日本 | — | — | B | ✓ | japanpost |
| 🇰🇷 南韓 | — | — | B | ✓ | — |
| 🇻🇳 越南 | —（社團目錄）| — | B | ✓ | — |
| 🇺🇸 美國 | —（Scott 商業）| — | B | ✓ | usps |
| 🇬🇧 英國 | —（SG 商業）| — | B | ✓ | royalmail |

### 4.1 自訂地區登錄表（非 ISO／幻想）

| code | 實體 | 收錄門檻備註 |
|---|---|---|
| _(空，待首次需要時登錄)_ | | 見 §6.3 |

---

## 5. `catalog_number`（issue 級）與 item 級 `wns`

issue 級 `catalog_number` 由 `{local, scott}` 擴成具名多目錄 map（皆選填、皆附連結）：

```
catalog_number: { local, scott, sg, michel, yvert, colnect, stampworld }
```

**WNS 在 item 層**：每枚 stamp item 增 `wns` 欄（如 `"HK001.2026"`），對應該枚的 UPU 官方號。

> WNS 號形如 `HK001.2026`（含 `.`），但僅存於 item 欄位、**不**進 canonical ID。

---

## 6. 邊界案例

- **6.1 合作發行**（如港－葡聯合）：**各地區各立一條**，互相 cross-ref。
- **6.2 長期定值票**：無單一發行日 → Track B 失效。有志號者走 A；無者個案處理記於 `notes`。
- **6.3 幻想／地方／cinderella 收錄政策**：須具「郵政性質」方收錄；以 `tier`／`verified`
  標可信度；命名空間 `xa–zz` 並登錄 §4.1。明顯偽票／詐騙票不收。

---

## 7. 與 schema 的關係（遷移紀錄）

- **canonical ID** = 檔名 + `id`，取代舊式 `{region}-{year}-{animal}-r{round}`。
- 遷移已完成：(a) ✅ `content.config.ts` 的 `catalog_number` 擴成 §5、item 增 `wns` 欄；
  (b) ✅ `scripts/migrate_ids.py`（一次性改名 + 文字級 cross-ref 改寫，267 條）；
  (c) ⬜ 舊 URL 重導——**暫緩**（站未正式上線、無外部入站連結，見 backlog item 11）。
- `catalog_number.local` 維持原值（如 `特455`、`2004-1T`）；canonical 僅取其正規化形（`tw-sp455`、
  `cn-2004-1`，去補零／去尾碼）。資料層 local 的清理另計（backlog item 8）。

---

## 8. 資料／圖片來源與參考連結

### WNS（UPU 官方，**單枚郵票**級資料＋圖片）

[wnsstamps.post](https://wnsstamps.post/)（UPU／WADP，2002-01-01 啟用，收錄約 160 個國家／
郵政機構、現逾 12 萬枚已認證郵票）為**官方資料源與圖片源**，且圖片**品質與規格一致**：

> **著作權**：圖片著作權仍屬**發行國郵政**，但 UPU／WADP **允許使用者下載**。本站採用時須
> 標註出處（如「© [發行郵政] via UPU/WADP WNS」），並比照 D6 來源分級記入 `sources`。

- **逐枚**附 WNS 號、發行日、主題、尺寸、面值、齒孔、發行單位、印刷廠、印刷技術、設計者。
- **圖片**：`https://wnsstamps.post/images/T180/{WNS}.jpg`——**只含郵票本體（裁切）**，
  **不含完整小全張**。故 stamp item 圖可用 WNS；**小全張／小型張整張圖**須另取自官方站／
  hkstmp／stampshk。
- 查詢用本 repo 的 **`wns-query`** skill（`.claude/skills/wns-query/`），可按會員國／年／月／
  主題／字詞／WNS 號過濾。涵蓋 2002 起；台灣不在內（非 UPU）。
- **排序不友善**：WNS 形如 `HK001.2026`（序號在前、年份在後），字串排序會「序號優先」，把
  不同年份的同序號票（`…001.2025` 與 `…001.2026`）誤群在一起——另一個**不入 canonical ID、
  不當排序鍵**的理由。全站排序一律用 `issue_date`；若需依 WNS 排序，須重排成 `YYYY.NNN`。

### 各地區／目錄參考

| 主題 | 連結 |
|---|---|
| 台灣 中華郵政 郵票分類／志號 | https://www.post.gov.tw/post/internet/W_stamphouse/index.jsp?ID=2801 |
| 中國 郵票志号體系 | https://www.rmzxw.com.cn/c/2017-02-22/1357754.shtml |
| 日本 郵趣用語集 | https://yushu.or.jp/tanoshimi/orientation/PDF/PDF015.pdf |
| 萬國郵聯 WNS | https://wnsstamps.post/ |
| 美國 Scott | https://www.amosadvantage.com/ |
| 英國 Stanley Gibbons | https://www.stanleygibbons.com/ |
| Colnect（免費社群，跨目錄轉換） | https://colnect.com/ |
| Stampworld（免費社群） | https://www.stampworld.com/ |
