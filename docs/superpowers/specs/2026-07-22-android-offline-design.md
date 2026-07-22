# EPUB／Word 版面轉換工具 Android 離線版設計

## 1. 目標

建立一個完全離線、僅支援 64 位元 ARM Android 裝置的應用程式，將目前桌面版 v0.5.0 的 EPUB 與 DOCX 轉換能力帶到 Android。使用者從 Android 系統文件選擇器選取檔案、設定輸出模式、執行轉換，再透過系統文件建立器儲存 DOCX。任何文件內容都不得上傳網路。

## 2. 支援範圍

### 輸入

- EPUB（無 DRM）
- DOCX

### EPUB 輸出

- A4 一頁四格
- A6 標準 16 頁書帖
- A5 直向，一頁一張
- 4 × 6 英吋直向，一頁一張

### DOCX 輸出

- A5 直向重新排版
- 4 × 6 英吋直向重新排版

### 保留的桌面版規則

- EPUB 圖片、章節順序、標題與基本字元格式
- 前置頁不編號，序章／楔子／Prologue 從第 1 頁開始
- 純圖片頁計入頁數但不顯示頁碼
- DOCX 以原始 `w:p` 段落為唯一分段依據，不按句號、顯示換行或字數重切段落
- DOCX 保留段落格式、一般表格、內嵌圖片、超連結與手動分頁；過寬表格及圖片縮至可用寬度
- 安全、最大化、無邊界三種邊界模式

### 第一版不包含

- PDF 輸出或 PDF 預覽
- DRM EPUB
- 雲端同步、登入、帳號或伺服器
- 32 位元 ABI
- x86／x86_64 發行 APK
- Android 直接列印整合
- 背景常駐或應用程式關閉後繼續轉換

## 3. 技術架構

### Android 層

- Kotlin
- Jetpack Compose + Material 3
- 單 Activity
- ViewModel 管理畫面狀態與轉換工作
- Kotlin Coroutines 在 `Dispatchers.IO` 執行檔案複製及 Python 轉換
- Storage Access Framework：
  - `OpenDocument` 選取 EPUB／DOCX
  - `CreateDocument` 選擇 DOCX 儲存位置
- 僅宣告必要權限；不要求 `MANAGE_EXTERNAL_STORAGE` 或傳統全域儲存權限

### Python 層

- Chaquopy 17
- Python 3.13
- 將桌面版 `epub_a4_word` 核心放在 `app/src/main/python`
- 排除 Tkinter GUI 與桌面命令列啟動器
- 新增 `android_bridge.py`，提供單一、穩定的 Android 呼叫介面：

```python
def convert_file(
    input_path: str,
    output_path: str,
    options_json: str,
    progress_callback,
) -> dict:
    ...
```

- `options_json` 包含來源類型、輸出模式、邊界、字型、字級、頁碼與裁切線設定
- 回傳可直接轉為 Kotlin 資料模型的字典：輸出路徑、內容頁數、紙張數、圖片數、書帖數、警告
- Python 例外轉成結構化錯誤，Android 顯示中文錯誤訊息

### 檔案資料流

1. 使用者選取輸入 URI。
2. Android 將 URI 內容串流複製到 App cache 的工作目錄。
3. Python 只操作工作目錄中的一般檔案路徑。
4. Python 產生暫存 DOCX。
5. Android 使用 `CreateDocument` 取得目的 URI。
6. Android 將暫存 DOCX 串流複製至目的 URI。
7. 成功後刪除工作目錄；失敗時保留到顯示錯誤完成後再清理。

這個邊界讓 Python 核心不需要理解 `content://` URI，也避免直接取得整個儲存空間權限。

## 4. UI 設計

採單頁四步驟流程：

1. **選擇文件**：顯示檔名、格式與大小。
2. **選擇輸出模式**：根據 EPUB／DOCX 動態顯示合法模式。
3. **排版設定**：邊界、頁碼、裁切線；EPUB 額外顯示字型、內文字級與標題字級。
4. **開始轉換**：顯示百分比、目前階段及取消按鈕。

完成畫面顯示：

- 輸出模式
- 內容頁數
- 紙張／列印面數
- 圖片數
- 書帖數（適用時）
- 最多八項警告與「查看更多」
- 「儲存 Word」按鈕
- 「轉換另一個文件」按鈕

## 5. 狀態模型

```kotlin
data class ConversionOptions(
    val mode: OutputMode,
    val marginMode: MarginMode,
    val fontName: String,
    val bodyFontPt: Float,
    val headingFontPt: Float,
    val pageNumbers: Boolean,
    val cutGuides: Boolean,
)

sealed interface ConversionUiState {
    data object Idle : ConversionUiState
    data class Ready(...) : ConversionUiState
    data class Running(val percent: Int, val message: String) : ConversionUiState
    data class AwaitingSave(val result: ConversionResultUi) : ConversionUiState
    data class Saved(val destinationName: String, val result: ConversionResultUi) : ConversionUiState
    data class Failed(val message: String, val details: String?) : ConversionUiState
}
```

