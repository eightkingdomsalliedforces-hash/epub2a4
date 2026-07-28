package tw.daniel.epubword.cover.model

import org.json.JSONObject

enum class ImageMode(val wire: String) {
    FRONT_ONLY("front_only"),
    FULL_SPREAD("full_spread"),
}

enum class ElementKind(val wire: String) {
    IMAGE("image"),
    TEXT("text"),
    SHAPE("shape"),
    BARCODE_PLACEHOLDER("barcode_placeholder"),
    GUIDE("guide"),
}

enum class CoverRegion(val wire: String) {
    BACK("back"),
    SPINE("spine"),
    FRONT("front"),
    SPREAD("spread"),
}

data class TrimSize(
    val widthMm: Double,
    val heightMm: Double,
)

data class CoverMetadata(
    val title: String = "",
    val author: String = "",
    val description: String = "",
    val isbn: String = "",
    val publisher: String = "",
    val price: String = "",
    val publicationPlace: String = "",
    val translator: String = "",
    val isbnAddon: String = "",
    val publisherId: String = "",
    val englishTitle: String = "",
    val volumeNumber: String = "",
    val arcLabel: String = "",
    val seriesName: String = "",
    val internalBookCode: String = "",
    val spineAccentColor: String = "#F15A24",
    val backVerticalCopy: String = "",
    val backHighlightCopy: String = "",
    val spineStyle: String = "reference_stacked",
    val accentColorMode: String = "auto",
    val extractedAccentColor: String = "",
    val language: String = "",
    val pageCountIsEstimate: Boolean = false,
    val embeddedImages: List<JSONObject> = emptyList(),
)

data class ElementTransform(
    val xMm: Double,
    val yMm: Double,
    val widthMm: Double,
    val heightMm: Double,
    val rotationDeg: Double = 0.0,
)

data class CoverElement(
    val id: String,
    val kind: ElementKind,
    val region: CoverRegion,
    val transform: ElementTransform,
    val zIndex: Int = 0,
    val opacity: Double = 1.0,
    val content: JSONObject = JSONObject(),
)

data class CoverExportSettings(
    val dpi: Int = 300,
    val showCropMarks: Boolean = true,
    val showAssemblyMarks: Boolean = true,
)

data class CoverProject(
    val schemaVersion: Int,
    val sourceFile: String,
    val sourceType: String,
    val metadata: CoverMetadata,
    val trimSize: TrimSize,
    val pageCount: Int,
    val paperCaliperMm: Double,
    val manualSpineWidthMm: Double?,
    val bleedMm: Double,
    val overlapMm: Double,
    val imageMode: ImageMode,
    val workingDir: String = "",
    val background: JSONObject = JSONObject(),
    val elements: List<CoverElement> = emptyList(),
    val exportSettings: CoverExportSettings = CoverExportSettings(),
)

class CoverProjectFormatException(
    message: String,
    cause: Throwable? = null,
) : IllegalArgumentException(message, cause)
