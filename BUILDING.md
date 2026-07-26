# 建置與驗證

## 共用需求

- Python 3.13（64 位元）。
- Git。
- 建議使用隔離虛擬環境。
- 要執行實際 DOCX 頁數／尺寸測試，需安裝 LibreOffice `soffice` 與 Poppler `pdfinfo`。

安裝共用測試依賴：

```bash
python3.13 -m pip install -e ".[test]"
```

共用驗證：

```bash
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
python3.13 -m compileall -q python/src app/src/main/python scripts
python3.13 scripts/verify_project.py
```

`python-tests/test_single_page_blank_page_regression.py` 會在可用時呼叫 LibreOffice 與 `pdfinfo`，確認：

- A5 是 148 × 210 mm。
- 4×6 是 101.6 × 152.4 mm。
- B6-on-A5 的外部紙張是 A5。
- 產生 N 個內容頁時，PDF 也必須恰好為 N 頁。

## PySide6 桌面版

安裝：

```bash
python3.13 -m pip install -e ".[test,desktop]"
```

測試與 smoke：

```bash
QT_QPA_PLATFORM=offscreen \
PYTHONPATH=python/src:app/src/main/python \
python3.13 -m pytest desktop/tests -q

QT_QPA_PLATFORM=offscreen python3.13 scripts/desktop_smoke.py --offscreen
```

啟動：

```bash
epub2a4-desktop
```

桌面 GitHub Actions：`.github/workflows/desktop.yml`

該 workflow 在 Ubuntu、Windows、macOS 的 Python 3.13 上執行：

- 共用 Python 測試。
- PySide6／pytest-qt 桌面測試。
- offscreen smoke。
- Python 編譯與專案結構檢查。
- 驗證後的完整來源封裝。

## Windows 可攜版

本機需要 Windows x64 與 Python 3.13：

```powershell
python -m pip install -e ".[test,desktop,portable]"
python -m PyInstaller --clean --noconfirm packaging/windows/EPUB2A4.spec
New-Item -ItemType File -Path "dist/EPUB2A4-Windows-Portable-x64/portable.flag" -Force
python scripts/verify_windows_portable.py dist/EPUB2A4-Windows-Portable-x64
```

封裝後 smoke：

```powershell
& "dist/EPUB2A4-Windows-Portable-x64/EPUB2A4.exe" --portable-smoke-test
if ($LASTEXITCODE -ne 0) { throw "portable smoke failed" }
```

GitHub Actions：`.github/workflows/windows-portable.yml`

工作流程會建立並上傳：

```text
EPUB2A4-Windows-Portable-x64.zip
EPUB2A4-Windows-Portable-x64.zip.sha256
Windows-portable-verification-reports
```

必須確認 ZIP 內同時存在：

```text
EPUB2A4.exe
_internal/PySide6/plugins/platforms/qwindows.dll
```

## Android APK

建議環境：

- Android Studio。
- Android SDK 36。
- JDK 17。
- Gradle 8.13。
- Python 3.13（64 位元）。

若 Chaquopy 找不到 Python，在使用者的 `~/.gradle/gradle.properties` 加入：

```properties
chaquopyBuildPython=/完整路徑/python3.13
```

Android Studio：

1. 開啟專案根目錄。
2. 安裝 Android SDK 36／Build Tools。
3. 等待 Gradle Sync。
4. 選擇 `Build > Build APK(s)`。
5. Debug APK 位於 `app/build/outputs/apk/debug/app-debug.apk`。

命令列：

```bash
gradle --no-daemon testDebugUnitTest assembleDebug
```

APK 驗證：

```bash
apkanalyzer manifest permissions app-debug.apk
apkanalyzer files list app-debug.apk | grep '^lib/'
zipalign -c -P 16 -v 4 app-debug.apk
```

預期：

- API 24–36。
- 原生 ABI 只有 `arm64-v8a`。
- 沒有 `android.permission.INTERNET`。
- 沒有傳統全域讀寫儲存權限。
- 16 KB zip alignment 通過。

Android GitHub Actions：`.github/workflows/android.yml`

## 發佈前驗證矩陣

每次正式交付至少需要：

1. 全部共用 Python 測試通過。
2. Ubuntu／Windows／macOS 桌面測試通過。
3. Desktop offscreen smoke 通過。
4. Android Kotlin 單元測試、Debug APK 與 16 KB alignment 通過。
5. Windows PyInstaller onedir、封裝後 EXE smoke、ZIP 重新解壓驗證及 SHA-256 通過。
6. 以只有正面、明確正面＋封底、書末普通插圖三種 EPUB 驗證封面辨識。
7. 以中文譯名、英文譯名及同系列不同卷驗證跨語言查詢不錯配。
8. 以三頁 A5、4×6、B6-on-A5 文件驗證無空白頁及正確紙張尺寸。
9. 最後在 Windows Microsoft Word 實機檢查頁數、裁切位置及列印結果。

舊 DOCX、舊封面專案及舊 Windows portable 不會自動取得修正，必須重新轉換、重建專案或重新下載新版封裝。
