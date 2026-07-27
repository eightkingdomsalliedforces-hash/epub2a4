package tw.daniel.epubword.cover.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AndroidCoverWordPreviewRegressionTest {
    @Test
    fun pendingWordPreviewRequiresANewRequestAndDocxPath() {
        val pending = CoverUiState(
            wordPreviewPath = "/cache/cover/preview.docx",
            wordPreviewRequestId = 2L,
            handledWordPreviewRequestId = 1L,
        )
        val handled = pending.copy(handledWordPreviewRequestId = 2L)
        val missingPath = pending.copy(wordPreviewPath = null)

        assertTrue(pending.hasPendingWordPreview)
        assertFalse(handled.hasPendingWordPreview)
        assertFalse(missingPath.hasPendingWordPreview)
    }
}
