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
- `Windows portable EXE`：執行共用與桌面測試、建立 PyInstaller onedir、檢查 Qt plugin、實際執行 `EPUB2A4.exe --portable-smoke-test`，只有完整 workflow GREEN 才視為本次版本已驗證。

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
