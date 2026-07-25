package tw.daniel.epubword.python

import org.junit.Assert.assertEquals
import org.junit.Test

class PythonCoverGatewayContractTest {
    @Test
    fun coverGatewayUsesExpectedBridgeFunctions() {
        assertEquals(
            listOf(
                "cover_inspect_source_json",
                "cover_new_project_json",
                "cover_apply_template_json",
                "cover_render_preview_json",
                "cover_export_json",
            ),
            PythonCoverGateway.BRIDGE_FUNCTIONS,
        )
    }
}
