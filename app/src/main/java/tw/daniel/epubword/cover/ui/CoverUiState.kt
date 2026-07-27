package tw.daniel.epubword.cover.ui

import tw.daniel.epubword.cover.model.CoverProject
import tw.daniel.epubword.cover.model.ImageMode

enum class CoverStatus {
    IDLE,
    STAGING,
    INSPECTING,
    SETUP,
    CREATING,
    EDITING,
    RENDERING,
    EXPORTING,
    READY_TO_SAVE,
    SAVING,
    COMPLETED,
    ERROR,
}

enum class TrimPreset(val label: String, val widthMm: Double, val heightMm: Double) {
    A5("A5", 148.0, 210.0),
    B6("B6", 128.0, 182.0),
    A6("A6", 105.0, 148.0),
    INCH_4X6("4 × 6 英吋", 101.6, 152.4),
}

enum class PaperPreset(val gsm: Int, val caliperMm: Double) {
    GSM_70(70, 0.09),
    GSM_80(80, 0.10),
    GSM_100(100, 0.12),
    GSM_120(120, 0.14),
}

data class CoverUiState(
    val status: CoverStatus = CoverStatus.IDLE,
    val sourceName: String? = null,
    val sourcePath: String? = null,
    val sourceType: String? = null,
    val metadataTitle: String = "",
    val metadataAuthor: String = "",
    val metadataDescription: String = "",
    val metadataIsbn: String = "",
    val metadataPublisher: String = "",
    val metadataLanguage: String = "",
    val trimPreset: TrimPreset = TrimPreset.A5,
    val pageCount: Int = 0,
    val pageCountEstimated: Boolean = false,
    val pageCountConfirmed: Boolean = false,
    val paperPreset: PaperPreset = PaperPreset.GSM_80,
    val paperCaliperMm: Double = PaperPreset.GSM_80.caliperMm,
    val manualSpineWidthMm: Double? = null,
    val bleedMm: Double = 3.0,
    val imageMode: ImageMode = ImageMode.FRONT_ONLY,
    val templateId: String = "minimal_text",
    val warnings: List<String> = emptyList(),
    val project: CoverProject? = null,
    val projectJson: String = "",
    val previewPath: String? = null,
    val selectedElementId: String? = null,
    val guidesVisible: Boolean = true,
    val guides: CoverGuides = CoverGuides(),
    val canUndo: Boolean = false,
    val canRedo: Boolean = false,
    val exportPdfPath: String? = null,
    val exportDocxPath: String? = null,
    val exportDpi: Int = 300,
    val exportDirectoryRequestId: Long = 0L,
    val handledExportDirectoryRequestId: Long = 0L,
    val wordPreviewPath: String? = null,
    val wordPreviewRequestId: Long = 0L,
    val handledWordPreviewRequestId: Long = 0L,
    val saveMessage: String? = null,
    val errorMessage: String? = null,
) {
    val isBusy: Boolean get() = status in setOf(
        CoverStatus.STAGING,
        CoverStatus.INSPECTING,
        CoverStatus.CREATING,
        CoverStatus.RENDERING,
        CoverStatus.EXPORTING,
        CoverStatus.SAVING,
    )

    val sheetCount: Int get() = if (pageCount > 0) (pageCount + 1) / 2 else 0
    val autoSpineWidthMm: Double get() = sheetCount * paperCaliperMm
    val effectiveSpineWidthMm: Double get() = manualSpineWidthMm ?: autoSpineWidthMm
    val selectedElement get() = project?.elements?.firstOrNull { it.id == selectedElementId }

    val canCreateProject: Boolean get() =
        !sourcePath.isNullOrBlank() && pageCount > 0 && pageCountConfirmed && status == CoverStatus.SETUP

    val canExport: Boolean get() =
        project != null && projectJson.isNotBlank() && pageCountConfirmed &&
            status in setOf(CoverStatus.EDITING, CoverStatus.COMPLETED)

    val canChooseExportDirectory: Boolean get() =
        status == CoverStatus.READY_TO_SAVE &&
            !exportPdfPath.isNullOrBlank() &&
            !exportDocxPath.isNullOrBlank()

    val hasPendingWordPreview: Boolean get() =
        wordPreviewRequestId > handledWordPreviewRequestId && !wordPreviewPath.isNullOrBlank()
}
