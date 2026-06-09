# 來源調查與爬取指南

各郵政生肖／農曆新年郵票的權威線上來源、可爬性與資料量盤點,供 Phase P 資料採集
與日後建檔使用。調查日期 2026-06-09(以實際打開頁面驗證,非僅憑記憶)。

> 落地原則見 `build-plan.md` 的 Phase P:raw 全收、不在採集階段套用 D8;`tier` 對應
> 見 `data-model.md`(official / reference / secondary)。

## 通則(先讀)

- **Colnect 全站有 Anubis proof-of-work 反爬**,`curl` / WebFetch 一律被擋,只能用
  headless 瀏覽器(Playwright)繞。台日韓中美越蒙各國調查都驗證過——**不要當主爬源**,
  僅在需要 Scott／Michel／Yvert 編號交叉對照時動用。StampWorld 為 Cloudflare 403、
  同樣避開。
- **版權**:幾乎所有郵票圖案仍在著作權保護內(郵政與委託設計師持有)。**圖片可直接
  下載 ≠ 取得重製／公開展示授權**。參考站宜採「縮圖 + 連回官方來源」並標註
  `ⓒ {郵政}`;正式上線前逐一確認各郵政圖像使用條款。最安全的圖源是 Wikimedia
  Commons(授權明確)。這也呼應 spec 裡 `/data/` 授權的待決問題。
- **優先順序**:官方一手(official)> 靜態且圖片可直連的權威目錄(reference)>
  需 headless 的來源。日韓美有官方結構化來源;中國官方無歷史目錄,只能用 reference。

## 總覽表

| 郵政 | 狀態 | 套數量級 | 最佳來源 | tier | 可爬性 | raw 估計 |
|---|---|---|---|---|---|---|
| 🇹🇼 台灣 中華郵政 | ✅ 已爬 75 | 75(1968–2025) | W_stamphouse `生肖` 子分類 | reference→official | 易 | 29 MB |
| 🇯🇵 日本 1997– | ✅ 已爬 28 | 28(1997–2025 年度) | 官方 `stamp.json` | official | 極易 | <1 MB(圖小) |
| 🇯🇵 日本 1950–96 | ✅ 已爬 47 | 47(1950–1996,40 圖) | dorama(metadata)+ yuubinsyumi(圖) | reference | 易(靜態) | 4 MB |
| 🇰🇷 韓國 | ✅ 已爬 113 | 113(1957–2020) | K-stamp 博物館(含早期) | official | 易(JSP,無反爬) | 168 MB |
| 🇨🇳 中國 | ✅ 已爬 47 | 47 套+4 冊(四輪 1980–2026) | 5151sc.com(靜態目錄) | reference | 易(curl) | 20 MB |
| 🇺🇸 美國 | ⏳ 腳本就緒待 key | ~31(三輪 1992–) | Smithsonian Open Access API | official | 中(DEMO_KEY 限流,需免費 key) | 50–300 MB |
| 🇻🇳 越南 | ✅ 已爬 11 | 11(2010,2016–25,含貓年) | vietnamstamp.com.vn | official | 易(靜態) | 21 MB |
| 🇲🇳 蒙古 | ✅ 已爬 6 | 6(2021–2026,官方僅近年) | mongolstamps.com Laravel API | official | 中(API route) | 1.2 MB |
| 🇮🇲 Isle of Man | ⚠️ 僅在售 2 | 2(2025 蛇/2026 馬;官方店無歷史) | iomstamps.com(Shopify) | official | 易但無歷史 | <1 MB |
| 🇫🇷 法國 | ✅ 已爬 21 | 21(2005–2025 連續) | philatelie-francaise.com | reference | 易(靜態) | 10 MB |
| 🇭🇰 香港 | ⚠️ 僅當年 3 | 3(2026;官方站無歷史) | stamps.hongkongpost.hk | official | 易但無歷史 | 5 MB |
| 🇲🇴 澳門 | ⚠️ 已爬 12(品質待篩) | 187 圖(各國比較頁,僅 31 疑似澳門) | cmm.gov.mo 生肖專題 | reference | 易但混多國 | 231 MB |
| 🇸🇬 新加坡 | ✅ 已爬 53 | 53 件(2020–2031) | shop.singpost GraphQL | official | 易(GraphQL) | 24 MB |
| 🇲🇾 馬來西亞 | ✅ 已爬 4 | 4 套(2024–26,僅現貨) | shop.pos.com.my Magento | official | 易但僅現貨 | 6 MB |
| 🇹🇭 泰國 | ✅ 已爬 22 | 22(2003–14,2017–26) | siamstamp + thailex | reference | 易(靜態) | 5 MB |
| 🇨🇦 加拿大 | ✅ 已爬 58 | 58 枚(1997–2021 兩輪) | postagestampguide | reference | 易(直連) | 19 MB |
| 🎄 聖誕島 | ✅ 已爬 13 | 13(2014–2026) | auspost collectables | official | 易(AEM offset) | 22 MB |
| 🇳🇿 紐西蘭 | ✅ 已爬 34 | 34(1997–2026,過濾變體) | nzpost BigCommerce sitemap | official | 易(sitemap) | 14 MB |
| 已研究待爬 | ⬜ | 見 Backlog 節 | 菲律賓/不丹/朝鮮 + Guernsey/UN/Jersey/列支/澳洲 | 混 | 菲易·餘難 | — |

