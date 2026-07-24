# 建置 Android APK

## 建議環境

- Android Studio，含 Android SDK 36
- JDK 17
- Python 3.13（64 位元）
- Gradle 8.13

## Android Studio

1. 以 Android Studio 開啟專案根目錄。
2. 安裝缺少的 Android SDK 36／Build Tools。
3. 確認電腦可執行 `python3.13`。若名稱不同，在使用者的 `~/.gradle/gradle.properties` 加入：

   ```properties
   chaquopyBuildPython=/完整路徑/python3.13
   ```

4. 等待 Gradle Sync 完成。
5. 選擇 `Build > Build APK(s)`。
6. Debug APK 位於 `app/build/outputs/apk/debug/app-debug.apk`。

## 命令列

專案不依賴已提交的 Gradle Wrapper JAR；有 Gradle 8.13 時可執行：

```bash
gradle --no-daemon testDebugUnitTest assembleDebug
```

也可以把專案推送到 GitHub，手動執行 `.github/workflows/android.yml`。工作流程會建立並上傳 `EPUB-Word-Android-debug` artifact。

## 本機驗證

```bash
python3.13 -m pip install -e '.[test]'
PYTHONPATH=python/src:app/src/main/python python3.13 -m pytest python-tests -q
PYTHONPATH=python/src:app/src/main/python python3.13 -m compileall -q python/src app/src/main/python
python3.13 scripts/verify_project.py
```

## APK 驗證

產生 APK 後至少執行：

```bash
apkanalyzer manifest permissions app-debug.apk
apkanalyzer files list app-debug.apk | grep '^lib/'
zipalign -c -P 16 -v 4 app-debug.apk
```

預期沒有 `android.permission.INTERNET` 或全域儲存權限，且原生 ABI 只有 `arm64-v8a`。仍需在 Android 15／16 的 16 KB ARM64 環境做啟動與實際轉換驗證。
