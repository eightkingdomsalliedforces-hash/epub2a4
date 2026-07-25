package tw.daniel.epubword.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import tw.daniel.epubword.cover.model.TrimSize
import tw.daniel.epubword.cover.model.createCoverHandoff
import tw.daniel.epubword.model.ConversionResult
import tw.daniel.epubword.model.InputKind
import tw.daniel.epubword.model.OutputMode
import tw.daniel.epubword.model.StagedInput
import java.io.File

class ConversionCoverHandoffTest {
    @Test
    fun handoffUsesActualConvertedPageCount() {
        val stagedEpub = StagedInput(
            localFile = File("build/tmp/handoff/source.epub"),
            displayName = "source.epub",
            kind = InputKind.EPUB,
            sizeBytes = 123L,
        )
        val result = ConversionResult(
            outputPath = "build/tmp/handoff/result.docx",
            title = "測試書",
            author = "測試作者",
            miniPageCount = 164,
            printSideCount = 42,
            imageCount = 0,
            warnings = emptyList(),
            outputMode = OutputMode.SIGNATURE16.wireValue,
            paperSheetCount = 21,
            signatureCount = 2,
            paddedMiniPageCount = 176,
            sourceFormat = "epub",
        )

        val handoff = createCoverHandoff(stagedEpub, result, OutputMode.SIGNATURE16)

        assertEquals(164, handoff.pageCount)
        assertEquals(TrimSize(105.0, 148.0), handoff.trimSize)
        assertTrue(handoff.pageCountConfirmed)
        assertEquals("測試書", handoff.title)
        assertEquals("測試作者", handoff.author)
    }

    @Test
    fun singlePageModesMapToTheirPhysicalTrim() {
        assertEquals(TrimSize(148.0, 210.0), OutputMode.A5.coverTrimSize())
        assertEquals(TrimSize(101.6, 152.4), OutputMode.PHOTO_4X6.coverTrimSize())
    }
}
