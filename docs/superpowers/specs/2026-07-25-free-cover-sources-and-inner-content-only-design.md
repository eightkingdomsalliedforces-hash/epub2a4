# 免費封面來源、跨語言書名解析、EPUB 封底擷取與只輸出內文設計

日期：2026-07-25

## 目標

本階段改善 EPUB2A4 的封面與轉換流程，要求所有新增網路來源都可免費使用，並避免程式擅自加入或輸出使用者未要求的封面內容。

完成後應具備以下行為：

1. Google Books 僅要求 Google API Key，不再要求 Programmable Search Engine ID。
2. Open Library 保留，但可由使用者個別開關。
3. 新增 Gutendex／Project Gutenberg 作為免費補充來源。
4. 新增免費的跨語言書名解析流程，解決 Open Library 常只收錄原文書名、而 EPUB 只提供中文譯名的問題。
5. EPUB 若內嵌正面封面與封底，封面工具可直接辨識並取用兩者。
6. 轉換頁面新增「只輸出內文，不含封面與封底」，而且預設勾選。
7. 不加入 Z-Library、付費 API 或不穩定的網頁爬蟲。

## 範圍

### 納入

- Google Books API Key 設定與請求流程。
- Open Library、Gutendex 搜尋來源開關。
- EPUB 書名清理、卷數拆分與作者名稱標準化。
- Google Books 書目橋接。
- Wikidata 多語言標籤、別名、正式標題與 ISBN 解析。
- 使用者手動輸入原文書名或搜尋別名。
- 成功別名的本機快取與同系列重用。
- EPUB 內嵌正面封面、封底與純圖片頁辨識。
- 封面專案初始化時自動使用可辨識的正面與封底圖片。
- EPUB 轉換時排除已辨識的封面頁與封底頁。
- 每個來源獨立錯誤、限速及快取狀態。
- Windows、macOS、Ubuntu 共用與桌面測試，以及 Windows portable 建置驗證。

### 不納入

- Z-Library 或其他未提供穩定正式開發者 API 的來源。
- 下載完整電子書。
- 付費 ISBN／書目 API。
- 自動產生封面圖片、封底文字、書脊文字或條碼。
- 以 OCR 猜測一般正文圖片是不是封底。
- 把機器翻譯結果直接當成已確認的正式原名。

## 使用者介面

### 1. 搜尋來源設定

搜尋封面區顯示三個可獨立勾選的封面來源：

- Google Books
- Open Library
- Project Gutenberg（Gutendex）

預設狀態：

- Google Books：啟用；未設定 API Key 時顯示「需要 Google Books API Key」。
- Open Library：啟用。
- Project Gutenberg：啟用。

程式至少要求一個封面來源啟用；全部取消時停用搜尋按鈕並顯示原因。

Wikidata 是書名別名解析器，不是封面來源，因此不放在封面來源勾選清單中。它可在進階設定中個別停用；預設啟用。

### 2. Google 設定視窗

現有「Google 圖片搜尋設定」改為「Google Books API 設定」。

只保留：

- Google API Key
- 顯示／隱藏 API Key
- 儲存到系統或可攜資料夾
- 僅本次使用
- 清除已儲存

刪除 Search Engine ID 欄位及其完整性驗證。現有已儲存 JSON 若仍包含 `search_engine_id`，載入時忽略該欄位，不造成錯誤。

### 3. 搜尋條件與解析狀態

搜尋區新增：

- `原文書名／搜尋別名（選填）` 輸入欄。
- `自動尋找原文書名與 ISBN` 勾選項，預設啟用。
- 書名解析狀態摘要。

狀態摘要應能顯示：

```text
原始書名：魔法禁書目錄 1
清理後書名：魔法禁書目錄
辨識卷數：1
找到的原文名：とある魔術の禁書目録
其他別名：A Certain Magical Index
找到的 ISBN：9784840226586
本次查詢：ISBN、原始書名、原文名、英文名
```

只有使用者輸入值或高可信度解析結果可以作為正式查詢別名。低可信度候選只能顯示給使用者選擇，不可靜默覆蓋原始書名。

### 4. EPUB 來源檢查結果

選擇 EPUB 後，來源檢查區可顯示：

- 已找到正面封面
- 已找到封底
- 可能找到封底，等待確認
- 未找到封底
- 預估正文頁數

封面工具的預設模板仍是「原始封面（不加文字）」。

### 5. 轉換選項

在轉換頁面新增勾選框：

