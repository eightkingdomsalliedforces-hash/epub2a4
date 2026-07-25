# 免費封面來源、EPUB 封底擷取與只輸出內文設計

日期：2026-07-25

## 目標

本階段改善 EPUB2A4 的封面與轉換流程，要求所有新增網路來源都可免費使用，並避免程式擅自加入或輸出使用者未要求的封面內容。

完成後應具備以下行為：

1. Google Books 僅要求 Google API Key，不再要求 Programmable Search Engine ID。
2. Open Library 保留，但可由使用者個別開關。
3. 新增 Gutendex／Project Gutenberg 作為免費補充來源。
4. EPUB 若內嵌正面封面與封底，封面工具可直接辨識並取用兩者。
5. 轉換頁面新增「只輸出內文，不含封面與封底」，而且預設勾選。
6. 不加入 Z-Library、付費 API 或不穩定的網頁爬蟲。

## 範圍

### 納入

- Google Books API Key 設定與請求流程。
- Open Library、Gutendex 搜尋來源開關。
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

## 使用者介面

### 1. 搜尋來源設定

搜尋封面區顯示三個可獨立勾選的來源：

- Google Books
- Open Library
- Project Gutenberg（Gutendex）

預設狀態：

- Google Books：啟用；未設定 API Key 時顯示「需要 Google Books API Key」。
- Open Library：啟用。
- Project Gutenberg：啟用。

程式至少要求一個來源啟用；全部取消時停用搜尋按鈕並顯示原因。

### 2. Google 設定視窗

現有「Google 圖片搜尋設定」改為「Google Books API 設定」。

只保留：

- Google API Key
- 顯示／隱藏 API Key
- 儲存到系統或可攜資料夾
- 僅本次使用
- 清除已儲存

刪除 Search Engine ID 欄位及其完整性驗證。現有已儲存 JSON 若仍包含 `search_engine_id`，載入時忽略該欄位，不造成錯誤。

### 3. EPUB 來源檢查結果

選擇 EPUB 後，來源檢查區可顯示：

- 已找到正面封面
- 已找到封底
- 未找到封底
- 預估正文頁數

封面工具的預設模板仍是「原始封面（不加文字）」。

### 4. 轉換選項

在轉換頁面新增勾選框：

> 只輸出內文，不含封面與封底

規則：

- 預設勾選。
- 使用者可取消勾選，以保留 EPUB 原有封面頁與封底頁。
- 選項只影響正文 DOCX／PDF 輸出，不刪除 EPUB 檔案，也不影響封面工具擷取圖片。
- 設定應保存在目前的轉換設定或專案狀態中，重新開啟同一工作流程時維持使用者最後選擇；首次使用仍預設勾選。

## 搜尋架構

### 共用介面

所有公開來源實作相同的 provider 介面：

- 輸入：書名、作者、ISBN、語言、最大結果數。
- 輸出：標準化封面候選項目。
- 每個候選項目包含來源、書名、作者、ISBN、預覽網址、原圖網址及來源頁面。

搜尋控制器依使用者勾選項目呼叫 provider，合併並去除重複結果。

### Google Books

- 使用 Books API。
- API Key 透過 `key` 查詢參數傳送。
- 沒有 API Key 時，不呼叫 Google Books；其他免費來源仍可繼續搜尋。
- 不再依賴 Search Engine ID 或 Custom Search JSON API。

### Open Library

- 保留正式 Search API 與 Covers API。
- 使用可識別的 User-Agent。
- 維持保守的一秒一次請求限制。
- 快取相同搜尋與圖片下載結果，減少 429。

### Gutendex／Project Gutenberg

- 使用 Gutendex JSON API。
- 以 `search`、語言及書目資訊查詢。
- 只建立具有可用封面圖片格式的候選項目。
- 標示來源為 Project Gutenberg。
- 主要作為古典文學與公版書補充，不取代 Google Books 或 Open Library。

### 錯誤隔離

每個 provider 的錯誤獨立呈現，例如：

- Google Books：API Key 無效。
- Open Library：暫時限流。
- Project Gutenberg：服務無法連線。

一個來源失敗時，其他來源的成功結果仍然顯示。只有所有已啟用來源都失敗且沒有結果時，搜尋才視為整體失敗。

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

第三級只能標記為「可能的封底」，不能在沒有其他證據時自動排除。介面可顯示候選並讓使用者確認。

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

舊設定缺少 `content_only` 時視為 `true`，符合本階段的預設行為。

## 相容性

- 舊的 Google 憑證檔仍可讀取，只使用 `api_key`。
- 舊轉換設定沒有 `content_only` 時使用新預設 `true`。
- 舊封面專案不自動刪除既有文字元素；新建立的「原始封面」專案才採用不加文字的規則。
- 使用者若需要舊行為，可取消勾選「只輸出內文」或主動套用文字模板。

## 測試策略

### 共用 Python 測試

- Google Books 只需 API Key，沒有 Search Engine ID 也可搜尋。
- 缺少 Google API Key 時只略過 Google Books，不阻斷 Open Library 與 Gutendex。
- Open Library 和 Gutendex 可個別開關。
- provider 部分失敗時仍回傳其他來源結果。
- EPUB 2、EPUB 3 正面封面辨識。
- 明確標示及閱讀順序末端封底辨識。
- 正文插圖不被誤判為封底。
- `content_only=true` 排除已確認的正面與封底頁。
- `content_only=false` 保留所有原始頁面。
- 正面與封底圖片能各自建立封面專案元素，且沒有自動文字或條碼。

### 桌面 UI 測試

- Google 設定視窗沒有 Search Engine ID。
- 三個來源勾選框可獨立操作。
- 「只輸出內文」首次載入預設勾選。
- 選擇 EPUB 後顯示正面與封底辨識狀態。
- 中可信度封底要求使用者確認。

### 完整驗證

- Windows、macOS、Ubuntu 共用及桌面測試。
- Desktop offscreen smoke、編譯與結構檢查。
- Windows portable PyInstaller 建置與封裝後 EXE smoke。
- 使用至少三種測試 EPUB：只有正面、正面加明確封底、正文末端含一般插圖但沒有封底。

## 驗收標準

1. 新使用者只填 Google Books API Key 即可使用 Google Books。
2. 沒有任何 API Key 時，Open Library 與 Gutendex 仍能搜尋。
3. 每個免費來源都能單獨關閉，且錯誤互不連帶。
4. 含正面與封底的 EPUB 建立專案後，畫布顯示兩張來源圖片，沒有自動文字與條碼。
5. 「只輸出內文」預設勾選，輸出文件不含已確認的正面封面及封底頁。
6. 取消該選項後，輸出恢復 EPUB 原有閱讀順序。
7. 正文插圖不會被自動刪除。
8. 不需要付費服務，也不整合 Z-Library。
