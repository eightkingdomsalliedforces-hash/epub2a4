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

        val restored = CoverProjectJson.decode(
            CoverProjectJson.encode(CoverProjectJson.decode(fixture.toString())),
        )

        assertEquals("NT$110", restored.metadata.price)
        assertEquals("台北", restored.metadata.publicationPlace)
        assertEquals("李彥樺", restored.metadata.translator)
        assertEquals("00110", restored.metadata.isbnAddon)
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
