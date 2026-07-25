# Windows 可攜式桌面版設計

## 目標

由 GitHub Actions 在 `windows-latest` 與 Python 3.13 上建立可直接執行的 Windows x64 可攜式發行包。使用者下載 `EPUB2A4-Windows-Portable-x64.zip`、解壓縮後，直接雙擊 `EPUB2A4.exe`，不需要另行安裝 Python、PySide6 或 pip 套件。

## 發行格式

採用 PyInstaller `onedir` 模式，而不是單檔 `onefile`：

- 發行資料夾名稱：`EPUB2A4-Windows-Portable-x64`
- 主程式：`EPUB2A4.exe`
- Qt、Python runtime、Pillow、lxml、python-docx、pypdf、keyring 與 platformdirs 等依賴放在同一發行資料夾內
- 最終 artifact：`EPUB2A4-Windows-Portable-x64.zip`
- 同時產生 `EPUB2A4-Windows-Portable-x64.zip.sha256`

`onedir` 可避免單檔版每次啟動先解壓至暫存目錄，並降低啟動時間、封裝除錯難度及防毒誤判機率。

## 封裝入口與功能

PyInstaller 入口沿用 `epub_a4_word_desktop.__main__`，預設啟動 PySide6 主介面，保留現有 EPUB／DOCX 轉換模式、封面編輯器與 PDF／DOCX 匯出功能。`--legacy-gui` 仍由現有命令列分流處理，不在封裝層複製 GUI 邏輯。

為讓 CI 能驗證封裝後的真正 EXE，桌面入口新增內部 `--portable-smoke-test` 參數。該參數只建立 PySide6 application 與主視窗、驗證 HOME／CONVERTER／COVER 路由可用，處理一次事件循環後立即結束並回傳 0；一般使用者不會在正常雙擊流程看到此模式。

## PyInstaller 結構

建立專用 spec：`packaging/windows/EPUB2A4.spec`。

spec 必須：

- 從 `python/src` 收集 `epub_a4_word` 與 `epub_a4_word_desktop`
- 收集 PySide6 所需 Qt plugins、translations 與 DLL
- 收集 Pillow、lxml、bs4、docx、pypdf、keyring、platformdirs 的隱式匯入與資料
- 使用 `console=False`，正常啟動不顯示命令提示字元
- 建立 `EPUB2A4.exe` 的 `COLLECT` onedir 輸出
- 不包含測試、Git metadata、快取、Android build 或來源 ZIP

## GitHub Actions

新增 `.github/workflows/windows-portable.yml`，支援：

- `workflow_dispatch`
- 推送至 `feature/cross-platform-cover-tool`
- PR 合併前檢查

Windows job 依序執行：

1. Checkout。
2. 安裝 Python 3.13。
3. 安裝 `.[test,desktop]` 與 PyInstaller。
4. 執行共用 Python 與桌面測試。
5. 執行現有 offscreen source smoke。
6. 用 spec 建立 onedir。
7. 驗證 `EPUB2A4.exe`、Qt platform plugin 與主要 runtime 檔案存在。
8. 設定 `QT_QPA_PLATFORM=offscreen`，執行封裝後的 `EPUB2A4.exe --portable-smoke-test`。
9. 用 PowerShell `Compress-Archive` 建立 ZIP。
10. 計算 SHA-256。
11. 上傳 ZIP、SHA-256、PyInstaller warnings 與測試報告。

只有測試、封裝及封裝後 EXE smoke 全部成功時才上傳正式 portable artifact。

## TDD 與驗收

先加入 `desktop/tests/test_windows_portable_packaging.py`，在 spec、workflow 與 smoke 入口尚不存在時確認 RED。測試至少驗證：

- spec 採 onedir `COLLECT` 且名稱為 `EPUB2A4`
- spec 關閉 console
- workflow 使用 `windows-latest`、Python 3.13、PyInstaller、封裝後 smoke、ZIP 與 SHA-256
- portable smoke 參數由桌面入口處理
- legacy 分流規則沒有被破壞

GREEN 階段除了 Python 測試外，以 GitHub Windows runner 實際建立並執行 EXE 作為最終判定。

## 使用者體驗與限制

使用方式：下載 artifact、解壓縮全部內容、雙擊 `EPUB2A4.exe`。不可只複製 EXE 或刪除旁邊的 `_internal`／Qt runtime 檔案。

第一版不進行 Windows Authenticode 程式碼簽章，因此 SmartScreen 可能顯示未知發行者。這是簽章限制，不表示封裝測試失敗。工作流程不建立安裝程式、不修改系統登錄、不加入自動更新，也不改動 Android UI 或搜尋功能。
