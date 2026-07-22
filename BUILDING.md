# 建置 Android APK

倉庫根目錄的 `android-source.zip` 包含完整 Android Studio 專案。GitHub Actions 會自動解壓、執行 Python 測試、Gradle 單元測試、建立 arm64-v8a Debug APK，並檢查 16 KB APK 對齊。

## GitHub Actions

1. 開啟倉庫的 **Actions**。
2. 選擇 **Android debug APK**。
3. 按 **Run workflow**。
4. 工作完成後下載 `EPUB-Word-Android-debug` artifact。

推送新的 `android-source.zip` 或修改工作流程也會自動觸發建置。

## 本機建置

```bash
unzip android-source.zip
cd EPUB_Word_Android_Offline_v0.1.0
gradle --no-daemon testDebugUnitTest assembleDebug
```

需要 JDK 17、Android SDK 36、Gradle 8.13、Python 3.13。輸出 APK 位於：

```text
app/build/outputs/apk/debug/app-debug.apk
```
