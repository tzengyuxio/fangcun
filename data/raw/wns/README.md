# WNS 原始記錄（UPU/WADP）

萬國郵聯 WNS（[wnsstamps.post](https://wnsstamps.post/)）的原始查詢結果，落地於此供日後重用，
免去重複查詢／下載。屬「網路原始來源」層（同 `data/raw/` 其餘採集素材），非最終網站內容。

## 結構

```
wns/
├── README.md          # 本檔（納版控）
├── zodiac/            # 跨會員國生肖票總索引（subject 詞語掃描，2026-06-12）
│   ├── coverage.json  # 查詢方法、統計、caveats、by_member／by_animal 索引（納版控）
│   ├── records.json   # 1,639 枚去重記錄（WNS 原欄位 + 啟發式 animal 分類，依 date 排序）
│   └── western-excluded.json  # 被排除的西洋星座票（保留供複查）
└── cn/                # China（People's Republic）
    ├── coverage.json  # 各年 WNS 筆數 + 中國生肖票 WNS 號索引（納版控）
    ├── {year}.json    # 該年 China 全部 WNS 記錄，wns-query --json 原樣輸出（納版控）
    └── img/           # 下載的生肖郵票圖（T180, 180px）。**gitignore，本機備份**
```

僅存「有資料」年份的逐年 JSON（2002, 2003, 2004, 2008–2013, 2023）；0 筆年份的結果記於 `coverage.json`。

## zodiac/ 跨國總索引

以多組 subject 關鍵詞（year of the ×17 動物、zodiac、lunar/chinese new year、法文、
干支拼音、KR 賀年詞等）掃出 **65 個郵政、1,639 枚（2002–2026）** 生肖票，作為後續逐國
建檔的起點。**詞語掃描有盲區**（subject 不含關鍵詞即漏，已知補掃 CN 干支拼音、KR
「New Year's Greetings」），建檔某國前仍應照 `cn/` 模式做逐年 member 全量掃描複核；
方法、統計與完整 caveats 見 `zodiac/coverage.json`。

## 重新產生／擴充

```sh
# 某年全部記錄
node .claude/skills/wns-query/query.mjs --member China --year <YYYY> --page-size 200 --json > cn/<YYYY>.json
# 下載某枚圖
curl -sL -o cn/img/<WNS>.jpg "https://wnsstamps.post/images/T180/<WNS>.jpg"
```

需 web-access 的 CDP proxy（見 `wns-query` skill）。其他會員國比照建 `wns/<cc>/`。

## 重點（詳見 coverage.json）

- WNS 自 **2002** 啟用：1980–2001 的中國生肖票**不在** WNS。
- 某年有 WNS 資料 ≠ 有生肖票：**2002（壬午馬）、2003（癸未羊）該年無生肖票提交**。
- 有中國生肖票的年份：**2004, 2008–2013, 2023**（`zodiac_wns` 欄列出 WNS 號）。
- 著作權屬中國郵政，UPU/WADP 允許下載，使用須標註「© 中国邮政 via UPU/WADP WNS」。
- 圖僅 **T180（180px）** 一種尺寸。

> 圖源盤點與替換可行性分析見 [`docs/cn-image-sources.md`](../../docs/cn-image-sources.md)。
