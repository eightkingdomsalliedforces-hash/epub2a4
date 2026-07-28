package tw.daniel.epubword.cover.ui

import org.json.JSONObject

data class CoverTemplateOption(
    val id: String,
    val label: String,
)

const val PUBLISHER_BACK_MATTER_TEMPLATE_ID = "publisher_back_matter"
const val MODERN_VERTICAL_TEMPLATE_ID = "modern_vertical_back_with_spine"

val COVER_TEMPLATE_OPTIONS: List<CoverTemplateOption> = listOf(
    CoverTemplateOption("minimal_text", "極簡文字"),
    CoverTemplateOption("front_image_plain_back", "正面圖片＋純色封底"),
    CoverTemplateOption("full_spread", "跨頁滿版圖片"),
    CoverTemplateOption(PUBLISHER_BACK_MATTER_TEMPLATE_ID, "出版社式封底"),
    CoverTemplateOption(MODERN_VERTICAL_TEMPLATE_ID, "現代直排封底＋可選書脊"),
)

data class InspectedPageCount(
    val pageCount: Int,
    val estimated: Boolean,
)

fun resolveCoverInspectionPageCount(inspection: JSONObject): InspectedPageCount {
    val pageCount = when {
        inspection.has("page_count") && !inspection.isNull("page_count") ->
            inspection.optInt("page_count", 0)
        inspection.has("fixed_page_count") && !inspection.isNull("fixed_page_count") ->
            inspection.optInt("fixed_page_count", 0)
        else -> 0
    }.coerceAtLeast(0)
    return InspectedPageCount(
        pageCount = pageCount,
        estimated = pageCount > 0 && inspection.optBoolean("page_count_estimated", false),
    )
}


fun normalizedPublisherIsbn13(value: String): String {
    val compact = value
        .trim()
        .replace(Regex("^urn:isbn:", RegexOption.IGNORE_CASE), "")
        .replace(Regex("[\\s-]"), "")
    if (!compact.matches(Regex("97[89]\\d{10}"))) return ""
    val checksum = compact.take(12).mapIndexed { index, character ->
        character.digitToInt() * if (index % 2 == 0) 1 else 3
    }.sum()
    val expected = (10 - checksum % 10) % 10
    return compact.takeIf { it.last().digitToInt() == expected }.orEmpty()
}

fun validPublisherAddon(value: String): Boolean {
    val compact = value.filter(Char::isDigit)
    return value.isBlank() || (compact == value.trim() && compact.length in setOf(2, 5))
}
