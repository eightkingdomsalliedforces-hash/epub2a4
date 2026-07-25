package tw.daniel.epubword.ui

import android.app.Application
import android.net.Uri
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import tw.daniel.epubword.cover.model.CoverHandoff
import tw.daniel.epubword.cover.model.createCoverHandoff
import tw.daniel.epubword.data.DocumentRepository
import tw.daniel.epubword.model.ConversionOptions
import tw.daniel.epubword.model.ConversionResult
import tw.daniel.epubword.model.InputKind
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.StagedInput
import tw.daniel.epubword.python.PythonConversionGateway
import java.io.File
import java.util.concurrent.CancellationException
import java.util.concurrent.atomic.AtomicBoolean

enum class WorkStatus {
    IDLE, STAGING, READY, CONVERTING, READY_TO_SAVE, SAVING, COMPLETED, CANCELLED, ERROR,
}

data class ConversionUiState(
    val inputName: String? = null,
    val inputKind: InputKind? = null,
    val inputSizeBytes: Long? = null,
    val options: ConversionOptions = ConversionOptions(),
    val status: WorkStatus = WorkStatus.IDLE,
    val progress: Int = 0,
    val statusMessage: String = "請先選擇 EPUB 或 DOCX 文件。",
    val result: ConversionResult? = null,
    val errorMessage: String? = null,
    val pendingOutputName: String? = null,
    val saveRequestId: Long = 0,
    val handledSaveRequestId: Long = 0,
    val coverHandoff: CoverHandoff? = null,
    val coverHandoffRequestId: Long = 0,
    val handledCoverHandoffRequestId: Long = 0,
) {
    val isBusy: Boolean get() = status in setOf(WorkStatus.STAGING, WorkStatus.CONVERTING, WorkStatus.SAVING)
    val canConvert: Boolean get() = inputName != null && !isBusy
    val canSave: Boolean get() = status == WorkStatus.READY_TO_SAVE && pendingOutputName != null
    val canCreateCover: Boolean get() = result != null && inputName != null && !isBusy
}

class ConversionViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = DocumentRepository(application)
    private val gateway = PythonConversionGateway(application)
    private val cancellation = AtomicBoolean(false)
    private var stagedInput: StagedInput? = null
    private var pendingOutput: File? = null
    private var activeJob: Job? = null

    private val _uiState = kotlinx.coroutines.flow.MutableStateFlow(ConversionUiState())
    val uiState: kotlinx.coroutines.flow.StateFlow<ConversionUiState> = _uiState

    fun selectInput(uri: Uri) {
        if (_uiState.value.isBusy) return
        activeJob?.cancel()
        activeJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                status = WorkStatus.STAGING,
                progress = 0,
                statusMessage = "正在讀取文件…",
                errorMessage = null,
                result = null,
                coverHandoff = null,
            )
            runCatching { repository.stageInput(uri) }
                .onSuccess { input ->
                    repository.delete(stagedInput?.localFile)
                    repository.delete(pendingOutput)
                    pendingOutput = null
                    stagedInput = input
                    val normalized = _uiState.value.options.normalizedFor(input.kind)
                    _uiState.value = _uiState.value.copy(
                        inputName = input.displayName,
                        inputKind = input.kind,
                        inputSizeBytes = input.sizeBytes,
                        options = normalized,
                        status = WorkStatus.READY,
                        progress = 0,
                        statusMessage = "文件已就緒。",
                        errorMessage = null,
                        pendingOutputName = null,
                    )
                }
                .onFailure { failure ->
                    _uiState.value = _uiState.value.copy(
                        status = WorkStatus.ERROR,
                        statusMessage = "無法開啟文件。",
                        errorMessage = failure.message ?: "無法讀取所選文件。",
                    )
                }
        }
    }

    fun setOutputMode(mode: OutputMode) = updateOptions { copy(outputMode = mode) }
    fun setMarginMode(mode: MarginMode) = updateOptions { copy(marginMode = mode) }
    fun setFontName(value: String) = updateOptions { copy(fontName = value) }
    fun setBodyFontPt(value: Double) = updateOptions { copy(bodyFontPt = value) }
    fun setHeadingFontPt(value: Double) = updateOptions { copy(headingFontPt = value) }
    fun setPageNumbers(value: Boolean) = updateOptions { copy(pageNumbers = value) }
    fun setCutGuides(value: Boolean) = updateOptions { copy(cutGuides = value) }

    private fun updateOptions(transform: ConversionOptions.() -> ConversionOptions) {
        if (_uiState.value.isBusy) return
        val kind = _uiState.value.inputKind
        val updated = _uiState.value.options.transform().let { options ->
            if (kind == null) options else options.normalizedFor(kind)
        }
        _uiState.value = _uiState.value.copy(options = updated)
    }

    fun convert() {
        val input = stagedInput ?: return
        if (_uiState.value.isBusy) return
        cancellation.set(false)
        repository.delete(pendingOutput)
        val output = repository.createOutputFile(input, _uiState.value.options.outputMode)
        pendingOutput = output

        activeJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                status = WorkStatus.CONVERTING,
                progress = 0,
                statusMessage = "準備轉換…",
                errorMessage = null,
                result = null,
                pendingOutputName = null,
                coverHandoff = null,
            )
            try {
                val result = gateway.convert(
                    input = input.localFile,
                    output = output,
                    options = _uiState.value.options.normalizedFor(input.kind),
                    cancellation = cancellation,
                ) { percent, message ->
                    _uiState.value = _uiState.value.copy(
                        progress = percent,
                        statusMessage = message,
                    )
                }
                val name = repository.suggestedOutputName(input, _uiState.value.options.outputMode)
                _uiState.value = _uiState.value.copy(
                    status = WorkStatus.READY_TO_SAVE,
                    progress = 100,
                    statusMessage = "轉換完成，請選擇儲存位置。",
                    result = result,
                    pendingOutputName = name,
                    saveRequestId = _uiState.value.saveRequestId + 1,
                )
            } catch (_: CancellationException) {
                repository.delete(output)
                pendingOutput = null
                _uiState.value = _uiState.value.copy(
                    status = WorkStatus.CANCELLED,
                    progress = 0,
                    statusMessage = "轉換已取消。",
                    pendingOutputName = null,
                )
            } catch (failure: Throwable) {
                Log.e(TAG, "Conversion failed", failure)
                repository.delete(output)
                pendingOutput = null
                _uiState.value = _uiState.value.copy(
                    status = WorkStatus.ERROR,
                    progress = 0,
                    statusMessage = "轉換失敗。",
                    errorMessage = failure.message ?: "未知錯誤",
                    pendingOutputName = null,
                )
            }
        }
    }

    fun cancelConversion() {
        if (_uiState.value.status == WorkStatus.CONVERTING) {
            cancellation.set(true)
            _uiState.value = _uiState.value.copy(statusMessage = "正在取消…")
        }
    }

    fun requestSave() {
        if (_uiState.value.canSave) {
            _uiState.value = _uiState.value.copy(saveRequestId = _uiState.value.saveRequestId + 1)
        }
    }

    fun markSaveDialogHandled(requestId: Long) {
        if (requestId > _uiState.value.handledSaveRequestId) {
            _uiState.value = _uiState.value.copy(handledSaveRequestId = requestId)
        }
    }

    fun saveOutput(destination: Uri?) {
        if (destination == null) {
            _uiState.value = _uiState.value.copy(statusMessage = "尚未儲存；可再次按下儲存。")
            return
        }
        val output = pendingOutput ?: return
        if (_uiState.value.status != WorkStatus.READY_TO_SAVE) return
        activeJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                status = WorkStatus.SAVING,
                statusMessage = "正在儲存 Word 文件…",
                errorMessage = null,
            )
            runCatching { repository.saveOutput(output, destination) }
                .onSuccess {
                    repository.delete(output)
                    pendingOutput = null
                    _uiState.value = _uiState.value.copy(
                        status = WorkStatus.COMPLETED,
                        statusMessage = "文件已儲存。",
                        pendingOutputName = null,
                    )
                }
                .onFailure { failure ->
                    _uiState.value = _uiState.value.copy(
                        status = WorkStatus.READY_TO_SAVE,
                        statusMessage = "儲存失敗；可重新選擇位置。",
                        errorMessage = failure.message ?: "無法儲存文件。",
                    )
                }
        }
    }

    fun requestCoverHandoff() {
        val input = stagedInput ?: return
        val state = _uiState.value
        val result = state.result ?: return
        if (state.isBusy) return
        activeJob = viewModelScope.launch {
            runCatching {
                val copied = withContext(Dispatchers.IO) { repository.copyForCoverSession(input) }
                createCoverHandoff(copied, result, state.options.outputMode)
            }.onSuccess { handoff ->
                _uiState.value = _uiState.value.copy(
                    coverHandoff = handoff,
                    coverHandoffRequestId = _uiState.value.coverHandoffRequestId + 1L,
                    errorMessage = null,
                )
            }.onFailure { failure ->
                _uiState.value = _uiState.value.copy(
                    errorMessage = failure.message ?: "無法將來源交給封面工具。",
                )
            }
        }
    }

    fun markCoverHandoffHandled(requestId: Long) {
        if (requestId > _uiState.value.handledCoverHandoffRequestId) {
            _uiState.value = _uiState.value.copy(
                handledCoverHandoffRequestId = requestId,
                coverHandoff = null,
            )
        }
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }

    override fun onCleared() {
        cancellation.set(true)
        repository.delete(pendingOutput)
        repository.delete(stagedInput?.localFile)
        repository.clearWorkingFiles()
        gateway.close()
        super.onCleared()
    }

    private companion object {
        const val TAG = "EpubWordConversion"
    }
}
