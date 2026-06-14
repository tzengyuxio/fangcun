# 關於頁 ＋ 首頁精選改造 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 把 `/about/` 換成導論內容、新建 `/about-site/` 編輯方針頁、首頁精選區改成自動隨機真圖。

**Architecture:** 純 Astro 靜態頁;內容內嵌於 `.astro`(不引 markdown collection)。首頁精選用
build 時產生的候選池 JSON ＋ 前端 JS 隨機挑 3 套。無測試框架,驗證 = `npm run build` 通過 ＋ grep/dist 檢查。

**Tech Stack:** Astro 5(static)、Zod content collections、既有 `src/lib/catalog.ts` helper。

對應 spec:`docs/superpowers/specs/2026-06-15-about-pages-and-homepage-design.md`。

---

### Task 1: `/about/` 導論內容

**Files:**
- Modify: `src/pages/about/index.astro`(整檔換掉 placeholder)

- [ ] **Step 1: 寫入四節導論內容**

用 `<Base>`、`.container`,四節(`<section>`):①什麼是生肖郵票(1950 日本虎、12 年循環)、
②干支與生肖(地支↔生肖、越南貓/日本野豬變體)、③發行年≠生肖年(D5,1968 雞票 1969 才雞年)、
④台灣脈絡(1968 首套雞票世界首套、50 萬套、1968–1991 共 24 套兩輪)。繁中、參考站語氣。
適度連到 `/catalog/`。標題 `<Base title="認識生肖郵票 — 方寸裡的生肖" description="...">`。

- [ ] **Step 2: build 驗證**

Run: `npm run build`
Expected: Complete,無錯。

- [ ] **Step 3: 內容檢查**

Run: `grep -c "發行年" dist/about/index.html`
Expected: ≥1(且無「籌備中」)。

- [ ] **Step 4: Commit**

```bash
git add src/pages/about/index.astro
git commit -m "feat(about): write the zodiac-stamp primer (replace placeholder)"
```

---

### Task 2: `/about-site/` 編輯方針頁 ＋ footer 連結

**Files:**
- Create: `src/pages/about-site/index.astro`
- Modify: `src/layouts/Base.astro`(footer 加連結)

- [ ] **Step 1: 新建 about-site 頁**

四節:①本站定位(可被引用的參考站、非藏品展示)、②來源分級 D6(official/reference/secondary
定義與判準)、③查證標記(已查證/未經查證的意義;未查證=來源待補非錯誤)、④勘誤回報(GitHub Issues,
連 `https://github.com/tzengyuxio/fangcun/issues`)。`<Base title="關於本站 — 方寸裡的生肖" description="...">`。

- [ ] **Step 2: footer 加連結**

`src/layouts/Base.astro` 的 `.site-footer` 內,於 `footer-copy` 前加一行連結到 `${base}/about-site/`
(文字「關於本站 · 編輯方針與勘誤」)。

- [ ] **Step 3: build ＋ 檢查**

Run: `npm run build && test -f dist/about-site/index.html && grep -c "github.com/tzengyuxio/fangcun/issues" dist/about-site/index.html`
Expected: build Complete、檔案存在、grep ≥1。

- [ ] **Step 4: Commit**

```bash
git add src/pages/about-site/index.astro src/layouts/Base.astro
git commit -m "feat(about-site): editorial policy page + footer link"
```

---

### Task 3: catalog 三軸錨點 ＋ 首頁三軸分流

**Files:**
- Modify: `src/pages/catalog/index.astro`(三 `<section class="block">` 各加 `id`)
- Modify: `src/pages/index.astro`(`axes[].href` 加錨點)

- [ ] **Step 1: catalog section 加 id**

三 section 分別加 `id="zodiac"`、`id="region"`、`id="timeline"`(對應 壹/貳/參)。

- [ ] **Step 2: 首頁三軸 href 分流**

`src/pages/index.astro` 的 `axes` 三筆 href 改為 `${base}/catalog/#zodiac`、`/catalog/#region`、
`/catalog/#timeline`。

