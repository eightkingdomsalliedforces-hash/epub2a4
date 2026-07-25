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
import tw.daniel.epubword.cover.model.CoverProject
import tw.daniel.epubword.cover.model.CoverProjectJson
import tw.daniel.epubword.cover.model.CoverRegion
import tw.daniel.epubword.cover.model.ElementKind
import tw.daniel.epubword.cover.model.ElementTransform
import tw.daniel.epubword.cover.model.ImageMode
import tw.daniel.epubword.python.PythonCoverGateway
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
    private var previewGeneration = 0

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
                undoHistory.clear()
                redoHistory.clear()
                val metadata = inspection.optJSONObject("metadata") ?: JSONObject()
                val fixedPages = if (
                    !inspection.has("fixed_page_count") || inspection.isNull("fixed_page_count")
                ) 0 else inspection.getInt("fixed_page_count")
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
                        pageCount = fixedPages,
                        pageCountEstimated = fixedPages <= 0,
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
        if (value == 200 || value == 300) _uiState.update { it.copy(exportDpi = value) }
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
        val updated = project.elements.map { element ->
            if (element.id != elementId) element else element.copy(
                transform = patch.transform ?: element.transform,
                opacity = patch.opacity ?: element.opacity,
                content = patch.content?.let { JSONObject(it.toString()) }
                    ?: JSONObject(element.content.toString()),
            )
        }
        if (updated == project.elements) return
        commitProject(project.copy(elements = updated))
    }

    fun applyTransformPatch(patch: ElementTransformPatch) {
        val element = _uiState.value.project?.elements?.firstOrNull { it.id == patch.elementId } ?: return
        val current = element.transform
        val scale = patch.scale.takeIf { it.isFinite() && it > 0.0 } ?: 1.0
        patchElement(
            patch.elementId,
            ElementPatch(
                transform = current.copy(
                    xMm = current.xMm + patch.deltaXMm,
                    yMm = current.yMm + patch.deltaYMm,
                    widthMm = max(0.1, current.widthMm * scale),
                    heightMm = max(0.1, current.heightMm * scale),
                    rotationDeg = current.rotationDeg + patch.rotationDeltaDeg,
                ),
            ),
        )
    }

    fun addText() {
        val project = _uiState.value.project ?: return
        val spine = project.manualSpineWidthMm ?: ((project.pageCount + 1) / 2) * project.paperCaliperMm
        val element = CoverElement(
            id = "android-text-${UUID.randomUUID()}",
            kind = ElementKind.TEXT,
            region = CoverRegion.FRONT,
            transform = ElementTransform(
                xMm = project.bleedMm + project.trimSize.widthMm + spine + 12.0,
                yMm = project.bleedMm + 24.0,
                widthMm = max(20.0, project.trimSize.widthMm - 24.0),
                heightMm = 30.0,
            ),
            zIndex = (project.elements.maxOfOrNull(CoverElement::zIndex) ?: 0) + 1,
            content = JSONObject()
                .put("text", "新文字")
                .put("font_size_pt", 24.0)
                .put("color", "#111111")
                .put("align", "center"),
        )
        commitProject(project.copy(elements = project.elements + element), selectId = element.id)
    }

    fun importLocalImage(uri: Uri) {
        val project = _uiState.value.project ?: return
        viewModelScope.launch {
            runCatching { repository.stageLocalImage(uri) }
                .onSuccess { file ->
                    val spine = project.manualSpineWidthMm
                        ?: ((project.pageCount + 1) / 2) * project.paperCaliperMm
                    val element = CoverElement(
                        id = "android-image-${UUID.randomUUID()}",
                        kind = ElementKind.IMAGE,
                        region = CoverRegion.FRONT,
                        transform = ElementTransform(
                            xMm = project.bleedMm + project.trimSize.widthMm + spine,
                            yMm = project.bleedMm,
                            widthMm = project.trimSize.widthMm,
                            heightMm = project.trimSize.heightMm,
                        ),
                        zIndex = (project.elements.maxOfOrNull(CoverElement::zIndex) ?: 0) + 1,
                        content = JSONObject()
                            .put("path", file.absolutePath)
                            .put("fit", "cover"),
                    )
                    commitProject(project.copy(elements = project.elements + element), selectId = element.id)
                }
                .onFailure(::showError)
        }
    }

    fun removeElement(elementId: String) {
        val project = _uiState.value.project ?: return
        if (project.elements.none { it.id == elementId }) return
        commitProject(
            project.copy(elements = project.elements.filterNot { it.id == elementId }),
            selectId = null,
        )
    }

    fun undo() {
        if (undoHistory.isEmpty()) return
        val current = _uiState.value.projectJson
        if (current.isNotBlank()) redoHistory.addLast(current)
        val restored = undoHistory.removeLast()
        setProjectImmediately(restored, clearSelection = true)
        schedulePreview(restored)
    }

    fun redo() {
        if (redoHistory.isEmpty()) return
        val current = _uiState.value.projectJson
        if (current.isNotBlank()) pushBounded(undoHistory, current)
        val restored = redoHistory.removeLast()
        setProjectImmediately(restored, clearSelection = true)
        schedulePreview(restored)
    }

    private fun commitProject(project: CoverProject, selectId: String? = _uiState.value.selectedElementId) {
        val nextJson = CoverProjectJson.encode(project)
        val current = _uiState.value.projectJson
        if (nextJson == current) return
        if (current.isNotBlank()) pushBounded(undoHistory, current)
        redoHistory.clear()
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
                guides = buildGuides(project),
                canUndo = undoHistory.isNotEmpty(),
                canRedo = redoHistory.isNotEmpty(),
                errorMessage = null,
            )
        }
    }

    private fun schedulePreview(projectJson: String) {
        val generation = ++previewGeneration
        viewModelScope.launch {
            _uiState.update { it.copy(status = CoverStatus.RENDERING) }
            runCatching {
                withContext(Dispatchers.IO) {
                    gateway.renderPreview(projectJson, repository.createPreviewFile(), 1600)
                        .getString("path")
                }
            }.onSuccess { path ->
                if (generation == previewGeneration) _uiState.update {
                    it.copy(status = CoverStatus.EDITING, previewPath = path, errorMessage = null)
                }
            }.onFailure { if (generation == previewGeneration) showError(it) }
        }
    }

    fun dismissError() = _uiState.update {
        it.copy(
            status = when {
                it.project != null -> CoverStatus.EDITING
                it.sourcePath != null -> CoverStatus.SETUP
                else -> CoverStatus.IDLE
            },
            errorMessage = null,
        )
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
        gateway.close()
        repository.clearSession()
        super.onCleared()
    }

    private companion object {
        const val MAX_HISTORY = 50
    }
}