ViewModel 持有工作目錄及暫存輸出路徑。旋轉螢幕不重啟轉換；程序被系統終止後不承諾恢復未完成工作。

## 6. 進度與取消

- Python 既有進度 callback 經 `android_bridge.py` 呼叫 Kotlin callback。
- Kotlin 將進度更新至 `StateFlow`。
- 取消採協作式取消：Kotlin 設定取消旗標；Python 在解析、圖片分析、分頁和寫檔階段檢查旗標並拋出專用取消例外。
- 取消或失敗時刪除不完整 DOCX。

## 7. 相容性與建置

- `minSdk = 24`
- `targetSdk = 36`
- 僅封裝 `arm64-v8a`
- AGP 8.13.2、Gradle 8.13、JDK 17
- Chaquopy 17、Python 3.13
- Compose BOM 2026.06.00
- `activity-compose` 1.13.0
- Release APK 啟用 R8，但保留 Chaquopy 及 Python 啟動所需類別
- 建置必須檢查每個 Python 相依套件是否有可用的 Android arm64 wheel；若某套件無 wheel，優先替換為純 Python 或 Android 可用套件，而不是在手機上編譯原生延伸
- APK 需以 APK Analyzer 與 `zipalign -c -P 16` 驗證 16 KB 對齊；並在 Android 15／16 的 16 KB ARM64 測試環境執行啟動及轉換測試

## 8. 相依套件策略

桌面核心目前依賴：

- beautifulsoup4
- lxml
- Pillow
- python-docx

Android 建置的第一個技術閘門是確認上述套件在 Python 3.13／arm64-v8a 下可安裝。若 `lxml` 或 Pillow 的 Android wheel 不可用：

1. 不降低為 32 位元或引入伺服器。
2. 先評估 Chaquopy 官方套件庫中的其他 Python 版本。
3. 若仍不可用，將 EPUB XML 解析改為標準庫 `xml.etree.ElementTree`，圖片尺寸改由 Android `BitmapFactory` 或純 Java/Kotlin bridge 提供。
4. DOCX XML 操作仍需維持原段落節點與格式，不得退化為純文字重建。

## 9. 錯誤處理

使用者可理解的錯誤分類：

- 文件無法讀取或 URI 權限失效
- 不支援的檔案格式
- EPUB 損壞、缺少容器或書脊
- DOCX 損壞
- DRM 或加密內容
- 儲存空間不足
- 記憶體不足
- 輸出位置無法寫入
- SVG 圖片缺少支援
- 使用者取消

錯誤畫面保留重試和重新選檔入口，不顯示原始 Python traceback；詳細資訊可複製供除錯。

## 10. 測試策略

### Python 單元與回歸測試

- 原桌面版測試全部保留並在 Android 核心來源上執行
- 新增 Android bridge options 解析、回傳結果與取消測試
- 固定 EPUB／DOCX fixture 比對頁面、圖片、書帖和頁碼結果

### Kotlin 單元測試

- 輸入格式判斷
- 模式合法性與預設值
- options JSON 編碼
- Python 回傳資料解析
- ViewModel 狀態轉換
- URI 檔名及暫存檔命名

### Android 儀器測試

- OpenDocument／CreateDocument contract 狀態流程（使用測試替身）
- 小型 EPUB 轉 A5
- 小型 EPUB 轉 16 頁書帖
- DOCX 轉 A5，確認同一原始段落未新增段落節點
- DOCX 轉 4×6，確認表格與圖片不超出紙張寬度
- 取消時不留下不完整輸出

### 實機驗收

- Android 7、Android 12、Android 15/16 ARM64
- 4 KB 與 16 KB 頁面大小環境
- 100 MB 以上 EPUB 的記憶體與耗時觀察
- 無網路模式下完成所有轉換

## 11. 交付物

- Android Studio 完整專案
- 可安裝的 arm64-v8a debug APK
- 若簽署設定允許，另提供 release APK
- 中文 README：安裝、使用、列印與已知限制
- 桌面核心來源與 Android 專用 bridge
- 自動測試與測試 fixture
- 建置及 16 KB 相容性驗證紀錄

## 12. 驗收標準

1. 飛航模式下可完成 EPUB 與 DOCX 轉換。
2. 只出現與來源格式相容的輸出模式。
3. EPUB 同一輸入及設定的內容頁序、圖片數和書帖頁序與桌面版一致。
4. DOCX 不按句子或顯示換行新增段落；原始 `w:p` 數量除必要的分頁／頁尾結構外保持一致。
5. A5 與 4×6 紙張尺寸正確，表格與內嵌圖片不超出可用寬度。
6. 轉換過程 UI 不凍結，進度可見，取消可停止工作並清理暫存檔。
7. App 不要求網路權限及全域儲存權限。
8. arm64-v8a APK 可在 Android API 24 以上安裝。
9. APK 與所有原生函式庫通過 16 KB 對齊檢查。
