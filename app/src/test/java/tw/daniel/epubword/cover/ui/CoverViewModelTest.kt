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
}
