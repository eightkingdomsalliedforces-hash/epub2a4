package tw.daniel.epubword.cover.model

import tw.daniel.epubword.model.ConversionResult
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.StagedInput

data class CoverHandoff(
    val sourcePath: String,
    val sourceName: String,
    val sourceType: String,
    val pageCount: Int,
    val pageCountConfirmed: Boolean,
    val trimSize: TrimSize,
    val title: String,
    val author: String,
)

fun OutputMode.coverTrimSize(): TrimSize = when (this) {
    OutputMode.SIGNATURE16, OutputMode.FOUR_UP -> TrimSize(105.0, 148.0)
    OutputMode.A5 -> TrimSize(148.0, 210.0)
    OutputMode.B6_ON_A5 -> TrimSize(128.0, 182.0)
    OutputMode.PHOTO_4X6 -> TrimSize(101.6, 152.4)
}

fun createCoverHandoff(
    source: StagedInput,
    result: ConversionResult,
    outputMode: OutputMode,
): CoverHandoff {
    require(source.localFile.path.isNotBlank()) { "封面來源路徑不可為空。" }
    require(result.miniPageCount > 0) { "轉換結果頁數必須大於 0。" }
    return CoverHandoff(
        sourcePath = source.localFile.absolutePath,
        sourceName = source.displayName,
        sourceType = source.kind.name.lowercase(),
        pageCount = result.miniPageCount,
        pageCountConfirmed = true,
        trimSize = outputMode.coverTrimSize(),
        title = result.title,
        author = result.author,
    )
}
