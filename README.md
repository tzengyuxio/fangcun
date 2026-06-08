# 方寸裡的生肖（Zodiac Stamp Reference Site）

一個關於**生肖郵票**的科普／參考站。涵蓋各郵政（台、中、港、澳、日、美…）發行的
生肖郵票，追求資料的完整度與正確度，目標是成為可被引用的權威來源。

> 「方寸」是郵票的代稱；「生肖」是旗艦展廳。

## 定位

- **參考站，不是個人收藏館**：內容是「世界上的生肖票」，不是「我買了哪些」。
- **公信力掛帥**：每筆資料都有分級來源與查證標記，可被引用。
- **資料驅動**：整站由一份結構化資料生成，新增年份或勘誤只改資料、不動版面。

## 技術棧

- [Astro](https://astro.build/)（靜態網站）
- Content Collections + Zod（build-time 資料驗證）
- GitHub Pages 部署

## 專案狀態

🚧 **規劃完成、尚未建置。** 規格與資料已備妥，Astro 專案本體待 scaffold。

接手開發請依序讀：

| 文件 | 用途 |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Claude Code 接手指引（核心鐵則 + 指令） |
| [`docs/spec.md`](./docs/spec.md) | 完整設計規格（D1–D9、資訊架構、結果取捨） |
| [`docs/build-plan.md`](./docs/build-plan.md) | 分階段建置 roadmap |
| [`docs/data-model.md`](./docs/data-model.md) | Issue／Source schema 詳解 + Zod 對應 |
| [`docs/sources.md`](./docs/sources.md) | 來源清單與分級原則 |
| [`data/`](./data/) | 種子資料（已查證的首批 Issue 與 Source） |

## Quick start（scaffold 後）

```sh
npm install
npm run dev      # http://localhost:4321
npm run build    # 產生 ./dist/，Zod 驗證在此把關
```

## 授權

- 程式碼：TBD
- 開放資料（`/data/`）：擬採 CC BY，待確認（見 spec 待決問題）。
