# 重建狀態

## 已驗證

- Python 轉換核心與 Android Bridge：完整測試套件通過。
- DOCX 測試文件可透過 Bridge 重新排版為 A5 DOCX。
- EPUB 測試文件可透過 Bridge 轉換為 4×6 DOCX，進度回呼與圖片統計正常。
- Android Python 原始碼可由 Python 編譯器解析。
- Kotlin 的資料模型 smoke test 通過。
- 全部 Kotlin 應用程式原始碼已用 Android／Compose／Chaquopy API stub 做型別編譯檢查。
- 專案只設定 `arm64-v8a`，且 Manifest 不要求網路或傳統全域儲存權限。
- 共用封面核心 Task 10（Tasks 1–10）已通過 CoverProject schema、PDF／DOCX 結構、golden geometry 與 service bridge 驗收。
- 桌面 PySide6 Task 10（Tasks 1–10）由 GitHub Actions 在 Ubuntu、Windows、macOS 的 Python 3.13 與 `QT_QPA_PLATFORM=offscreen` 執行。
- 桌面驗收涵蓋預設 PySide6／legacy Tkinter 分流、完整轉換模式、HOME／CONVERTER／COVER 導覽、毫米畫布、封面素材與裁切、可攜式專案，以及獨立 PDF／DOCX 匯出。
- `scripts/desktop_smoke.py --offscreen` 會實際建立主視窗、走過轉換與封面路由、渲染預覽並驗證雙格式輸出。

## GitHub Actions 驗證

- `Desktop PySide6 tests`：Python 3.13，Ubuntu／Windows／macOS，正式安裝 PySide6 6.11.1、pytest-qt、keyring、platformdirs。
- `Android debug APK`：安裝 Android SDK 36、執行測試、建立 Debug APK，並執行 16 KB 對齊檢查。
- 經驗證的桌面 Tasks 8–10 原始碼與 SHA-256 會由 Linux job 以 workflow artifact 交付。

## 尚待驗證或後續計畫

- 尚未進行 Android UI（封面編輯介面）。
- 尚未加入封面網路搜尋。
- 尚未執行桌面安裝程式、簽章、公證或自動更新等 release packaging。
- 無顯示的 CI 使用 Qt offscreen 平台；實體螢幕上的視覺細節、系統字型差異與原生檔案選擇器仍需人工桌面驗收。
- PDF 是列印基準；Word 與 LibreOffice 對部分浮動文字框、字型替代及絕對定位的呈現可能略有差異。

Android 轉換應用程式仍維持 API 24–36、arm64-v8a、離線且不要求傳統全域儲存權限。
