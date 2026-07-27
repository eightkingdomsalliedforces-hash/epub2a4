package tw.daniel.epubword.cover.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.json.JSONObject

data class CoverEditorCallbacks(
    val onBack: () -> Unit = {},
    val onUndo: () -> Unit = {},
    val onRedo: () -> Unit = {},
    val onApplyTemplate: (String) -> Unit = {},
    val onAddImage: () -> Unit = {},
    val onSelectEmbeddedImage: (String) -> Unit = {},
    val onAddText: () -> Unit = {},
    val onToggleGuides: () -> Unit = {},
    val onPreviewWord: () -> Unit = {},
    val onPrepareExport: (Int) -> Unit = {},
    val onRequestExportDirectory: () -> Unit = {},
    val onSelectElement: (String?) -> Unit = {},
    val onSelectAtMm: (Offset) -> Unit = {},
    val onPatchElement: (String, ElementPatch) -> Unit = { _, _ -> },
    val onDeleteElement: (String) -> Unit = {},
    val onTransformElement: (ElementTransformPatch) -> Unit = {},
)

private enum class EditorSheet { NONE, TEMPLATES, EMBEDDED_IMAGES, LAYERS, INSPECTOR }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CoverEditorScreen(
    state: CoverUiState,
    callbacks: CoverEditorCallbacks,
    modifier: Modifier = Modifier,
) {
    var sheet by remember { mutableStateOf(EditorSheet.NONE) }
    var viewport by remember { mutableStateOf(CoverViewport(scalePxPerMm = 1.0)) }
    var showExportDialog by remember { mutableStateOf(false) }
    val selected = state.project?.elements?.firstOrNull { it.id == state.selectedElementId }
    val embeddedImages = state.project?.metadata?.embeddedImages.orEmpty()
    val bitmap = remember(state.previewPath) {
        state.previewPath?.let(BitmapFactory::decodeFile)?.asImageBitmap()
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        topBar = {
            Column(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(onClick = callbacks.onBack) { Text("返回") }
                    TextButton(
                        onClick = callbacks.onUndo,
                        enabled = state.canUndo,
                        modifier = Modifier.semantics { contentDescription = "復原" },
                    ) { Text("復原") }
                    TextButton(
                        onClick = callbacks.onRedo,
                        enabled = state.canRedo,
                        modifier = Modifier.semantics { contentDescription = "重做" },
                    ) { Text("重做") }
                    TextButton(onClick = { sheet = EditorSheet.TEMPLATES }) { Text("模板") }
                    TextButton(onClick = callbacks.onAddImage) { Text("加入圖片") }
                    if (embeddedImages.isNotEmpty()) {
                        TextButton(onClick = { sheet = EditorSheet.EMBEDDED_IMAGES }) {
                            Text("EPUB 圖片")
                        }
                    }
                    TextButton(onClick = callbacks.onAddText) { Text("加入文字") }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    TextButton(onClick = callbacks.onToggleGuides) {
                        Text(if (state.guidesVisible) "隱藏導引線" else "顯示導引線")
                    }
                    TextButton(onClick = { sheet = EditorSheet.LAYERS }) { Text("圖層") }
                    TextButton(
                        onClick = { if (selected != null) sheet = EditorSheet.INSPECTOR },
                        enabled = selected != null,
                    ) { Text("屬性") }
                    TextButton(
                        onClick = callbacks.onPreviewWord,
                        enabled = state.canExport,
                    ) { Text("Word 預覽") }
                    Button(
                        onClick = { showExportDialog = true },
                        enabled = state.canExport,
                    ) { Text("匯出") }
                    if (state.canChooseExportDirectory) {
                        TextButton(onClick = callbacks.onRequestExportDirectory) {
                            Text("重新選擇資料夾")
                        }
                    }
                }
                state.saveMessage?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                state.errorMessage?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
    ) { padding ->
        Box(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentAlignment = Alignment.Center,
        ) {
            if (bitmap != null && state.project != null) {
                val project = state.project
                val spine = project.manualSpineWidthMm
                    ?: ((project.pageCount + 1) / 2) * project.paperCaliperMm
                CoverEditorCanvas(
                    bitmap = bitmap,
                    viewport = viewport,
                    guides = if (state.guidesVisible) state.guides else CoverGuides(),
                    selected = selected?.transform,
                    selectedElementId = selected?.id,
                    canvasWidthMm = project.trimSize.widthMm * 2 + spine + project.bleedMm * 2,
                    canvasHeightMm = project.trimSize.heightMm + project.bleedMm * 2,
                    onCommitTransform = callbacks.onTransformElement,
                    onCommitViewport = { viewport = it },
                    onLongPressMm = callbacks.onSelectAtMm,
                    modifier = Modifier.fillMaxSize(),
                )
            } else {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("封面預覽尚未產生", style = MaterialTheme.typography.titleMedium)
                    state.errorMessage?.let {
                        Text(it, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }

    when (sheet) {
        EditorSheet.TEMPLATES -> ModalBottomSheet(onDismissRequest = { sheet = EditorSheet.NONE }) {
            TemplateChoices(
                publisherReady = normalizedPublisherIsbn13(
                    state.project?.metadata?.isbn.orEmpty(),
                ).isNotBlank() && !state.project?.metadata?.publisher.isNullOrBlank(),
                onApply = {
                    callbacks.onApplyTemplate(it)
                    sheet = EditorSheet.NONE
                },
            )
        }
        EditorSheet.EMBEDDED_IMAGES -> ModalBottomSheet(onDismissRequest = { sheet = EditorSheet.NONE }) {
            EmbeddedImageChoices(
                images = embeddedImages,
                onSelect = {
                    callbacks.onSelectEmbeddedImage(it)
                    sheet = EditorSheet.NONE
                },
            )
        }
        EditorSheet.LAYERS -> ModalBottomSheet(onDismissRequest = { sheet = EditorSheet.NONE }) {
            LayersSheet(
                elements = state.project?.elements.orEmpty(),
                selectedElementId = state.selectedElementId,
                onSelect = {
                    callbacks.onSelectElement(it)
                    sheet = EditorSheet.INSPECTOR
                },
                onDelete = callbacks.onDeleteElement,
            )
        }
        EditorSheet.INSPECTOR -> if (selected != null) {
            ModalBottomSheet(onDismissRequest = { sheet = EditorSheet.NONE }) {
                ElementInspectorSheet(
                    element = selected,
                    onApply = { callbacks.onPatchElement(selected.id, it) },
                    onDelete = {
                        callbacks.onDeleteElement(selected.id)
                        sheet = EditorSheet.NONE
                    },
                )
            }
        }
        EditorSheet.NONE -> Unit
    }

    if (showExportDialog) {
        ExportCoverDialog(
            initialDpi = state.exportDpi,
            onDismiss = { showExportDialog = false },
            onExport = {
                showExportDialog = false
                callbacks.onPrepareExport(it)
            },
        )
    }
}

@Composable
private fun TemplateChoices(
    publisherReady: Boolean,
    onApply: (String) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("套用模板", style = MaterialTheme.typography.titleLarge)
        COVER_TEMPLATE_OPTIONS.forEach { option ->
            val enabled = option.id != PUBLISHER_BACK_MATTER_TEMPLATE_ID || publisherReady
            Button(
                onClick = { onApply(option.id) },
                enabled = enabled,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(option.label)
            }
        }
        if (!publisherReady) {
            Text(
                "出版社式封底需要先返回設定頁，填入有效 ISBN-13 與出版社名稱後重新建立。",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun EmbeddedImageChoices(
    images: List<JSONObject>,
    onSelect: (String) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("EPUB 內嵌圖片", style = MaterialTheme.typography.titleLarge)
        images.forEach { image ->
            val id = image.optString("id")
            if (id.isNotBlank()) {
                val role = image.optString("role", "image")
                val width = image.optInt("width_px")
                val height = image.optInt("height_px")
                Button(onClick = { onSelect(id) }, modifier = Modifier.fillMaxWidth()) {
                    Text("$id · $role · ${width}×${height}px")
                }
            }
        }
    }
}
