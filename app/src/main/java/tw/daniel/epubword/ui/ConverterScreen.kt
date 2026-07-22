package tw.daniel.epubword.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Transform
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import tw.daniel.epubword.model.InputKind
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConverterScreen(
    state: ConversionUiState,
    onChooseInput: () -> Unit,
    onOutputMode: (OutputMode) -> Unit,
    onMarginMode: (MarginMode) -> Unit,
    onFontName: (String) -> Unit,
    onBodyFontSize: (Double) -> Unit,
    onHeadingFontSize: (Double) -> Unit,
    onPageNumbers: (Boolean) -> Unit,
    onCutGuides: (Boolean) -> Unit,
    onConvert: () -> Unit,
    onCancel: () -> Unit,
    onSave: () -> Unit,
    onDismissError: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("EPUB／Word 排版工具", fontWeight = FontWeight.SemiBold)
                        Text("完全離線 · arm64", style = MaterialTheme.typography.labelSmall)
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            StepCard(number = 1, title = "選擇文件") {
                OutlinedButton(
                    onClick = onChooseInput,
                    enabled = !state.isBusy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.FolderOpen, contentDescription = null)
                    Text(
                        text = state.inputName ?: "選擇 EPUB 或 DOCX",
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
                state.inputKind?.let { kind ->
                    Text(
                        text = "已識別：${kind.name} · ${state.inputSizeBytes.orZero().fileSizeText()}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            StepCard(number = 2, title = "輸出尺寸") {
                val modes = state.inputKind?.let { OutputMode.allowedFor(it) } ?: OutputMode.entries
                modes.forEach { mode ->
                    FilterChip(
                        selected = state.options.outputMode == mode,
                        onClick = { onOutputMode(mode) },
                        enabled = !state.isBusy,
                        label = { Text(mode.label) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (state.inputKind == InputKind.DOCX) {
                    Text(
                        "Word 會依原始段落重新流排，不會按句子拆段。",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            StepCard(number = 3, title = "排版設定") {
                Text("邊界", fontWeight = FontWeight.Medium)
                MarginMode.entries.forEach { mode ->
                    FilterChip(
                        selected = state.options.marginMode == mode,
                        onClick = { onMarginMode(mode) },
                        enabled = !state.isBusy,
                        label = { Text(mode.label) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }

                if (state.inputKind != InputKind.DOCX) {
                    HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                    OutlinedTextField(
                        value = state.options.fontName,
                        onValueChange = onFontName,
                        enabled = !state.isBusy,
                        label = { Text("字型名稱") },
                        supportingText = { Text("手機沒有該字型時，Word 開啟後會使用替代字型。") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )

                    Text("內文字級：${state.options.bodyFontPt.oneDecimal()} pt")
                    Slider(
                        value = state.options.bodyFontPt.toFloat(),
                        onValueChange = { onBodyFontSize(it.toDouble()) },
                        valueRange = 6f..14f,
                        steps = 15,
                        enabled = !state.isBusy,
                    )
                    Text("標題字級：${state.options.headingFontPt.oneDecimal()} pt")
                    Slider(
                        value = state.options.headingFontPt.toFloat(),
                        onValueChange = { onHeadingFontSize(it.toDouble()) },
                        valueRange = 8f..20f,
                        steps = 23,
                        enabled = !state.isBusy,
                    )
                }

                SettingCheck(
                    label = "顯示頁碼",
                    checked = state.options.pageNumbers,
                    enabled = !state.isBusy,
                    onCheckedChange = onPageNumbers,
                )
                val guidesRelevant = state.options.outputMode in setOf(OutputMode.SIGNATURE16, OutputMode.FOUR_UP)
                SettingCheck(
                    label = "顯示裁切／折線",
                    checked = state.options.cutGuides,
                    enabled = !state.isBusy && guidesRelevant,
                    onCheckedChange = onCutGuides,
                )
            }

            StepCard(number = 4, title = "轉換與儲存") {
                when (state.status) {
                    WorkStatus.CONVERTING, WorkStatus.STAGING, WorkStatus.SAVING -> {
                        LinearProgressIndicator(
                            progress = { state.progress.coerceIn(0, 100) / 100f },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text("${state.progress}% · ${state.statusMessage}")
                    }
                    else -> Text(state.statusMessage)
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Button(
                        onClick = onConvert,
                        enabled = state.canConvert,
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Default.Transform, contentDescription = null)
                        Text("開始轉換", modifier = Modifier.padding(start = 6.dp))
                    }
                    if (state.status == WorkStatus.CONVERTING) {
                        OutlinedButton(onClick = onCancel) {
                            Icon(Icons.Default.Cancel, contentDescription = null)
                            Text("取消", modifier = Modifier.padding(start = 6.dp))
                        }
                    }
                }

                AnimatedVisibility(visible = state.canSave) {
                    Button(
                        onClick = onSave,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(Icons.Default.Save, contentDescription = null)
                        Text("選擇儲存位置", modifier = Modifier.padding(start = 8.dp))
                    }
                }

                state.result?.let { result ->
                    HorizontalDivider(modifier = Modifier.padding(vertical = 6.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Description, contentDescription = null)
                        Text(
                            result.title.ifBlank { state.pendingOutputName ?: "轉換結果" },
                            modifier = Modifier.padding(start = 8.dp),
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    if (result.sourceFormat == "epub") {
                        Text("內容頁：${result.miniPageCount} · 列印面：${result.printSideCount}")
                        Text("紙張：${result.paperSheetCount} · 書帖：${result.signatureCount}")
                    }
                    Text("圖片：${result.imageCount}")
                    if (result.warnings.isNotEmpty()) {
                        Text("提醒", fontWeight = FontWeight.Medium)
                        result.warnings.take(8).forEach { warning -> Text("• $warning") }
                        if (result.warnings.size > 8) {
                            Text("另有 ${result.warnings.size - 8} 項提醒。", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            state.errorMessage?.let { message ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("發生錯誤", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(4.dp))
                        Text(message)
                        TextButton(onClick = onDismissError, modifier = Modifier.align(Alignment.End)) {
                            Text("關閉")
                        }
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun StepCard(number: Int, title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("$number　$title", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun SettingCheck(
    label: String,
    checked: Boolean,
    enabled: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Checkbox(checked = checked, onCheckedChange = onCheckedChange, enabled = enabled)
        Text(label)
    }
}

private fun Double.oneDecimal(): String = String.format(Locale.US, "%.1f", this)

private fun Long?.orZero(): Long = this ?: 0L

private fun Long.fileSizeText(): String = when {
    this >= 1024L * 1024L -> String.format(Locale.US, "%.1f MB", this / (1024.0 * 1024.0))
    this >= 1024L -> String.format(Locale.US, "%.1f KB", this / 1024.0)
    else -> "$this B"
}
