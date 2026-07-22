package tw.daniel.epubword.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversionModelsTest {
    @Test
    fun docxOnlyOffersSinglePageModes() {
        assertEquals(listOf(OutputMode.A5, OutputMode.PHOTO_4X6), OutputMode.allowedFor(InputKind.DOCX))
    }

    @Test
    fun invalidDocxModeNormalizesToA5AndDisablesCutGuides() {
        val result = ConversionOptions(
            outputMode = OutputMode.SIGNATURE16,
            cutGuides = true,
        ).normalizedFor(InputKind.DOCX)

        assertEquals(OutputMode.A5, result.outputMode)
        assertFalse(result.cutGuides)
    }

    @Test
    fun optionJsonEscapesFontAndUsesWireValues() {
        val json = ConversionOptions(
            outputMode = OutputMode.PHOTO_4X6,
            marginMode = MarginMode.SAFE,
            fontName = "Noto \"Serif\"",
        ).toJson()

        assertTrue(json.contains("\"imposition_mode\":\"single_4x6\""))
        assertTrue(json.contains("\"margin_mode\":\"safe\""))
        assertTrue(json.contains("Noto \\\"Serif\\\""))
    }
}