---

## 已爬取

### 🇹🇼 台灣 中華郵政（75 套,`data/raw/post-tw/`)

- 來源:`https://www.post.gov.tw/post/internet/W_stamphouse/index.jsp?ID=2802&stamp_subcat_name=生肖&type=2802`
- 腳本:`scripts/scrape_post_tw.py`。分頁參數 `topage` + 固定 `PreRowDatas=12`(非 `page`);
  詳情頁 `ID=2803&file_name={code}`,欄位表 `th.hd→td`,主圖輪播 `a[data-cycle-desc]`,
  說明文 `div.LineHeight180`。
- 範圍:民國 57(1968)首套雞票 → 民國 114(2025);含新年／生肖郵票、`LD` 郵資票、
  少數郵展小全張。詳情頁是官方一手資料(可標 official)。

### 🇯🇵 日本 1997–2025（28 套,`data/raw/jp-japanpost/`)

- 來源:官方切手檔案 JSON `https://www.post.japanpost.jp/enjoy/culture/stamp/archive/json/stamp.json`
  (906 筆全切手,UTF-8 with BOM,以 `decode('utf-8-sig')` 處理),過濾 `title` 含「年賀」
  得 28 筆(**2007 年度官方未收錄**,如實缺席)。tier=official。
- 腳本:`scripts/scrape_jp_japanpost.py`。圖片可直接 curl、無反爬。圖檔 URL 跨年份有三種
  前綴,**直接用 JSON 的 `img` 欄位,不要自己拼 URL**。
- 已存 metadata 含詳情頁 url、pdf url、發行日、type、keyword,供日後抓多枚 sheet 圖。

---

## 待爬 / 缺口

### 🇯🇵 日本 1950–1996 缺口（官方源不含）

- 官方 `stamp.json` 只回溯 1997。**最具標誌的 1950 首套虎(世界第一套生肖郵票)不在官方源**。
- **metadata 主源**:`http://dorama.tank.jp/d/nengakittehtml.html`(歷代一覽表,Shift_JIS,需
  `iconv -f SHIFT_JIS`;含發行日／面額／お年玉シート,1950–1997 連續完整,無圖、無反爬)。
- **圖片主源**:`https://www.yuubinsyumi.com/shopbrand/ct285/`(昭和年賀,分頁 `/ct285/pageN/`,
  詳情 `/shopdetail/{id}/ct285/`)。圖片 CDN
  `https://makeshop-multi-images.akamaized.net/yuubinsyumi/itemimages/{id}.jpg`,**無尾碼或尾碼 2
  = 500×500 全解析**(尾碼 3 = 100×100 縮圖)。商家庫存導向,有缺年缺枚。
- **補洞**:Wikimedia Commons `Category:New Year stamps of Japan`(授權明確,但僅 ~16 檔)。
- 範圍 ~47 套、圖約 100–150 張、raw <20 MB。**版權**:日本郵票非自動公領域;2018 後保護期
  作者歿後 70 年,1950s 設計者多未過期 → 圖以識別性／合理使用,別當公領域。

### 🇰🇷 韓國（K-stamp 官方博物館,含早期缺口）

