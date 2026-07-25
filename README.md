# EPUB／Word 排版工具 Android 離線版

這是桌面版 v0.5.0 的 Android 離線移植專案。應用程式使用 Android 系統文件選擇器讀取 EPUB／DOCX，再將可編輯的 DOCX 儲存到使用者指定的位置；文件內容不會上傳網路。

## 功能

- EPUB → A4 四格
- EPUB → A6 標準 16 頁書帖
- EPUB → A5 一頁一張
- EPUB → 4×6 英吋一頁一張
- DOCX → A5 重新排版
- DOCX → 4×6 英吋重新排版
- 安全、最大化、無邊界三種邊界
- 字型、內文字級、標題字級、頁碼、裁切線
- 進度顯示與協作式取消
- 完全離線，不要求網路或全域儲存權限

## 系統需求

- Android 7.0（API 24）以上
- 64 位元 ARM（arm64-v8a）
- 第一版不支援 32 位元、x86、DRM EPUB、PDF 輸出或 Android 直接列印

## 使用

1. 按「選擇 EPUB 或 DOCX」。
2. 選擇合法的輸出模式。
3. 設定邊界、字型、字級與頁碼。
4. 按「開始轉換」。
5. 轉換完成後，在 Android 系統視窗選擇 DOCX 儲存位置。

DOCX 模式直接修改 Word 文件的頁面尺寸與可流動版面；原始 `w:p` 段落不會按句號或畫面自動換行拆成新段落。過寬表格與內嵌圖片會縮到可用寬度。

## 建置

請看 [BUILDING.md](BUILDING.md)。第一次建置需要網路下載 Android、Gradle、Compose、Chaquopy 及 Python wheel；安裝後的 App 轉換文件不需要網路。

目前已完成與尚待 Android 建置環境驗證的項目，請看 [BUILD_STATUS.md](BUILD_STATUS.md)。

## 隱私

`AndroidManifest.xml` 不宣告 `INTERNET`、`MANAGE_EXTERNAL_STORAGE`、傳統讀寫外部儲存權限。App 只能存取使用者在系統文件選擇器中明確選取的檔案及目的位置。

## 已知限制

- SVG 若需要 CairoSVG 才能轉換，Android 第一版會列出警告並略過該 SVG；一般 JPEG、PNG、GIF、WebP 可使用 Pillow。
- 浮動 Word 圖形、文字方塊與絕對定位物件在縮小紙張後可能需要人工微調。
- 應用程式被系統終止後，不恢復正在執行的轉換。

## Cross-platform cover core (Tasks 1–10)

The canonical `epub_a4_word.cover` package includes schema-v1 project JSON, EPUB/DOCX/PDF metadata inspection, spine and A4 geometry, deterministic templates, Pillow preview rendering, exact A4 PDF export, editable A4 DOCX export, a unified service API, Android JSON wrappers, and golden structural acceptance tooling through Task 10.

Core QA commands:

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
python3.13 scripts/inspect_cover_exports.py PROJECT.json COVER.pdf COVER.docx
python3.13 scripts/compare_cover_geometry.py LEFT.json RIGHT.json --tolerance-mm 0.05
```

## 電腦版 PySide6

- Windows、macOS、Linux 使用相同 PySide6 介面。
- `epub2a4-desktop` 預設啟動 PySide6；`epub2a4-desktop --legacy-gui` 暫時開啟舊 Tkinter 介面。
- 轉換頁保留 EPUB 的 A4 四格、A6 書帖、A5、4×6，以及 DOCX 的 A5、4×6 模式。
- 封面工具可使用 EPUB 內建圖片或本機圖片；此階段尚未啟用網路搜尋。
- 畫布、屬性欄與封面專案中的位置及尺寸都以毫米儲存；縮放只影響畫面顯示。
- 封面 PDF 與 DOCX 獨立輸出，不修改正文來源檔。

安裝與驗證：

```bash
python3.13 -m pip install -e ".[test]"
python3.13 -m pip install "PySide6==6.11.1" "pytest-qt>=4.4,<5" "keyring==25.7.0" "platformdirs==4.10.1"
QT_QPA_PLATFORM=offscreen python3.13 -m pytest desktop/tests -q
QT_QPA_PLATFORM=offscreen python3.13 scripts/desktop_smoke.py
```

啟動：

```bash
epub2a4-desktop
epub2a4-desktop --legacy-gui
```

### 封面專案

使用「儲存專案」建立 `.cover.json` 與同層的 `<專案檔名>_assets/` 資料夾。圖片依 SHA-256 去重後複製，JSON 只儲存相對路徑；重新開啟時，相對資產路徑會以專案所在目錄解析。移動專案時必須同時移動 JSON 與其資產資料夾。

本機圖片與 EPUB 內建圖片都會先複製到工作資產目錄，不會回寫或修改來源 EPUB。單張圖片上限為 50 MiB，最大像素尺寸為 20000 × 20000。

### 快捷鍵

- Ctrl+Z：復原
- Ctrl+Shift+Z：重做
- Ctrl+0：符合視窗
- Ctrl+1：100%

### DOCX 相容性

PDF 是列印基準。DOCX 保留錨定圖片、真正文字框、裁切線、拼接標記與 A4 sections，方便後續編輯；Word 與 LibreOffice 對部分浮動文字框、字型替代及絕對定位的呈現可能略有差異，列印前應以輸出的 PDF 對照。

封面網路搜尋、Android 封面 UI 與桌面後續發行封裝不屬於目前完成的桌面 Tasks 1–10。
