# 重建狀態

## 已驗證

- Python 轉換核心與 Android Bridge：既有完整測試套件通過。
- 共用封面核心已通過 CoverProject schema、PDF／DOCX 結構、golden geometry 與 service bridge 驗收。
- 桌面 PySide6 既有功能由 GitHub Actions 在 Ubuntu、Windows、macOS 的 Python 3.13 與 Qt offscreen 執行。
- Windows 可攜式 PyInstaller onedir、Qt `qwindows.dll`、封裝後 EXE smoke 與 ZIP 驗證已有成功基準。
- 新增封面搜尋／分類、下載限制、完整書衣合成及 B6-on-A5 幾何的焦點檢查。
- B6-on-A5 測試文件保持 A5 紙張、中央 128 × 182 mm 內容區，裁切模式產生 8 段外部標記。

## GitHub Actions 驗證

- `Desktop PySide6 tests`：Python 3.13，Ubuntu／Windows／macOS，正式安裝 PySide6、pytest-qt、keyring、platformdirs。
- `Android debug APK`：安裝 Android SDK、執行測試、建立 Debug APK並檢查 16 KB 對齊。
- `Windows portable EXE`：執行焦點功能測試、建立 PyInstaller onedir、檢查 Qt plugin、實際執行 `EPUB2A4.exe --portable-smoke-test`，並重新解壓 ZIP 驗證封裝內容。

## 2026-07-25：進入 Windows 實機驗收階段

本階段以最新 `main` 重新建立 Windows portable ZIP。只有 workflow 全綠、封裝後 EXE smoke 通過且 ZIP 驗證成功，才交付使用者進行實機驗收。

實機驗收順序：

1. 啟動 `EPUB2A4.exe`，確認首頁、轉換頁與封面工具可以正常開啟。
2. 使用一個含書名、作者與 ISBN 的 EPUB 建立封面專案，確認 Google Books 與 Open Library 自動回傳正面封面候選。
3. 設定 Google Custom Search API Key 與 Search Engine ID，確認正面、背面、書脊、完整書衣及參考照片搜尋均可用，且重新啟動後的憑證行為符合標準／portable 模式規則。
4. 選擇候選圖片後人工修改分類，確認結果不會自動套用，並測試分區套用與完整書衣合成。
5. 以同一本 EPUB 轉換 `B6 內容置於 A5 紙張`：分別輸出普通列印與附裁切標記版本。
6. 在 Microsoft Word 檢查頁面尺寸為 A5、內容區為中央 B6、文字仍可編輯、圖片未超出裁切區，且裁切版本每頁有 8 段外部標記。
7. 以 A5 紙張實際列印至少一頁，量測裁切後尺寸是否為 128 × 182 mm，並確認裁切線不穿過文字、圖片或頁碼。

## 本次新增、待使用者實機驗收

- Windows 依中繼資料自動搜尋 Google Books 與 Open Library 正面封面。
- 已設定使用者憑證時，自動搜尋正面、背面、書脊、完整書衣與實拍參考圖。
- 候選自動分類但可人工修正；不自動套用、不生成圖片。
- 分區編輯與背面 → 書脊 → 正面完整書衣合成。
- EPUB 語意重排成 B6 內容置於 A5 紙張，普通列印或附裁切標記。
- 真實 Google Books、Open Library、Google Custom Search 結果、Windows 系統憑證庫、Word 列印裁切位置與原生 UI 視覺仍需使用者在 Windows 實機確認。

## 尚待驗證或後續計畫

- Android UI 的實體裝置人工驗收仍待完成；本次 Windows 功能不修改 Android UI。
- 尚未執行 Windows Authenticode 簽章、安裝程式、自動更新或 macOS 公證。
- Word 與 LibreOffice 對浮動物件、字型替代及 VML 裁切標記可能略有差異。

Android 轉換應用程式仍維持 API 24–36、arm64-v8a，文件轉換在本機執行且不要求傳統全域儲存權限。