- **官方主源**:K-stamp 인터넷우표박물관 `https://stamp.epost.go.kr/`,**本身就涵蓋 1945–
  至今含早期**,優先級高於前一輪發現的在售端點(`service.epost.go.kr`,只是子集、缺早期)。
  純 JSP、`curl -A Mozilla` 即 200,**無反爬、不需 JS/登入**。
  - 列表:`spsg0103.jsp?stampCode=05&yearCode={十年桶 1950/1960/…}&page_num=N`
    (`stampCode=05` = 연하우표/新年票,每頁 24 筆;GET 篩選不穩時退用全列表掃 seqnum 或 Playwright)。
  - 詳情:`spsg0102.jsp?tbsmh15seqnum=<A>&tbsmh01seqnum=<B>`,內含
    `ImgView('http://image.epost.go.kr/stamp/data_img/{so,ss,sw}/<id>.jpg')`,正則抽圖即可。
  - 圖片實測:`http://image.epost.go.kr/stamp/data_img/so/116360751478450.jpg` → 200,598×598,330 KB。
- 範圍:最早 **1957-12-11 第 1 次 연하우표**(早期零星、非連續十二生肖;近數十年逐年對應當年
  生肖)。完整 60+ 年度、影像 ~150–250 張、raw 50–125 MB(只補 1957–1989 缺口約 20–40 MB)。
- 語言:韓文生肖 쥐/소/호랑이/토끼/용/뱀/말/양/원숭이/닭/개/돼지;關鍵詞 `연하우표`、`띠우표`。
  版權標 ⓒ Korea Post / 우정사업본부;部分圖走 http(留意混合內容)。

### 🇨🇳 中國（官方無歷史目錄,用靜態商業目錄）

- 官方(`chinapost.com.cn`、`jiyou.11185.cn`)**無結構化歷史目錄**(CMS 文章流 / JS 商城 405),
  不適合全集爬取。
- **官方查證/升級路徑(使用者提供,2026-06-10)**:
  - 中國郵政商城 `https://mall.11185.cn/web/searchJy?businessId=JY&prodGoodsType=NORMAL&classficationId=JY-0`
    —— **SPA**(34 個 script,商品由 JS/API 載入),且為**現售**商城,curl 抓不到、只含當期。
  - `https://www.chinapost.com.cn/cn/category/1814/325172-1.htm`(郵票發行信息)—— 動態渲染、
    僅 **2018–2026** 近年。
  - 兩者皆官方(可升 `tier=official`)但需 **playwright 渲染**且只覆蓋近年 → 適合當「**近年資料的
    官方查證 + tier 升級**」用,無法取代 5151sc 的 1980–2026 骨幹。**待辦**:用 headless 抽近年發行日/
    面值/圖,對齊現有 `verified:false` 的 CN 套並升級來源。
- **主爬源**:`http://www.5151sc.com/`(點購收藏網,靜態 PHP,`?page=N` 分頁,詳情
  `prosp-{id}.html`)。圖片直連、無 referer:`http://www.5151sc.com/upload/YYYYMM/{file}.jpg`
  (實測 750×622、67 KB;`/upload/sm/` 縮圖會 404,要抓 `/upload/YYYYMM/` 全尺寸)。tier=reference。
- 補充:Colnect 中國專區(編號最全,需 headless 過 Anubis)、百度百科(單套高清圖交叉校對)。
- 範圍:四輪 ~46 套(1980 T46 起),基本款 60–70 枚;含大版/小版/小本票變體 150–300 張,
  raw <50 MB。**版權**:中國郵政享著作權;商業站圖僅供內部索引,且站隨時可能加 WAF／封境外 IP,
  建議低速率 + 抓後本地存檔。

### 🇺🇸 美國（Smithsonian 官方 API;Arago 已下線）

- **⚠ Arago 已死**:`arago.si.edu/*` 全 302 導向搜尋頁,舊 URL 結構失效。**勿用 Arago**。
- **主源**:**Smithsonian Open Access API**(取代 Arago)。搜尋
  `https://api.si.edu/openaccess/api/v1.0/search?q=lunar+new+year+unit_code:NPM&api_key=KEY`
  (api.data.gov 免費 key),公領域件在 `online_media` 含 IIIF URL
  `https://ids.si.edu/ids/iiif/{idsId}/full/full/0/default.jpg`(可指定尺寸)。亦有 GitHub
  bulk JSON(`Smithsonian/OpenAccess`)。**curl + key 可取,無 JS、無反爬**。
