---
name: wns-build-catalog
description: 從 WNS（萬國郵聯 UPU/WADP）官方資料，為某一地區郵政建立整批生肖郵票 catalog 的標準作業流程。封裝 member 全量掃描 → 識別生肖 issue → 逐枚取規格與圖 → 判斷生肖年/輪次/特殊結構 → 建檔腳本 → 逐套官方來源 → 驗證的完整 SOP，並收錄實作踩坑清單。復用 wns-query skill。用於把香港、日本、加拿大、紐西蘭、法國等 UPU 會員的生肖票一致、高效地灌進「方寸裡的生肖」。Triggers on "用 WNS 建某國生肖票", "建立某地區生肖郵票 catalog", "WNS 批量建檔", "WNS catalog SOP", "從 WNS 補某郵政".
---

# wns-build-catalog

從 WNS 官方資料為**一個地區郵政**建立整批生肖票 catalog 的流程指引。**不是一鍵自動建檔器**——
機械可複用的只有「取資料／落地／算 ID／下載圖」這層；每個地區真正花工夫的是**判斷點**
（生肖判定、發行年≠生肖年、輪次、特殊結構、來源），這份 SOP 把流程與**踩坑清單**固化下來，
讓下一個郵政不重蹈覆轍。

## 何時用

要把某個 **UPU 會員**（台灣不在內）的生肖票整批補進 catalog 時。WNS **自 2002 啟用**，
更早的票不在 WNS（需改走 Scott／reference，見 §7 收尾）。

## 前置

- **`wns-query` skill**：所有 WNS 查詢經其 CDP proxy（先 `node ~/.claude/skills/web-access/scripts/check-deps.mjs`）。
- **必讀**：`docs/id-scheme.md`（canonical ID）、`docs/data-model.md`（schema 欄位）、
  `data/raw/wns/README.md`（provenance 落地）、`data/raw/wns/zodiac/coverage.json`（既有跨國索引與盲區）。
- **鐵則**：D5（issue_date 排序／zodiac 歸類，永不混用）、D6（來源分級＋verified）、D8（只收生肖票）。

---

## 流程（以 `<cc>` = 地區小寫碼、`<Member>` = WNS 會員名為佔位；實例用 US）

### 1. member 全量逐年掃描 → provenance

照 `cn/` 模式落地 `data/raw/wns/<cc>/{year}.json`（**正負結果都記**，免重查）：

```sh
for y in $(seq 2002 2026); do
  node .claude/skills/wns-query/query.mjs --member "<Member>" --year $y --page-size 300 --json \
    > data/raw/wns/<cc>/$y.json
  echo "$y: $(jq '.count' data/raw/wns/<cc>/$y.json) total"
done
```

> ⚠ **不要只信 `zodiac/records.json` 的索引**——它是 subject 詞語掃描，有盲區
> （如美國 `US001.2011` subject 只寫「Lunar New Year」、`animal=null`；giclée 異常標註）。
> member 全量掃才能補齊。

### 2. 識別生肖 issue

從每年 json 篩生肖票（`subject` 含 `Lunar|Year of|New Year|Chinese New Year`…，依該國語言調整），
**逐枚人工核對**。注意 §「踩坑」的盲區與西洋星座排除。

### 3. 逐枚取完整規格 ＋ 下載圖

WNS 列表版欄位較少（qty/tech 常空）；**逐枚 `--wns` 取 detail** 才完整：

```sh
node .claude/skills/wns-query/query.mjs --wns <WNS> --json > data/raw/wns/<cc>/detail/<WNS>.json
curl -sL -A "Mozilla/5.0" -o public/img/stamps/<cc>/<WNS>.jpg \
  "https://wnsstamps.post/images/T180/<WNS>.jpg"
```

放行該區圖納版控（若要）：`.gitignore` 加 `!public/img/stamps/<cc>/`。

### 4. 判斷點檢查表（**每套逐一確認，不可自動**）

