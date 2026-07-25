# 重建狀態

## 已驗證

- Python 轉換核心與 Android Bridge：完整測試套件通過。
- DOCX 測試文件可透過 Bridge 重新排版為 A5 DOCX。
- EPUB 測試文件可透過 Bridge 轉換為 4×6 DOCX，進度回呼與圖片統計正常。
- Android Python 原始碼可由 Python 編譯器解析。
- Kotlin 的資料模型 smoke test 通過。
- 全部 Kotlin 應用程式原始碼已用 Android／Compose／Chaquopy API stub 做型別編譯檢查。
- 專案只設定 `arm64-v8a`，且 Manifest 不要求網路或傳統全域儲存權限。

## 尚待外部 Android 建置環境驗證

目前執行環境沒有 Android SDK、Gradle 發行版或 Android 模擬器，因此尚未在此環境產生 APK，也尚未聲稱完成實機驗證。

專案附有 GitHub Actions 工作流程。將原始碼推送到 GitHub 後，工作流程會安裝 Android SDK 36、執行測試、建立 Debug APK，並用 `zipalign -P 16` 檢查 16 KB 對齊。

## Cover core Task 10 status

Tasks 1–10 of the shared cover core and export plan are implemented and covered by Python acceptance tests. The completed scope includes editable OOXML DOCX sections, unified service and Android JSON bridge APIs, golden PDF/DOCX structure checks, geometry comparison, and CoverProject schema-v1 documentation.

The shared-core plan did not include platform UI work. Desktop PySide6 integration is now completed below; Android cover UI remains separate. The existing Android conversion application constraints remain API 24–36, arm64-v8a only, offline, and without broad storage permissions.

## Desktop PySide6 Task 10 status

Desktop Tasks 1–10 are implemented on `feature/cross-platform-cover-tool`. GitHub Actions installs the real PySide6 6.11.1、pytest-qt、keyring and platformdirs packages and runs the shared core tests, all desktop tests, compileall, project verification, and the end-to-end offscreen smoke script on Ubuntu、Windows、macOS with Python 3.13.

The desktop smoke gate opens `MainWindow`, navigates to `COVER`, loads a schema-v1 project, renders a preview through the shared cover service, and exports independently validated PDF and DOCX files. The old Tkinter UI remains available only through `--legacy-gui`; CI cannot visually inspect a native Tk window in a headless runner, so its import-order and dispatch behavior remain covered by automated tests rather than a visible-window assertion.

Not included in this completed desktop plan: Android cover UI and online image search.