- 補充:`about.usps.com/newsroom/...`(近年逐年發行新聞,200、純 HTML、有圖);Mystic Stamp
  指南(WebFetch 可取的完整文字清單,核對齊全度)。NPM 展覽頁與 USPS store 皆 Cloudflare／
  Akamai 403,走 API 不爬 HTML。
- 範圍:第一輪 1992–2006(Clarence Lee,12 單枚 + 2 全張)、第二輪 2008–2019(Kam Mak)、
  第三輪 2020–(規劃至 2031)。約 31 設計 + 全張、核心圖 50–80 張(IIIF 高解析 0.5–2 MB/張
  → 50–300 MB)。**版權分層**:Smithsonian 僅對「底層作品公領域」者給 media URL,LNY 設計仍在
  著作權內,部分件可能只給 CC0 metadata、不附影像。

### 🇻🇳 越南（含「貓年」特色）

- **主源**:`https://vietnamstamp.com.vn/`(越南郵政集郵公司,靜態 PHP,商品 `.html` slug、
  `curl` 帶一般 UA 即 200)。圖片 base `https://vietnamstamp.com.vn/media/`,分類／商品圖可
  直接 curl(舊檔可能 404,**以當前頁面實際 src 為準,勿用快取連結**)。tier=official。
- 補充:Vietstamp(`vietstamp.net`,北越早期票深度最佳,但 Cloudflare,需 Playwright)。
- 範圍:近代一輪 12+ 套,每套 1–2 枚;含北越早期更多。raw 10–40 MB(併早期票 100 MB+)。
- **特色務必標註**:越南以**貓(Mèo)取代兔年、水牛取代牛**——與中台日韓的最大差異,第四位
  「Mão/貓」年圖案要特別蒐。版權屬 VNPost。

### 🇲🇳 蒙古

- **主源**:`https://mongolstamps.com/en`(Mongol Post 官方,**Nuxt/Vue SPA**——curl 只得殼,
  真實資料在 `window.__NUXT__`,需正則解出或 Playwright 渲染)。圖床
  `https://api.mongolstamps.com/images/upload/<hash>.jpg` **可直接 curl 高清原圖**(實測 200、
  1600×1600、~430 KB)。tier=official。
- 補充:UB Stamps(`ubstamps.com`,靜態英文 vendor,補近年圖文)。
- 範圍:標準 12 生肖(無貓年變體,以 Tsagaan Sar 白月為節慶框架),近代一輪 12+ 套(常 1 枚 +
  小全張),raw 10–20 MB。風險:SPA 改版會變動 `__NUXT__`／API 形態。

### 歐洲及其他發行國(全局盤點,待評估)

**最值得優先納入的 5 個**(資料厚 × 可爬 × 公信力):

1. **Isle of Man Post** `iomstamps.com`(最優先)——官方授權 Shopify,每生肖一 collection
   (`/collections/yearofthehorse`),完整十二生肖、名家雕刻版。**直接打
   `/collections/{handle}/products.json` 或 `/products/{handle}.json` 取結構化 JSON**;圖片
   `iomstamps.com/cdn/shop/files/*.jpg?width=1600`。(`iompost.com` 會 301 到 `iomstamps.com`)
   **⚠ 實測限制(2026-06)**:官方店 `products.json` 只列**目前在售**商品,整站僅 Snake(2025)
   與 Horse(2026)兩年,較舊生肖年已售罄下架——**此來源結構性無法提供完整十二生肖**,歷史輪次
   需改用第三方目錄(Colnect 需 headless)。腳本已設計成依標題自動分組,日後新年份上架會自動收進。
2. **法國 La Poste**——靜態目錄 `philatelie-francaise.com/timbre_affiche/timbre.php?lig=NNNN`,
   欄位齊全(年份/生肖/設計者/面值/Yvert/印量/印刷法);圖片規律
   `philatelie-francaise.com/image/image-{year}/{year}-F{number}.jpg`。官方
   `laposte.fr/collaborations/astrologie` 佐證。2005 起年度發行。tier=reference。
