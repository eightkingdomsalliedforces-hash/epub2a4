package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp

fun normalizeCoverExportDpi(value: Int): Int {
    require(value == 200 || value == 300) { "封面匯出只支援 200 或 300 DPI。" }
    return value
}

@Composable
fun ExportCoverDialog(
    initialDpi: Int = 300,
    onDismiss: () -> Unit,
    onExport: (Int) -> Unit,
) {
    var dpi by remember(initialDpi) { mutableIntStateOf(normalizeCoverExportDpi(initialDpi)) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("輸出完整書封") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("將先在本機建立獨立 PDF 與可編輯 DOCX，再讓你選擇儲存資料夾。")
                listOf(
                    300 to "300 DPI（建議列印品質）",
                    200 to "200 DPI（低記憶體模式）",
                ).forEach { (value, label) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectable(
                                selected = dpi == value,
                                onClick = { dpi = value },
                                role = Role.RadioButton,
                            ),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = dpi == value, onClick = null)
                        Text(label)
                    }
                }
                Text("若 300 DPI 記憶體不足，App 會明確提示；不會自動降低品質。")
            }
        },
        confirmButton = {
            Button(onClick = { onExport(normalizeCoverExportDpi(dpi)) }) {
                Text("開始輸出")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
