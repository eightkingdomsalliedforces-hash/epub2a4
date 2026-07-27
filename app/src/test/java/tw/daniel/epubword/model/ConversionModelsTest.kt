package tw.daniel.epubword.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversionModelsTest {
    @Test
    fun docxOffersSinglePageModesIncludingB6OnA5() {
        assertEquals(
            listOf(OutputMode.A5, OutputMode.B6_ON_A5, OutputMode.PHOTO_4X6),
            OutputMode.allowedFor(InputKind.DOCX),
        )
    }

    @Test
    fun epubOffersB6OnA5() {
        assertTrue(OutputMode.B6_ON_A5 in OutputMode.allowedFor(InputKind.EPUB))
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
    fun b6OnA5KeepsCutGuidesAndSerializesCropMarkMode() {
        val result = ConversionOptions(
            outputMode = OutputMode.B6_ON_A5,
            cutGuides = true,
        ).normalizedFor(InputKind.DOCX)
        val json = result.toJson()

        assertTrue(result.cutGuides)
        assertTrue(json.contains("\"imposition_mode\":\"b6_on_a5\""))
        assertTrue(json.contains("\"output_mark_mode\":\"crop_marks\""))
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

    @Test
    fun contentOnlyDefaultsOnAndIsSerialized() {
        val defaults = ConversionOptions()
        val disabled = defaults.copy(contentOnly = false).toJson()

        assertTrue(defaults.contentOnly)
        assertTrue(disabled.contains("\"content_only\":false"))
    }
}
