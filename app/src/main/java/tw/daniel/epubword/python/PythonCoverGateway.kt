package tw.daniel.epubword.python

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.io.File

/** Thin JSON gateway to the shared Python cover service. */
class PythonCoverGateway(
    context: Context,
    private val executor: LargeStackPythonExecutor = LargeStackPythonExecutor(),
) : AutoCloseable {
    private val appContext = context.applicationContext

    fun inspectSource(source: File): JSONObject = executor.run {
        JSONObject(module().callAttr(BRIDGE_FUNCTIONS[0], source.absolutePath).toString())
    }

    fun newProject(source: File, settings: JSONObject): String = executor.run {
        module().callAttr(
            BRIDGE_FUNCTIONS[1],
            source.absolutePath,
            settings.toString(),
        ).toString()
    }

    fun applyTemplate(projectJson: String, templateId: String): String = executor.run {
        module().callAttr(BRIDGE_FUNCTIONS[2], projectJson, templateId).toString()
    }

    fun extractEmbeddedAsset(projectJson: String, assetId: String): JSONObject = executor.run {
        JSONObject(
            module().callAttr(
                EXTRACT_EMBEDDED_ASSET_FUNCTION,
                projectJson,
                assetId,
            ).toString(),
        )
    }

    fun renderPreview(
        projectJson: String,
        outputPng: File,
        maxPx: Int = 1600,
    ): JSONObject = executor.run {
        outputPng.parentFile?.mkdirs()
        JSONObject(
            module().callAttr(
                BRIDGE_FUNCTIONS[3],
                projectJson,
                outputPng.absolutePath,
                maxPx,
            ).toString(),
        )
    }

    fun export(
        projectJson: String,
        pdf: File,
        docx: File,
        dpi: Int = 300,
    ): JSONObject = executor.run {
        pdf.parentFile?.mkdirs()
        docx.parentFile?.mkdirs()
        JSONObject(
            module().callAttr(
                BRIDGE_FUNCTIONS[4],
                projectJson,
                pdf.absolutePath,
                docx.absolutePath,
                dpi,
            ).toString(),
        )
    }

    private fun module(): PyObject {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(appContext))
        }
        return Python.getInstance().getModule("android_bridge")
    }

    override fun close() {
        executor.close()
    }

    companion object {
        val BRIDGE_FUNCTIONS = listOf(
            "cover_inspect_source_json",
            "cover_new_project_json",
            "cover_apply_template_json",
            "cover_render_preview_json",
            "cover_export_json",
        )
        const val EXTRACT_EMBEDDED_ASSET_FUNCTION = "cover_extract_embedded_asset_json"
    }
}
