package tw.daniel.epubword.cover.ui

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AndroidCoverCapabilitiesRegressionTest {
    @Test
    fun estimatedEpubPageCountUsesSharedInspectionResult() {
        val inspection = JSONObject(
            """{
                "fixed_page_count": null,
                "page_count": 164,
                "page_count_estimated": true
            }""".trimIndent(),
        )

        val result = resolveCoverInspectionPageCount(inspection)

        assertEquals(164, result.pageCount)
        assertTrue(result.estimated)
    }

    @Test
    fun publisherBackMatterTemplateIsAvailableOnAndroid() {
        assertTrue(
            COVER_TEMPLATE_OPTIONS.any {
                it.id == "publisher_back_matter" && it.label == "出版社式封底"
            },
        )
    }
}
