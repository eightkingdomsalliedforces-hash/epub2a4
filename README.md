# EPUB2A4：EPUB／Word 排版與書封工具

EPUB2A4 是跨平台文件排版專案，包含：

- Android 離線轉換應用程式。
- Windows／macOS／Linux 的 PySide6 桌面程式。
- EPUB、DOCX 共用轉換核心。
- 可編輯書封專案、PDF／DOCX 封面輸出與免費封面搜尋。

正文轉換在本機執行，不會上傳 EPUB、DOCX、PDF、正文或本機圖片。桌面封面搜尋只有在使用者主動執行時，才會傳送書名、作者、ISBN、語言及使用者輸入的正式別名。

## 轉換功能

- EPUB → A4 四格。
- EPUB → A6 標準 16 頁書帖。
- EPUB → A5 一頁一張。
- EPUB → 4×6 英吋一頁一張。
- EPUB → B6 內容置於 A5 紙張，可選普通列印或裁切標記。
- DOCX → A5／4×6 英吋可流動版面。
- 安全、最大化、無邊界三種邊界。
- 字型、內文字級、標題字級、行距、段距、頁碼及裁切線設定。
- 背景進度與協作式取消。

### 紙張尺寸與空白頁防護

單頁模式使用以下實際紙張尺寸：

| 模式 | DOCX／PDF 紙張尺寸 |
|---|---:|
| A5 | 148.0 × 210.0 mm |
| 4×6 英吋 | 101.6 × 152.4 mm |
| B6 內容置於 A5 | 外部紙張 148.0 × 210.0 mm；內容區 128.0 × 182.0 mm |

A5、4×6 與 B6-on-A5 都使用單一頂層 OOXML 表格，每個實體頁面對應一個不可拆分的固定高度列，以避免 Microsoft Word 因隱藏前置段落或頁面間分頁段落產生額外空白頁。A5、4×6、B6-on-A5、A4 四合一與 16 頁裝訂現在共用同一套固定 Word 行高、段後距與底部安全區；分頁器與 DOCX 寫入器不再各自估算，因此長篇中日文、英文及混排文字會在進入紙張邊界前拆頁。舊 DOCX 不會自動修復，必須用新版重新轉換。

### 只輸出內文

EPUB 轉換預設勾選：

> 只輸出內文，不含封面與封底

程式只會排除高可信度的正面封面與封底頁；一般正文插圖、章節插畫及含實質文字的頁面不會被刪除。疑似封底必須由使用者確認後才能作為封底使用。取消勾選即可保留 EPUB 原始閱讀順序。桌面版與 Android 版都提供此選項；DOCX 重新排版不受影響。

## EPUB 內嵌正面與封底

封面工具會依 EPUB 2／EPUB 3 的 OPF、manifest、spine、guide 與 landmarks 判斷：

- 正面封面。
- 明確標示的封底。
- 位於書末、尺寸相符但只具中可信度的「可能封底」。

明確包含正面與封底的 EPUB 會建立兩個獨立、可裁切與移動的圖片元素，不會合成成固定圖檔，也不會自動加入書名、簡介、出版社、書脊文字或條碼。可能封底只會在使用者勾選確認後採用。

## 免費封面搜尋

桌面版提供三個可個別開關的來源：

- **Google Books**：只需要 Google Books API Key；不需要 Search Engine ID。
- **Open Library**：不需要 API Key。
- **Project Gutenberg（Gutendex）**：不需要 API Key，主要補充公版書與古典文學。

搜尋前會建立有優先順序的查詢：

1. 通過校驗的 ISBN-13／ISBN-10。
2. 使用者手動輸入的原文書名、英文名或正式別名。
3. EPUB 原始書名與作者。
4. 清理格式標記並拆出卷數後的書名。
5. Google Books 回傳的標準化書名與 ISBN。
6. Wikidata 解析出的日文、英文及其他語言正式名稱。

Wikidata 只用於跨語言名稱與識別碼解析，不提供封面圖片。作者不同、卷數不同或同名電影／動畫／遊戲不會被自動採用。Open Library 因中文譯名找不到作品時，會改用解析出的原名、英文名或 ISBN 再查詢。

中可信度別名會逐項顯示「確認並使用」與「忽略」。未確認的名稱不會進入 Open Library 等來源的查詢，也不會寫入永久快取；確認後會重新搜尋，並且只有在使用者實際選定候選封面後才保存。成功且由使用者選用的正式別名可保存在本機。系列名稱可以跨卷重用，但舊卷 ISBN 不會套用到新卷。

程式不整合 Z-Library、不下載完整電子書，也不使用付費 ISBN API 或不穩定的書站爬蟲。

## Google Books API Key

1. 在 Google Cloud 建立專案。
2. 啟用 Books API。
3. 建立 API Key。
4. 在桌面程式開啟「Google Books API 設定」並貼上金鑰。

未設定金鑰時只會略過 Google Books，Open Library 與 Project Gutenberg 仍可使用。舊憑證檔若含 `search_engine_id` 仍可讀取，但新流程會忽略該欄位，新的可攜憑證檔只儲存 `api_key`。

## 書封專案

`epub_a4_word.cover` 提供：