3. **香港 Hongkong Post** `stamps.hongkongpost.hk`——政府官方、靜態 HTML,第五輪生肖(每年
   4 枚 + 小全張,含雷射剪紙),**與中國／澳門聯合發行**(三地對照價值)。圖片規律
   `/filemanager/common/stamps/latest_stamps_issues/{YEAR}/{theme}/stamps.jpg`;新聞稿
   `info.gov.hk/gia/...` 補發行日與描述。tier=official。
   **⚠ 實測限制(2026-06)**:此站是「現行在售」電商站,`latest_stamps_issues` 只列**當年(2026)**
   發行,**無 2025 蛇及更早的歷史輪次頁面**。對不存在路徑會回「200 但 body 是 redirect 殼」的假陽性
   (腳本已加殼偵測)。歷史輪次須改用 info.gov.hk 新聞稿存檔或第三方目錄。
4. **Guernsey Post**——**完整十二生肖循環 2014–2025 已完結**(Chrissy Lau 設計,風格統一);
   官方店若同 Shopify 則比照 IoM。設計師頁 `chrissylau.com/guernseypost.php` 有 12 動物總覽。
5. **聯合國 UNPA** `unstamps.org`——完整生肖循環(Tiger Pan 繪,每年一版 10 枚),國際中立,
   適合作「非主權發行者」代表。

**其他確有發行(簡列)**:Jersey Post(2016–2025,Shopify,與 China Post 王虎鳴合作)、
列支敦士登(雷射鏤刻銀箔,官方 `shop.philatelie.li` Magento;博物館目錄需 Playwright)、
馬爾他(僅 2024–2026)、加拿大(兩輪 1997–2020)、澳洲(年度 + 十二生肖小全張,圖走 Adobe
Dynamic Media)、紐西蘭(+ Niue/Tokelau 代發)、新加坡 SingPost、泰國(詩琳通公主親繪)、
菲律賓 PHLPost、澳門。

**排除**:英國 Royal Mail(只是 generic 煙火票 + 標籤貼紙,非生肖插畫)、愛爾蘭 An Post
(查無發行)。**待查**:印尼、馬來西亞。

**建議納入優先順序**:
1. 第一批(易爬、官方、資料厚):Isle of Man、法國、香港。
2. 第二批(完整循環、補國際代表):Guernsey、聯合國、Jersey。
3. 第三批(規模小或需額外處理):列支敦士登、澳洲、加拿大、新加坡、馬爾他。
4. 待查/暫緩:印尼、馬來西亞、泰國、紐西蘭代發屬地。

---

## 已爬:澳門 / 新加坡 / 馬來西亞(2026-06-09)

- **新加坡 SingPost**(✅ 53 件,2020–2031,`data/raw/sg-singpost/`):列表頁 JS 渲染,改用官方
  **Magento GraphQL** `/graphql`(`products(search:"zodiac")`)一次取全 53 件 Zodiac Series,圖
  `media_gallery` 即時 CDN URL。tier=official。最乾淨。`scripts/scrape_sg_singpost.py`。
- **馬來西亞 Pos Malaysia**(✅ 4 套,2024–2026,`data/raw/my-posmalaysia/`):`shop.html?cat=3838`
  225 件單頁,whole-word 馬來文動物名 + CNY 規則過濾。**線上僅現貨**(Snake 2025/Horse 2026 + CNY
  2024/25),歷史已下架。圖走 Magento gallery 剝 `/cache/` 取原圖。tier=official。`scripts/scrape_my_posmalaysia.py`。
- **澳門**(⚠️ 12 生肖頁 187 圖,`data/raw/mo-macaopost/`,**品質待篩**):來源 cmm.gov.mo 是通訊博物館
  的**「各國生肖票比較教育頁」,非澳門自家目錄**——187 張混中/越/韓/法/HK/澳/加/星等多國票,僅 31 張
  標 `macau_likely`(recall 不準)。raw 全抓並標 `caption`/`macau_likely` 待建檔人工精篩。
  **建議**:澳門自家票日後改用官方 `philately.ctt.gov.mo` 或第三方目錄重做。`scripts/scrape_mo_macaopost.py`。
  **2026-06-10 建檔狀態:未建**——此 raw 無發行日/年份/套結構,無法轉成 Issue;待重抓 CTT 官方目錄。

