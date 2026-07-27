package tw.daniel.epubword

import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import tw.daniel.epubword.cover.ui.CoverEditorCallbacks
import tw.daniel.epubword.cover.ui.CoverSetupCallbacks
import tw.daniel.epubword.cover.ui.CoverViewModel
import tw.daniel.epubword.cover.ui.publisherLogoSearchUri
import tw.daniel.epubword.ui.AppRoot
import tw.daniel.epubword.ui.ConversionViewModel
import tw.daniel.epubword.ui.theme.EpubWordTheme
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            EpubWordTheme {
                val conversionViewModel: ConversionViewModel = viewModel()
                val conversionState by conversionViewModel.uiState.collectAsStateWithLifecycle()
                val coverViewModel: CoverViewModel = viewModel()
                val coverState by coverViewModel.uiState.collectAsStateWithLifecycle()
                var coverWordPreviewRequested by remember { mutableStateOf(false) }

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
                    coverState.exportDocxPath,
                ) {
                    if (
                        coverState.exportDirectoryRequestId >
                        coverState.handledExportDirectoryRequestId &&
                        coverState.canChooseExportDirectory
                    ) {
                        val requestId = coverState.exportDirectoryRequestId
                        coverViewModel.markExportDirectoryRequestHandled(requestId)
                        val previewPath = coverState.exportDocxPath
                        if (coverWordPreviewRequested && !previewPath.isNullOrBlank()) {
                            coverWordPreviewRequested = false
                            try {
                                val previewFile = File(previewPath)
                                require(previewFile.isFile && previewFile.length() > 0L) {
                                    "找不到 Word 預覽檔。"
                                }
                                val uri = FileProvider.getUriForFile(
                                    this@MainActivity,
                                    "$packageName.fileprovider",
                                    previewFile,
                                )
                                val previewIntent = Intent(Intent.ACTION_VIEW)
                                    .setDataAndType(uri, DOCX_MIME)
                                    .addFlags(
                                        Intent.FLAG_GRANT_READ_URI_PERMISSION or
                                            Intent.FLAG_ACTIVITY_NEW_TASK,
                                    )
                                startActivity(Intent.createChooser(previewIntent, "Word 預覽"))
                            } catch (failure: ActivityNotFoundException) {
                                Toast.makeText(
                                    this@MainActivity,
                                    "未安裝可開啟 DOCX 的 Word、WPS 或文件檢視器。",
                                    Toast.LENGTH_LONG,
                                ).show()
                            } catch (failure: Throwable) {
                                Toast.makeText(
                                    this@MainActivity,
                                    failure.message ?: "無法開啟 Word 預覽。",
                                    Toast.LENGTH_LONG,
                                ).show()
                            }
                        } else {
                            coverDirectoryLauncher.launch(null)
                        }
                    }
                }

                LaunchedEffect(coverState.errorMessage) {
                    if (coverState.errorMessage != null) coverWordPreviewRequested = false
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
                        onIsbn = coverViewModel::setMetadataIsbn,
                        onIsbnAddon = coverViewModel::setMetadataIsbnAddon,
                        onPublisher = coverViewModel::setMetadataPublisher,
                        onPrice = coverViewModel::setMetadataPrice,
                        onPublicationPlace = coverViewModel::setMetadataPublicationPlace,
                        onTranslator = coverViewModel::setMetadataTranslator,
                        onPublisherId = coverViewModel::setMetadataPublisherId,
                        onEnglishTitle = coverViewModel::setMetadataEnglishTitle,
                        onVolumeNumber = coverViewModel::setMetadataVolumeNumber,
                        onArcLabel = coverViewModel::setMetadataArcLabel,
                        onSeriesName = coverViewModel::setMetadataSeriesName,
                        onInternalBookCode = coverViewModel::setMetadataInternalBookCode,
                        onSpineAccentColor = coverViewModel::setMetadataSpineAccentColor,
                        onChoosePublisherLogo = {
                            publisherLogoLauncher.launch(arrayOf("image/*"))
                        },
                        onSearchPublisherLogo = {
                            startActivity(
                                Intent(
                                    Intent.ACTION_VIEW,
                                    android.net.Uri.parse(
                                        publisherLogoSearchUri(coverState.metadataPublisher),
                                    ),
                                ),
                            )
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
                        onPreviewWord = {
                            coverWordPreviewRequested = true
                            coverViewModel.prepareExport(coverState.exportDpi)
                        },
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
