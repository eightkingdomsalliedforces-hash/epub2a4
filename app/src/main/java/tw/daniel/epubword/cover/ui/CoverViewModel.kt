package tw.daniel.epubword.cover.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import tw.daniel.epubword.cover.data.CoverDocumentRepository
import tw.daniel.epubword.cover.data.StagedCoverSource
import tw.daniel.epubword.cover.model.CoverElement
import tw.daniel.epubword.cover.model.CoverHandoff
import tw.daniel.epubword.cover.model.CoverProject
import tw.daniel.epubword.cover.model.CoverProjectJson
import tw.daniel.epubword.cover.model.CoverRegion
import tw.daniel.epubword.cover.model.ElementKind
import tw.daniel.epubword.cover.model.ElementTransform
import tw.daniel.epubword.cover.model.ImageMode
import tw.daniel.epubword.cover.model.TrimSize
import tw.daniel.epubword.python.PythonCoverGateway
import java.io.File
import java.util.UUID
import kotlin.math.max

class CoverViewModel @JvmOverloads constructor(
    application: Application,
    private val repository: CoverDocumentRepository = CoverDocumentRepository(application),
    private val gateway: PythonCoverGateway = PythonCoverGateway(application),
) : AndroidViewModel(application) {
    private val _uiState = MutableStateFlow(CoverUiState())
    val uiState: StateFlow<CoverUiState> = _uiState.asStateFlow()
    private var stagedSource: StagedCoverSource? = null
    private val undoHistory = ArrayDeque<String>()
    private val redoHistory = ArrayDeque<String>()
    private val previewDebouncer = PreviewDebouncer(viewModelScope) { renderPreviewNow(it) }
    private var pendingExports: PendingCoverExports? = null

    fun selectSource(uri: Uri) {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update { it.copy(status = CoverStatus.STAGING, errorMessage = null) }
            runCatching {
                withContext(Dispatchers.IO) {
                    val staged = repository.stageSource(uri)
                    staged to gateway.inspectSource(staged.localFile)
                }
            }.onSuccess { (staged, inspection) ->
                stagedSource = staged
                resetEditorSession()
                val metadata = inspection.optJSONObject("metadata") ?: JSONObject()
                val inspectedPages = resolveCoverInspectionPageCount(inspection)
                _uiState.update {
                    it.copy(
                        status = CoverStatus.SETUP,
                        sourceName = staged.displayName,
                        sourcePath = staged.localFile.absolutePath,
                        sourceType = inspection.optString("source_type", staged.kind.name.lowercase()),
                        metadataTitle = metadata.optString("title"),
                        metadataAuthor = metadata.optString("author"),
                        metadataDescription = metadata.optString("description"),
                        metadataIsbn = metadata.optString("isbn"),
                        metadataPublisher = metadata.optString("publisher"),
                        metadataLanguage = metadata.optString("language"),
                        pageCount = inspectedPages.pageCount,
                        pageCountEstimated = inspectedPages.estimated,
                        pageCountConfirmed = false,
                        warnings = inspection.stringList("warnings"),
                        project = null,
                        projectJson = "",
                        previewPath = null,
                        selectedElementId = null,
                        canUndo = false,
                        canRedo = false,
                        exportPdfPath = null,
                        exportDocxPath = null,
                        saveMessage = null,
                    )
                }
            }.onFailure(::showError)
        }
    }

    fun openHandoff(handoff: CoverHandoff) {
        if (_uiState.value.isBusy) return
        viewModelScope.launch {
            _uiState.update { it.copy(status = CoverStatus.STAGING, errorMessage = null) }
            runCatching {
                withContext(Dispatchers.IO) {
                    val staged = repository.stageHandoff(handoff)
                    staged to gateway.inspectSource(staged.localFile)
                }
            }.onSuccess { (staged, inspection) ->
                stagedSource = staged
                resetEditorSession()
                val metadata = inspection.optJSONObject("metadata") ?: JSONObject()
                _uiState.update {
                    it.copy(
                        status = CoverStatus.SETUP,
                        sourceName = staged.displayName,
                        sourcePath = staged.localFile.absolutePath,
                        sourceType = inspection.optString("source_type", handoff.sourceType),
                        metadataTitle = handoff.title.ifBlank { metadata.optString("title") },
                        metadataAuthor = handoff.author.ifBlank { metadata.optString("author") },
                        metadataDescription = metadata.optString("description"),
                        metadataIsbn = metadata.optString("isbn"),
                        metadataPublisher = metadata.optString("publisher"),
                        metadataLanguage = metadata.optString("language"),
                        trimPreset = trimPresetFor(handoff.trimSize),
                        pageCount = handoff.pageCount,
                        pageCountEstimated = false,
                        pageCountConfirmed = handoff.pageCountConfirmed,
                        warnings = inspection.stringList("warnings"),
                        project = null,
                        projectJson = "",
                        previewPath = null,
                        selectedElementId = null,
                        canUndo = false,
                        canRedo = false,
                        exportPdfPath = null,
                        exportDocxPath = null,
                        saveMessage = "已從轉換結果帶入實際頁數與裁切尺寸。",
                    )
                }
            }.onFailure(::showError)
        }
    }

    fun setTrimPreset(value: TrimPreset) = _uiState.update { it.copy(trimPreset = value) }
    fun setPageCount(value: Int) = _uiState.update {
        it.copy(pageCount = value.coerceAtLeast(0), pageCountConfirmed = false)
    }
    fun confirmPageCount(confirmed: Boolean) = _uiState.update {
        it.copy(pageCountConfirmed = confirmed && it.pageCount > 0)
    }
    fun setPaperPreset(value: PaperPreset) = _uiState.update {
        it.copy(paperPreset = value, paperCaliperMm = value.caliperMm)
    }
    fun setCaliper(value: Double) {
        if (value > 0.0 && value.isFinite()) _uiState.update {
            it.copy(paperCaliperMm = value, errorMessage = null)
        }
    }
    fun setManualSpine(value: Double?) {
        if (value == null || (value > 0.0 && value.isFinite())) _uiState.update {
            it.copy(manualSpineWidthMm = value, errorMessage = null)
        }
    }
    fun setBleed(value: Double) {
        if (value in 0.0..10.0 && value.isFinite()) _uiState.update {
            it.copy(bleedMm = value, errorMessage = null)
        }
    }
    fun setImageMode(value: ImageMode) = _uiState.update { it.copy(imageMode = value) }
    fun setTemplate(value: String) = _uiState.update { it.copy(templateId = value) }
    fun setExportDpi(value: Int) {
        _uiState.update { it.copy(exportDpi = normalizeCoverExportDpi(value)) }
    }

    fun createProject() {
        val state = _uiState.value
        val staged = stagedSource
        if (staged == null || !state.canCreateProject) {
            _uiState.update { it.copy(errorMessage = "請選擇來源並確認正文頁數。") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(status = CoverStatus.CREATING, errorMessage = null) }
            runCatching {
                withContext(Dispatchers.IO) {
                    val settings = JSONObject()
                        .put("working_dir", staged.workingFiles.root.absolutePath)
                        .put("trim_width_mm", state.trimPreset.widthMm)
                        .put("trim_height_mm", state.trimPreset.heightMm)
                        .put("page_count", state.pageCount)
                        .put("paper_caliper_mm", state.paperCaliperMm)
                        .put("manual_spine_width_mm", state.manualSpineWidthMm ?: JSONObject.NULL)
                        .put("bleed_mm", state.bleedMm)
                        .put("overlap_mm", 5.0)
                        .put("image_mode", state.imageMode.wire)
                    val created = gateway.newProject(staged.localFile, settings)
                    gateway.applyTemplate(created, state.templateId)
                }
            }.onSuccess { projectJson ->
                pendingExports = null
                undoHistory.clear()
                redoHistory.clear()
                setProjectImmediately(projectJson, clearSelection = true)
                schedulePreview(projectJson)
            }.onFailure(::showError)
        }
    }

    fun selectElement(elementId: String?) = _uiState.update { state ->
        val valid = elementId?.takeIf { id -> state.project?.elements?.any { it.id == id } == true }
        state.copy(selectedElementId = valid)
    }

    fun selectElementAt(pointMm: androidx.compose.ui.geometry.Offset) {
        selectElement(_uiState.value.project?.topmostElementAt(pointMm))
    }

    fun toggleGuides() = _uiState.update { it.copy(guidesVisible = !it.guidesVisible) }

    fun applyTemplate(templateId: String) {
        val currentJson = _uiState.value.projectJson.takeIf(String::isNotBlank) ?: return
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { gateway.applyTemplate(currentJson, templateId) } }
                .onSuccess {
                    _uiState.update { state -> state.copy(templateId = templateId) }
                    commitProject(CoverProjectJson.decode(it))
                }
                .onFailure(::showError)
        }
    }

    fun patchElement(elementId: String, patch: ElementPatch) {
        val project = _uiState.value.project ?: return
        runCatching { project.patchElement(elementId, patch) }
            .onSuccess { commitProject(it) }
            .onFailure(::showError)
    }

    fun applyTransformPatch(patch: ElementTransformPatch) {
        val project = _uiState.value.project ?: return
        runCatching { project.applyTransformPatch(patch) }
            .onSuccess { commitProject(it, selectId = patch.elementId) }
            .onFailure(::showError)
    }

    fun addText() {
        val project = _uiState.value.project ?: return
        val (next, id) = project.addTextElement()
        commitProject(next, selectId = id)
    }

    fun importLocalImage(uri: Uri) {
        viewModelScope.launch {
            runCatching { repository.stageLocalImage(uri) }
                .onSuccess(::addImageFile)
                .onFailure(::showError)
        }
    }

    fun selectEmbeddedImage(assetId: String) {
        val projectJson = _uiState.value.projectJson.takeIf(String::isNotBlank) ?: return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    gateway.extractEmbeddedAsset(projectJson, assetId).getString("path")
                }
            }.onSuccess { addImageFile(File(it)) }
                .onFailure(::showError)
        }
    }

    private fun addImageFile(file: File) {
        val project = _uiState.value.project ?: return
        runCatching { project.addImageElement(file) }
            .onSuccess { (next, id) -> commitProject(next, selectId = id) }
            .onFailure(::showError)
    }

    fun removeElement(elementId: String) {
        val project = _uiState.value.project ?: return
        runCatching { project.removeElement(elementId) }
            .onSuccess { commitProject(it, selectId = null) }
            .onFailure(::showError)
    }

    fun undo() {
        if (undoHistory.isEmpty()) return
        val current = _uiState.value.projectJson
        if (current.isNotBlank()) pushBounded(redoHistory, current)
        val restored = undoHistory.removeLast()
        pendingExports = null
        setProjectImmediately(restored, clearSelection = true)
        schedulePreview(restored)
    }

    fun redo() {
        if (redoHistory.isEmpty()) return
        val current = _uiState.value.projectJson
        if (current.isNotBlank()) pushBounded(undoHistory, current)
        val restored = redoHistory.removeLast()
        pendingExports = null
        setProjectImmediately(restored, clearSelection = true)
        schedulePreview(restored)
    }

    fun prepareExport(dpi: Int) {
        val normalizedDpi = normalizeCoverExportDpi(dpi)
        val state = _uiState.value
        val projectJson = state.projectJson.takeIf(String::isNotBlank)
        if (!state.canExport || projectJson == null) {
            _uiState.update { it.copy(errorMessage = "請先完成封面並確認正文頁數。") }
            return
        }
        viewModelScope.launch {
            _uiState.update {
                it.copy(
                    status = CoverStatus.EXPORTING,
                    exportDpi = normalizedDpi,
                    errorMessage = null,
                    saveMessage = null,
                )
            }
            try {
                val pending = withContext(Dispatchers.IO) {
                    val title = state.metadataTitle.ifBlank { state.project?.metadata?.title.orEmpty() }
                        .ifBlank { "書籍" }
                    val pdf = repository.createPdfFile(title).apply { delete() }
                    val docx = repository.createDocxFile(title).apply { delete() }
                    gateway.export(projectJson, pdf, docx, normalizedDpi)
                    require(pdf.isFile && pdf.length() > 0L) { "PDF 封面輸出失敗。" }
                    require(docx.isFile && docx.length() > 0L) { "DOCX 封面輸出失敗。" }
                    PendingCoverExports(pdf, docx, title)
                }
                pendingExports = pending
                _uiState.update {
                    it.copy(
                        status = CoverStatus.READY_TO_SAVE,
                        exportPdfPath = pending.pdf.absolutePath,
                        exportDocxPath = pending.docx.absolutePath,
                        exportDirectoryRequestId = it.exportDirectoryRequestId + 1L,
                        saveMessage = "PDF 與 DOCX 已在本機建立，請選擇儲存資料夾。",
                    )
                }
            } catch (failure: OutOfMemoryError) {
                _uiState.update {
                    it.copy(
                        status = CoverStatus.EDITING,
                        errorMessage = if (normalizedDpi == 300) {
                            "300 DPI 匯出需要更多記憶體。請關閉其他 App 後重試，或明確選擇 200 DPI。"
                        } else {
                            "200 DPI 匯出時記憶體不足。請關閉其他 App 後重試。"
                        },
                    )
                }
            } catch (failure: Throwable) {
                _uiState.update {
                    it.copy(
                        status = CoverStatus.EDITING,
                        errorMessage = failure.message ?: "封面匯出失敗。",
                    )
                }
            }
        }
    }

    fun markExportDirectoryRequestHandled(requestId: Long) = _uiState.update {
        if (requestId > it.handledExportDirectoryRequestId) {
            it.copy(handledExportDirectoryRequestId = requestId)
        } else {
            it
        }
    }

    fun requestExportDirectoryAgain() = _uiState.update {
        if (it.canChooseExportDirectory) {
            it.copy(
                exportDirectoryRequestId = it.exportDirectoryRequestId + 1L,
                saveMessage = "請重新選擇儲存資料夾。",
            )
        } else {
            it
        }
    }

    fun exportDirectoryCancelled() = _uiState.update {
        if (pendingExports != null) {
            it.copy(
                status = CoverStatus.READY_TO_SAVE,
                saveMessage = "已取消選擇資料夾；本機輸出仍保留，可重新儲存。",
            )
        } else {
            it.copy(status = CoverStatus.EDITING)
        }
    }

    fun saveExports(treeUri: Uri) {
        val pending = pendingExports ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(status = CoverStatus.SAVING, errorMessage = null) }
            runCatching {
                repository.saveExportPair(pending.pdf, pending.docx, treeUri, pending.title)
            }.onSuccess { result ->
                _uiState.update {
                    it.copy(
                        status = if (result.isComplete) CoverStatus.COMPLETED else CoverStatus.READY_TO_SAVE,
                        saveMessage = result.userMessage,
                        errorMessage = result.errorMessage,
                    )
                }
                if (result.isComplete) pendingExports = null
            }.onFailure { failure ->
                _uiState.update {
                    it.copy(
                        status = CoverStatus.READY_TO_SAVE,
                        errorMessage = failure.message ?: "儲存封面輸出失敗。",
                        saveMessage = "PDF 與 DOCX 尚未完整儲存，可重試。",
                    )
                }
            }
        }
    }

    private fun commitProject(project: CoverProject, selectId: String? = _uiState.value.selectedElementId) {
        val nextJson = CoverProjectJson.encode(project)
        val current = _uiState.value.projectJson
        if (nextJson == current) return
        if (current.isNotBlank()) pushBounded(undoHistory, current)
        redoHistory.clear()
        pendingExports = null
        setProjectImmediately(nextJson, selectId = selectId)
        schedulePreview(nextJson)
    }

    private fun setProjectImmediately(
        projectJson: String,
        clearSelection: Boolean = false,
        selectId: String? = null,
    ) {
        val project = CoverProjectJson.decode(projectJson)
        _uiState.update {
            it.copy(
                status = CoverStatus.EDITING,
                project = project,
                projectJson = projectJson,
                selectedElementId = if (clearSelection) null else selectId,
                guides = project.editorGuides(),
                canUndo = undoHistory.isNotEmpty(),
                canRedo = redoHistory.isNotEmpty(),
                exportPdfPath = null,
                exportDocxPath = null,
                saveMessage = null,
                errorMessage = null,
            )
        }
    }

    private fun schedulePreview(projectJson: String) {
        previewDebouncer.schedule(projectJson)
    }

    private suspend fun renderPreviewNow(projectJson: String) {
        if (_uiState.value.projectJson != projectJson) return
        _uiState.update { it.copy(status = CoverStatus.RENDERING) }
        runCatching {
            withContext(Dispatchers.IO) {
                gateway.renderPreview(projectJson, repository.createPreviewFile(), 1600)
                    .getString("path")
            }
        }.onSuccess { path ->
            if (_uiState.value.projectJson == projectJson) _uiState.update {
                it.copy(status = CoverStatus.EDITING, previewPath = path, errorMessage = null)
            }
        }.onFailure {
            if (_uiState.value.projectJson == projectJson) showError(it)
        }
    }

    fun dismissError() = _uiState.update {
        it.copy(
            status = when {
                pendingExports != null -> CoverStatus.READY_TO_SAVE
                it.project != null -> CoverStatus.EDITING
                it.sourcePath != null -> CoverStatus.SETUP
                else -> CoverStatus.IDLE
            },
            errorMessage = null,
        )
    }

    private fun resetEditorSession() {
        pendingExports = null
        undoHistory.clear()
        redoHistory.clear()
        previewDebouncer.cancel()
    }

    private fun showError(failure: Throwable) {
        _uiState.update {
            it.copy(status = CoverStatus.ERROR, errorMessage = failure.message ?: "封面處理失敗。")
        }
    }

    private fun pushBounded(history: ArrayDeque<String>, value: String) {
        history.addLast(value)
        while (history.size > MAX_HISTORY) history.removeFirst()
    }

    override fun onCleared() {
        previewDebouncer.cancel()
        gateway.close()
        repository.clearSession(keepForRetry = pendingExports != null)
        super.onCleared()
    }

    private data class PendingCoverExports(
        val pdf: File,
        val docx: File,
        val title: String,
    )

    private companion object {
        const val MAX_HISTORY = 50
    }
}

private fun trimPresetFor(trimSize: TrimSize): TrimPreset = when {
    trimSize.matches(TrimPreset.A5) -> TrimPreset.A5
    trimSize.matches(TrimPreset.A6) -> TrimPreset.A6
    trimSize.matches(TrimPreset.INCH_4X6) -> TrimPreset.INCH_4X6
    else -> throw IllegalArgumentException("轉換結果的裁切尺寸不受支援。")
}

private fun TrimSize.matches(preset: TrimPreset): Boolean =
    kotlin.math.abs(widthMm - preset.widthMm) < 0.000001 &&
        kotlin.math.abs(heightMm - preset.heightMm) < 0.000001

private fun JSONObject.stringList(key: String): List<String> {
    val array = optJSONArray(key) ?: return emptyList()
    return buildList { for (index in 0 until array.length()) add(array.optString(index)) }
}
