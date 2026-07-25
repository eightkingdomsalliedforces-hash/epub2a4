package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import tw.daniel.epubword.cover.model.ImageMode
import java.util.Locale

data class CoverSetupCallbacks(
    val onChooseSource: () -> Unit = {},
    val onTrimPreset: (TrimPreset) -> Unit = {},
    val onPageCount: (Int) -> Unit = {},
    val onConfirmPageCount: (Boolean) -> Unit = {},
    val onPaperPreset: (PaperPreset) -> Unit = {},
    val onCaliper: (Double) -> Unit = {},
    val onManualSpine: (Double?) -> Unit = {},
    val onBleed: (Double) -> Unit = {},
    val onImageMode: (ImageMode) -> Unit = {},
    val onTemplate: (String) -> Unit = {},
    val onCreateProject: () -> Unit = {},
)

@Composable
fun CoverSetupScreen(
    state: CoverUiState,
    callbacks: CoverSetupCallbacks,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(modifier.fillMaxSize()) {
        val cards = listOf<@Composable () -> Unit>(
            { SourceCard(state, callbacks) },
            { PageAndTrimCard(state, callbacks) },
            { PaperAndSpineCard(state, callbacks) },
            { AppearanceCard(state, callbacks) },
            { CreateCard(state, callbacks) },
        )
        if (maxWidth < 700.dp) {
            Column(
                modifier = Modifier.fillMaxSize().padding(PaddingValues(16.dp)),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                cards.forEach { it() }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxSize().padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    cards.filterIndexed { index, _ -> index % 2 == 0 }.forEach { it() }
                }
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    cards.filterIndexed { index, _ -> index % 2 == 1 }.forEach { it() }
                }
            }
        }
    }
}

@Composable
private fun SourceCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    StepCard("來源與書籍資料") {
        Text(state.sourceName ?: "尚未選擇 EPUB、DOCX 或 PDF")
        if (state.metadataTitle.isNotBlank()) Text("書名：${state.metadataTitle}")
        if (state.metadataAuthor.isNotBlank()) Text("作者：${state.metadataAuthor}")
        OutlinedButton(
            onClick = callbacks.onChooseSource,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
            enabled = !state.isBusy,
        ) {
            Text("選擇來源")
        }
    }
}

@Composable
private fun PageAndTrimCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    var pageText by remember(state.pageCount) { mutableStateOf(state.pageCount.takeIf { it > 0 }?.toString() ?: "") }
    var pageError by remember { mutableStateOf<String?>(null) }
    StepCard("裁切尺寸與正文頁數") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TrimPreset.entries.forEach { preset ->
                FilterChip(
                    selected = state.trimPreset == preset,
                    onClick = { callbacks.onTrimPreset(preset) },
                    label = { Text(preset.label) },
                )
            }
        }
        OutlinedTextField(
            value = pageText,
            onValueChange = { value ->
                pageText = value
                val parsed = value.toIntOrNull()
                pageError = if (parsed == null || parsed <= 0) "頁數必須是正整數。" else null
                if (parsed != null && parsed > 0) callbacks.onPageCount(parsed)
            },
            label = { Text("正文頁數") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            isError = pageError != null,
            supportingText = { pageError?.let { Text(it) } },
            modifier = Modifier.fillMaxWidth(),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .toggleable(
                    value = state.pageCountConfirmed,
                    enabled = state.pageCount > 0 && !state.isBusy,
                    role = Role.Checkbox,
                    onValueChange = callbacks.onConfirmPageCount,
                )
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = state.pageCountConfirmed, onCheckedChange = null)
            Text("我已確認正文頁數")
        }
        if (state.pageCountEstimated) {
            Text("頁數為估算值", color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun PaperAndSpineCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    var caliperText by remember(state.paperCaliperMm) { mutableStateOf(state.paperCaliperMm.toString()) }
    var spineText by remember(state.manualSpineWidthMm) { mutableStateOf(state.manualSpineWidthMm?.toString() ?: "") }
    StepCard("紙張與書脊") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PaperPreset.entries.forEach { preset ->
                FilterChip(
                    selected = state.paperPreset == preset,
                    onClick = { callbacks.onPaperPreset(preset) },
                    label = { Text("${preset.gsm}g") },
                )
            }
        }
        DecimalField(
            value = caliperText,
            onValueChange = { value ->
                caliperText = value
                parsePositiveDouble(value, "紙張厚度").getOrNull()?.let(callbacks.onCaliper)
            },
            label = "單張紙厚度（mm）",
        )
        Text("自動書脊：${String.format(Locale.US, "%.1f", state.autoSpineWidthMm)} mm")
        DecimalField(
            value = spineText,
            onValueChange = { value ->
                spineText = value
                if (value.isBlank()) callbacks.onManualSpine(null)
                else parsePositiveDouble(value, "手動書脊").getOrNull()?.let(callbacks.onManualSpine)
            },
            label = "手動書脊（留空使用自動值）",
        )
        Text("實際書脊：${String.format(Locale.US, "%.1f", state.effectiveSpineWidthMm)} mm")
    }
}

@Composable
private fun AppearanceCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    var bleedText by remember(state.bleedMm) { mutableStateOf(state.bleedMm.toString()) }
    StepCard("外觀與模板") {
        DecimalField(
            value = bleedText,
            onValueChange = { value ->
                bleedText = value
                value.toDoubleOrNull()?.takeIf { it in 0.0..10.0 }?.let(callbacks.onBleed)
            },
            label = "出血（mm）",
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ImageMode.entries.forEach { mode ->
                Row(
                    modifier = Modifier.selectable(
                        selected = state.imageMode == mode,
                        role = Role.RadioButton,
                        onClick = { callbacks.onImageMode(mode) },
                    ).padding(8.dp),
                ) {
                    Text(if (mode == ImageMode.FRONT_ONLY) "僅正面圖片" else "全展開圖片")
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(
                "minimal_text" to "極簡",
                "front_image_plain_back" to "正面圖片",
                "full_spread" to "全圖覆蓋",
                "top_bottom_blocks" to "上下色塊",
            ).forEach { (id, label) ->
                FilterChip(
                    selected = state.templateId == id,
                    onClick = { callbacks.onTemplate(id) },
                    label = { Text(label) },
                )
            }
        }
    }
}

@Composable
private fun CreateCard(state: CoverUiState, callbacks: CoverSetupCallbacks) {
    StepCard("建立封面") {
        state.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.warnings.forEach { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = callbacks.onCreateProject,
            enabled = state.canCreateProject,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
        ) {
            Text(if (state.isBusy) "處理中…" else "建立封面")
        }
    }
}

@Composable
private fun StepCard(title: String, content: @Composable Column.() -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            content()
        }
    }
}

@Composable
private fun DecimalField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        modifier = Modifier.fillMaxWidth(),
    )
}

fun parsePositiveDouble(text: String, field: String): Result<Double> = runCatching {
    val value = text.toDoubleOrNull() ?: error("$field 必須是數字。")
    require(value > 0.0 && value.isFinite()) { "$field 必須大於 0。" }
    value
}
