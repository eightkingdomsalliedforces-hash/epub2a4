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
import tw.daniel.epubword.cover.model.CoverProjectJson
import tw.daniel.epubword.cover.model.ImageMode
import tw.daniel.epubword.python.PythonCoverGateway

class CoverViewModel @JvmOverloads constructor(
    application: Application,
    private val repository: CoverDocumentRepository = CoverDocumentRepository(application),
    private val gateway: PythonCoverGateway = PythonCoverGateway(application),
) : AndroidViewModel(application) {
    private val _uiState = MutableStateFlow(CoverUiState())
    val uiState: StateFlow<CoverUiState> = _uiState.asStateFlow()
    private var stagedSource: StagedCoverSource? = null

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
        if (value > 0.0 && value.isFinite()) {
            _uiState.update { it.copy(paperCaliperMm = value, errorMessage = null) }
        }
    }

    fun setManualSpine(value: Double?) {
        if (value == null || (value > 0.0 && value.isFinite())) {
            _uiState.update { it.copy(manualSpineWidthMm = value, errorMessage = null) }
        }
    }

    fun setBleed(value: Double) {
        if (value in 0.0..10.0 && value.isFinite()) {
            _uiState.update { it.copy(bleedMm = value, errorMessage = null) }
        }
    }

    fun setImageMode(value: ImageMode) = _uiState.update { it.copy(imageMode = value) }
    fun setTemplate(value: String) = _uiState.update { it.copy(templateId = value) }

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
                        .put(
                            "manual_spine_width_mm",
                            state.manualSpineWidthMm ?: JSONObject.NULL,
                        )
                        .put("bleed_mm", state.bleedMm)
                        .put("overlap_mm", 5.0)
                        .put("image_mode", state.imageMode.wire)
                    val created = gateway.newProject(staged.localFile, settings)
                    val templated = gateway.applyTemplate(created, state.templateId)
                    val preview = gateway.renderPreview(
                        templated,
                        repository.createPreviewFile(),
                        1600,
                    )
                    Triple(
                        CoverProjectJson.decode(templated),
                        templated,
                        preview.getString("path"),
                    )
                }
            }.onSuccess { (project, projectJson, previewPath) ->
                _uiState.update {
                    it.copy(
                        status = CoverStatus.EDITING,
                        project = project,
                        projectJson = projectJson,
                        previewPath = previewPath,
                        errorMessage = null,
                    )
                }
            }.onFailure(::showError)
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
            it.copy(
                status = CoverStatus.ERROR,
                errorMessage = failure.message ?: "封面處理失敗。",
            )
        }
    }

    override fun onCleared() {
        gateway.close()
        repository.clearSession()
        super.onCleared()
    }
}

private fun JSONObject.stringList(key: String): List<String> {
    val array = optJSONArray(key) ?: return emptyList()
    return buildList {
        for (index in 0 until array.length()) add(array.optString(index))
    }
}