- **生肖／地支**：由 subject 解析；注意各地變體（越南卯=貓、日本亥=野豬、未=綿羊 vs 山羊）。
- **發行年 ≠ 生肖年（D5）**：各國模式不同——**美國多當年初發當年生肖**（少數提前年底，如
  US 雞/豬）、**台灣提前一年**。`zodiac_year` 依生肖、`issue_date` 依實際發行，逐套定。
- **canonical ID**：Track B＝`<cc>-<yyyymmdd>`（`issue_date` 去 dash）。同日多套：主票
  （zodiac 非 null）佔 `-a`，伴隨品依 `series_name` 排 `-b/-c`（見 id-scheme §2.2）。
- **輪次 round / series_name / region.name**：需 domain knowledge（如美國三輪、series 名
  第二輪叫「Celebrating Lunar New Year」）。region.name 用中文（「美國郵政」「香港郵政」）。
- **特殊結構**：十二生肖一次全發 → **單一 `souvenir_sheet` item、`zodiac:null`**（非 12 個
  stamp item，比照 tw-sp302）；小型張＝`miniature_sheet`、郵票小冊＝`booklet`；
  giclée/print 等非郵票本體 → 存疑設 `verified:false`。

### 5. 建檔（腳本模板見下方 §腳本）

每套輸出 `src/content/catalog/<cc>-<yyyymmdd>.json`，欄位映射：

| WNS / 判斷 | catalog |
|---|---|
| `date` | `issue_date`；`<cc>-<date>` → `id` |
| `subject` | `series_name`／`significance` 參考；解析生肖 |
| `w`×`h` | `items[].dimensions_mm` |
| `denom`（`Forever`→`value:null`）| `items[].denomination`（currency 該國幣別）|
| `perf`／`tech`／`printer` | `perforation`／`printing_process`／`printer`（`-`/空→`""`）|
| `qty`（去逗號）| `items[].mintage` |
| `wns` | `items[].wns` |
| `img` | `items[].image` = `/img/stamps/<cc>/<WNS>.jpg` |

`sources` 至少 `un-wns`（official）。

### 6. 設計者 ＋ 逐套官方來源

- **設計者**：WNS 多半沒有（`artist` 空）→ 查該國郵政官網。常**按系列/輪次通用**
  （一次查證適用多套），但 **`sources[].url` 必須逐套連自己那套的官方稿**。
- **加官方來源**（如美國 `us-usps`，official tier）：`sources.json` 補一筆 source，
  issue 的 `sources[].url` 填**該套自己年份的 release**。

### 7. notes 文風 ＋ verified ＋ 版權

- **notes 無草稿味**：不留「暫標未查證」「圖片待補」「WNS subject 未標生肖依發行年判定」
  這類編輯備忘（verified 欄位＋頁面 badge＋fallback 圖已表達）。**全形標點**。
- **版權標註獨立成段**：圖來源句用 `\n` 換行自成一個 `<p>`，如
  `…敘述。\n圖片來源 © <郵政> via UPU/WADP WNS。`（WNS 圖合規要求；非 WNS 官圖標 `© <郵政>`）。
- **verified 判準**：資料齊、單純、圖源 WNS → `true`；需額外判斷（giclée、十二全套、
  reference-only）→ `false` 待複核。

### 8. 驗證

```sh
npm run build                              # Zod 把關
# 抽查詳情頁（dev + playwright）：D5 並列、規格、圖、來源連結、badge
# 連結可達 + 無交叉污染：
for f in dist/catalog/issue/<cc>-*/index.html; do
  href=$(grep -o 'https://<官網>/[^"]*' "$f" | head -1)
  curl -sL -o /dev/null -w "%{http_code} $f\n" "$href"
done
```

---

## 踩坑清單（美國實戰）

1. **輪次代表稿 ≠ 逐套稿**：別讓同輪所有套都連同一篇稿（會出現「2021 牛連 2025 蛇稿」）。
   逐套連自己年份的 release。
