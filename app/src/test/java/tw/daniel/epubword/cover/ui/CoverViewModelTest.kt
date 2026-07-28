package tw.daniel.epubword.cover.ui

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.daniel.epubword.cover.model.CoverProjectJson

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

    @Test
    fun modernCoverCreationSettingsUseSharedSnakeCaseKeys() {
        val state = CoverUiState(
            metadataBackVerticalCopy = "黑色直排內文",
            metadataBackHighlightCopy = "醒目文案",
            metadataSpineStyle = "parallel_columns",
            metadataAccentColorMode = "manual",
            metadataExtractedAccentColor = "#2674D9",
            metadataSpineAccentColor = "#336699",
            showCropMarks = false,
        )

        val settings = buildCoverCreationSettings(state, "/tmp/work")

        assertEquals("黑色直排內文", settings.getString("back_vertical_copy"))
        assertEquals("醒目文案", settings.getString("back_highlight_copy"))
        assertEquals("parallel_columns", settings.getString("spine_style"))
        assertEquals("manual", settings.getString("accent_color_mode"))
        assertEquals("#2674D9", settings.getString("extracted_accent_color"))
        assertEquals("#336699", settings.getString("spine_accent_color"))
        assertFalse(settings.getBoolean("show_crop_marks"))
    }

    @Test
    fun cropFrameMutationChangesOnlySharedProjectSetting() {
        val original = CoverProjectJson.decode(
            javaClass.getResource("/cover-project-v1.json")!!.readText(),
        )

        val changed = withShowCropMarks(original, false)

        assertFalse(changed.exportSettings.showCropMarks)
        assertEquals(
            original,
            changed.copy(exportSettings = original.exportSettings),
        )
    }
}