> 只輸出內文，不含封面與封底

規則：

- 預設勾選。
- 使用者可取消勾選，以保留 EPUB 原有封面頁與封底頁。
- 選項只影響正文 DOCX／PDF 輸出，不刪除 EPUB 檔案，也不影響封面工具擷取圖片。
- 設定應保存在目前的轉換設定或專案狀態中，重新開啟同一工作流程時維持使用者最後選擇；首次使用仍預設勾選。

## 搜尋架構

### 共用封面來源介面

所有公開封面來源實作相同的 provider 介面：

- 輸入：書名、作者、ISBN、語言、最大結果數。
- 輸出：標準化封面候選項目。
- 每個候選項目包含來源、書名、作者、ISBN、預覽網址、原圖網址及來源頁面。

搜尋控制器依使用者勾選項目呼叫 provider，合併並去除重複結果。

### 查詢計畫

搜尋不再只建立一個文字查詢，而是先產生有優先順序的 `QueryPlan`：

1. EPUB 中有效且通過校驗的 ISBN-13／ISBN-10。
2. 使用者手動輸入的原文書名或搜尋別名。
3. EPUB 原始書名＋作者。
4. 清理後書名＋作者＋卷數。
5. Google Books 回傳的標準化書名、作者與 ISBN。
6. Wikidata 回傳的原文標題、各語言別名、作者別名與 ISBN。

每個查詢項目記錄：

- 查詢類型。
- 查詢文字或 ISBN。
- 來源。
- 語言。
- 可信度。
- 產生原因。

同一 provider 不重複呼叫完全相同的正規化查詢。

### 書名清理與卷數拆分

離線清理器只做可逆的結構整理，不做自由翻譯：

- Unicode 正規化。
- 移除副檔名、網站尾綴和已知電子版標記。
- 移除「繁體中文版」「簡體中文版」「電子書版」「完整版」等格式詞。
- 將全形數字與羅馬數字標準化。
- 從「第 01 卷」「Vol. 1」「01」等格式提取卷數。
- 保留清理前原始值，不直接覆蓋 EPUB metadata。
- 對括號中的副標題採保守策略：先保留完整標題，再建立一個不含格式標記的備用查詢。

### Google Books：封面來源與書目橋接

- 使用 Books API。
- API Key 透過 `key` 查詢參數傳送。
- 沒有 API Key 時，不呼叫 Google Books；其他免費來源與 Wikidata 仍可繼續工作。
- 不再依賴 Search Engine ID 或 Custom Search JSON API。
- 除提供封面候選外，Google Books 結果可補充：標準化書名、作者、ISBN、語言及出版資訊。
- Google Books 回傳資料不會直接覆蓋使用者欄位，只加入別名解析結果與後續查詢計畫。

### Wikidata：跨語言書名解析器

Wikidata 不提供封面候選，只負責將譯名連接到原文名、其他語言名稱與 ISBN。

解析流程：

1. 以清理後書名和作者在使用者語言中搜尋實體。
2. 取得候選實體的 label、alias、description 與必要 claims。
3. 收集作品或版本的多語言標題、ISBN-13、ISBN-10、作者及系列關係。
4. 使用作者、卷數、系列名稱及 ISBN 對候選評分。
5. 只有高可信度結果才自動加入 QueryPlan；中可信度結果顯示給使用者確認。

防止錯配：

- 作者明顯不同時不得自動採用。
- 系列相同但卷數不同時降低分數。
- 只有模糊書名相似、沒有作者或 ISBN 支持時不得自動採用。
- 電影、動畫、遊戲等同名但非書籍實體不得加入書籍查詢。
- 解析失敗不阻斷正常封面搜尋。

### Open Library

- 保留正式 Search API 與 Covers API。
- 使用可識別的 User-Agent。
- 維持保守的一秒一次請求限制。
- 快取相同搜尋與圖片下載結果，減少 429。
- 查詢順序優先使用 ISBN，其次使用使用者別名、Wikidata 原文名、英文名、原始譯名。
- 不依賴 Open Library 自己完成譯名到原名的轉換。

### Gutendex／Project Gutenberg

- 使用 Gutendex JSON API。
- 以 `search`、語言及書目資訊查詢。
- 只建立具有可用封面圖片格式的候選項目。
- 標示來源為 Project Gutenberg。
- 主要作為古典文學與公版書補充，不取代 Google Books 或 Open Library。

### 手動別名與本機快取