2. **souvenir sheet 要 12→1**：十二生肖一次全發是**一個 `souvenir_sheet` item**，不是 12 個 stamp。
3. **WNS subject 盲區**：`animal=null`、「Giclée Print」等異常標註要查單枚頁/官方稿釐清，存疑設 false。
4. **早於 2002 不在 WNS**：該段改走 Scott 號＋reference 來源（如 `us-mystic`）、無 WNS 圖用
   fallback、`verified:false`；D5 仍要逐套判（提前年底發行的標註）。
5. **WNS 列表版欄位不全**：qty/tech 常空，要逐枚 `--wns` detail 補；早年仍可能全缺，留空勿臆測。
6. **member 解析**：`--member` 模糊比對，確認 `memberResolved` 命中正確郵政。
7. **翻頁累積式**：`--page N` 回前 N+1 頁累積；超過約 1,200 筆會回空，大會員拆細關鍵詞。
8. **圖版控**：`public/img/stamps/<cc>/` 預設被 `public/img/stamps/*` 忽略，要 `!` 放行該區。

---

## 腳本模板（建檔；逐地區改 ISSUES 映射）

```python
import json, pathlib
OUT = pathlib.Path("src/content/catalog")
DETAIL = pathlib.Path("data/raw/wns/<cc>/detail")
CC, REGION_NAME = "<cc>", "<中文郵政名>"

# 每套一筆：(wns, date, animal, branch, zodiac_year, round)  ← 判斷點 §4 的人工結論
ISSUES = [
    # ("US001.2025", "2025-01-14", "蛇", "巳", 2025, 3),
]
SERIES = {1: "...", 2: "...", 3: "..."}          # 各輪 series_name
DESIGNER = {1: "...", 2: "...", 3: "..."}         # 各輪設計者

def num(s):
    if s in (None, "", "-", "Forever"): return None
    try: return float(s)
    except ValueError: return None

for wns, date, animal, branch, zy, rnd in ISSUES:
    rec = json.loads((DETAIL / f"{wns}.json").read_text())["results"][0]
    val = num(rec.get("denom"))
    item = {
        "type": "stamp",
        "denomination": {"value": val, "currency": "<CUR>"},
        "description": f"...（{'Forever 永久郵資' if val is None else str(rec['denom'])}）",
        "image": f"/img/stamps/{CC}/{wns}.jpg",
        "mintage": int(rec["qty"].replace(",", "")) if rec.get("qty") not in (None,"","?") else None,
        "wns": wns,
    }
    w, h = num(rec.get("w")), num(rec.get("h"))
    if w and h: item["dimensions_mm"] = {"w": w, "h": h}
    if item["mintage"] is None: del item["mintage"]
    issue = {
        "id": f"{CC}-{date.replace('-','')}",
        "region": {"code": CC.upper(), "name": REGION_NAME},
        "zodiac": {"animal": animal, "branch": branch},
        "zodiac_year": zy, "issue_date": date, "round": rnd,
        "series_name": SERIES[rnd],
        "catalog_number": {"local": None, "scott": None},
        "designer": DESIGNER[rnd],
        "printer": rec.get("printer") if rec.get("printer") not in (None,"-","") else "",
        "printing_process": rec.get("tech") or "",
        "perforation": rec.get("perf") or "",
        "items": [item],
        "significance": "...",
        "notes": "...。\n圖片來源 © <郵政> via UPU/WADP WNS。",   # 版權獨立段、無草稿味
        "images": [item["image"]],
        "sources": [{"ref": "un-wns", "tier": "official", "url": "https://wnsstamps.post/"}],
        "verified": True,                                       # 判準見 §7
        "updated_at": "<YYYY-MM-DD>",
    }
    (OUT / f"{issue['id']}.json").write_text(json.dumps(issue, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
```

> 小全張全套版本：`items` 改放單一 `{"type":"souvenir_sheet", ...}`、`zodiac:null`、`zodiac_year:null`。
