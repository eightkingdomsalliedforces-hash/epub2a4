package tw.daniel.epubword.cover.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import tw.daniel.epubword.cover.model.CoverElement
import tw.daniel.epubword.cover.model.ElementKind
import tw.daniel.epubword.cover.model.ElementTransform

data class ElementPatch(
    val transform: ElementTransform? = null,
    val opacity: Double? = null,
    val content: JSONObject? = null,
)

@Composable
fun ElementInspectorSheet(
    element: CoverElement,
    onApply: (ElementPatch) -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var x by remember(element.id, element.transform.xMm) { mutableStateOf(element.transform.xMm.toString()) }
    var y by remember(element.id, element.transform.yMm) { mutableStateOf(element.transform.yMm.toString()) }
    var width by remember(element.id, element.transform.widthMm) { mutableStateOf(element.transform.widthMm.toString()) }
    var height by remember(element.id, element.transform.heightMm) { mutableStateOf(element.transform.heightMm.toString()) }
    var rotation by remember(element.id, element.transform.rotationDeg) { mutableStateOf(element.transform.rotationDeg.toString()) }
    var opacity by remember(element.id, element.opacity) { mutableStateOf(element.opacity.toString()) }
    var error by remember(element.id) { mutableStateOf<String?>(null) }

    Column(
        modifier = modifier.navigationBarsPadding().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("元素屬性", style = MaterialTheme.typography.titleLarge)
        Text("${element.kind.wire} · ${element.region.wire}")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumberField(x, { x = it }, "X（mm）", Modifier.weight(1f))
            NumberField(y, { y = it }, "Y（mm）", Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumberField(width, { width = it }, "寬（mm）", Modifier.weight(1f))
            NumberField(height, { height = it }, "高（mm）", Modifier.weight(1f))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumberField(rotation, { rotation = it }, "旋轉角度", Modifier.weight(1f))
            NumberField(opacity, { opacity = it }, "透明度 0–1", Modifier.weight(1f))
        }

        when (element.kind) {
            ElementKind.TEXT -> TextElementControls(element, onApply)
            ElementKind.IMAGE -> ImageElementSummary(element)
            else -> Unit
        }

        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = {
                val parsed = listOf(x, y, width, height, rotation, opacity).map(String::toDoubleOrNull)
                if (parsed.any { it == null } || parsed[2]!! <= 0.0 || parsed[3]!! <= 0.0 || parsed[5]!! !in 0.0..1.0) {
                    error = "請輸入有效的毫米尺寸、角度與透明度。"
                    return@Button
                }
                error = null
                onApply(
                    ElementPatch(
                        transform = ElementTransform(
                            xMm = parsed[0]!!,
                            yMm = parsed[1]!!,
                            widthMm = parsed[2]!!,
                            heightMm = parsed[3]!!,
                            rotationDeg = parsed[4]!!,
                        ),
                        opacity = parsed[5]!!,
                    ),
                )
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("套用") }
        TextButton(onClick = onDelete, modifier = Modifier.fillMaxWidth()) {
            Text("刪除元素", color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun TextElementControls(element: CoverElement, onApply: (ElementPatch) -> Unit) {
    var text by remember(element.id, element.content.optString("text")) {
        mutableStateOf(element.content.optString("text"))
    }
    var size by remember(element.id, element.content.optDouble("font_size_pt", 24.0)) {
        mutableStateOf(element.content.optDouble("font_size_pt", 24.0).toString())
    }
    OutlinedTextField(
        value = text,
        onValueChange = { text = it },
        label = { Text("文字內容") },
        modifier = Modifier.fillMaxWidth(),
    )
    NumberField(size, { size = it }, "字級（pt）", Modifier.fillMaxWidth())
    Button(
        onClick = {
            val fontSize = size.toDoubleOrNull()?.takeIf { it > 0.0 } ?: return@Button
            val content = JSONObject(element.content.toString())
                .put("text", text)
                .put("font_size_pt", fontSize)
            onApply(ElementPatch(content = content))
        },
        modifier = Modifier.fillMaxWidth(),
    ) { Text("套用文字") }
}

@Composable
private fun ImageElementSummary(element: CoverElement) {
    Text("圖片：${element.content.optString("path", "尚未指定")}")
    Text("填滿方式：${element.content.optString("fit", "cover")}")
    Text("裁切、翻轉與影像調整會保存在元素 content 內，不改動原始圖片。")
}

@Composable
private fun NumberField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        singleLine = true,
        modifier = modifier,
    )
}
