package tw.daniel.epubword.cover.ui

import org.json.JSONObject

data class CoverTemplateOption(
    val id: String,
    val label: String,
)

val COVER_TEMPLATE_OPTIONS: List<CoverTemplateOption> = listOf(
    CoverTemplateOption("minimal_text", "極簡文字"),
    CoverTemplateOption("front_image_plain_back", "正面圖片＋純色封底"),
    CoverTemplateOption("full_spread", "跨頁滿版圖片"),
    CoverTemplateOption("top_bottom_blocks", "上下色塊"),
    CoverTemplateOption("publisher_back_matter", "出版社式封底"),
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
