package tw.daniel.epubword.model

import java.io.File

/** Input format after the selected SAF document has been staged locally. */
enum class InputKind(val extension: String) {
    EPUB("epub"),
    DOCX("docx");

    companion object {
        fun fromFileName(name: String): InputKind? = when (name.substringAfterLast('.', "").lowercase()) {
            "epub" -> EPUB
            "docx" -> DOCX
            else -> null
        }
    }
}

enum class OutputMode(val wireValue: String, val label: String, val fileSuffix: String) {
    SIGNATURE16("signature16", "A6 16 頁書帖", "A6_16頁書帖"),
    FOUR_UP("four_up", "A4 四格", "A4_四格"),
    A5("single_a5", "A5 一頁一張", "A5"),
    B6_ON_A5("b6_on_a5", "B6 置於 A5 右下角", "B6_A5"),
    PHOTO_4X6("single_4x6", "4×6 英吋一頁一張", "4x6");

    companion object {
        fun allowedFor(kind: InputKind): List<OutputMode> = when (kind) {
            InputKind.EPUB -> listOf(SIGNATURE16, FOUR_UP, A5, B6_ON_A5, PHOTO_4X6)
            InputKind.DOCX -> listOf(A5, B6_ON_A5, PHOTO_4X6)
        }
    }
}

enum class MarginMode(val wireValue: String, val label: String) {
    SAFE("safe", "安全（5 mm）"),
    MAXIMIZED("maximized", "最大化（2 mm）"),
    BORDERLESS("borderless", "無邊界（0 mm）"),
}

enum class WritingPreset(
    val writingMode: String,
    val bindingDirection: String,
    val label: String,
    val description: String,
) {
    TAIWAN_VERTICAL(
        "taiwan_vertical",
        "right",
        "台灣直排（右裝訂）",
        "由上往下，欄位由右往左 · 右裝訂",
    ),
    HORIZONTAL(
        "horizontal",
        "left",
        "橫排（左裝訂）",
        "由左往右 · 左裝訂",
    ),
}

data class ConversionOptions(
    val outputMode: OutputMode = OutputMode.SIGNATURE16,
    val writingPreset: WritingPreset = WritingPreset.TAIWAN_VERTICAL,
    val marginMode: MarginMode = MarginMode.MAXIMIZED,
    val fontName: String = "Noto Serif CJK TC",
    val bodyFontPt: Double = 8.5,
    val headingFontPt: Double = 11.0,
    val lineSpacing: Double = 1.23,
    val paragraphSpacingPt: Double = 2.5,
    val pageNumbers: Boolean = true,
    val cutGuides: Boolean = true,
    val contentOnly: Boolean = true,
) {
    fun normalizedFor(kind: InputKind): ConversionOptions {
        val allowed = OutputMode.allowedFor(kind)
        val mode = if (outputMode in allowed) outputMode else allowed.first()
        return copy(
            outputMode = mode,
            cutGuides = cutGuides && mode in setOf(
                OutputMode.SIGNATURE16,
                OutputMode.FOUR_UP,
                OutputMode.B6_ON_A5,
            ),
        )
    }

    fun toJson(): String {
        val values = linkedMapOf<String, String>(
            "imposition_mode" to outputMode.wireValue.jsonQuoted(),
            "writing_mode" to writingPreset.writingMode.jsonQuoted(),
            "binding_direction" to writingPreset.bindingDirection.jsonQuoted(),
            "margin_mode" to marginMode.wireValue.jsonQuoted(),
            "font_name" to fontName.jsonQuoted(),
            "body_font_pt" to bodyFontPt.jsonNumber(),
            "heading_font_pt" to headingFontPt.jsonNumber(),
            "line_spacing" to lineSpacing.jsonNumber(),
            "paragraph_spacing_pt" to paragraphSpacingPt.jsonNumber(),
            "page_numbers" to pageNumbers.toString(),
            "cut_guides" to cutGuides.toString(),
            "output_mark_mode" to (
                if (outputMode == OutputMode.B6_ON_A5 && cutGuides) "crop_marks" else "normal"
            ).jsonQuoted(),
            "content_only" to contentOnly.toString(),
        )
        return values.entries.joinToString(prefix = "{", postfix = "}") { (key, value) ->
            "${key.jsonQuoted()}:$value"
        }
    }
}

data class StagedInput(
    val localFile: File,
    val displayName: String,
    val kind: InputKind,
    val sizeBytes: Long,
)

data class ConversionResult(
    val outputPath: String,
    val title: String,
    val author: String,
    val miniPageCount: Int,
    val printSideCount: Int,
    val imageCount: Int,
    val warnings: List<String>,
    val outputMode: String,
    val paperSheetCount: Int,
    val signatureCount: Int,
    val paddedMiniPageCount: Int,
    val sourceFormat: String,
)

private fun String.jsonQuoted(): String = buildString {
    append('"')
    for (character in this@jsonQuoted) {
        when (character) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\b' -> append("\\b")
            '\u000C' -> append("\\f")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (character.code < 0x20) {
                append("\\u%04x".format(character.code))
            } else {
                append(character)
            }
        }
    }
    append('"')
}

private fun Double.jsonNumber(): String {
    require(isFinite()) { "JSON 數值必須是有限值" }
    return toString()
}
