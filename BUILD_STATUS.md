# 重建狀態

## 已完成的自動化範圍

- 共用 EPUB／DOCX 轉換核心與 Android Bridge 測試。
- EPUB OPF、manifest、spine、guide、landmarks 與正面／封底角色辨識。
- EPUB 預設只輸出內文，以及保留原始封面／封底的反向選項。
- A5、4×6、B6-on-A5 的 OOXML 空白頁回歸與 PDF 頁數驗證。
- A5 148 × 210 mm、4×6 101.6 × 152.4 mm 的尺寸驗證。
- EPUB 正面與明確封底作為兩個獨立可編輯圖片元素。
- 中可信度封底需使用者確認後才能採用。
- Google Books API-key-only、Open Library、Gutendex 與 Wikidata 跨語言名稱解析。
- 書名正規化、卷數拆分、ISBN 校驗、查詢去重、來源錯誤隔離及本機別名快取。
- Windows／macOS／Ubuntu PySide6 測試架構。
- Windows PyInstaller onedir、Qt `qwindows.dll`、封裝後 EXE smoke、ZIP 與 SHA-256 驗證架構。

## 本次必須重新執行的 GitHub Actions

- `Desktop PySide6 tests`：Ubuntu／Windows／macOS，Python 3.13。
- `Android debug APK`：Kotlin 單元測試、共用 Python、Debug APK、16 KB alignment。
- `Windows portable EXE`：焦點回歸、PyInstaller、封裝後 EXE smoke、ZIP 重新解壓驗證。

只有全部 required checks 通過後才能合併與交付新版 Windows ZIP。

## Windows 實機驗收

CI 全綠後仍需在使用者的 Windows Microsoft Word 實際驗證：

1. 建立三頁 A5 文件，確認 Word 顯示三頁且紙張為 148 × 210 mm。
2. 建立三頁 4×6 文件，確認 Word 顯示三頁且紙張為 101.6 × 152.4 mm。
3. 建立 B6-on-A5 文件，確認沒有前置、頁間或尾端空白頁。
4. 使用含正面與封底的 EPUB，確認封面專案顯示兩張獨立圖片且沒有自動文字／條碼。
5. 使用只有中文譯名的 EPUB，確認可由 Wikidata／Google Books 補出原名或 ISBN，再查 Open Library。
6. 未設定 Google API Key 時，確認 Open Library 與 Project Gutenberg 仍能搜尋。
7. 勾選「只輸出內文」時不輸出已確認封面／封底；取消後恢復 EPUB 原始閱讀順序。
8. 實際列印至少一頁，核對縮放、裁切位置及印表機驅動沒有自動改紙張。

## 尚待人工或發佈基礎設施處理

- Microsoft Word 與實體印表機的最終驗收。
- Android 實體裝置人工轉換與儲存驗收。
- Windows Authenticode、安裝程式與自動更新。
- macOS 簽章與公證。
- 外部免費服務的即時可用性與限流狀況；程式只能隔離錯誤，不能保證第三方永遠在線。

Android 仍維持 API 24–36、arm64-v8a，文件轉換不要求網路或傳統全域儲存權限。桌面封面搜尋不會上傳 EPUB、DOCX、PDF、正文或本機圖片。