- schema-v1 `.cover.json` 專案。
- EPUB／DOCX／PDF 中繼資料與內嵌圖片檢查。
- 正面、封底、書脊與完整展開幾何。
- 毫米座標的可編輯元素。
- Pillow 預覽。
- PDF／DOCX 書封輸出。
- 本機圖片、EPUB 內嵌圖片與網路候選素材。

使用「儲存專案」會建立 `.cover.json` 與同層 `<專案檔名>_assets/`。圖片以 SHA-256 去重並使用相對路徑；移動專案時必須同時移動 JSON 與資產資料夾。

網路圖片下載只接受 HTTPS、限制為 50 MiB、最大解碼尺寸 20,000 × 20,000 像素，且必須能由 Pillow 實際解碼。搜尋結果不會自動套用第一張，圖片權利仍需由使用者依來源確認。

### 封面輸出檔案

每次封面匯出會先顯示實際列印分頁、重疊區與檔名，然後產生：

- `<書名>-完整書衣-原始尺寸.pdf`：單頁、自訂原始尺寸、100% 比例，適合印刷店或大尺寸輸出。
- `<書名>-A4拼接列印.pdf`：完整書衣可放入橫向 A4 時為一頁；放不下時只分成「封底側」與「正面側」兩頁。
- `<書名>-A4拼接列印.docx`：與 A4 PDF 使用同一列印計畫，頁數、方向與重疊區一致。

不再輸出編輯器中不存在的獨立細長書脊頁。A4 拼接版會標示頁面用途、重疊黏貼區及「100% 實際大小列印」；列印時必須關閉「符合紙張大小」或其他自動縮放。封底區域沒有可見圖片時，匯出前會要求選擇「返回補上封底」或「仍然輸出空白封底」。

## Android 使用

系統需求：

- Android 7.0（API 24）以上。
- 64 位元 ARM（arm64-v8a）。

操作流程：

1. 選擇 EPUB 或 DOCX。
2. 選擇輸出模式與排版設定。
3. EPUB 可保留預設的「只輸出內文」，或取消以保留原始封面／封底。
4. 開始轉換。
5. 完成後在 Android 系統文件視窗選擇 DOCX 儲存位置。

Android 版本不要求網路權限，也不要求傳統全域儲存權限。DOCX 模式會依原始 Word 段落重新流排；不會按句號或畫面換行拆成新段落。過寬表格及圖片會縮到可用寬度。

## 電腦版 PySide6

系統需求：Windows、macOS 或 Linux；開發環境使用 Python 3.13。

安裝：

```bash
python3.13 -m pip install -e ".[test,desktop]"
```

啟動：

```bash
epub2a4-desktop
```

舊介面仍可暫時使用：

```bash
epub2a4-desktop --legacy-gui
```

快捷鍵：

- `Ctrl+Z`：復原。
- `Ctrl+Shift+Z`：重做。
- `Ctrl+0`：符合視窗。
- `Ctrl+1`：100%。

PDF 是書封列印基準。Word 與 LibreOffice 對浮動物件、替代字型及 VML 裁切標記可能略有差異，正式列印前仍應人工核對。

## Windows 可攜版

GitHub Actions 的 `Windows portable EXE` 會：

- 執行共用及焦點回歸測試。
- 使用 PyInstaller onedir 建置。
- 驗證 Qt `qwindows.dll`。
- 實際執行 `EPUB2A4.exe --portable-smoke-test`。
- 重新解壓 ZIP 後再次驗證。
- 產生 SHA-256。

使用方式：

1. 下載 `EPUB2A4-Windows-Portable-x64.zip`。
2. 完整解壓縮到新資料夾。
3. 執行資料夾內的 `EPUB2A4.exe`。

不可只複製 EXE，也不可刪除 `_internal`。可攜模式以同層 `portable.flag` 啟用 `data/`。目前未簽署 Windows Authenticode，因此 SmartScreen 可能顯示未知發行者。

## 開發與驗證

完整指令請看 [BUILDING.md](BUILDING.md)。常用命令：

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
QT_QPA_PLATFORM=offscreen PYTHONPATH=python/src:app/src/main/python \
  python3.13 -m pytest desktop/tests -q
python3.13 -m compileall -q python/src app/src/main/python scripts
python3.13 scripts/verify_project.py
```

LibreOffice 與 `pdfinfo` 存在時，測試會實際將 DOCX 轉成 PDF，驗證 A5、4×6、B6-on-A5 的頁數與紙張尺寸。

建置與實機驗證狀態請看 [BUILD_STATUS.md](BUILD_STATUS.md)。
## v0.8.0 排版控制

- Desktop 與 Android 預設使用「台灣直排（右裝訂）」；也可切回「橫排（左裝訂）」。
- 台灣直排由上往下閱讀、欄位由右往左排列，中文保持直立。
- 英文與長數字交由 Microsoft Word 的原生直排規則處理，不拆成單字元文字。
- 圖片保持正向，並維持 EPUB／DOCX 原本的內容順序。
- 「顯示頁碼」是唯一頁碼開關：開啟時文字頁與圖片頁都有頁碼；關閉時所有頁面都沒有頁碼，適合漫畫。
- 直排效果以 Microsoft Word 的東亞版面支援為準；其他文書軟體可能有不同的字型替代或旋轉結果。
