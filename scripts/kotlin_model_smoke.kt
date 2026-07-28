import tw.daniel.epubword.model.ConversionOptions
import tw.daniel.epubword.model.InputKind
import tw.daniel.epubword.model.MarginMode
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.WritingPreset

fun main() {
    check(WritingPreset.TAIWAN_VERTICAL.writingMode == "taiwan_vertical")
    check(WritingPreset.TAIWAN_VERTICAL.bindingDirection == "right")
    check(OutputMode.allowedFor(InputKind.DOCX) == listOf(OutputMode.A5, OutputMode.PHOTO_4X6))
    check(OutputMode.allowedFor(InputKind.EPUB).contains(OutputMode.SIGNATURE16))
    val normalized = ConversionOptions(outputMode = OutputMode.SIGNATURE16)
        .normalizedFor(InputKind.DOCX)
    check(normalized.outputMode == OutputMode.A5)
    val json = ConversionOptions(
        outputMode = OutputMode.PHOTO_4X6,
        marginMode = MarginMode.SAFE,
        fontName = "Noto \"Serif\" CJK TC",
        bodyFontPt = 9.5,
        headingFontPt = 12.0,
        pageNumbers = true,
        cutGuides = false,
    ).toJson()
    check(json.contains("\"imposition_mode\":\"single_4x6\""))
    check(json.contains("Noto \\\"Serif\\\" CJK TC"))
    check(json.contains("\"page_numbers\":true"))
    println("Kotlin model smoke test passed")
}
