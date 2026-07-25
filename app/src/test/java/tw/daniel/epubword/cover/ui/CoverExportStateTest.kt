package tw.daniel.epubword.cover.ui

import android.net.Uri
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.daniel.epubword.cover.data.SavedCoverFiles

class CoverExportStateTest {
    @Test
    fun cannotSaveBeforeBothLocalExportsExist() {
        val state = CoverUiState(status = CoverStatus.EDITING)
        assertFalse(state.canChooseExportDirectory)
    }

    @Test
    fun canChooseDirectoryOnlyAfterBothLocalExportsExist() {
        val state = CoverUiState(
            status = CoverStatus.READY_TO_SAVE,
            exportPdfPath = "/tmp/cover.pdf",
            exportDocxPath = "/tmp/cover.docx",
        )
        assertTrue(state.canChooseExportDirectory)
    }

    @Test
    fun partialSaveNamesTheSuccessfulFile() {
        val result = SavedCoverFiles(pdfUri = Uri.EMPTY, docxUri = null)
        assertEquals("PDF 已儲存；DOCX 儲存失敗，可重試。", result.userMessage)
    }

    @Test
    fun completeSaveNamesBothFiles() {
        val result = SavedCoverFiles(pdfUri = Uri.EMPTY, docxUri = Uri.EMPTY)
        assertEquals("PDF 與 DOCX 已儲存。", result.userMessage)
    }
}
