package tw.daniel.epubword.cover.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CoverViewModelTest {
    @Test
    fun spineUsesCeilingSheetCount() {
        val state = CoverUiState(pageCount = 161, paperCaliperMm = 0.10)
        assertEquals(81, state.sheetCount)
        assertEquals(8.1, state.autoSpineWidthMm, 0.0001)
        assertEquals(8.1, state.effectiveSpineWidthMm, 0.0001)
    }

    @Test
    fun manualSpineOverridesAutomaticWidth() {
        val state = CoverUiState(
            pageCount = 160,
            paperCaliperMm = 0.10,
            manualSpineWidthMm = 12.5,
        )
        assertEquals(12.5, state.effectiveSpineWidthMm, 0.0001)
    }

    @Test
    fun projectRequiresSourcePositiveConfirmedPageCountAndIdleStatus() {
        val incomplete = CoverUiState(pageCount = 160, pageCountConfirmed = false)
        assertFalse(incomplete.canCreateProject)

        val ready = incomplete.copy(
            sourceName = "book.epub",
            sourcePath = "/tmp/book.epub",
            pageCountConfirmed = true,
            status = CoverStatus.SETUP,
        )
        assertTrue(ready.canCreateProject)
        assertFalse(ready.copy(status = CoverStatus.CREATING).canCreateProject)
    }

    @Test
    fun publisherLogoSearchTargetsWikimediaMediaSearch() {
        val uri = publisherLogoSearchUri("台灣角川")
        assertTrue(uri.startsWith("https://commons.wikimedia.org/w/index.php?"))
        assertTrue(uri.contains("Special%3AMediaSearch"))
        assertTrue(uri.contains("%E5%8F%B0%E7%81%A3%E8%A7%92%E5%B7%9D+logo"))
    }
}