## 建檔進度(raw → src/content/catalog)

- ✅ **TW** 59、**CN** 47(2007–2026 已升級官方 spb)、**JP** 75(1950–2025;dorama+官方 archive)、
  **HK** 1(僅 2026 馬;官方站 stamps.hongkongpost.hk 有完整歷史,待加抓多年)。
- ⛔ **MO** 未建(見上,需 CTT 官方來源)。
- 轉檔腳本:`convert_post_tw.py` / `convert_cn.py`+`upgrade_cn_spb.py` / `convert_jp.py` / `convert_hk.py`。

## Backlog(待研究 / 待爬)

使用者指定發行者,**已研究來源與可爬性(2026-06-09)**,依推薦優先序:

| 發行者 | 最佳來源 | tier | 範圍 | 可爬性 | 備註 |
|---|---|---|---|---|---|
| 🇹🇭 泰國 | siamstamp.com(主)+ thailex.info(補早期) | reference | 2003–2026,~18–20 套 | 易(靜態;憑證過期用 `-k`) | 詩琳通公主繪;官方站不可達 |
| 🇨🇦 加拿大 | postagestampguide.com series 1465 + 官方交叉核對 | reference | 1997–2021,58 枚兩輪 | 易(圖直連無反爬,~6–8 MB) | 官方僅組合圖,逐枚靠三方 |
| 🎄 聖誕島 | collectables.auspost.com.au 詳情頁 + Adobe DM CDN | official | 1996–(站上 2014+),~30 套 | 易(詳情頁直連;列表 Load more 需 JS) | slug 不規則須從列表抓;1996–2013 靠 PDF/三方 |
| 🇳🇿 紐西蘭 | collectables.nzpost.co.nz(BigCommerce,可改解析度) | official | 1997–,~29 年度 | 易但**編號變體爆量需過濾** | Niue/Tokelau 生肖稀少可略 |
| 🇵🇭 菲律賓 | phlpost.gov.ph 新聞稿(wp-content/uploads) | official | ~2023–2025(3 套) | 易但**圖多現場照非乾淨掃描** | 官網無郵票目錄 |
| 🇧🇹 不丹 | bhutanstampeauction.bt + gnhcorner.com(不穩) | official | 1993–,~30 套但源不全 | 難(官方無目錄、商業站 403/CAPTCHA) | best-effort、近年優先 |
| 🇰🇵 朝鮮 | Wayback 快照(.kp 官方 502、三方全反爬) | secondary | 1992–,變體繁多 | 難 | **公信力爭議:CTO/濫發,須標警示、列次要** |

優先抓:**泰國、加拿大**(都易爬、圖直連、資料厚);次:聖誕島、紐西蘭(需處理 JS 分頁/變體);
菲律賓(淺);不丹、朝鮮(來源弱/有爭議,best-effort)。

其他待辦:

- **美國 USPS**:`scripts/scrape_us_usps.py` 已就緒,但 DEMO_KEY 被限流(429)。需至
  `https://api.data.gov/signup/` 申請免費專屬 key,以 `SI_API_KEY=... uv run scripts/scrape_us_usps.py` 執行。
- **Colnect API** `https://colnect.com/en/help/collecting/colnect_api`:**潛在價值高但有門檻**。
  能繞過全站 Anubis 反爬,取得最完整跨國目錄與 Scott/Michel/Yvert 編號交叉對照,補各來源缺口
  (日 1950–96、韓早期、IoM/港歷史輪次)。**但**:(a) 連 API 說明頁本身都在 Anubis 後,目前 curl 讀不到
  條款;(b) 據了解 Colnect API 需付費 Premium 會員 + 申請 key、有 rate limit;(c) 圖片多為使用者
  上傳、版權狀態模糊,僅宜當**編號交叉對照與文字補遺**,不宜當主圖源(本站官方一手優先)。
  **後續**:由使用者確認是否註冊/付費取得 key → 取得後寫 `scripts/` adapter,定位為缺口補遺 + 編號對照。
- **歐洲第二/三批**:Guernsey、聯合國、Jersey、列支敦士登、澳洲;印尼(待查是否發行)。