使用者可輸入原文書名、英文名或其他正式別名。成功找到並由使用者選用封面後，程式可在本機保存：

```text
原始書名 → 已確認別名、作者、系列、卷數、ISBN
```

規則：

- 只存本機，不上傳整本 EPUB 或 EPUB 內容。
- 優先以 ISBN 作為快取鍵；沒有 ISBN 時使用正規化書名＋作者＋卷數。
- 同系列新卷只能重用系列別名，不能重用舊卷 ISBN。
- 介面提供清除別名快取功能。
- 快取結果屬於查詢提示，不覆寫 EPUB metadata。

### 候選結果評分

候選分數至少考慮：

1. ISBN 完全相同：最高權重。
2. 標準化書名或已確認原文名完全相同。
3. 作者相同或已確認作者別名相同。
4. 系列名稱相同。
5. 卷數相同。
6. 語言符合。
7. 只有部分字串相似：低權重。

卷數不同、作者不同或媒體類型不符時必須扣分。程式可排序候選，但不能未經使用者操作自動下載或套用網路封面。

### 錯誤隔離

每個元件的錯誤獨立呈現，例如：

- Google Books：API Key 無效。
- Wikidata：暫時無法解析別名。
- Open Library：暫時限流。
- Project Gutenberg：服務無法連線。

一個來源或解析器失敗時，其他來源的成功結果仍然顯示。只有所有已啟用封面來源都失敗且沒有結果時，搜尋才視為整體失敗；別名解析失敗本身不算封面搜尋整體失敗。

## EPUB 正面與封底辨識

### 正面封面

依可信度順序辨識：

1. EPUB 3 manifest 的 `properties="cover-image"`。
2. EPUB 2 metadata 的 `meta name="cover"` 指向項目。
3. guide 中 type 為 `cover` 的參照頁。
4. spine 開頭的純圖片頁，檔名或 id 包含 cover／front／表紙／封面。

### 封底

依可信度順序辨識：

1. guide、manifest 或 landmarks 中明確標示 `back-cover`、`backcover`、`rear-cover` 等語意的資源。
2. spine 結尾的純圖片頁，檔名、id、標題或替代文字包含 backcover／back-cover／rear／封底／裏表紙。
3. 與正面封面尺寸和比例相近、位於閱讀順序末端且頁面只包含單張圖片的候選。

第三級只能標記為「可能的封底」，不能在沒有其他證據時自動排除。介面顯示候選並讓使用者確認。

### 避免誤刪

以下內容不能因「只輸出內文」而自動移除：

- 正文中的插圖。
- 章節插畫。
- 彩頁或插頁，但未被明確標記為封面／封底。
- 同時含有實質正文文字與圖片的頁面。

只有高可信度的正面封面與封底頁會自動排除；中可信度封底必須經使用者確認後才能排除。

## 封面專案初始化

### 只有正面封面

- 將圖片放入正面區域。
- 封底保持空白。
- 不建立任何文字、條碼或書脊元素。

### 同時有正面與封底

- 正面圖片放入正面區域。
- 封底圖片放入封底區域。
- 保持各自原始比例，使用可編輯裁切方式填滿成品區域。
- 不把兩張圖片合成新圖檔；專案內保留兩個獨立圖片元素。
- 書脊保持空白，除非使用者自行加入圖片或文字。

### 只有完整展開圖

若 EPUB 明確包含完整書衣展開圖，則可建立一個 `FULL_SPREAD` 圖片元素；不能把一般橫向插圖誤認為完整書衣。

## 轉換資料流

1. 解析 EPUB package、manifest、guide、landmarks 與 spine。
2. 建立封面資源辨識結果，包含可信度及判斷理由。
3. 估算正文頁數時，預設排除高可信度封面與封底頁。
4. 使用者開始轉換：
   - 勾選「只輸出內文」：從內容區塊流中排除已確認的封面與封底頁。
   - 未勾選：保留原始 spine 閱讀順序。
5. 封面工具仍可存取被排除頁面的圖片資源。

## 資料模型

來源檢查結果新增或標準化以下欄位：

```text
front_cover_resource: string | null
front_cover_page: string | null
back_cover_resource: string | null
back_cover_page: string | null
back_cover_confidence: high | medium | none
back_cover_reasons: list[string]
```

轉換設定新增：

```text
content_only: bool = true
confirmed_back_cover_page: string | null
```

搜尋請求新增：

```text
manual_alias: string
resolve_aliases: bool = true
enabled_providers: set[google_books | open_library | gutendex]
```

