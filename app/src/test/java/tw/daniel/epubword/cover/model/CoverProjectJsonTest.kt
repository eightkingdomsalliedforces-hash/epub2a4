package tw.daniel.epubword.cover.model

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class CoverProjectJsonTest {
    @Test
    fun decodesSchemaV1Fixture() {
        val text = javaClass.getResource("/cover-project-v1.json")!!.readText()
        val project = CoverProjectJson.decode(text)

        assertEquals(1, project.schemaVersion)
        assertEquals("黃金範例書", project.metadata.title)
        assertEquals(ImageMode.FULL_SPREAD, project.imageMode)
        assertEquals(160, project.pageCount)
    }

    @Test
    fun encodeDecodePreservesMillimetres() {
        val text = javaClass.getResource("/cover-project-v1.json")!!.readText()
        val restored = CoverProjectJson.decode(
            CoverProjectJson.encode(CoverProjectJson.decode(text)),
        )
        assertEquals(12.75, restored.elements.first().transform.xMm, 0.000001)
    }

    @Test
    fun preservesPublisherMetadataUsedBySharedTemplates() {
        val fixture = JSONObject(javaClass.getResource("/cover-project-v1.json")!!.readText())
        fixture.getJSONObject("metadata")
            .put("price", "NT$110")
            .put("publication_place", "台北")
            .put("translator", "李彥樺")
            .put("isbn_addon", "00110")
            .put("publisher_id", "kadokawa-tw")
            .put("english_title", "Welcome to the Classroom")
            .put("volume_number", "2")
            .put("arc_label", "二年級篇")
            .put("series_name", "輕小說")
            .put("internal_book_code", "CL0308-17")
            .put("spine_accent_color", "#F15A24")

        val restored = CoverProjectJson.decode(
            CoverProjectJson.encode(CoverProjectJson.decode(fixture.toString())),
        )

        assertEquals("NT$110", restored.metadata.price)
        assertEquals("台北", restored.metadata.publicationPlace)
        assertEquals("李彥樺", restored.metadata.translator)
        assertEquals("00110", restored.metadata.isbnAddon)
        assertEquals("kadokawa-tw", restored.metadata.publisherId)
        assertEquals("Welcome to the Classroom", restored.metadata.englishTitle)
        assertEquals("2", restored.metadata.volumeNumber)
        assertEquals("二年級篇", restored.metadata.arcLabel)
        assertEquals("輕小說", restored.metadata.seriesName)
        assertEquals("CL0308-17", restored.metadata.internalBookCode)
        assertEquals("#F15A24", restored.metadata.spineAccentColor)
    }

    @Test
    fun preservesModernCoverMetadata() {
        val fixture = JSONObject(javaClass.getResource("/cover-project-v1.json")!!.readText())
        fixture.getJSONObject("metadata")
            .put("back_vertical_copy", "第一欄\n第二欄")
            .put("back_highlight_copy", "醒目文案")
            .put("spine_style", "parallel_columns")
            .put("accent_color_mode", "manual")
            .put("extracted_accent_color", "#D56A31")

        val restored = CoverProjectJson.decode(
            CoverProjectJson.encode(CoverProjectJson.decode(fixture.toString())),
        )

        assertEquals("第一欄\n第二欄", restored.metadata.backVerticalCopy)
        assertEquals("醒目文案", restored.metadata.backHighlightCopy)
        assertEquals("parallel_columns", restored.metadata.spineStyle)
        assertEquals("manual", restored.metadata.accentColorMode)
        assertEquals("#D56A31", restored.metadata.extractedAccentColor)
    }

    @Test
    fun oldProjectUsesModernCoverMetadataDefaults() {
        val text = javaClass.getResource("/cover-project-v1.json")!!.readText()
        val restored = CoverProjectJson.decode(text)

        assertEquals("", restored.metadata.backVerticalCopy)
        assertEquals("", restored.metadata.backHighlightCopy)
        assertEquals("reference_stacked", restored.metadata.spineStyle)
        assertEquals("auto", restored.metadata.accentColorMode)
        assertEquals("", restored.metadata.extractedAccentColor)
    }

    @Test
    fun rejectsUnknownSchemaAndDuplicateElementIds() {
        val fixture = JSONObject(javaClass.getResource("/cover-project-v1.json")!!.readText())
        fixture.put("schema_version", 2)
        assertThrows(CoverProjectFormatException::class.java) {
            CoverProjectJson.decode(fixture.toString())
        }

        fixture.put("schema_version", 1)
        fixture.getJSONArray("elements").put(fixture.getJSONArray("elements").getJSONObject(0))
        assertThrows(CoverProjectFormatException::class.java) {
            CoverProjectJson.decode(fixture.toString())
        }
    }
}