- [ ] **Step 3: build ＋ 檢查**

Run: `npm run build && grep -o 'id="zodiac"\|id="region"\|id="timeline"' dist/catalog/index.html | sort -u | wc -l`
Expected: 3。

- [ ] **Step 4: Commit**

```bash
git add src/pages/catalog/index.astro src/pages/index.astro
git commit -m "feat(catalog): anchor the three index axes; link them from home"
```

---

### Task 4: 首頁精選區 — 自動候選池 ＋ 前端隨機真圖

**Files:**
- Modify: `src/pages/index.astro`(frontmatter 建池、移除 `demo[]`、嵌 JSON、加 `<script>`、卡片真圖)

- [ ] **Step 1: frontmatter 建候選池**

import `primaryImage`、`imgSrc`、`ANIMAL_BRANCH`。從 `issues` 篩出有真圖者,map 成 pool:
```js
const pool = issues
  .map((i) => ({ d: i.data, img: primaryImage(i.data) }))
  .filter((x) => x.img)
  .map(({ d, img }) => ({
    id: d.id ?? '',            // 註:getCollection entry.id 在 issues[].id;改用 i.id
    name: d.series_name || (d.zodiac ? `${d.zodiac.animal}年生肖郵票` : '生肖郵票'),
    sub: `${d.region.name} · ${d.issue_date.slice(0,4)}${d.zodiac ? ' · ' + d.zodiac.animal : ''}`,
    img: imgSrc(img, base),
  }));
```
(取 id 用 `i.id`:`issues.map((i) => ({ id: i.id, ... }))`,改寫上面為直接遍歷 `issues`。)
移除舊 `demo[]` 常數。

- [ ] **Step 2: 精選區改成空容器 ＋ 嵌池 JSON ＋ fallback**

把 `.album-grid` 內的 `demo.map(...)` 換成空 `<div class="album-grid" id="featured-grid"></div>`,
其後加:
```astro
<script id="featured-pool" type="application/json" set:html={JSON.stringify(pool)}></script>
```
傳給前端用的 base/fallback 以 data 屬性帶:`data-base={base} data-fallback={fallbackSrc(base)}`。

- [ ] **Step 3: 前端隨機 3 套 script**

頁尾加 `<script>`:讀 `#featured-pool` JSON,Fisher–Yates 洗牌取前 3,對每筆建
```html
<figure class="plate"><a href="{base}/catalog/issue/{id}/">
  <div class="stamp-wrap"><div class="stamp"><img class="stamp-photo" src="{img}" onerror=切fallback></div></div>
  <figcaption class="plate-label"><span class="plate-name">{name}</span><span class="plate-sub">{sub}</span></figcaption>
</a></figure>
```
插入 `#featured-grid`。池為空則隱藏整個 `.album` section。

- [ ] **Step 4: 卡片 .stamp-photo 樣式**

`.plate .stamp-photo { width:100%; height:auto; display:block; cursor:pointer; }`(沿用既有票框)。

- [ ] **Step 5: build ＋ 檢查**

Run: `npm run build && grep -c 'featured-pool' dist/index.html && grep -c 'catalog/issue/tw-' dist/index.html`
Expected: build Complete;`featured-pool` ≥1;池 JSON 含 tw issue id(≥1)。

- [ ] **Step 6: 視覺驗證(dev + playwright 或 curl)**

`npm run dev` 後確認首頁精選區出現 3 張真圖卡、刷新換組、點擊進詳情頁。

- [ ] **Step 7: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat(home): featured stamps from verified pool, random real images"
```

---

## Self-Review 註記

- Spec 涵蓋:about(T1)、about-site+footer(T2)、三軸分流(T3)、首頁精選 A(T4)。✓
- id 來源:Astro content `getCollection` entry 的 `id` 在 `issues[].id`(非 `data.id`)。T4 用 `i.id`。
- fallbackSrc/imgSrc/primaryImage 皆 `src/lib/catalog.ts` 既有。
- 無新增 schema、無 markdown pipeline。