書名解析結果新增：

```text
original_title: string
normalized_title: string
series_title: string | null
volume_number: string | null
aliases: list[ResolvedAlias]
isbns: list[string]
```

`ResolvedAlias` 至少包含：

```text
value: string
language: string | null
source: user | epub | google_books | wikidata | local_cache
confidence: high | medium | low
reasons: list[string]
```

舊設定缺少 `content_only` 時視為 `true`，符合本階段的預設行為。

## 相容性

- 舊的 Google 憑證檔仍可讀取，只使用 `api_key`。
- 舊轉換設定沒有 `content_only` 時使用新預設 `true`。
- 舊搜尋設定缺少 provider 開關時，三個免費來源視為啟用。
- 舊封面專案不自動刪除既有文字元素；新建立的「原始封面」專案才採用不加文字的規則。
- 使用者若需要舊行為，可取消勾選「只輸出內文」或主動套用文字模板。

## 隱私與安全

網路搜尋只傳送使用者允許的書目資訊：

- 書名及解析出的別名。
- 作者。
- ISBN。
- 語言與有限的搜尋參數。

不得上傳 EPUB、DOCX、PDF、正文內容或本機圖片。介面應清楚說明此限制。

## 測試策略

### 共用 Python 測試

- Google Books 只需 API Key，沒有 Search Engine ID 也可搜尋。
- 缺少 Google API Key 時只略過 Google Books，不阻斷 Open Library、Wikidata 與 Gutendex。
- Open Library 和 Gutendex 可個別開關。
- provider 部分失敗時仍回傳其他來源結果。
- 書名清理不破壞原始 metadata，並正確拆分常見卷數格式。
- 中文譯名可經 Wikidata 取得可信的日文或英文別名。
- 作者不符或卷數不符的 Wikidata 候選不得自動採用。
- Google Books ISBN 能加入 Open Library 的後續查詢計畫。
- 手動別名優先於自動解析別名。
- 本機快取不會將舊卷 ISBN 套到新卷。
- 相同正規化查詢不會重複呼叫同一 provider。
- EPUB 2、EPUB 3 正面封面辨識。
- 明確標示及閱讀順序末端封底辨識。
- 正文插圖不被誤判為封底。
- `content_only=true` 排除已確認的正面與封底頁。
- `content_only=false` 保留所有原始頁面。
- 正面與封底圖片能各自建立封面專案元素，且沒有自動文字或條碼。

### 桌面 UI 測試

- Google 設定視窗沒有 Search Engine ID。
- 三個封面來源勾選框可獨立操作。
- 原文書名／搜尋別名可以手動輸入。
- 顯示原始書名、清理後書名、卷數、解析別名與 ISBN。
- 中可信度別名要求使用者確認，不會靜默覆蓋查詢。
- 「只輸出內文」首次載入預設勾選。
- 選擇 EPUB 後顯示正面與封底辨識狀態。
- 中可信度封底要求使用者確認。

### 完整驗證

- Windows、macOS、Ubuntu 共用及桌面測試。
- Desktop offscreen smoke、編譯與結構檢查。
- Windows portable PyInstaller 建置與封裝後 EXE smoke。
- 使用至少三種測試 EPUB：只有正面、正面加明確封底、正文末端含一般插圖但沒有封底。
- 使用至少三種跨語言書目案例：中文譯名可找到日文原名、英文譯名可找到原文名、同系列不同卷不會錯配 ISBN。

## 驗收標準

1. 新使用者只填 Google Books API Key 即可使用 Google Books。
2. 沒有任何 API Key 時，Open Library、Wikidata 與 Gutendex 仍能工作。
3. 每個免費封面來源都能單獨關閉，且錯誤互不連帶。
4. 只有中文譯名的 EPUB 能在有可靠資料時解析出原文名或 ISBN，並用於 Open Library 查詢。
5. 解析器找不到可靠原名時，原始譯名搜尋仍正常執行，並允許使用者手動填別名。
6. 同名但作者不同、媒體類型不同或卷數不同的候選不會被自動採用。
7. 含正面與封底的 EPUB 建立專案後，畫布顯示兩張來源圖片，沒有自動文字與條碼。
8. 「只輸出內文」預設勾選，輸出文件不含已確認的正面封面及封底頁。
9. 取消該選項後，輸出恢復 EPUB 原有閱讀順序。
10. 正文插圖不會被自動刪除。
11. 不需要付費服務，也不整合 Z-Library。
