# EPUB／Word 排版工具 Android 離線版

這是桌面版 v0.6.0 的 Android 移植與跨平台桌面專案。應用程式使用系統文件選擇器讀取 EPUB／DOCX，再將可編輯的 DOCX 儲存到使用者指定的位置；文件轉換內容不會上傳網路。Windows 封面工具只有在使用者啟用封面搜尋時，才會將 ISBN、書名、作者或搜尋關鍵字送到圖片來源。

## 功能

- EPUB → A4 四格
- EPUB → A6 標準 16 頁書帖
- EPUB → A5 一頁一張
- EPUB → 4×6 英吋一頁一張
- EPUB → B6 內容置於 A5 紙張（普通列印或附裁切標記）
- DOCX → A5／4×6 英吋重新排版
- 安全、最大化、無邊界三種邊界
- 字型、內文字級、標題字級、頁碼、裁切線
- 進度顯示與協作式取消

## 系統需求

- Android 7.0（API 24）以上；64 位元 ARM（arm64-v8a）
- Windows 可攜版不需要另外安裝 Python 或 PySide6
- 第一版不支援 32 位元 Android、DRM EPUB、Windows Authenticode 簽章、自動更新或安裝程式

## Android 使用

1. 按「選擇 EPUB 或 DOCX」。
2. 選擇合法的輸出模式。
3. 設定邊界、字型、字級與頁碼。
4. 按「開始轉換」。
5. 轉換完成後，在 Android 系統視窗選擇 DOCX 儲存位置。

DOCX 模式直接修改 Word 文件的頁面尺寸與可流動版面；原始 `w:p` 段落不會按句號或畫面自動換行拆成新段落。過寬表格與內嵌圖片會縮到可用寬度。

## 建置

請看 [BUILDING.md](BUILDING.md)。第一次建置需要網路下載 Android、Gradle、Compose、Chaquopy、Python wheel 或桌面依賴；安裝後的文件轉換不需要網路。

目前已完成與待人工驗證項目請看 [BUILD_STATUS.md](BUILD_STATUS.md)。

## 隱私

文件轉換在本機完成。Windows 封面搜尋不會上傳 EPUB、DOCX 或 PDF 原檔，只會傳送 ISBN、書名、作者、語系或使用者輸入的關鍵字。Google Custom Search 的 API Key 與 Search Engine ID 不會寫入原始碼、封裝檔、搜尋結果或錯誤訊息。

## Cross-platform cover core

`epub_a4_word.cover` 包含 schema-v1 封面專案、EPUB／DOCX／PDF 中繼資料檢查、書脊與展開幾何、模板、Pillow 預覽、PDF／DOCX 輸出、搜尋提供者、下載驗證及完整書衣合成。

核心 QA 命令：

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
python3.13 scripts/inspect_cover_exports.py PROJECT.json COVER.pdf COVER.docx
python3.13 scripts/compare_cover_geometry.py LEFT.json RIGHT.json --tolerance-mm 0.05
```

## 電腦版 PySide6

- Windows、macOS、Linux 使用相同 PySide6 介面。
- `epub2a4-desktop` 預設啟動 PySide6；`epub2a4-desktop --legacy-gui` 暫時開啟舊 Tkinter 介面。
- 轉換頁保留原有模式，並新增「B6 內容置於 A5 紙張」。
- B6 模式保持 Word 紙張為 A5（148 × 210 mm），將可編輯 EPUB 內容重新排版到中央 B6（128 × 182 mm）區域；可選普通列印或 8 段外部裁切標記。
- 畫布、屬性欄與封面專案的位置及尺寸都以毫米儲存；縮放只影響畫面顯示。
- 封面 PDF 與 DOCX 獨立輸出，不修改正文來源檔。

安裝與驗證：

```bash
python3.13 -m pip install -e ".[test,desktop]"
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests -q
QT_QPA_PLATFORM=offscreen python3.13 scripts/desktop_smoke.py
```

啟動：

```bash
epub2a4-desktop
epub2a4-desktop --legacy-gui
```

### Windows 封面搜尋

建立 EPUB、DOCX 或 PDF 封面專案後：

1. 檔案內建封面會立即顯示。
2. 程式依 ISBN、書名與作者背景查詢 Google Books 和 Open Library。
3. 已儲存 Google Custom Search 憑證時，會同時搜尋正面、背面、書脊、完整書衣與實拍參考圖。
4. 未設定憑證時不會跳出阻擋視窗，只顯示「設定圖片搜尋」。
5. 結果會自動提出分類，但可由使用者改成正面、背面、書脊、完整書衣、參考圖或無法判定。
6. 程式不會自動套用第一張，也不會生成圖片。

選取素材後可以：

- **分區編輯**：將正面、背面、書脊分別加入畫布；每張圖仍可裁切、縮放、移動、替換、刪除及復原。
- **合成完整書衣**：依背面 → 書脊 → 正面的印刷順序合成一張 PNG，再作為完整展開圖片編輯；已是完整書衣的候選可直接使用。

一般圖片搜尋需要使用者自己的 Google API Key 與 Search Engine ID。標準 Windows 模式優先使用系統憑證庫；可攜模式預設只保留本次工作階段，明文儲存到可攜資料夾前會再次警告。

搜尋到的圖片均為網路上既有素材。每張卡片會顯示來源與授權提示；除非提供者明確回傳權利資訊，使用者仍需自行確認使用權。

### 封面專案

使用「儲存專案」建立 `.cover.json` 與同層的 `<專案檔名>_assets/` 資料夾。圖片依 SHA-256 去重後複製，JSON 只儲存相對路徑；移動專案時必須同時移動 JSON 與資產資料夾。

本機、內嵌與搜尋圖片都會先複製到工作資產目錄，不會回寫來源文件。搜尋圖片下載上限為 50 MiB，解碼尺寸上限為 20,000 × 20,000 像素，且只接受 HTTPS 與可實際解碼的圖片。

### 快捷鍵

- Ctrl+Z：復原
- Ctrl+Shift+Z：重做
- Ctrl+0：符合視窗
- Ctrl+1：100%

### DOCX 相容性

PDF 是封面列印基準。DOCX 保留錨定圖片、文字框、裁切線、拼接標記與 sections，方便後續編輯；Word 與 LibreOffice 對浮動物件、字型替代及 VML 裁切標記的呈現可能略有差異，列印前應人工核對。

## Windows 可攜式版本

GitHub Actions 的 `Windows portable EXE` 工作流程會在 `windows-latest` 與 Python 3.13 上執行測試、以 PyInstaller onedir 建立程式、實際啟動封裝後的 EXE，並上傳：

```text
EPUB2A4-Windows-Portable-x64.zip
EPUB2A4-Windows-Portable-x64.zip.sha256
```

使用方式：

1. 下載 `EPUB2A4-Windows-Portable-x64` artifact。
2. 將 ZIP 完整解壓縮。
3. 進入同名資料夾並雙擊 `EPUB2A4.exe`。

不可只複製 EXE，也不可刪除 `_internal`。可攜版以同層 `portable.flag` 啟用 `data/` 資料目錄。第一版未簽署 Authenticode，因此 SmartScreen 可能顯示未知發行者；請核對同一 artifact 中的 SHA-256。
