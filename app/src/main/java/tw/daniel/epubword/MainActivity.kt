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

                LaunchedEffect(state.saveRequestId, state.pendingOutputName) {
                    val pendingName = state.pendingOutputName
                    if (state.saveRequestId > state.handledSaveRequestId && pendingName != null) {
                        val requestId = state.saveRequestId
                        viewModel.markSaveDialogHandled(requestId)
                        outputLauncher.launch(pendingName)
                    }
                }

                AppRoot(
                    conversionState = state,
                    onChooseConversionSource = {
                        inputLauncher.launch(arrayOf(EPUB_MIME, DOCX_MIME, "application/octet-stream"))
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
                )
            }
        }
    }

    private companion object {
        const val EPUB_MIME = "application/epub+zip"
        const val DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
}
