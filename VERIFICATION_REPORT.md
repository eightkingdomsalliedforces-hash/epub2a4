# 重建驗證報告

驗證日期：2026-07-22

## 已執行檢查

| 項目 | 結果 |
|---|---|
| Android Bridge 與核心 Python 測試 | 40 passed |
| Android Python 原始碼 `compileall` | 通過 |
| 專案結構、API、ABI、權限、測試文件檢查 | 通過 |
| Kotlin 資料模型 smoke test | 通過 |
| 全部 Kotlin App 原始碼對 Android／Compose／Chaquopy API stub 編譯 | 通過 |
| Git 空白與修補格式檢查 | 通過 |

## 實際轉換檢查

### DOCX → A5

- 輸入：合成 A4 DOCX 測試文件
- 輸出大小：42,167 bytes
- 頁面尺寸：8,391 × 11,906 twips（A5）
- 內嵌圖片：1
- 進度回呼：4 次

### EPUB → 4×6 英吋

- 輸入：合成 EPUB 測試文件
- 輸出大小：37,860 bytes
- 頁面尺寸：5,760 × 8,640 twips（4 × 6 英吋）
- 內嵌圖片：1
- 內容頁：2
- 進度回呼：5 次

## 尚未完成的驗證

目前工作容器沒有 Android SDK、Gradle 發行版、Android 模擬器或可連接的實機，因此未在此容器執行：

- `testDebugUnitTest`
- `assembleDebug`
- APK 安裝與啟動
- Android 15／16 之 16 KB 實機轉換

專案已提供 `.github/workflows/android.yml`，會在 GitHub Actions 中安裝 Android SDK 36、執行測試、建立 Debug APK，並執行 `zipalign -P 16`。
