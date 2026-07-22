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
