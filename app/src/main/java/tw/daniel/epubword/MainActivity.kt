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
import tw.daniel.epubword.cover.ui.CoverSetupCallbacks
import tw.daniel.epubword.cover.ui.CoverViewModel
import tw.daniel.epubword.ui.AppRoot
import tw.daniel.epubword.ui.ConversionViewModel
import tw.daniel.epubword.ui.theme.EpubWordTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            EpubWordTheme {
                val conversionViewModel: ConversionViewModel = viewModel()
                val conversionState by conversionViewModel.uiState.collectAsStateWithLifecycle()
                val coverViewModel: CoverViewModel = viewModel()
                val coverState by coverViewModel.uiState.collectAsStateWithLifecycle()

                val inputLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri ->
                    if (uri != null) conversionViewModel.selectInput(uri)
                }
                val outputLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.CreateDocument(DOCX_MIME),
                ) { uri ->
                    conversionViewModel.saveOutput(uri)
                }
                val coverSourceLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri ->
                    if (uri != null) coverViewModel.selectSource(uri)
                }

                LaunchedEffect(conversionState.saveRequestId, conversionState.pendingOutputName) {
                    val pendingName = conversionState.pendingOutputName
                    if (
                        conversionState.saveRequestId > conversionState.handledSaveRequestId &&
                        pendingName != null
                    ) {
                        val requestId = conversionState.saveRequestId
                        conversionViewModel.markSaveDialogHandled(requestId)
                        outputLauncher.launch(pendingName)
                    }
                }

                AppRoot(
                    conversionState = conversionState,
                    onChooseConversionSource = {
                        inputLauncher.launch(arrayOf(EPUB_MIME, DOCX_MIME, "application/octet-stream"))
                    },
                    onOutputMode = conversionViewModel::setOutputMode,
                    onMarginMode = conversionViewModel::setMarginMode,
                    onFontName = conversionViewModel::setFontName,
                    onBodyFontSize = conversionViewModel::setBodyFontPt,
                    onHeadingFontSize = conversionViewModel::setHeadingFontPt,
                    onPageNumbers = conversionViewModel::setPageNumbers,
                    onCutGuides = conversionViewModel::setCutGuides,
                    onConvert = conversionViewModel::convert,
                    onCancelConversion = conversionViewModel::cancelConversion,
                    onSaveConversion = conversionViewModel::requestSave,
                    onDismissConversionError = conversionViewModel::dismissError,
                    coverState = coverState,
                    coverCallbacks = CoverSetupCallbacks(
                        onChooseSource = {
                            coverSourceLauncher.launch(
                                arrayOf(EPUB_MIME, DOCX_MIME, PDF_MIME, "application/octet-stream"),
                            )
                        },
                        onTrimPreset = coverViewModel::setTrimPreset,
                        onPageCount = coverViewModel::setPageCount,
                        onConfirmPageCount = coverViewModel::confirmPageCount,
                        onPaperPreset = coverViewModel::setPaperPreset,
                        onCaliper = coverViewModel::setCaliper,
                        onManualSpine = coverViewModel::setManualSpine,
                        onBleed = coverViewModel::setBleed,
                        onImageMode = coverViewModel::setImageMode,
                        onTemplate = coverViewModel::setTemplate,
                        onCreateProject = coverViewModel::createProject,
                    ),
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
