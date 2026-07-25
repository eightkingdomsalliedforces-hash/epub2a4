package tw.daniel.epubword.cover.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class CoverDocumentRepositoryTest {
    @Test
    fun acceptsOnlySupportedCoverInputs() {
        assertEquals(CoverInputKind.EPUB, kindFor("book.epub", "application/epub+zip"))
        assertEquals(CoverInputKind.DOCX, kindFor("book.docx", DOCX_MIME))
        assertEquals(CoverInputKind.PDF, kindFor("book.pdf", "application/pdf"))
        assertThrows(IllegalArgumentException::class.java) {
            kindFor("book.txt", "text/plain")
        }
    }

    @Test
    fun sanitizesIndependentExportNames() {
        assertEquals("測試書_完整書封.pdf", coverExportName("測試書/", "pdf"))
        assertEquals("測試書_完整書封.docx", coverExportName("測試書/", "docx"))
    }
}
