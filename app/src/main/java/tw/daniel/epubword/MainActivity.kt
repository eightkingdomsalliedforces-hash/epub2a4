package tw.daniel.epubword

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import tw.daniel.epubword.cover.ui.CoverEditorCallbacks
import tw.daniel.epubword.cover.ui.CoverSetupCallbacks
import tw.daniel.epubword.cover.ui.CoverViewModel
import tw.daniel.epubword.cover.ui.publisherLogoSearchUri
import android.net.Uri
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
                ) { uri -> if (uri != null) conversionViewModel.selectInput(uri) }
                val outputLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.CreateDocument(DOCX_MIME),
                ) { uri -> conversionViewModel.saveOutput(uri) }
                val coverSourceLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri -> if (uri != null) coverViewModel.selectSource(uri) }
                val coverImageLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri -> if (uri != null) coverViewModel.importLocalImage(uri) }
                val publisherLogoLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocument(),
                ) { uri -> if (uri != null) coverViewModel.assignPublisherLogo(uri) }
                val coverDirectoryLauncher = rememberLauncherForActivityResult(
                    contract = ActivityResultContracts.OpenDocumentTree(),
                ) { uri ->
                    if (uri == null) {
                        coverViewModel.exportDirectoryCancelled()
                    } else {
                        runCatching {
                            contentResolver.takePersistableUriPermission(
                                uri,
                                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                            )
                        }
                        coverViewModel.saveExports(uri)
                    }
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

                LaunchedEffect(
                    coverState.exportDirectoryRequestId,
                    coverState.handledExportDirectoryRequestId,
                ) {
                    if (
                        coverState.exportDirectoryRequestId >
                        coverState.handledExportDirectoryRequestId &&
                        coverState.canChooseExportDirectory
                    ) {
                        val requestId = coverState.exportDirectoryRequestId
                        coverViewModel.markExportDirectoryRequestHandled(requestId)
                        coverDirectoryLauncher.launch(null)
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
                    onContentOnly = conversionViewModel::setContentOnly,
                    onConvert = conversionViewModel::convert,
                    onCancelConversion = conversionViewModel::cancelConversion,
                    onSaveConversion = conversionViewModel::requestSave,
                    onDismissConversionError = conversionViewModel::dismissError,
                    onRequestCoverHandoff = conversionViewModel::requestCoverHandoff,
                    onOpenCoverHandoff = coverViewModel::openHandoff,
                    onMarkCoverHandoffHandled = conversionViewModel::markCoverHandoffHandled,
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
                        onChoosePublisherLogo = { publisherLogoLauncher.launch(arrayOf("image/*")) },
                        onSearchPublisherLogo = {
                            if (coverState.metadataPublisher.isNotBlank()) {
                                startActivity(
                                    Intent(
                                        Intent.ACTION_VIEW,
                                        Uri.parse(publisherLogoSearchUri(coverState.metadataPublisher)),
                                    ),
                                )
                            }
                        },
                        onCreateProject = coverViewModel::createProject,
                    ),
                    coverEditorCallbacks = CoverEditorCallbacks(
                        onUndo = coverViewModel::undo,
                        onRedo = coverViewModel::redo,
                        onApplyTemplate = coverViewModel::applyTemplate,
                        onAddImage = { coverImageLauncher.launch(arrayOf("image/*")) },
                        onSelectEmbeddedImage = coverViewModel::selectEmbeddedImage,
                        onAddText = coverViewModel::addText,
                        onToggleGuides = coverViewModel::toggleGuides,
                        onPrepareExport = coverViewModel::prepareExport,
                        onRequestExportDirectory = coverViewModel::requestExportDirectoryAgain,
                        onSelectElement = coverViewModel::selectElement,
                        onSelectAtMm = coverViewModel::selectElementAt,
                        onPatchElement = coverViewModel::patchElement,
                        onDeleteElement = coverViewModel::removeElement,
                        onTransformElement = coverViewModel::applyTransformPatch,
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
