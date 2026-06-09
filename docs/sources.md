# 來源清單與分級

本站公信力的骨幹。每筆 Issue 透過 `sources[].ref` 連到這裡分級過的來源（見 spec D6）。
結構化資料見 `../src/content/sources/sources.json`。

## 分級原則（tier）

| tier | 意義 | 取用態度 |
|---|---|---|
| `official` | 一手官方（發行郵政自身） | 最高可信，優先採用 |
| `reference` | 權威集郵目錄 | 可信，用於補齊製作／編號細節 |
| `secondary` | 二手新聞／部落格／百科 | 需交叉覆核，單一 secondary 不足以標 `verified: true` |

## 首批來源

| ref | 標題 | tier | URL |
|---|---|---|---|
| `post-stamphouse` | 中華郵政 郵票寶藏 | official | https://www.post.gov.tw/post/internet/W_stamphouse/index.jsp |
| `i-jiyou` | i集郵（中華郵政） | official | https://stamp.post.gov.tw/ |
| `udn-zodiac-2024` | 聯合新聞網「馬的不思議—生肖郵票特展」報導 | secondary | https://udn.com/news/story/7270/9191489 |
| `einfo-zodiac` | 環境資訊中心〈漫談台灣生肖郵票〉 | secondary | https://e-info.org.tw/node/2936 |
| `wiki-zodiac-stamp` | 維基百科「生肖郵票」 | secondary | https://zh.wikipedia.org/zh-hant/生肖郵票 |

> 註：原設計筆記以「來源1／來源4／來源6」等臨時編號引用。本交接包改用語意化
> `ref`（如 `udn-zodiac-2024`），對照如下：來源1 → `udn-zodiac-2024`、
> 來源4 → `einfo-zodiac`、來源6 → `wiki-zodiac-stamp`。

## 待覆核社群來源

- 清清集郵網（chch.idv.tw）：老牌華語郵學論壇，分版細、玩家深度高，適合覆核資料。
- Facebook 集郵／郵票交流社團：需登入站內搜尋確認，**未驗證連結不列入** `sources`。

## 勘誤與覆核流程（待建立）

- 來源彼此存在出入（如輪次與套數的說法不一），需建立勘誤與覆核流程。
- `/about-site/` 須公開編輯方針與本分級說明，並提供勘誤回報管道。
