package tw.daniel.epubword

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import tw.daniel.epubword.ui.AppRoot
import tw.daniel.epubword.ui.ConversionViewModel
import tw.daniel.epubword.ui.theme.EpubWordTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            EpubWordTheme {
                val viewModel: ConversionViewModel = viewModel()
                val state by viewModel.uiState.collectAsStateWithLifecycle()

                val inputLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri ->
                    if (uri != null) viewModel.selectInput(uri)
                }
                val outputLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.CreateDocument(DOCX_MIME),
                ) { uri ->
                    viewModel.saveOutput(uri)
                }
                val coverSourceLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { _ ->
                    // Cover source handoff is added by the cover setup task. The launcher
                    // remains activity-owned so the UI never handles Activity contracts.
                }
                val coverImageLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { _ -> }
                val coverDirectoryLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocumentTree(),
                ) { _ -> }

                LaunchedEffect(state.saveRequestId, state.pendingOutputName) {
                    val pendingName = state.pendingOutputName
                    if (
                        state.saveRequestId > state.handledSaveRequestId &&
                        pendingName != null
                    ) {
                        val requestId = state.saveRequestId
                        viewModel.markSaveDialogHandled(requestId)
                        outputLauncher.launch(pendingName)
                    }
                }

                AppRoot(
                    conversionState = state,
                    onChooseConversionSource = {
                        inputLauncher.launch(
                            arrayOf(
                                EPUB_MIME,
                                DOCX_MIME,
                                "application/octet-stream",
                            )
                        )
                    },
                    onOutputMode = viewModel::setOutputMode,
                    onMarginMode = viewModel::setMarginMode,
                    onFontName = viewModel::setFontName,
                    onBodyFontSize = viewModel::setBodyFontPt,
                    onHeadingFontSize = viewModel::setHeadingFontPt,
                    onPageNumbers = viewModel::setPageNumbers,
                    onCutGuides = viewModel::setCutGuides,
                    onConvert = viewModel::convert,
                    onCancelConversion = viewModel::cancelConversion,
                    onSaveConversion = viewModel::requestSave,
                    onDismissConversionError = viewModel::dismissError,
                    onChooseCoverSource = {
                        coverSourceLauncher.launch(
                            arrayOf(EPUB_MIME, DOCX_MIME, PDF_MIME, "application/octet-stream")
                        )
                    },
                    onChooseCoverImage = { coverImageLauncher.launch(arrayOf("image/*")) },
                    onChooseCoverDirectory = { coverDirectoryLauncher.launch(null) },
                )
            }
        }
    }

    private companion object {
        const val EPUB_MIME = "application/epub+zip"
        const val DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        const val PDF_MIME = "application/pdf"
    }
}