private fun buildGuides(project: CoverProject): CoverGuides {
    val spine = project.manualSpineWidthMm ?: ((project.pageCount + 1) / 2) * project.paperCaliperMm
    val bleed = project.bleedMm
    val trimW = project.trimSize.widthMm
    val trimH = project.trimSize.heightMm
    val back = MmRect(bleed, bleed, trimW, trimH)
    val spineRect = MmRect(bleed + trimW, bleed, spine, trimH)
    val front = MmRect(bleed + trimW + spine, bleed, trimW, trimH)
    val safeInset = 5.0
    return CoverGuides(
        bleedRects = listOf(MmRect(0.0, 0.0, trimW * 2 + spine + bleed * 2, trimH + bleed * 2)),
        regionRects = listOf(back, spineRect, front),
        safeRects = listOf(
            MmRect(back.xMm + safeInset, back.yMm + safeInset, max(0.0, back.widthMm - safeInset * 2), max(0.0, back.heightMm - safeInset * 2)),
            MmRect(front.xMm + safeInset, front.yMm + safeInset, max(0.0, front.widthMm - safeInset * 2), max(0.0, front.heightMm - safeInset * 2)),
        ),
    )
}

private fun JSONObject.stringList(key: String): List<String> {
    val array = optJSONArray(key) ?: return emptyList()
    return buildList { for (index in 0 until array.length()) add(array.optString(index)) }
}
