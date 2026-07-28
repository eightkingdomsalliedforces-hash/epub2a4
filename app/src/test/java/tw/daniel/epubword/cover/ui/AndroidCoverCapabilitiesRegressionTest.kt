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

    @Test
    fun modernVerticalTemplateIsAvailableAndUsesPublisherMetadataCard() {
        assertTrue(
            COVER_TEMPLATE_OPTIONS.any {
                it.id == MODERN_VERTICAL_TEMPLATE_ID
            },
        )
        assertTrue(
            CoverUiState(templateId = MODERN_VERTICAL_TEMPLATE_ID)
                .publisherTemplateSelected,
        )
    }

    @Test
    fun publisherTemplateRequiresAValidIsbnAndPublisher() {
        val base = CoverUiState(
            status = CoverStatus.SETUP,
            sourcePath = "/tmp/book.epub",
            pageCount = 160,
            pageCountConfirmed = true,
            templateId = PUBLISHER_BACK_MATTER_TEMPLATE_ID,
        )

        assertTrue(base.publisherTemplateIssue != null)
        assertTrue(!base.canCreateProject)

        val ready = base.copy(
            metadataIsbn = "978-475-752-157-5",
            metadataPublisher = "台灣角川",
            metadataIsbnAddon = "50110",
        )
        assertEquals(null, ready.publisherTemplateIssue)
        assertTrue(ready.canCreateProject)
        assertEquals("9784757521575", normalizedPublisherIsbn13(ready.metadataIsbn))
    }

    @Test
    fun setupCanRebuildAnExistingCoverAfterMetadataCorrection() {
        val state = CoverUiState(
            status = CoverStatus.EDITING,
            sourcePath = "/tmp/book.epub",
            pageCount = 160,
            pageCountConfirmed = true,
            templateId = PUBLISHER_BACK_MATTER_TEMPLATE_ID,
            metadataIsbn = "9784757521575",
            metadataPublisher = "台灣角川",
        )

        assertTrue(state.canCreateProject)
    }
}
